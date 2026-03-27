from uuid import UUID

from sqlalchemy import and_, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cooperative import Cooperative
from app.models.coop_member import CoopMember


class CooperativeRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        name: str,
        contribution_amount: int,
        due_day_offset: int,
        created_by_member_id: UUID,
    ) -> Cooperative:
        coop = Cooperative(
            name=name,
            contribution_amount=contribution_amount,
            due_day_offset=due_day_offset,
            created_by_member_id=created_by_member_id,
        )
        self.db.add(coop)
        await self.db.flush()
        return coop

    async def get_by_id(self, coop_id: UUID) -> Cooperative | None:
        result = await self.db.execute(
            select(Cooperative).where(Cooperative.id == coop_id)
        )
        return result.scalar_one_or_none()

    async def get_member_cooperatives(
        self, member_id: UUID
    ) -> list[tuple[Cooperative, CoopMember]]:
        result = await self.db.execute(
            select(Cooperative, CoopMember)
            .join(CoopMember, CoopMember.cooperative_id == Cooperative.id)
            .where(CoopMember.member_id == member_id)
            .order_by(CoopMember.joined_at)
        )
        return list(result.all())

    async def get_member_role(
        self, coop_id: UUID, member_id: UUID
    ) -> CoopMember | None:
        result = await self.db.execute(
            select(CoopMember).where(
                CoopMember.cooperative_id == coop_id,
                CoopMember.member_id == member_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_member_count(self, coop_id: UUID) -> int:
        result = await self.db.execute(
            select(func.count(CoopMember.id)).where(
                CoopMember.cooperative_id == coop_id
            )
        )
        return result.scalar_one()

    async def create_coop_member(
        self, coop_id: UUID, member_id: UUID, role: str
    ) -> CoopMember:
        coop_member = CoopMember(
            cooperative_id=coop_id,
            member_id=member_id,
            role=role,
        )
        self.db.add(coop_member)
        await self.db.flush()
        return coop_member

    async def update_settings(
        self,
        coop_id: UUID,
        contribution_amount: int | None = None,
        due_day_offset: int | None = None,
    ) -> Cooperative:
        values: dict = {}
        if contribution_amount is not None:
            values["contribution_amount"] = contribution_amount
        if due_day_offset is not None:
            values["due_day_offset"] = due_day_offset

        if values:
            await self.db.execute(
                update(Cooperative)
                .where(Cooperative.id == coop_id)
                .values(**values)
            )

        # Re-fetch to return the current persisted state
        return await self.get_by_id(coop_id)

    async def get_members_with_stats(self, coop_id: UUID) -> list[dict]:
        """
        Single query: all coop members with total contributions, last payment
        date, and a late_count derived from the last 3 closed periods.
        The caller maps late_count → RiskLevel.
        """
        stmt = text("""
            WITH last_3_periods AS (
                SELECT id, due_date
                FROM contribution_periods
                WHERE cooperative_id = :coop_id
                  AND closed_at IS NOT NULL
                ORDER BY period_number DESC
                LIMIT 3
            ),
            member_stats AS (
                SELECT
                    c.member_id,
                    SUM(CASE WHEN c.status = 'paid' THEN c.amount ELSE 0 END) AS total_contributed,
                    MAX(c.paid_at) AS last_paid_at
                FROM contributions c
                WHERE c.cooperative_id = :coop_id
                GROUP BY c.member_id
            ),
            member_risk AS (
                SELECT
                    c.member_id,
                    COUNT(*) FILTER (
                        WHERE c.status = 'unpaid'
                           OR (c.status = 'paid' AND c.paid_at > p.due_date)
                    ) AS late_count
                FROM contributions c
                JOIN last_3_periods p ON c.period_id = p.id
                WHERE c.cooperative_id = :coop_id
                GROUP BY c.member_id
            )
            SELECT
                m.id           AS member_id,
                m.full_name,
                cm.role,
                cm.joined_at,
                COALESCE(ms.total_contributed, 0) AS total_contributed,
                ms.last_paid_at,
                COALESCE(mr.late_count, 0)        AS late_count
            FROM coop_members cm
            JOIN members m ON cm.member_id = m.id
            LEFT JOIN member_stats ms ON cm.member_id = ms.member_id
            LEFT JOIN member_risk  mr ON cm.member_id = mr.member_id
            WHERE cm.cooperative_id = :coop_id
            ORDER BY cm.joined_at
        """)
        result = await self.db.execute(stmt, {"coop_id": coop_id})
        return [dict(row._mapping) for row in result.fetchall()]

    async def get_paid_count_for_period(
        self, coop_id: UUID, period_id: UUID
    ) -> int:
        """Count contributions with status='paid' for a given period in this coop."""
        from app.models.contribution import Contribution

        result = await self.db.execute(
            select(func.count(Contribution.id)).where(
                and_(
                    Contribution.cooperative_id == coop_id,
                    Contribution.period_id == period_id,
                    Contribution.status == "paid",
                )
            )
        )
        return result.scalar_one() or 0

    async def get_unpaid_members_for_period(
        self, coop_id: UUID, period_id: UUID
    ) -> list[dict]:
        """
        Return a list of members with unpaid contributions for the given period.
        Each dict has: member_id, full_name, phone_number.
        """
        from app.models.contribution import Contribution
        from app.models.member import Member as MemberModel

        result = await self.db.execute(
            select(MemberModel.id, MemberModel.full_name, MemberModel.phone_number)
            .join(Contribution, Contribution.member_id == MemberModel.id)
            .where(
                and_(
                    Contribution.cooperative_id == coop_id,
                    Contribution.period_id == period_id,
                    Contribution.status == "unpaid",
                )
            )
        )
        rows = result.all()
        return [
            {
                "member_id": row.id,
                "full_name": row.full_name,
                "phone_number": row.phone_number,
            }
            for row in rows
        ]

    async def get_active_member_phones(
        self, coop_id: UUID
    ) -> list[tuple[str, str]]:
        """
        Return (phone_number, full_name) tuples for all active members of the coop.
        """
        from app.models.member import Member as MemberModel

        result = await self.db.execute(
            select(MemberModel.phone_number, MemberModel.full_name)
            .join(CoopMember, CoopMember.member_id == MemberModel.id)
            .where(CoopMember.cooperative_id == coop_id)
        )
        return [(row.phone_number, row.full_name) for row in result.all()]

    async def search_members_by_name(
        self, coop_id: UUID, query: str
    ) -> list[dict]:
        """
        Fuzzy member name search within a cooperative using ILIKE.
        Returns member_id, full_name, role.
        """
        from app.models.member import Member as MemberModel

        pattern = f"%{query}%"
        result = await self.db.execute(
            select(
                MemberModel.id,
                MemberModel.full_name,
                CoopMember.role,
            )
            .join(CoopMember, CoopMember.member_id == MemberModel.id)
            .where(
                and_(
                    CoopMember.cooperative_id == coop_id,
                    MemberModel.full_name.ilike(pattern),
                )
            )
            .order_by(MemberModel.full_name)
            .limit(10)
        )
        rows = result.all()
        return [
            {
                "member_id": row.id,
                "full_name": row.full_name,
                "role": row.role,
            }
            for row in rows
        ]

    async def get_financial_summary(
        self, coop_id: UUID, days: int = 30
    ) -> dict:
        """
        Return aggregated financial data for the last N days.
        Used by AI summary flows and the WhatsApp financial summary handler.
        """
        from datetime import datetime, timedelta, timezone
        from app.models.contribution import Contribution
        from app.models.contribution_period import ContributionPeriod
        from app.models.withdrawal import Withdrawal

        since = datetime.now(timezone.utc) - timedelta(days=days)

        # Contributions paid in the last N days
        contrib_result = await self.db.execute(
            select(func.coalesce(func.sum(Contribution.amount), 0)).where(
                and_(
                    Contribution.cooperative_id == coop_id,
                    Contribution.status == "paid",
                    Contribution.paid_at >= since,
                )
            )
        )
        contributions_kobo = contrib_result.scalar_one() or 0

        # Withdrawals recorded in the last N days
        withdrawal_result = await self.db.execute(
            select(func.coalesce(func.sum(Withdrawal.amount), 0)).where(
                and_(
                    Withdrawal.cooperative_id == coop_id,
                    Withdrawal.created_at >= since,
                )
            )
        )
        withdrawals_kobo = withdrawal_result.scalar_one() or 0

        # Outstanding unpaid contributions (all time)
        unpaid_result = await self.db.execute(
            select(func.coalesce(func.sum(Contribution.amount), 0)).where(
                and_(
                    Contribution.cooperative_id == coop_id,
                    Contribution.status == "unpaid",
                )
            )
        )
        outstanding_debt_kobo = unpaid_result.scalar_one() or 0

        # Current open period for collection-rate calculation
        open_period_result = await self.db.execute(
            select(ContributionPeriod.id).where(
                and_(
                    ContributionPeriod.cooperative_id == coop_id,
                    ContributionPeriod.closed_at.is_(None),
                )
            ).order_by(ContributionPeriod.period_number.desc()).limit(1)
        )
        open_period_id = open_period_result.scalar_one_or_none()

        paid_count = 0
        total_count = 0
        if open_period_id:
            paid_r = await self.db.execute(
                select(func.count(Contribution.id)).where(
                    and_(
                        Contribution.cooperative_id == coop_id,
                        Contribution.period_id == open_period_id,
                        Contribution.status == "paid",
                    )
                )
            )
            paid_count = paid_r.scalar_one() or 0

            total_r = await self.db.execute(
                select(func.count(Contribution.id)).where(
                    and_(
                        Contribution.cooperative_id == coop_id,
                        Contribution.period_id == open_period_id,
                    )
                )
            )
            total_count = total_r.scalar_one() or 0

        collection_rate = int(paid_count / total_count * 100) if total_count else 0

        return {
            "contributions_kobo": int(contributions_kobo),
            "withdrawals_kobo": int(withdrawals_kobo),
            "outstanding_debt_kobo": int(outstanding_debt_kobo),
            "paid_count": paid_count,
            "total_count": total_count,
            "collection_rate_pct": collection_rate,
        }