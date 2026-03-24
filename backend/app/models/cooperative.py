import uuid

from sqlalchemy import BigInteger, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Cooperative(Base, TimestampMixin):
    __tablename__ = "cooperatives"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    contribution_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    due_day_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    # use_alter=True breaks the circular FK dependency with members at DDL time
    created_by_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("members.id", use_alter=True, name="fk_cooperatives_created_by"),
        nullable=True,
    )
    pool_balance: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)