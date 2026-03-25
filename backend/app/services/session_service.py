import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation_session import ConversationSession
from app.repositories.session_repository import SessionRepository

logger = logging.getLogger("akoweai")

_SESSION_EXPIRY_MINUTES = 30


async def load_or_create_session(
    phone: str, db: AsyncSession
) -> ConversationSession:
    """
    Load the existing session for this phone number, or create a new one.
    If the session has an active flow but has been idle for >30 minutes,
    the flow state is reset (session expired).
    """
    repo = SessionRepository(db)
    session = await repo.get_by_phone(phone)

    if session is None:
        session = await repo.create(phone)
        return session

    # Check for session expiry
    if session.current_flow is not None:
        expiry_threshold = datetime.now(timezone.utc) - timedelta(
            minutes=_SESSION_EXPIRY_MINUTES
        )
        if session.last_active < expiry_threshold:
            logger.debug("Session expired for phone=%s, resetting flow state", phone)
            session.current_flow = None
            session.current_step = 0
            session.flow_data = {}
            # The caller (webhook handler) is responsible for saving the session

    return session


async def save_session(session: ConversationSession, db: AsyncSession) -> None:
    """Persist the current session state to the database."""
    repo = SessionRepository(db)
    await repo.save(session)