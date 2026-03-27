from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contribution import Contribution
from app.models.contribution_period import ContributionPeriod


class PeriodRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_open_period(self, coop_id: UUID) -> ContributionPeriod | None:
        result = await self.db.execute(
            select(ContributionPeriod)
            .where(
                ContributionPeriod.cooperative_id == coop_id,
                ContributionPeriod.closed_at.is_(None),
            )
            .order_by(ContributionPeriod.period_number.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_latest_period_number(self, coop_id: UUID) -> int:
        result = await self.db.execute(
            select(ContributionPeriod.period_number)
            .where(ContributionPeriod.cooperative_id == coop_id)
            .order_by(ContributionPeriod.period_number.desc())
            .limit(1)
        )
        value = result.scalar_one_or_none()
        return value if value is not None else 0

    async def get_by_number(
        self, coop_id: UUID, period_number: int
    ) -> ContributionPeriod | None:
        result = await self.db.execute(
            select(ContributionPeriod).where(
                ContributionPeriod.cooperative_id == coop_id,
                ContributionPeriod.period_number == period_number,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, period_id: UUID) -> ContributionPeriod | None:
        result = await self.db.execute(
            select(ContributionPeriod).where(ContributionPeriod.id == period_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        coop_id: UUID,
        schedule_id: UUID,
        period_number: int,
        start_date: date,
        due_date: date,
    ) -> ContributionPeriod:
        period = ContributionPeriod(
            cooperative_id=coop_id,
            schedule_id=schedule_id,
            period_number=period_number,
            start_date=start_date,
            due_date=due_date,
        )
        self.db.add(period)
        await self.db.flush()
        return period

    async def close(self, period_id: UUID) -> None:
        await self.db.execute(
            update(ContributionPeriod)
            .where(ContributionPeriod.id == period_id)
            .values(closed_at=datetime.now(timezone.utc))
        )

    async def get_member_debt_periods(
        self, member_id: UUID, coop_id: UUID
    ) -> list[ContributionPeriod]:
        result = await self.db.execute(
            select(ContributionPeriod)
            .join(
                Contribution,
                and_(
                    Contribution.period_id == ContributionPeriod.id,
                    Contribution.member_id == member_id,
                    Contribution.status == "unpaid",
                ),
            )
            .where(
                ContributionPeriod.cooperative_id == coop_id,
                ContributionPeriod.closed_at.is_not(None),
            )
            .order_by(ContributionPeriod.period_number)
        )
        return list(result.scalars().all())