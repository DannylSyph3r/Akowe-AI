from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import and_, select, update
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contribution import Contribution
from app.models.cooperative import Cooperative
from app.models.pending_transaction import PendingTransaction


class PaymentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        reference: str,
        member_id: UUID,
        coop_id: UUID,
        period_ids: list[UUID],
        amount: int,
    ) -> PendingTransaction:
        transaction = PendingTransaction(
            reference=reference,
            member_id=member_id,
            cooperative_id=coop_id,
            period_ids=period_ids,
            amount=amount,
            status="pending",
        )
        self.db.add(transaction)
        await self.db.flush()
        return transaction

    async def get_by_reference(self, reference: str) -> PendingTransaction | None:
        result = await self.db.execute(
            select(PendingTransaction).where(PendingTransaction.reference == reference)
        )
        return result.scalar_one_or_none()

    async def is_already_paid(self, reference: str) -> bool:
        result = await self.db.execute(
            select(PendingTransaction.id).where(
                and_(
                    PendingTransaction.reference == reference,
                    PendingTransaction.status == "paid",
                )
            )
        )
        return result.scalar_one_or_none() is not None

    async def mark_paid(self, transaction_id: UUID) -> None:
        now = datetime.now(timezone.utc)
        await self.db.execute(
            update(PendingTransaction)
            .where(PendingTransaction.id == transaction_id)
            .values(status="paid", updated_at=now)
        )

    async def mark_failed(self, reference: str) -> None:
        now = datetime.now(timezone.utc)
        await self.db.execute(
            update(PendingTransaction)
            .where(PendingTransaction.reference == reference)
            .values(status="failed", updated_at=now)
        )

    async def mark_invalidated(self, reference: str) -> None:
        now = datetime.now(timezone.utc)
        await self.db.execute(
            update(PendingTransaction)
            .where(PendingTransaction.reference == reference)
            .values(status="invalidated", updated_at=now)
        )

    async def mark_contributions_paid(
        self, period_ids: list[UUID], member_id: UUID
    ) -> None:
        """Atomically mark all contributions for the given periods as paid."""
        now = datetime.now(timezone.utc)
        await self.db.execute(
            update(Contribution)
            .where(
                and_(
                    Contribution.member_id == member_id,
                    Contribution.period_id.in_(period_ids),
                )
            )
            .values(status="paid", paid_at=now)
        )

    async def increment_pool_balance(self, coop_id: UUID, amount: int) -> None:
        """Atomically increment the cooperative's pool balance."""
        await self.db.execute(
            update(Cooperative)
            .where(Cooperative.id == coop_id)
            .values(pool_balance=Cooperative.pool_balance + amount)
        )