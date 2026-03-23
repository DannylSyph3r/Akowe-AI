from uuid import UUID

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.enums import Role, StepUpAction
from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.security import decode_token, oauth2_scheme
from app.models.member import Member


async def get_current_member(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Member:
    payload = decode_token(token)

    if payload.get("type") != "access":
        raise UnauthorizedException("Invalid token type")

    member_id: str | None = payload.get("sub")
    if not member_id:
        raise UnauthorizedException("Invalid token payload")

    # Late import to avoid circular dependency at module load time
    from app.repositories.member_repository import MemberRepository

    member = await MemberRepository(db).get_by_id(UUID(member_id))
    if not member:
        raise UnauthorizedException("Member not found")

    return member


async def get_coop_membership(
    coop_id: UUID,
    current_member: Member = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.cooperative_repository import CooperativeRepository

    membership = await CooperativeRepository(db).get_member_role(
        coop_id, current_member.id
    )
    if not membership:
        raise ForbiddenException("You are not a member of this cooperative")
    return membership


async def require_coop_exco(
    membership=Depends(get_coop_membership),
):
    if membership.role != Role.EXCO.value:
        raise ForbiddenException("Exco access required")
    return membership


def require_step_up(action: StepUpAction):

    async def _dependency(x_step_up_token: str = Header(...)):
        payload = decode_token(x_step_up_token)
        if payload.get("type") != "step_up":
            raise ForbiddenException("Invalid step-up token")
        if payload.get("action") != action.value:
            raise ForbiddenException("Step-up action mismatch")
        return payload

    return _dependency