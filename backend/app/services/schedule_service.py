from datetime import date, timedelta
from uuid import UUID

from dateutil.relativedelta import relativedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Frequency
from app.core.exceptions import NotFoundException
from app.models.coop_schedule import CoopSchedule
from app.repositories.schedule_repository import ScheduleRepository

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _frequency_delta(frequency: Frequency) -> relativedelta:
    return {
        Frequency.WEEKLY:    relativedelta(weeks=1),
        Frequency.BIWEEKLY:  relativedelta(weeks=2),
        Frequency.TRIWEEKLY: relativedelta(weeks=3),
        Frequency.MONTHLY:   relativedelta(months=1),
        Frequency.BIMONTHLY: relativedelta(months=2),
        Frequency.QUARTERLY: relativedelta(months=3),
        Frequency.YEARLY:    relativedelta(years=1),
    }[frequency]


def compute_period_start(
    anchor_date: date, frequency: Frequency, period_number: int
) -> date:
    """Return the start date for a 1-indexed period number."""
    n = period_number - 1
    delta = _frequency_delta(frequency)
    scaled = relativedelta(
        years=delta.years * n,
        months=delta.months * n,
        weeks=delta.weeks * n,
        days=delta.days * n,
    )
    return anchor_date + scaled


def compute_period_end_date(
    anchor_date: date, frequency: Frequency, period_number: int
) -> date:
    """Return the last day of a period (day before the next period starts)."""
    return compute_period_start(anchor_date, frequency, period_number + 1) - timedelta(days=1)


def compute_next_period_dates(
    schedule: CoopSchedule, last_period_number: int
) -> tuple[date, date]:
    """Return (start_date, due_date) for the period after last_period_number."""
    freq = Frequency(schedule.frequency)
    next_number = last_period_number + 1
    start_date = compute_period_start(schedule.anchor_date, freq, next_number)
    due_date = start_date + timedelta(days=schedule.due_day_offset)
    return start_date, due_date


def format_period_label(
    period_number: int, start_date: date, end_date: date
) -> str:
    s = f"{_MONTHS[start_date.month - 1]} {start_date.day}"
    e = f"{_MONTHS[end_date.month - 1]} {end_date.day}"
    return f"Period {period_number} ({s} – {e})"


# Service

class ScheduleService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ScheduleRepository(db)

    async def get_active_schedule(self, coop_id: UUID) -> CoopSchedule:
        schedule = await self.repo.get_active(coop_id)
        if not schedule:
            raise NotFoundException("No active schedule found for this cooperative")
        return schedule

    async def create_schedule_version(
        self,
        coop_id: UUID,
        frequency: Frequency,
        due_day_offset: int,
    ) -> CoopSchedule:
        """
        Supersede the current active schedule and create a new version.
        anchor_date is always carried forward — it is immutable.
        due_day_offset is explicitly provided (caller resolves the effective value).
        """
        current = await self.get_active_schedule(coop_id)
        await self.repo.supersede(current.id)

        return await self.repo.create(
            coop_id=coop_id,
            frequency=frequency.value,
            anchor_date=current.anchor_date,
            due_day_offset=due_day_offset,
            version=current.version + 1,
        )