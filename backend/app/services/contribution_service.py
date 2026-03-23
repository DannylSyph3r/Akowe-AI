from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Frequency, RiskLevel
from app.repositories.contribution_repository import ContributionRepository
from app.repositories.schedule_repository import ScheduleRepository
from app.services.schedule_service import (
    compute_period_end_date,
    format_period_label,
)


class ContributionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.contrib_repo = ContributionRepository(db)
        self.schedule_repo = ScheduleRepository(db)

    async def get_member_balance(self, member_id: UUID, coop_id: UUID) -> dict:
        data = await self.contrib_repo.get_member_balance(member_id, coop_id)
        schedule = await self.schedule_repo.get_active(coop_id)
        freq = Frequency(schedule.frequency) if schedule else None

        recent_activity = []
        for row in data["recent_rows"]:
            if schedule and freq:
                end_date = compute_period_end_date(
                    schedule.anchor_date, freq, row.period_number
                )
                label = format_period_label(row.period_number, row.start_date, end_date)
            else:
                label = f"Period {row.period_number}"

            recent_activity.append({
                "period_label": label,
                "amount": row.amount,
                "status": row.status,
                "paid_at": row.paid_at,
            })

        return {
            "total_contributed_kobo": data["total_contributed_kobo"],
            "periods_paid": data["periods_paid"],
            "periods_total": data["periods_total"],
            "recent_activity": recent_activity,
        }

    async def get_member_history(
        self, member_id: UUID, coop_id: UUID, page: int, page_size: int
    ) -> dict:
        data = await self.contrib_repo.get_member_history(
            member_id, coop_id, page, page_size
        )
        schedule = await self.schedule_repo.get_active(coop_id)
        freq = Frequency(schedule.frequency) if schedule else None

        # Batch-fetch paid transaction references in one query
        paid_period_ids = [
            row.period_id for row in data["rows"] if row.status == "paid"
        ]
        tx_refs = await self.contrib_repo.get_paid_transaction_references(paid_period_ids)

        items = []
        for row in data["rows"]:
            if schedule and freq:
                end_date = compute_period_end_date(
                    schedule.anchor_date, freq, row.period_number
                )
                label = format_period_label(row.period_number, row.start_date, end_date)
            else:
                label = f"Period {row.period_number}"

            items.append({
                "period_label": label,
                "amount": row.amount,
                "status": row.status,
                "paid_at": row.paid_at,
                "transaction_reference": tx_refs.get(row.period_id),
            })

        return {
            "items": items,
            "total": data["total"],
            "page": page,
            "page_size": page_size,
        }

    async def calculate_risk_score(
        self, member_id: UUID, coop_id: UUID
    ) -> RiskLevel:
        return await self.contrib_repo.calculate_risk_score(member_id, coop_id)