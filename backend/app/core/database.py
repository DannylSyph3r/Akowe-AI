from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.async_database_url,
    pool_size=10,
    max_overflow=5,
    echo=False,
)

AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# Read-only synchronous engine — used exclusively by the ADK chatbot tool.
# Synchronous because ADK tool functions must be regular (non-async) callables.
# Pool size kept small; statement_timeout prevents runaway agent-generated queries.
# Deviation D26: readonly_engine is a module-level export initialised at startup.
# ---------------------------------------------------------------------------

from sqlalchemy import create_engine as _create_sync_engine

def _build_readonly_engine():
    from app.core.config import get_settings as _get_settings
    _settings = _get_settings()
    if not _settings.readonly_database_url:
        return None
    return _create_sync_engine(
        _settings.sync_readonly_database_url,
        pool_size=3,
        max_overflow=0,
        connect_args={"options": "-c statement_timeout=3000"},
    )


try:
    readonly_engine = _build_readonly_engine()
except Exception as _e:
    import logging as _logging
    _logging.getLogger("akoweai").warning(
        "readonly_engine could not be initialised: %s", _e
    )
    readonly_engine = None