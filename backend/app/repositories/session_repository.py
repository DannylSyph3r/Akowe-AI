from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation_session import ConversationSession


class SessionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_phone(self, phone: str) -> ConversationSession | None:
        result = await self.db.execute(
            select(ConversationSession).where(
                ConversationSession.phone_number == phone
            )
        )
        return result.scalar_one_or_none()

    async def create(self, phone: str) -> ConversationSession:
        session = ConversationSession(
            phone_number=phone,
            current_flow=None,
            current_step=0,
            flow_data={},
        )
        self.db.add(session)
        await self.db.flush()
        return session

    async def save(self, session: ConversationSession) -> None:
        """Update session state and refresh last_active timestamp."""
        now = datetime.now(timezone.utc)
        await self.db.execute(
            update(ConversationSession)
            .where(ConversationSession.phone_number == session.phone_number)
            .values(
                active_cooperative_id=session.active_cooperative_id,
                current_flow=session.current_flow,
                current_step=session.current_step,
                flow_data=session.flow_data,
                last_active=now,
            )
        )