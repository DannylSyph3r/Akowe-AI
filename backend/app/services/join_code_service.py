import secrets
import string
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Role
from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.models.contribution import Contribution
from app.models.join_code import JoinCode
from app.repositories.cooperative_repository import CooperativeRepository
from app.repositories.join_code_repository import JoinCodeRepository
from app.repositories.period_repository import PeriodRepository
from app.repositories.schedule_repository import ScheduleRepository
from app.services.schedule_service import compute_next_period_dates

_CODE_ALPHABET = string.ascii_uppercase + string.digits


def _generate_code() -> str:
    """8-character alphanumeric code from a safe alphabet (A-Z, 0-9)."""
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(8))


class JoinCodeService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = JoinCodeRepository(db)
        self.coop_repo = CooperativeRepository(db)
        self.period_repo = PeriodRepository(db)
        self.schedule_repo = ScheduleRepository(db)

    # Internal helpers
    def _validate_code(self, join_code: JoinCode | None) -> None:
        """
        Assert a join code is present, unredeemed, and unexpired.
        Raises BadRequestException with a specific message for each failure.
        Does not redeem — purely validates state.
        """
        if not join_code:
            raise BadRequestException("Invalid join code")
        if join_code.redeemed_at is not None:
            raise BadRequestException("This join code has already been used")
        if join_code.expires_at < datetime.now(timezone.utc):
            raise BadRequestException("This join code has expired")

    async def generate_join_code(
        self, coop_id: UUID, role: Role, expires_in_days: int
    ) -> JoinCode:
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)
        return await self.repo.create(
            coop_id=coop_id,
            code=_generate_code(),
            role=role.value,
            expires_at=expires_at,
        )

    async def generate_bulk(
        self, coop_id: UUID, count: int, expires_in_days: int
    ) -> list[JoinCode]:
        codes = [
            await self.generate_join_code(coop_id, Role.MEMBER, expires_in_days)
            for _ in range(count)
        ]
        await self.db.commit()
        return codes

    async def generate_exco_invite(
        self, coop_id: UUID, expires_in_days: int
    ) -> JoinCode:
        invite = await self.generate_join_code(coop_id, Role.EXCO, expires_in_days)
        await self.db.commit()
        return invite

    async def list_active(self, coop_id: UUID) -> list[JoinCode]:
        """Return all active (unredeemed, unexpired) codes for the cooperative."""
        return await self.repo.list_active_by_coop(coop_id)

    async def revoke(self, coop_id: UUID, code: str) -> None:
        """
        Revoke a join code by immediately expiring it.
        Raises NotFoundException if the code doesn't exist, is already redeemed,
        or has already expired.
        """
        rows_affected = await self.repo.revoke_by_code(coop_id, code)
        if rows_affected == 0:
            raise NotFoundException("Join code not found or already used/expired")
        await self.db.commit()

    async def validate_and_redeem(
        self, code: str, member_id: UUID
    ) -> JoinCode:
        """
        Validate and atomically redeem a join code.
        Used by Phase 6 WhatsApp flows for non-membership code operations.
        Does NOT create a CoopMember record — caller is responsible for that.
        """
        join_code = await self.repo.get_by_code(code)
        self._validate_code(join_code)
        return await self.repo.redeem(join_code.id, member_id)

    async def join_cooperative(self, code: str, member_id: UUID) -> dict:
        # 1. Fetch and validate — do not consume yet
        join_code = await self.repo.get_by_code(code)
        self._validate_code(join_code)

        coop_id = join_code.cooperative_id

        # 2. Membership check before redemption — don't consume the code
        #    if the member already belongs to this cooperative
        existing = await self.coop_repo.get_member_role(coop_id, member_id)
        if existing:
            raise ConflictException("You are already a member of this cooperative")

        # 3. Atomically redeem
        await self.repo.redeem(join_code.id, member_id)

        # 4. Create the membership record
        await self.coop_repo.create_coop_member(
            coop_id=coop_id,
            member_id=member_id,
            role=join_code.role,
        )

        coop = await self.coop_repo.get_by_id(coop_id)
        if not coop:
            raise NotFoundException("Cooperative not found")
            
        from app.services.period_service import PeriodService
        open_period = await PeriodService(self.db).get_or_create_current_period(coop_id)
        self.db.add(
            Contribution(
                member_id=member_id,
                cooperative_id=coop_id,
                period_id=open_period.id,
                amount=coop.contribution_amount,
                status="unpaid",
            )
        )

        next_due_date = open_period.due_date

        await self.db.commit()

        return {
            "cooperative_id": coop_id,
            "cooperative_name": coop.name,
            "role": join_code.role,
            "contribution_amount_kobo": coop.contribution_amount,
            "next_due_date": next_due_date,
        }