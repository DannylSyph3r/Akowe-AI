"""
Reminder service stub.

cancel_reminders_for_periods is intentionally a no-op until Phase 8.
Phase 8 will implement full reminder scheduling and cancellation logic.

Deviation D10: This stub exists so Phase 5 (payment processing) can call
cancel_reminders_for_periods without coupling to unbuilt Phase 8 code.
"""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("akoweai")


async def cancel_reminders_for_periods(
    period_ids: list[UUID],
    member_id: UUID,
    db: AsyncSession,
) -> None:
    """
    Cancel all pending reminders for the given member + periods.
    STUB — Phase 8 implements this fully.
    """
    # TODO (Phase 8): UPDATE reminder_log SET status='cancelled'
    # WHERE member_id = :member_id AND period_id = ANY(:period_ids)
    # AND status = 'pending'
    logger.debug(
        "cancel_reminders_for_periods called (stub) — member=%s periods=%s",
        member_id,
        period_ids,
    )