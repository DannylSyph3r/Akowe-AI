import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation_session import ConversationSession
from app.repositories.session_repository import SessionRepository

logger = logging.getLogger("akoweai")

_SESSION_EXPIRY_MINUTES = 30


async def load_or_create_session(
    phone: str, db: AsyncSession
) -> tuple[ConversationSession, bool]:
    """
    Load the existing session or create a new one.

    Returns:
        (session, was_expired) — was_expired is True if the session had an active
        flow that was reset due to 30-minute inactivity. The caller should notify
        the user before processing their current message.
    """
    repo = SessionRepository(db)
    session = await repo.get_by_phone(phone)

    if session is None:
        session = await repo.create(phone)
        return session, False

    was_expired = False
    if session.current_flow is not None:
        expiry_threshold = datetime.now(timezone.utc) - timedelta(
            minutes=_SESSION_EXPIRY_MINUTES
        )
        if session.last_active < expiry_threshold:
            logger.debug(
                "Session expired for phone=%s, flow=%s, resetting",
                phone,
                session.current_flow,
            )
            was_expired = True
            session.current_flow = None
            session.current_step = 0
            session.flow_data = {}

    return session, was_expired


async def save_session(session: ConversationSession, db: AsyncSession) -> None:
    """Persist the current session state to the database."""
    repo = SessionRepository(db)
    await repo.save(session)