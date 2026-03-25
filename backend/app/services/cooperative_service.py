from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Frequency, Role
from app.core.exceptions import NotFoundException
from app.repositories.cooperative_repository import CooperativeRepository
from app.repositories.schedule_repository import ScheduleRepository
from app.services.schedule_service import ScheduleService
import logging; logger = logging.getLogger("akoweai")


class CooperativeService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.coop_repo = CooperativeRepository(db)
        self.schedule_repo = ScheduleRepository(db)
        self.schedule_service = ScheduleService(db)

    async def create_cooperative(
        self,
        member_id: UUID,
        name: str,
        contribution_amount_kobo: int,
        frequency: Frequency,
        anchor_date: date,
        due_day_offset: int,
    ) -> dict:
        # Avoid circular import at module load
        from app.services.join_code_service import JoinCodeService

        coop = await self.coop_repo.create(
            name=name,
            contribution_amount=contribution_amount_kobo,
            due_day_offset=due_day_offset,
            created_by_member_id=member_id,
        )

        await self.schedule_repo.create(
            coop_id=coop.id,
            frequency=frequency.value,
            anchor_date=anchor_date,
            due_day_offset=due_day_offset,
            version=1,
        )

        await self.coop_repo.create_coop_member(
            coop_id=coop.id,
            member_id=member_id,
            role=Role.EXCO.value,
        )

        # Auto-generate one member join code (30-day expiry)
        join_code = await JoinCodeService(self.db).generate_join_code(
            coop_id=coop.id,
            role=Role.MEMBER,
            expires_in_days=30,
        )

        await self.db.commit()

        return {
            "cooperative_id": coop.id,
            "join_code": join_code.code,
            "exco_invite_code": None,
        }

    async def get_cooperative(self, coop_id: UUID) -> dict:
        coop = await self.coop_repo.get_by_id(coop_id)
        if not coop:
            raise NotFoundException("Cooperative not found")

        schedule = await self.schedule_service.get_active_schedule(coop_id)
        member_count = await self.coop_repo.get_member_count(coop_id)
        overview = await self.coop_repo.get_overview_stats(coop_id)

        return {
            "id": coop.id,
            "name": coop.name,
            "contribution_amount_kobo": coop.contribution_amount,
            "pool_balance": coop.pool_balance,
            "member_count": member_count,
            "collection_rate_pct": overview["collection_rate_pct"],
            "ytd_collected_kobo": overview["ytd_collected_kobo"],
            "current_schedule": {
                "version": schedule.version,
                "frequency": schedule.frequency,
                "anchor_date": schedule.anchor_date,
                "due_day_offset": schedule.due_day_offset,
            },
        }

    async def get_member_cooperatives(self, member_id: UUID) -> list[dict]:
        rows = await self.coop_repo.get_member_cooperatives(member_id)
        return [
            {
                "id": coop.id,
                "name": coop.name,
                "contribution_amount_kobo": coop.contribution_amount,
                "role": cm.role,
                "pool_balance": coop.pool_balance,
            }
            for coop, cm in rows
        ]

    async def update_settings(
        self,
        coop_id: UUID,
        contribution_amount_kobo: int | None,
        frequency: Frequency | None,
        due_day_offset: int | None,
    ) -> dict:
        coop = await self.coop_repo.get_by_id(coop_id)
        if not coop:
            raise NotFoundException("Cooperative not found")

        # A new schedule version is only warranted when the schedule itself changes
        if frequency is not None or due_day_offset is not None:
            current_schedule = await self.schedule_service.get_active_schedule(coop_id)

            effective_frequency = frequency or Frequency(current_schedule.frequency)
            effective_offset = (
                due_day_offset
                if due_day_offset is not None
                else current_schedule.due_day_offset
            )

            await self.schedule_service.create_schedule_version(
                coop_id=coop_id,
                frequency=effective_frequency,
                due_day_offset=effective_offset,
            )

        await self.coop_repo.update_settings(
            coop_id=coop_id,
            contribution_amount=contribution_amount_kobo,
            due_day_offset=due_day_offset,
        )

        await self.db.commit()

        return await self.get_cooperative(coop_id)

    async def broadcast_to_members(self, coop_id: UUID, message: str) -> int:
        from app.services.whatsapp_service import TEMPLATE_BROADCAST, send_template_message

        coop = await self.coop_repo.get_by_id(coop_id)
        if not coop:
            raise NotFoundException("Cooperative not found")

        member_phones = await self.coop_repo.get_active_member_phones(coop_id)
        sent_count = 0

        for phone, _ in member_phones:
            try:
                await send_template_message(
                    to=phone,
                    template_name=TEMPLATE_BROADCAST,
                    components=[
                        {
                            "type": "body",
                            "parameters": [
                                {"type": "text", "text": coop.name},
                                {"type": "text", "text": message},
                            ],
                        }
                    ],
                )
                sent_count += 1
            except Exception as exc:
                logger.warning("Broadcast send failed to %s: %s", phone, exc)

        return sent_count