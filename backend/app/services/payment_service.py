import hashlib
import hmac
import logging
import secrets
import time
from uuid import UUID

import httpx

from app.core.config import get_settings
from app.core.exceptions import BadRequestException, NotFoundException
from app.models.pending_transaction import PendingTransaction
from app.repositories.payment_repository import PaymentRepository
from app.services.period_service import PeriodService
from app.services.reminder_service import ReminderService

settings = get_settings()
logger = logging.getLogger("akoweai")


def generate_transaction_reference() -> str:
    """Generate a unique payment reference: AKOWE-{timestamp_ms}-{6 hex chars}."""
    ts_ms = int(time.time() * 1000)
    rand = secrets.token_hex(3).upper()
    return f"AKOWE-{ts_ms}-{rand}"


class PaymentService:
    def __init__(self, db):
        self.db = db
        self.payment_repo = PaymentRepository(db)
        self.period_service = PeriodService(db)

    async def create_pending_transaction(
        self,
        member_id: UUID,
        coop_id: UUID,
        period_data: list[dict],
        amount_kobo: int,
    ) -> PendingTransaction:
        """
        Create a PendingTransaction record.
        If any periods are future (id=None), they are persisted first via
        generate_future_periods before the transaction is created.
        """
        period_ids: list[UUID] = []

        future_indices = [i for i, p in enumerate(period_data) if p.get("id") is None]
        future_count = len(future_indices)

        if future_count > 0:
            # generate_future_periods uses find-or-create by period_number,
            # returning periods in ascending period_number order
            generated = await self.period_service.generate_future_periods(
                coop_id, future_count
            )
            gen_iter = iter(generated)
            for p in period_data:
                if p.get("id") is None:
                    period_ids.append(next(gen_iter).id)
                else:
                    period_ids.append(UUID(str(p["id"])))
        else:
            period_ids = [UUID(str(p["id"])) for p in period_data]

        reference = generate_transaction_reference()
        transaction = await self.payment_repo.create(
            reference=reference,
            member_id=member_id,
            coop_id=coop_id,
            period_ids=period_ids,
            amount=amount_kobo,
        )
        await self.db.commit()
        await self.db.refresh(transaction)
        return transaction

    def build_payment_initiation_url(self, reference: str) -> str:
        """
        Returns the URL for the WhatsApp CTA button.
        Points to our bridge page which auto-submits the form to Interswitch.
        """
        return f"{settings.prod_url}/api/payments/initiate/{reference}"

    async def poll_transaction_status(
        self, reference: str, amount_kobo: int
    ) -> dict:
        """
        Query Interswitch for authoritative transaction status.
        Uses v1 API — no authentication required.
        Query params are lowercase per the v1 spec.
        """
        params = {
            "merchantcode": settings.interswitch_merchant_code,
            "transactionreference": reference,
            "amount": amount_kobo,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(settings.interswitch_query_url, params=params)
            response.raise_for_status()
            return response.json()

    async def is_transaction_already_processed(self, reference: str) -> bool:
        return await self.payment_repo.is_already_paid(reference)

    async def process_successful_payment(
        self, transaction: PendingTransaction
    ) -> None:
        """
        Atomically:
        1. Mark PendingTransaction as paid
        2. Mark all covered Contribution records as paid
        3. Increment cooperative pool balance
        4. Cancel pending reminders for affected member + periods
        """
        await self.payment_repo.mark_paid(transaction.id)
        await self.payment_repo.mark_contributions_paid(
            transaction.period_ids, transaction.member_id
        )
        await self.payment_repo.increment_pool_balance(
            transaction.cooperative_id, transaction.amount
        )
        await ReminderService(self.db).cancel_reminders_for_periods(
            transaction.period_ids, transaction.member_id
        )


def verify_interswitch_webhook_signature(raw_body: bytes, signature_header: str) -> bool:
    """
    Verify X-Interswitch-Signature.
    Interswitch uses HMAC-SHA512 of the raw JSON body, hex-encoded.
    Fails closed if INTERSWITCH_WEBHOOK_SECRET is not configured.
    """
    if not settings.interswitch_webhook_secret:
        logger.error(
            "INTERSWITCH_WEBHOOK_SECRET is not configured — rejecting webhook request"
        )
        return False
    expected = hmac.new(
        settings.interswitch_webhook_secret.encode(),
        raw_body,
        hashlib.sha512,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)