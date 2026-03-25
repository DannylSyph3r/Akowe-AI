"""
Internal cron endpoints — Phase 8.

These endpoints are called by Railway cron jobs on a fixed schedule.
They are NOT mounted under /api and are NOT protected by JWT auth.
Security is a single shared secret checked via the Authorization header.
"""

import logging

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import UnauthorizedException
from app.services.period_service import PeriodService
from app.services.reminder_service import ReminderService

settings = get_settings()
logger = logging.getLogger("akoweai")

router = APIRouter(prefix="/internal", tags=["internal"])


def _verify_cron_secret(authorization: str = Header(...)) -> None:
    """
    Validates Authorization: Bearer {INTERNAL_CRON_SECRET}.
    Raises 401 if the token is missing or incorrect.
    """
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or token != settings.internal_cron_secret:
        raise UnauthorizedException("Invalid or missing cron secret")


@router.post("/process-reminders")
async def process_reminders(
    _auth=Depends(_verify_cron_secret),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Hourly cron — dispatch all pending reminders whose scheduled_at has passed.
    Schedule: 0 * * * * (top of every hour)
    """
    processed = await ReminderService(db).process_due_reminders()
    logger.info("process-reminders cron: dispatched %d reminders", processed)
    return {"processed": processed}


@router.post("/close-periods")
async def close_periods(
    _auth=Depends(_verify_cron_secret),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Hourly cron — close overdue periods and create the next period with reminders.
    Schedule: 5 * * * * (5 minutes past every hour)
    """
    result = await PeriodService(db).close_overdue_periods()
    logger.info(
        "close-periods cron: closed=%d created=%d",
        result["closed"],
        result["created"],
    )
    return result