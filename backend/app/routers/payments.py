import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import AsyncSessionFactory, get_db
from app.core.dependencies import get_current_member
from app.core.exceptions import BadRequestException, NotFoundException
from app.core.responses import ApiResponse
from app.models.member import Member
from app.repositories.cooperative_repository import CooperativeRepository
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

_COMPLETION_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>AkoweAI \u2014 Payment Received</title>
    <style>
        *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            background: #f0f4f8;
            padding: 24px;
        }}
        .card {{
            background: #ffffff;
            border-radius: 16px;
            padding: 40px 32px;
            max-width: 420px;
            width: 100%;
            box-shadow: 0 4px 24px rgba(0, 0, 0, 0.08);
            text-align: center;
        }}
        .check-circle {{
            width: 64px;
            height: 64px;
            background: #e8f9f0;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 24px;
        }}
        .check-circle svg {{
            width: 32px;
            height: 32px;
        }}
        .brand {{
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: #25D366;
            margin-bottom: 12px;
        }}
        h1 {{
            font-size: 22px;
            font-weight: 700;
            color: #111827;
            margin-bottom: 10px;
        }}
        .subtitle {{
            font-size: 15px;
            color: #6b7280;
            line-height: 1.6;
            margin-bottom: 28px;
        }}
        .ref-box {{
            background: #f9fafb;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 28px;
            text-align: left;
        }}
        .ref-label {{
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            color: #9ca3af;
            margin-bottom: 4px;
        }}
        .ref-value {{
            font-size: 13px;
            font-weight: 500;
            color: #374151;
            font-family: 'Courier New', monospace;
            word-break: break-all;
        }}
        .action-btn {{
            display: block;
            width: 100%;
            background: #25D366;
            color: #ffffff;
            text-decoration: none;
            padding: 14px 24px;
            border-radius: 10px;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            border: none;
            transition: background 0.15s ease;
        }}
        .action-btn:hover {{ background: #1ebe5d; }}
        .close-msg {{
            display: none;
            margin-top: 16px;
            font-size: 14px;
            color: #6b7280;
        }}
        .footer {{
            margin-top: 24px;
            font-size: 12px;
            color: #9ca3af;
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="check-circle">
            <svg viewBox="0 0 24 24" fill="none" stroke="#25D366" stroke-width="2.5"
                 stroke-linecap="round" stroke-linejoin="round">
                <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
        </div>
        <div class="brand">AkoweAI</div>
        <h1>Payment Received</h1>
        <p class="subtitle">
            Your receipt is being prepared.<br>
            Check WhatsApp for confirmation.
        </p>
        <div class="ref-box">
            <div class="ref-label">Transaction Reference</div>
            <div class="ref-value">{txnref}</div>
        </div>
        <a id="action-btn" class="action-btn" href="#">Loading&hellip;</a>
        <p id="close-msg" class="close-msg">You may now close this tab.</p>
        <div class="footer">Powered by AkoweAI &middot; Secured by Interswitch</div>
    </div>
    <script>
        (function () {{
            var isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(
                navigator.userAgent
            );
            var btn = document.getElementById('action-btn');
            var closeMsg = document.getElementById('close-msg');

            if (isMobile) {{
                btn.href = 'whatsapp://';
                btn.textContent = '\u2190 Back to WhatsApp';
            }} else {{
                btn.textContent = 'Close this tab';
                btn.addEventListener('click', function (e) {{
                    e.preventDefault();
                    window.close();
                    // If window.close() was blocked, surface the fallback message
                    setTimeout(function () {{
                        btn.style.display = 'none';
                        closeMsg.style.display = 'block';
                    }}, 300);
                }});
            }}
        }})();
    </script>
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
        if not member:
            return

        from app.repositories.cooperative_repository import CooperativeRepository
        from app.repositories.period_repository import PeriodRepository

        coop = await CooperativeRepository(db).get_by_id(transaction.cooperative_id)
        coop_name = coop.name if coop else "your cooperative"

        if len(transaction.period_ids) > 1:
            period_label = "Multiple Periods"
        elif len(transaction.period_ids) == 1:
            period = await PeriodRepository(db).get_by_id(transaction.period_ids[0])
            period_label = (
                period.start_date.strftime("%B %Y") if period else "Current Period"
            )
        else:
            period_label = "Current Period"

        await dispatch_payment_receipt(
            phone=member.phone_number,
            transaction=transaction,
            coop_name=coop_name,
            member_name=member.full_name,
            period_label=period_label,
        )


async def _send_payment_failure_message(transaction) -> None:
    """Notify the member that their payment could not be verified."""
    from app.services.whatsapp_service import send_text_message
    async with AsyncSessionFactory() as db:
        member_repo = MemberRepository(db)
        member = await member_repo.get_by_id(transaction.member_id)
        if member:
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

    coop_repo = CooperativeRepository(db)
    coop = await coop_repo.get_by_id(transaction.cooperative_id)

    member_name = member.full_name if member else "Member"
    coop_name = coop.name if coop else "Cooperative"
    cust_name = f"{member_name} - {coop_name}"

    html = _INITIATE_FORM_TEMPLATE.format(
        action_url=f"{settings.interswitch_base_url}/collections/w/pay",
        merchant_code=settings.interswitch_merchant_code,
        pay_item_id=settings.interswitch_pay_item_id,
        txn_ref=reference,
        amount=transaction.amount,
        cust_name=cust_name,
        redirect_url=f"{settings.prod_url}/api/payments/redirect",
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

    return HTMLResponse(
        content=_COMPLETION_HTML_TEMPLATE.format(txnref=txnref or "\u2014")
    )


@router.post("/webhook")
async def payment_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> Response:
    """
    Interswitch webhook endpoint.
    Verifies X-Interswitch-Signature (HMAC-SHA512 of raw body).
    Always returns bare 200 — Interswitch discards any response body.
    """
    raw_body = await request.body()
    signature = request.headers.get("X-Interswitch-Signature", "")

    if not verify_interswitch_webhook_signature(raw_body, signature):
        logger.warning("Interswitch webhook signature verification failed")
        return Response(status_code=200)

    try:
        payload = json.loads(raw_body)
    except Exception:
        return Response(status_code=200)

    event_type = payload.get("event", "")
    if event_type == "TRANSACTION.COMPLETED":
        event_data = payload.get("data", {})
        txnref = event_data.get("merchantReference", "")
        amount = int(event_data.get("amount", 0))
        if txnref:
            background_tasks.add_task(_verify_and_process_payment, txnref, amount)

    return Response(status_code=200)


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