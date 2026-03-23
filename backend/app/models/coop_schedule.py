import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class CoopSchedule(Base, TimestampMixin):
    __tablename__ = "coop_schedules"
    __table_args__ = (
        CheckConstraint(
            "frequency IN ('weekly','biweekly','triweekly','monthly','bimonthly','quarterly','yearly')",
            name="ck_coop_schedules_frequency",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cooperative_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cooperatives.id"), nullable=False
    )
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    anchor_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_day_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    superseded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )