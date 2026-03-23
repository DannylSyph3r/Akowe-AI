from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel

from app.core.enums import ContributionStatus


class JoinCoopRequest(BaseModel):
    code: str


class JoinCoopResponse(BaseModel):
    cooperative_id: UUID
    cooperative_name: str
    role: str
    contribution_amount_kobo: int
    next_due_date: date | None


class ActivityItem(BaseModel):
    period_label: str
    amount: int
    status: ContributionStatus
    paid_at: datetime | None


class BalanceResponse(BaseModel):
    total_contributed_kobo: int
    periods_paid: int
    periods_total: int
    recent_activity: list[ActivityItem]


class HistoryItem(BaseModel):
    period_label: str
    amount: int
    status: ContributionStatus
    paid_at: datetime | None
    transaction_reference: str | None


class PaginatedHistory(BaseModel):
    items: list[HistoryItem]
    total: int
    page: int
    page_size: int