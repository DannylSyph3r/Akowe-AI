import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import (
    get_coop_membership,
    get_current_member,
    require_coop_exco,
    require_step_up,
)
from app.core.enums import RiskLevel, StepUpAction
from app.core.responses import ApiResponse
from app.models.member import Member
from app.repositories.cooperative_repository import CooperativeRepository
from app.prompts.financial_summary import COOP_STATUS_INSIGHT_PROMPT
from app.schemas.cooperative import (
    CooperativeDetailResponse,
    CooperativeListItem,
    CreateCooperativeRequest,
    CreateCooperativeResponse,
    ExcoInviteRequest,
    ExcoInviteResponse,
    GenerateJoinCodesRequest,
    InsightResponse,
    JoinCodeItem,
    JoinCodesResponse,
    MemberListItem,
    PaginatedWithdrawals,
    PayablePeriodItem,
    PayablePeriodsResponse,
    RecordWithdrawalRequest,
    RecordWithdrawalResponse,
    UpdateSettingsRequest,
    WithdrawalListItem,
)
from app.services.cooperative_service import CooperativeService
from app.services.gemini_service import GeminiProClient
from app.services.join_code_service import JoinCodeService
from app.services.period_service import PeriodService
from app.services.withdrawal_service import WithdrawalService

logger = logging.getLogger("akoweai")

router = APIRouter(prefix="/cooperatives", tags=["cooperatives"])


