import hashlib
import hmac
import json
import logging
import secrets
import time
from datetime import datetime, timezone
from uuid import UUID

import httpx

from app.core.config import get_settings
from app.core.exceptions import BadRequestException, NotFoundException
from app.models.pending_transaction import PendingTransaction
from app.repositories.payment_repository import PaymentRepository
from app.services.period_service import PeriodService
from app.services.reminder_service import cancel_reminders_for_periods

settings = get_settings()
logger = logging.getLogger("akoweai")

# Interswitch OAuth token cache (in-process, single-instance safe)
_token_cache: dict = {"token": None, "expires_at": 0.0}  # expires_at is unix timestamp


async def _get_interswitch_token() -> str:
    """
    Return a valid Interswitch OAuth2 Bearer token.
    Fetches a new one only when the cached token is within 30s of expiry.
    """
    now = time.time()
    if _token_cache["token"] and _token_cache["expires_at"] > now + 30:
        return _token_cache["token"]

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            settings.interswitch_auth_url,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
            },
            auth=(settings.interswitch_client_id, settings.interswitch_secret_key),
        )
        response.raise_for_status()
        data = response.json()

    token = data["access_token"]
    expires_in = int(data.get("expires_in", 3600))

    _token_cache["token"] = token
    _token_cache["expires_at"] = time.time() + expires_in

    return token


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
        Uses v2 API — reference is appended as a query param, Bearer token required.
        """
        try:
            token = await _get_interswitch_token()
        except Exception as e:
            logger.error("Failed to obtain Interswitch token: %s", e)
            raise

        url = f"{settings.interswitch_query_url}?transactionReference={reference}"

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                url,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}",
                },
            )
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
        4. Cancel pending reminders (stub until Phase 8)
        """
        await self.payment_repo.mark_paid(transaction.id)
        await self.payment_repo.mark_contributions_paid(
            transaction.period_ids, transaction.member_id
        )
        await self.payment_repo.increment_pool_balance(
            transaction.cooperative_id, transaction.amount
        )
        await cancel_reminders_for_periods(
            transaction.period_ids, transaction.member_id, self.db
        )


def verify_interswitch_webhook_signature(raw_body: bytes, signature_header: str) -> bool:
    """
    Verify X-Interswitch-Signature.
    Interswitch uses HMAC-SHA512 of the raw JSON body, hex-encoded.
    """
    expected = hmac.new(
        settings.interswitch_secret_key.encode(),
        raw_body,
        hashlib.sha512,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)