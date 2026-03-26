from uuid import UUID

from sqlalchemy import cast, select
from sqlalchemy import Date as SADate
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Frequency
from app.models.contribution import Contribution
from app.models.contribution_period import ContributionPeriod
from app.models.coop_member import CoopMember
from app.repositories.contribution_repository import ContributionRepository
from app.repositories.cooperative_repository import CooperativeRepository
from app.repositories.period_repository import PeriodRepository
from app.repositories.schedule_repository import ScheduleRepository
from app.services.schedule_service import (
    ScheduleService,
    compute_next_period_dates,
    compute_period_end_date,
    format_period_label,
)


class PeriodService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.period_repo = PeriodRepository(db)
        self.schedule_repo = ScheduleRepository(db)
        self.schedule_service = ScheduleService(db)
        self.coop_repo = CooperativeRepository(db)
        self.contribution_repo = ContributionRepository(db)

    async def get_or_create_current_period(
        self, coop_id: UUID
    ) -> ContributionPeriod:
        open_period = await self.period_repo.get_open_period(coop_id)
        if open_period:
            return open_period

        schedule = await self.schedule_service.get_active_schedule(coop_id)
        last_number = await self.period_repo.get_latest_period_number(coop_id)
        start_date, due_date = compute_next_period_dates(schedule, last_number)

        return await self.period_repo.create(
            coop_id=coop_id,
            schedule_id=schedule.id,
            period_number=last_number + 1,
            start_date=start_date,
            due_date=due_date,
        )

    async def close_period_and_create_next(
        self, period: ContributionPeriod
    ) -> tuple[ContributionPeriod, list[UUID]]:
        """
        Close the given period, open the next one, and pre-generate contribution
        records for all members who had joined by the new period's start date.
        Returns the new period and the list of member_ids for whom contributions
        were created (used by the caller to schedule reminders).
        """
        await self.period_repo.close(period.id)

        next_period = await self.get_or_create_current_period(period.cooperative_id)

        # Members who joined on or before the new period's start date
        result = await self.db.execute(
            select(CoopMember).where(
                CoopMember.cooperative_id == period.cooperative_id,
                cast(CoopMember.joined_at, SADate) <= next_period.start_date,
            )
        )
        active_members = result.scalars().all()

        coop = await self.coop_repo.get_by_id(period.cooperative_id)

        await self.contribution_repo.create_bulk([
            {
                "member_id": cm.member_id,
                "cooperative_id": period.cooperative_id,
                "period_id": next_period.id,
                "amount": coop.contribution_amount,
                "status": "unpaid",
            }
            for cm in active_members
        ])

        await self.db.commit()

        member_ids = [cm.member_id for cm in active_members]
        return next_period, member_ids

    async def close_overdue_periods(self) -> dict:
        """
        Find all contribution periods whose due_date has passed and are still open,
        close each one, create the next period, and schedule reminders for new members.
        Returns a dict with the count of periods closed and created.
        """
        from datetime import date as _date
        from app.services.reminder_service import ReminderService

        today = _date.today()

        result = await self.db.execute(
            select(ContributionPeriod).where(
                ContributionPeriod.due_date <= today,
                ContributionPeriod.closed_at.is_(None),
            )
        )
        overdue_periods = result.scalars().all()

        if not overdue_periods:
            return {"closed": 0, "created": 0}

        reminder_service = ReminderService(self.db)
        closed_count = 0
        created_count = 0

        for period in overdue_periods:
            next_period, member_ids = await self.close_period_and_create_next(period)
            await reminder_service.schedule_reminders_for_period(next_period, member_ids)
            closed_count += 1
            created_count += 1

        return {"closed": closed_count, "created": created_count}

    async def generate_future_periods(
        self, coop_id: UUID, count: int
    ) -> list[ContributionPeriod]:
        """
        Persist future periods on demand (find-or-create by period_number).
        Called at payment initiation time — not during the payable list read.
        """
        schedule = await self.schedule_service.get_active_schedule(coop_id)
        latest_number = await self.period_repo.get_latest_period_number(coop_id)

        periods: list[ContributionPeriod] = []
        for i in range(1, count + 1):
            future_number = latest_number + i
            existing = await self.period_repo.get_by_number(coop_id, future_number)
            if existing:
                periods.append(existing)
                continue

            start_date, due_date = compute_next_period_dates(
                schedule, latest_number + i - 1
            )
            period = await self.period_repo.create(
                coop_id=coop_id,
                schedule_id=schedule.id,
                period_number=future_number,
                start_date=start_date,
                due_date=due_date,
            )
            periods.append(period)

        return periods

    async def get_member_debt_periods(
        self, member_id: UUID, coop_id: UUID
    ) -> list[ContributionPeriod]:
        return await self.period_repo.get_member_debt_periods(member_id, coop_id)

    async def get_payable_periods(
        self, coop_id: UUID, member_id: UUID
    ) -> list[dict]:
        """
        Pure read — returns current open period, all debt periods, and up to 3
        computed future periods. Future periods are NOT persisted here.
        """
        schedule = await self.schedule_service.get_active_schedule(coop_id)
        freq = Frequency(schedule.frequency)
        coop = await self.coop_repo.get_by_id(coop_id)

        result: list[dict] = []

        # --- Debt periods (closed, member has unpaid contribution) ---
        debt_periods = await self.period_repo.get_member_debt_periods(
            member_id, coop_id
        )
        # Fetch snapshotted amounts for debt periods in one query
        debt_amounts = await self.contribution_repo.get_amounts_for_periods(
            member_id, [p.id for p in debt_periods]
        )
        for p in debt_periods:
            end_date = compute_period_end_date(schedule.anchor_date, freq, p.period_number)
            result.append({
                "id": p.id,
                "period_number": p.period_number,
                "start_date": p.start_date,
                "due_date": p.due_date,
                "amount": debt_amounts.get(p.id, coop.contribution_amount),
                "label": format_period_label(p.period_number, p.start_date, end_date),
                "is_debt": True,
                "is_future": False,
            })

        # --- Current open period (only if member has not already paid for it) ---
        open_period = await self.period_repo.get_open_period(coop_id)
        if open_period:
            paid_check = await self.db.execute(
                select(Contribution.id).where(
                    Contribution.member_id == member_id,
                    Contribution.period_id == open_period.id,
                    Contribution.status == "paid",
                )
            )
            if paid_check.scalar_one_or_none() is None:
                end_date = compute_period_end_date(
                    schedule.anchor_date, freq, open_period.period_number
                )
                result.append({
                    "id": open_period.id,
                    "period_number": open_period.period_number,
                    "start_date": open_period.start_date,
                    "due_date": open_period.due_date,
                    "amount": coop.contribution_amount,
                    "label": format_period_label(
                        open_period.period_number, open_period.start_date, end_date
                    ),
                    "is_debt": False,
                    "is_future": False,
                })

        # --- Up to 3 future periods (computed, not persisted) ---
        latest_number = await self.period_repo.get_latest_period_number(coop_id)
        for i in range(1, 4):
            future_number = latest_number + i
            start_date, due_date = compute_next_period_dates(
                schedule, latest_number + i - 1
            )
            end_date = compute_period_end_date(schedule.anchor_date, freq, future_number)
            result.append({
                "id": None,
                "period_number": future_number,
                "start_date": start_date,
                "due_date": due_date,
                "amount": coop.contribution_amount,
                "label": format_period_label(future_number, start_date, end_date),
                "is_debt": False,
                "is_future": True,
            })

        return result

    async def get_all_periods(self, coop_id: UUID) -> list[dict]:
        """All persisted periods for the coop, for the history filter dropdown."""
        periods = await self.period_repo.get_all_periods(coop_id)
        return [
            {
                "id": p.id,
                "period_number": p.period_number,
                "label": p.start_date.strftime("%B %Y"),
                "start_date": p.start_date,
                "due_date": p.due_date,
                "is_open": p.closed_at is None,
            }
            for p in periods
        ]