@router.post("", status_code=201)
async def create_cooperative(
    body: CreateCooperativeRequest,
    current_member: Member = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    result = await CooperativeService(db).create_cooperative(
        member_id=current_member.id,
        name=body.name,
        contribution_amount_kobo=body.contribution_amount_kobo,
        frequency=body.frequency,
        anchor_date=body.anchor_date,
        due_day_offset=body.due_day_offset,
    )
    return ApiResponse.success(
        data=CreateCooperativeResponse(**result),
        message="Cooperative created",
        status_code=201,
    )


@router.get("")
async def list_cooperatives(
    current_member: Member = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    items = await CooperativeService(db).get_member_cooperatives(current_member.id)
    return ApiResponse.success(
        data=[CooperativeListItem(**item) for item in items],
        message="OK",
    )


@router.get("/{coop_id}")
async def get_cooperative(
    coop_id: UUID,
    _membership=Depends(get_coop_membership),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    result = await CooperativeService(db).get_cooperative(coop_id)
    return ApiResponse.success(data=CooperativeDetailResponse(**result), message="OK")


@router.patch("/{coop_id}/settings")
async def update_settings(
    coop_id: UUID,
    body: UpdateSettingsRequest,
    _exco=Depends(require_coop_exco),
    _step_up=Depends(require_step_up(StepUpAction.SETTINGS)),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    result = await CooperativeService(db).update_settings(
        coop_id=coop_id,
        contribution_amount_kobo=body.contribution_amount_kobo,
        frequency=body.frequency,
        due_day_offset=body.due_day_offset,
    )
    return ApiResponse.success(
        data=CooperativeDetailResponse(**result), message="Settings updated"
    )


@router.get("/{coop_id}/members")
async def get_members(
    coop_id: UUID,
    _exco=Depends(require_coop_exco),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    rows = await CooperativeRepository(db).get_members_with_stats(coop_id)

    members = []
    for row in rows:
        late_count: int = row["late_count"]
        risk_level = (
            RiskLevel.HIGH if late_count >= 2
            else RiskLevel.MEDIUM if late_count == 1
            else RiskLevel.LOW
        )
        members.append(
            MemberListItem(
                member_id=row["member_id"],
                full_name=row["full_name"],
                role=row["role"],
                joined_at=row["joined_at"],
                risk_level=risk_level,
                total_contributed=row["total_contributed"],
                last_paid_at=row["last_paid_at"],
            )
        )

    return ApiResponse.success(data=members, message="OK")


@router.post("/{coop_id}/join-codes", status_code=201)
async def generate_join_codes(
    coop_id: UUID,
    body: GenerateJoinCodesRequest,
    _exco=Depends(require_coop_exco),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    codes = await JoinCodeService(db).generate_bulk(
        coop_id, body.count, body.expires_in_days
    )
    return ApiResponse.success(
        data=JoinCodesResponse(
            codes=[JoinCodeItem(code=jc.code, expires_at=jc.expires_at) for jc in codes]
        ),
        message="Join codes generated",
        status_code=201,
    )


@router.post("/{coop_id}/exco-invites", status_code=201)
async def generate_exco_invite(
    coop_id: UUID,
    body: ExcoInviteRequest,
    _exco=Depends(require_coop_exco),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    invite = await JoinCodeService(db).generate_exco_invite(
        coop_id, body.expires_in_days
    )
    return ApiResponse.success(
        data=ExcoInviteResponse(code=invite.code, expires_at=invite.expires_at),
        message="Exco invite generated",
        status_code=201,
    )


@router.get("/{coop_id}/periods/payable")
async def get_payable_periods(
    coop_id: UUID,
    current_member: Member = Depends(get_current_member),
    _membership=Depends(get_coop_membership),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    periods = await PeriodService(db).get_payable_periods(coop_id, current_member.id)
    return ApiResponse.success(
        data=PayablePeriodsResponse(
            periods=[PayablePeriodItem(**p) for p in periods]
        ),
        message="OK",
    )


@router.post("/{coop_id}/withdrawals", status_code=201)
async def record_withdrawal(
    coop_id: UUID,
    body: RecordWithdrawalRequest,
    current_member: Member = Depends(get_current_member),
    _exco=Depends(require_coop_exco),
    _step_up=Depends(require_step_up(StepUpAction.WITHDRAWAL)),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    result = await WithdrawalService(db).record_withdrawal(
        coop_id=coop_id,
        amount_kobo=body.amount_kobo,
        reason=body.reason,
        authorized_by_member_id=current_member.id,
    )
    return ApiResponse.success(
        data=RecordWithdrawalResponse(**result),
        message="Withdrawal recorded",
        status_code=201,
    )


@router.get("/{coop_id}/withdrawals")
async def list_withdrawals(
    coop_id: UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _membership=Depends(get_coop_membership),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    items = await WithdrawalService(db).get_withdrawals(coop_id, page, page_size)
    return ApiResponse.success(
        data=PaginatedWithdrawals(
            items=[WithdrawalListItem(**item) for item in items],
            page=page,
            page_size=page_size,
        ),
        message="OK",
    )


@router.get("/{coop_id}/insights")
async def get_insights(
    coop_id: UUID,
    _exco=Depends(require_coop_exco),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    rows = await CooperativeRepository(db).get_members_with_stats(coop_id)

    at_risk = [
        row for row in rows if row["late_count"] >= 1
    ]

    if not at_risk:
        return ApiResponse.success(
            data=InsightResponse(insight="All members are up to date with contributions."),
            message="OK",
        )

    coop_result = await CooperativeRepository(db).get_by_id(coop_id)
    coop_name = coop_result.name if coop_result else "this cooperative"
    member_count = len(rows)
    high_risk_names = [
        row["full_name"] for row in at_risk if row["late_count"] >= 2
    ][:5]
    medium_risk_names = [
        row["full_name"] for row in at_risk if row["late_count"] == 1
    ][:5]

    context = (
        f"Cooperative: {coop_name}\n"
        f"Total members: {member_count}\n"
        f"Members at risk: {len(at_risk)}\n"
        f"High risk (2+ late payments): {len(high_risk_names)} — "
        f"{', '.join(high_risk_names) if high_risk_names else 'none'}\n"
        f"Medium risk (1 late payment): {len(medium_risk_names)} — "
        f"{', '.join(medium_risk_names) if medium_risk_names else 'none'}"
    )

    try:
        insight = await GeminiProClient().generate_summary(
            context, COOP_STATUS_INSIGHT_PROMPT
        )
    except Exception as exc:
        logger.warning("Gemini insight generation failed: %s", exc)
        insight = (
            f"{len(at_risk)} member(s) have late or missed contributions "
            f"and may need follow-up."
        )

    return ApiResponse.success(
        data=InsightResponse(insight=insight),
        message="OK",
    )