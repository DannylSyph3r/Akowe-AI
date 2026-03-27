from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.join_code import JoinCode


class JoinCodeRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        coop_id: UUID,
        code: str,
        role: str,
        expires_at: datetime,
    ) -> JoinCode:
        join_code = JoinCode(
            cooperative_id=coop_id,
            code=code,
            role=role,
            expires_at=expires_at,
        )
        self.db.add(join_code)
        await self.db.flush()
        return join_code

    async def get_by_code(self, code: str) -> JoinCode | None:
        result = await self.db.execute(
            select(JoinCode).where(JoinCode.code == code)
        )
        return result.scalar_one_or_none()

    async def redeem(self, join_code_id: UUID, member_id: UUID) -> JoinCode:
        now = datetime.now(timezone.utc)
        await self.db.execute(
            update(JoinCode)
            .where(JoinCode.id == join_code_id)
            .values(redeemed_at=now, redeemed_by_member_id=member_id)
        )
        result = await self.db.execute(
            select(JoinCode).where(JoinCode.id == join_code_id)
        )
        return result.scalar_one()

    async def list_active_by_coop(self, coop_id: UUID) -> list[JoinCode]:

        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(JoinCode)
            .where(
                JoinCode.cooperative_id == coop_id,
                JoinCode.redeemed_at.is_(None),
                JoinCode.expires_at > now,
            )
            .order_by(JoinCode.created_at.desc())
        )
        return list(result.scalars().all())

    async def revoke_by_code(self, coop_id: UUID, code: str) -> int:

        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            update(JoinCode)
            .where(
                JoinCode.code == code,
                JoinCode.cooperative_id == coop_id,
                JoinCode.redeemed_at.is_(None),
            )
            .values(expires_at=now)
        )
        return result.rowcount