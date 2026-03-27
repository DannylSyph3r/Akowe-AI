import logging
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contribution import Contribution
from app.models.contribution_period import ContributionPeriod
from app.models.cooperative import Cooperative
from app.models.member import Member
from app.models.reminder_log import ReminderLog
from app.services.whatsapp_service import (
    TEMPLATE_CONTRIBUTION_REMINDER,
    send_template_message,
)

logger = logging.getLogger("akoweai")

_REMINDER_STAGES: list[tuple[str, timedelta]] = [
    ("7_day", timedelta(days=-7)),
    ("3_day", timedelta(days=-3)),
    ("1_day", timedelta(days=-1)),
    ("due_date", timedelta(days=0)),
    ("1_week_overdue", timedelta(days=7)),
    ("2_weeks_overdue", timedelta(days=14)),
]


def _to_utc_midnight(d: date) -> datetime:
    """Convert a date to a timezone-aware datetime at midnight UTC."""
    return datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=timezone.utc)


class ReminderService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def schedule_reminders_for_period(
        self,
        period: ContributionPeriod,
        member_ids: list[UUID],
    ) -> None:
        """Schedule reminder stages for unpaid members in a period."""
        if not member_ids:
            return

        paid_result = await self.db.execute(
            select(Contribution.member_id).where(
                Contribution.period_id == period.id,
                Contribution.status == "paid",
                Contribution.member_id.in_(member_ids),
            )
        )
        already_paid: set[UUID] = {row[0] for row in paid_result.all()}

        rows = []
        for member_id in member_ids:
            if member_id in already_paid:
                continue
            for stage, offset in _REMINDER_STAGES:
                scheduled_at = _to_utc_midnight(period.due_date + offset)
                rows.append(
                    {
                        "member_id": member_id,
                        "period_id": period.id,
                        "stage": stage,
                        "status": "pending",
                        "scheduled_at": scheduled_at,
                    }
                )

        if not rows:
            return

        await self.db.execute(
            pg_insert(ReminderLog)
            .values(rows)
            .on_conflict_do_nothing(
                index_elements=["member_id", "period_id", "stage"]
            )
        )
        await self.db.commit()

    async def get_due_reminders(self) -> list[ReminderLog]:
        """
        Return up to 100 pending reminders whose scheduled_at has passed,
        excluding reminders for periods the member has already paid.
        """
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(ReminderLog)
            .join(
                Contribution,
                and_(
                    Contribution.member_id == ReminderLog.member_id,
                    Contribution.period_id == ReminderLog.period_id,
                ),
            )
            .where(
                ReminderLog.status == "pending",
                ReminderLog.scheduled_at <= now,
                Contribution.status != "paid",
            )
            .limit(100)
        )
        return list(result.scalars().all())

    async def dispatch_reminder(
        self,
        reminder: ReminderLog,
        member: Member,
        period: ContributionPeriod,
        coop: Cooperative,
    ) -> None:
        """
        Send the contribution reminder WhatsApp template and mark the reminder sent.
        Template variables:
          {{1}} member full name
          {{2}} contribution amount in naira (integer)
          {{3}} period label e.g. "March 2026"
          {{4}} due date e.g. "31 Mar 2026"
        """
        amount_naira = str(coop.contribution_amount // 100)
        period_label = period.due_date.strftime("%B %Y")
        due_date_str = period.due_date.strftime("%d %b %Y")

        components = [
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "text": member.full_name},
                    {"type": "text", "text": amount_naira},
                    {"type": "text", "text": period_label},
                    {"type": "text", "text": due_date_str},
                ],
            }
        ]

        await send_template_message(
            to=member.phone_number,
            template_name=TEMPLATE_CONTRIBUTION_REMINDER,
            components=components,
        )

        await self.db.execute(
            update(ReminderLog)
            .where(ReminderLog.id == reminder.id)
            .values(status="sent", sent_at=datetime.now(timezone.utc))
        )

    async def cancel_reminders_for_periods(
        self,
        period_ids: list[UUID],
        member_id: UUID,
    ) -> None:
        """
        Bulk-cancel all pending reminders for the given member + periods.
        Called by PaymentService after a successful payment.
        Signature matches the existing call site in payment_service.py (D20).
        """
        if not period_ids:
            return

        await self.db.execute(
            update(ReminderLog)
            .where(
                ReminderLog.member_id == member_id,
                ReminderLog.period_id.in_(period_ids),
                ReminderLog.status == "pending",
            )
            .values(status="cancelled")
        )
        await self.db.commit()

    async def process_due_reminders(self) -> int:
        """
        Fetch all due reminders, batch-load related data, dispatch each.
        Per-reminder errors are logged and do not halt the batch.
        Returns the count of successfully dispatched reminders.
        """
        reminders = await self.get_due_reminders()
        if not reminders:
            return 0

        # Batch-load all related objects to avoid N+1 queries
        member_ids = {r.member_id for r in reminders}
        period_ids = {r.period_id for r in reminders}

        members_by_id = {
            m.id: m for m in await self._fetch_members(member_ids)
        }
        periods_by_id = {
            p.id: p for p in await self._fetch_periods(period_ids)
        }
        coop_ids = {p.cooperative_id for p in periods_by_id.values()}
        coops_by_id = {
            c.id: c for c in await self._fetch_coops(coop_ids)
        }

        processed = 0
        for reminder in reminders:
            member = members_by_id.get(reminder.member_id)
            period = periods_by_id.get(reminder.period_id)
            if not period:
                continue
            coop = coops_by_id.get(period.cooperative_id)

            if not member or not coop:
                logger.warning(
                    "Skipping reminder %s — missing member or coop", reminder.id
                )
                continue

            try:
                await self.dispatch_reminder(reminder, member, period, coop)
                processed += 1
            except Exception as exc:
                logger.error(
                    "Reminder dispatch failed reminder_id=%s member=%s: %s",
                    reminder.id,
                    reminder.member_id,
                    exc,
                )

        if processed > 0:
            await self.db.commit()

        return processed

    async def _fetch_members(self, member_ids: set[UUID]) -> list[Member]:
        if not member_ids:
            return []
        result = await self.db.execute(
            select(Member).where(Member.id.in_(member_ids))
        )
        return list(result.scalars().all())

    async def _fetch_periods(self, period_ids: set[UUID]) -> list[ContributionPeriod]:
        if not period_ids:
            return []
        result = await self.db.execute(
            select(ContributionPeriod).where(ContributionPeriod.id.in_(period_ids))
        )
        return list(result.scalars().all())

    async def _fetch_coops(self, coop_ids: set[UUID]) -> list[Cooperative]:
        if not coop_ids:
            return []
        result = await self.db.execute(
            select(Cooperative).where(Cooperative.id.in_(coop_ids))
        )
        return list(result.scalars().all())