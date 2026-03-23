from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import RiskLevel
from app.models.contribution import Contribution
from app.models.contribution_period import ContributionPeriod


class ContributionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_bulk(self, contributions: list[dict]) -> None:
        if not contributions:
            return
        self.db.add_all([Contribution(**c) for c in contributions])
        await self.db.flush()

    async def get_member_balance(self, member_id: UUID, coop_id: UUID) -> dict:
        totals_result = await self.db.execute(
            select(
                func.coalesce(
                    func.sum(Contribution.amount).filter(
                        Contribution.status == "paid"
                    ),
                    0,
                ),
                func.count(Contribution.id).filter(Contribution.status == "paid"),
                func.count(Contribution.id),
            ).where(
                Contribution.member_id == member_id,
                Contribution.cooperative_id == coop_id,
            )
        )
        total_contributed, periods_paid, periods_total = totals_result.one()

        recent_result = await self.db.execute(
            select(
                ContributionPeriod.period_number,
                ContributionPeriod.start_date,
                ContributionPeriod.due_date,
                Contribution.amount,
                Contribution.status,
                Contribution.paid_at,
            )
            .join(ContributionPeriod, Contribution.period_id == ContributionPeriod.id)
            .where(
                Contribution.member_id == member_id,
                Contribution.cooperative_id == coop_id,
            )
            .order_by(ContributionPeriod.period_number.desc())
            .limit(4)
        )

        return {
            "total_contributed_kobo": total_contributed,
            "periods_paid": periods_paid,
            "periods_total": periods_total,
            "recent_rows": recent_result.all(),
        }

    async def get_member_history(
        self,
        member_id: UUID,
        coop_id: UUID,
        page: int,
        page_size: int,
    ) -> dict:
        offset = (page - 1) * page_size

        total_result = await self.db.execute(
            select(func.count(Contribution.id)).where(
                Contribution.member_id == member_id,
                Contribution.cooperative_id == coop_id,
            )
        )
        total = total_result.scalar_one()

        rows_result = await self.db.execute(
            select(
                ContributionPeriod.period_number,
                ContributionPeriod.start_date,
                ContributionPeriod.due_date,
                Contribution.amount,
                Contribution.status,
                Contribution.paid_at,
                Contribution.period_id,
            )
            .join(ContributionPeriod, Contribution.period_id == ContributionPeriod.id)
            .where(
                Contribution.member_id == member_id,
                Contribution.cooperative_id == coop_id,
            )
            .order_by(ContributionPeriod.period_number.desc())
            .limit(page_size)
            .offset(offset)
        )

        return {"total": total, "rows": rows_result.all()}

    async def get_paid_transaction_references(
        self, period_ids: list[UUID]
    ) -> dict[UUID, str]:
        """Batch fetch of paid transaction references for a list of period IDs."""
        if not period_ids:
            return {}
        result = await self.db.execute(
            text("""
                SELECT unnest(period_ids) AS period_id, reference
                FROM pending_transactions
                WHERE status = 'paid'
                  AND period_ids && :period_ids::uuid[]
            """),
            {"period_ids": period_ids},
        )
        # First reference found wins (shouldn't be multiple paid tx per period)
        mapping: dict[UUID, str] = {}
        for row in result.fetchall():
            pid = row.period_id
            if pid not in mapping:
                mapping[UUID(str(pid))] = row.reference
        return mapping

    async def get_amounts_for_periods(
        self, member_id: UUID, period_ids: list[UUID]
    ) -> dict[UUID, int]:
        """Fetch the snapshotted contribution amount per period for a member."""
        if not period_ids:
            return {}
        result = await self.db.execute(
            select(Contribution.period_id, Contribution.amount).where(
                Contribution.member_id == member_id,
                Contribution.period_id.in_(period_ids),
            )
        )
        return {row.period_id: row.amount for row in result.all()}

    async def calculate_risk_score(
        self, member_id: UUID, coop_id: UUID
    ) -> RiskLevel:
        result = await self.db.execute(
            text("""
                WITH last_3 AS (
                    SELECT id, due_date
                    FROM contribution_periods
                    WHERE cooperative_id = :coop_id
                      AND closed_at IS NOT NULL
                    ORDER BY period_number DESC
                    LIMIT 3
                )
                SELECT
                    COUNT(*) FILTER (
                        WHERE c.status = 'unpaid'
                           OR (c.status = 'paid' AND c.paid_at > p.due_date)
                    ) AS late_count
                FROM contributions c
                JOIN last_3 p ON c.period_id = p.id
                WHERE c.member_id = :member_id
                  AND c.cooperative_id = :coop_id
            """),
            {"member_id": member_id, "coop_id": coop_id},
        )
        late_count: int = result.scalar_one() or 0

        if late_count >= 2:
            return RiskLevel.HIGH
        if late_count == 1:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW