import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ReminderLog(Base):
    __tablename__ = "reminder_log"
    __table_args__ = (
        UniqueConstraint("member_id", "period_id", "stage"),
        Index("idx_reminder_log_scheduled", "scheduled_at", "status"),
        CheckConstraint(
            "stage IN ('7_day','3_day','1_day','due_date','1_week_overdue','2_weeks_overdue')",
            name="ck_reminder_log_stage",
        ),
        CheckConstraint(
            "status IN ('pending','sent','cancelled')",
            name="ck_reminder_log_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id"), nullable=False
    )
    period_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contribution_periods.id"), nullable=False
    )
    stage: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )