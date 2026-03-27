from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.core.enums import Frequency, RiskLevel, Role


class CreateCooperativeRequest(BaseModel):
    name: str
    contribution_amount_kobo: int
    frequency: Frequency
    anchor_date: date
    due_day_offset: int

    @field_validator("contribution_amount_kobo")
    @classmethod
    def amount_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Contribution amount must be positive")
        return v

    @field_validator("due_day_offset")
    @classmethod
    def offset_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Due day offset must be non-negative")
        return v


class UpdateSettingsRequest(BaseModel):
    contribution_amount_kobo: int | None = None
    frequency: Frequency | None = None
    due_day_offset: int | None = None


class GenerateJoinCodesRequest(BaseModel):
    count: int
    expires_in_days: int

    @field_validator("count")
    @classmethod
    def count_in_range(cls, v: int) -> int:
        if not (1 <= v <= 50):
            raise ValueError("Count must be between 1 and 50")
        return v

    @field_validator("expires_in_days")
    @classmethod
    def days_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("expires_in_days must be positive")
        return v


class ExcoInviteRequest(BaseModel):
    expires_in_days: int

    @field_validator("expires_in_days")
    @classmethod
    def days_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("expires_in_days must be positive")
        return v


# --- Responses

class ScheduleInfo(BaseModel):
    version: int
    frequency: Frequency
    anchor_date: date
    due_day_offset: int


class CreateCooperativeResponse(BaseModel):
    cooperative_id: UUID
    join_code: str
    exco_invite_code: None = None


class CooperativeDetailResponse(BaseModel):
    id: UUID
    name: str
    contribution_amount_kobo: int
    pool_balance: int
    member_count: int
    current_schedule: ScheduleInfo


class CooperativeListItem(BaseModel):
    id: UUID
    name: str
    contribution_amount_kobo: int
    role: Role
    pool_balance: int


class MemberListItem(BaseModel):
    member_id: UUID
    full_name: str
    role: Role
    joined_at: datetime
    risk_level: RiskLevel
    total_contributed: int
    last_paid_at: datetime | None


class JoinCodeItem(BaseModel):
    code: str
    expires_at: datetime


class JoinCodesResponse(BaseModel):
    codes: list[JoinCodeItem]


class ExcoInviteResponse(BaseModel):
    code: str
    expires_at: datetime


class PayablePeriodItem(BaseModel):
    id: UUID | None
    period_number: int
    start_date: date
    due_date: date
    amount: int
    label: str
    is_debt: bool
    is_future: bool


class PayablePeriodsResponse(BaseModel):
    periods: list[PayablePeriodItem]


class RecordWithdrawalRequest(BaseModel):
    amount_kobo: int = Field(..., gt=0, description="Withdrawal amount in kobo")
    reason: str = Field(..., min_length=3, max_length=500)


class RecordWithdrawalResponse(BaseModel):
    withdrawal_id: UUID
    pool_balance_after: int


class WithdrawalListItem(BaseModel):
    id: UUID
    amount: int
    reason: str
    authorized_by_name: str
    pool_balance_after: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedWithdrawals(BaseModel):
    items: list[WithdrawalListItem]
    page: int
    page_size: int


class InsightResponse(BaseModel):
    insight: str