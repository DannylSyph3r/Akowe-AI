import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import AsyncSessionFactory, get_db
from app.core.dependencies import get_current_member
from app.core.exceptions import BadRequestException, NotFoundException
from app.core.responses import ApiResponse
from app.models.member import Member
from app.repositories.member_repository import MemberRepository
from app.repositories.payment_repository import PaymentRepository
from app.services.payment_service import (
    PaymentService,
    verify_interswitch_webhook_signature,
)

router = APIRouter(prefix="/payments", tags=["payments"])
settings = get_settings()
logger = logging.getLogger("akoweai")

# HTML pages
_INITIATE_FORM_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>AkoweAI — Redirecting to payment...</title>
    <style>
        body {{ font-family: sans-serif; display: flex; justify-content: center;
               align-items: center; min-height: 100vh; margin: 0; background: #f5f5f5; }}
        p {{ color: #555; }}
    </style>
</head>
<body>
    <p>Redirecting to secure payment page...</p>
    <form id="f" method="post" action="{action_url}">
        <input type="hidden" name="merchant_code" value="{merchant_code}">
        <input type="hidden" name="pay_item_id" value="{pay_item_id}">
        <input type="hidden" name="txn_ref" value="{txn_ref}">
        <input type="hidden" name="amount" value="{amount}">
        <input type="hidden" name="currency" value="566">
        <input type="hidden" name="cust_name" value="{cust_name}">
        <input type="hidden" name="site_redirect_url" value="{redirect_url}">
    </form>
    <script>document.getElementById('f').submit();</script>
</body>
</html>"""

_COMPLETION_HTML = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>AkoweAI — Payment Received</title>
    <style>
        body {{ font-family: sans-serif; display: flex; justify-content: center;
               align-items: center; min-height: 100vh; margin: 0; background: #f5f5f5; }}
        .card {{ background: white; border-radius: 12px; padding: 32px; text-align: center;
                 max-width: 380px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .emoji {{ font-size: 48px; margin-bottom: 16px; }}
        h1 {{ color: #1a1a1a; font-size: 22px; margin-bottom: 8px; }}
        p {{ color: #666; margin-bottom: 24px; line-height: 1.5; }}
        a {{ display: inline-block; background: #25D366; color: white;
             text-decoration: none; padding: 12px 28px; border-radius: 8px;
             font-weight: 600; font-size: 16px; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="emoji">✅</div>
        <h1>Payment Received</h1>
        <p>Your receipt is being prepared.<br>You will receive a WhatsApp message shortly.</p>
        <a href="whatsapp://">← Return to WhatsApp</a>
    </div>
</body>
</html>"""


# Background task — runs after response is sent, owns its own DB session
async def _verify_and_process_payment(txnref: str, posted_amount: int) -> None:
    """
    Requery Interswitch, validate the amount, and process or mark the payment.
    Runs as a BackgroundTask — creates its own DB session.
    """
    async with AsyncSessionFactory() as db:
        try:
            payment_repo = PaymentRepository(db)
            payment_svc = PaymentService(db)

            # Idempotency guard
            if await payment_repo.is_already_paid(txnref):
                return

            transaction = await payment_repo.get_by_reference(txnref)
            if not transaction:
                logger.error("Payment redirect received for unknown reference: %s", txnref)
                return

            # Requery Interswitch for authoritative status
            try:
                status_data = await payment_svc.poll_transaction_status(
                    txnref, transaction.amount
                )
            except Exception:
                logger.exception("Interswitch requery failed for ref=%s", txnref)
                return  # Don't mark failed — we don't know what happened

            response_code = status_data.get("ResponseCode", "")
            returned_amount = status_data.get("Amount", 0)

            if response_code in ("00", "10", "11"):
                # Amount must match what was on the original payment request
                if int(returned_amount) != int(transaction.amount):
                    logger.error(
                        "Amount mismatch for %s: expected %d kobo, Interswitch returned %d",
                        txnref, transaction.amount, returned_amount,
                    )
                    await payment_repo.mark_failed(txnref)
                    await db.commit()
                    await _send_payment_failure_message(transaction)
                    return

                await payment_svc.process_successful_payment(transaction)
                await db.commit()
                await _send_payment_receipt(transaction)
            else:
                await payment_repo.mark_failed(txnref)
                await db.commit()
                await _send_payment_failure_message(transaction)

        except Exception:
            await db.rollback()
            logger.exception("Unhandled error in payment background task for ref=%s", txnref)


async def _send_payment_receipt(transaction) -> None:
    """Send WhatsApp receipt template to the member after successful payment."""
    from app.services.whatsapp_service import dispatch_payment_receipt
    async with AsyncSessionFactory() as db:
        member_repo = MemberRepository(db)
        member = await member_repo.get_by_id(transaction.member_id)
        if member:
            from app.repositories.cooperative_repository import CooperativeRepository
            coop = await CooperativeRepository(db).get_by_id(transaction.cooperative_id)
            coop_name = coop.name if coop else "your cooperative"
            await dispatch_payment_receipt(
                phone=member.phone_number,
                transaction=transaction,
                coop_name=coop_name,
                member_name=member.full_name,
            )


async def _send_payment_failure_message(transaction) -> None:
    """Notify the member that their payment could not be verified."""
    from app.services.whatsapp_service import send_text_message
    async with AsyncSessionFactory() as db:
        member_repo = MemberRepository(db)
        member = await member_repo.get_by_id(transaction.member_id)
        if member:
            retry_url = f"{settings.railway_backend_url}/api/payments/retry-page/{transaction.reference}"
            await send_text_message(
                member.phone_number,
                f"⚠️ We could not confirm your payment (ref: {transaction.reference}).\n\n"
                "Please try again or contact your cooperative admin if the issue persists.",
            )


# Routes
@router.get("/initiate/{reference}", include_in_schema=False)
async def payment_initiate(
    reference: str,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """
    Bridge page: opens in WhatsApp IAB, auto-submits form to Interswitch WebPay.
    Unauthenticated — the reference is an opaque token.
    """
    payment_repo = PaymentRepository(db)
    transaction = await payment_repo.get_by_reference(reference)
    if not transaction or transaction.status not in ("pending",):
        return HTMLResponse(
            content="<html><body><p>This payment link is no longer valid.</p></body></html>",
            status_code=410,
        )

    member_repo = MemberRepository(db)
    member = await member_repo.get_by_id(transaction.member_id)
    cust_name = member.full_name if member else "Member"

    html = _INITIATE_FORM_TEMPLATE.format(
        action_url=f"{settings.interswitch_base_url}/collections/w/pay",
        merchant_code=settings.interswitch_merchant_code,
        pay_item_id=settings.interswitch_pay_item_id,
        txn_ref=reference,
        amount=transaction.amount,
        cust_name=cust_name,
        redirect_url=f"{settings.railway_backend_url}/api/payments/redirect",
    )
    return HTMLResponse(content=html)


@router.post("/redirect", include_in_schema=False)
async def payment_redirect(
    request: Request,
    background_tasks: BackgroundTasks,
) -> HTMLResponse:
    """
    Receives Interswitch's browser-side form POST after payment attempt.
    Always returns 200 with an HTML completion page.
    Payment verification runs as a background task.
    """
    form_data = await request.form()
    txnref = str(form_data.get("txnref", "")).strip()
    amount_str = str(form_data.get("amount", "0")).strip()

    try:
        amount = int(amount_str)
    except ValueError:
        amount = 0

    if txnref:
        background_tasks.add_task(_verify_and_process_payment, txnref, amount)

    return HTMLResponse(content=_COMPLETION_HTML)


@router.post("/webhook")
async def payment_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> ApiResponse:
    """
    Interswitch webhook endpoint.
    Verifies X-Interswitch-Signature (HMAC-SHA512 of raw body).
    Always returns 200 to prevent Interswitch retries.
    """
    raw_body = await request.body()
    signature = request.headers.get("X-Interswitch-Signature", "")

    if not verify_interswitch_webhook_signature(raw_body, signature):
        logger.warning("Interswitch webhook signature verification failed")
        return ApiResponse.success(data=None, message="ok")

    try:
        payload = __import__("json").loads(raw_body)
    except Exception:
        return ApiResponse.success(data=None, message="ok")

    event_type = payload.get("event", "")
    if event_type == "TRANSACTION.COMPLETED":
        event_data = payload.get("data", {})
        txnref = event_data.get("merchantReference", "")
        amount = int(event_data.get("amount", 0))
        if txnref:
            background_tasks.add_task(_verify_and_process_payment, txnref, amount)

    return ApiResponse.success(data=None, message="ok")


@router.post("/retry")
async def retry_payment(
    request: Request,
    current_member: Member = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """
    Retry a failed payment with a fresh transaction reference.
    Invalidates the old reference and returns a new payment URL.
    """
    body = await request.json()
    old_reference = body.get("old_reference", "").strip()
    if not old_reference:
        raise BadRequestException("old_reference is required")

    payment_repo = PaymentRepository(db)
    old_tx = await payment_repo.get_by_reference(old_reference)

    if not old_tx:
        raise NotFoundException("Transaction not found")
    if old_tx.status != "failed":
        raise BadRequestException("Transaction is not in a failed state")
    if old_tx.member_id != current_member.id:
        raise BadRequestException("Transaction does not belong to you")

    await payment_repo.mark_invalidated(old_reference)

    # Rebuild period data (all periods already exist at this point)
    period_data = [{"id": pid} for pid in old_tx.period_ids]
    payment_svc = PaymentService(db)
    new_tx = await payment_svc.create_pending_transaction(
        member_id=old_tx.member_id,
        coop_id=old_tx.cooperative_id,
        period_data=period_data,
        amount_kobo=old_tx.amount,
    )

    payment_url = payment_svc.build_payment_initiation_url(new_tx.reference)
    return ApiResponse.success(
        data={"payment_url": payment_url, "new_reference": new_tx.reference},
        message="Retry payment link generated",
    )