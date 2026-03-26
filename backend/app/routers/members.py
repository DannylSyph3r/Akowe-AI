from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_coop_membership, get_current_member
from app.core.responses import ApiResponse
from app.models.member import Member
from app.schemas.member import (
    BalanceResponse,
    JoinCoopRequest,
    JoinCoopResponse,
    PaginatedHistory,
)
from app.services.contribution_service import ContributionService
from app.services.join_code_service import JoinCodeService

router = APIRouter(prefix="/members", tags=["members"])

_DEFAULT_PAGE_SIZE = 20


@router.post("/join", status_code=201)
async def join_cooperative(
    body: JoinCoopRequest,
    current_member: Member = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    result = await JoinCodeService(db).join_cooperative(body.code, current_member.id)
    return ApiResponse.success(
        data=JoinCoopResponse(**result),
        message="Joined cooperative successfully",
        status_code=201,
    )


@router.get("/me/balance")
async def get_balance(
    coop_id: UUID = Query(...),
    current_member: Member = Depends(get_current_member),
    _membership=Depends(get_coop_membership),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    result = await ContributionService(db).get_member_balance(current_member.id, coop_id)
    return ApiResponse.success(data=BalanceResponse(**result), message="OK")


@router.get("/me/history")
async def get_history(
    coop_id: UUID = Query(...),
    page: int = Query(default=1, ge=1),
    current_member: Member = Depends(get_current_member),
    _membership=Depends(get_coop_membership),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    result = await ContributionService(db).get_member_history(
        current_member.id, coop_id, page - 1, _DEFAULT_PAGE_SIZE
    )
    return ApiResponse.success(data=PaginatedHistory(**result), message="OK")