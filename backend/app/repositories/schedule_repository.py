from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.coop_schedule import CoopSchedule


class ScheduleRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_active(self, coop_id: UUID) -> CoopSchedule | None:
        result = await self.db.execute(
            select(CoopSchedule).where(
                CoopSchedule.cooperative_id == coop_id,
                CoopSchedule.superseded_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def supersede(self, schedule_id: UUID) -> None:
        await self.db.execute(
            update(CoopSchedule)
            .where(CoopSchedule.id == schedule_id)
            .values(superseded_at=datetime.now(timezone.utc))
        )

    async def create(
        self,
        coop_id: UUID,
        frequency: str,
        anchor_date: date,
        due_day_offset: int,
        version: int,
    ) -> CoopSchedule:
        schedule = CoopSchedule(
            cooperative_id=coop_id,
            frequency=frequency,
            anchor_date=anchor_date,
            due_day_offset=due_day_offset,
            version=version,
        )
        self.db.add(schedule)
        await self.db.flush()
        return schedule