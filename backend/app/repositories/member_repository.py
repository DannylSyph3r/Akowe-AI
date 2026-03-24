from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.member import Member


class MemberRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, member_id: UUID) -> Member | None:
        result = await self.db.execute(
            select(Member).where(Member.id == member_id)
        )
        return result.scalar_one_or_none()

    async def get_by_phone(self, phone_number: str) -> Member | None:
        result = await self.db.execute(
            select(Member).where(Member.phone_number == phone_number)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        phone_number: str,
        full_name: str,
        pin_hash: str | None = None,
    ) -> Member:
        member = Member(
            phone_number=phone_number,
            full_name=full_name,
            pin_hash=pin_hash,
        )
        self.db.add(member)
        await self.db.flush()
        return member

    async def update_refresh_token_hash(
        self, member_id: UUID, token_hash: str | None
    ) -> None:
        await self.db.execute(
            update(Member)
            .where(Member.id == member_id)
            .values(refresh_token_hash=token_hash)
        )