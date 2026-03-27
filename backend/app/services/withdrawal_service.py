import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.models.cooperative import Cooperative
from app.models.coop_member import CoopMember
from app.models.member import Member
from app.models.withdrawal import Withdrawal
from app.services.whatsapp_service import (
    TEMPLATE_WITHDRAWAL_ALERT,
    send_template_message,
)

logger = logging.getLogger("akoweai")


class WithdrawalService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_withdrawal(
        self,
        coop_id: UUID,
        amount_kobo: int,
        reason: str,
        authorized_by_member_id: UUID,
    ) -> dict:
        """
        Validate, record, and broadcast a cooperative withdrawal.
        Uses a conditional UPDATE as an atomic balance guard to prevent
        the pool going negative even under concurrent requests.
        """
        # Load cooperative for validation and broadcast context
        coop_result = await self.db.execute(
            select(Cooperative).where(Cooperative.id == coop_id)
        )
        coop = coop_result.scalar_one_or_none()
        if not coop:
            raise NotFoundException("Cooperative not found")

        if amount_kobo <= 0:
            raise BadRequestException("Withdrawal amount must be greater than zero")

        if amount_kobo > coop.pool_balance:
            raise BadRequestException(
                f"Insufficient pool balance. "
                f"Available: ₦{coop.pool_balance // 100:,}, "
                f"Requested: ₦{amount_kobo // 100:,}"
            )

        # Atomic decrement with balance guard — prevents going negative
        # under concurrent withdrawals
        update_result = await self.db.execute(
            update(Cooperative)
            .where(
                Cooperative.id == coop_id,
                Cooperative.pool_balance >= amount_kobo,
            )
            .values(pool_balance=Cooperative.pool_balance - amount_kobo)
            .returning(Cooperative.pool_balance)
        )
        new_balance = update_result.scalar_one_or_none()
        if new_balance is None:
            raise BadRequestException(
                "Withdrawal could not be processed — balance may have changed. "
                "Please try again."
            )

        withdrawal = Withdrawal(
            cooperative_id=coop_id,
            amount=amount_kobo,
            reason=reason,
            authorized_by_member_id=authorized_by_member_id,
            pool_balance_after=new_balance,
        )
        self.db.add(withdrawal)
        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(withdrawal)

        # Load authorized member name for broadcast
        member_result = await self.db.execute(
            select(Member).where(Member.id == authorized_by_member_id)
        )
        authorized_member = member_result.scalar_one_or_none()
        authorized_name = authorized_member.full_name if authorized_member else "Exco"

        # Broadcast to all members — errors are logged, not raised
        await self._broadcast_withdrawal_notification(
            withdrawal=withdrawal,
            coop=coop,
            authorized_member_name=authorized_name,
        )

        return {
            "withdrawal_id": withdrawal.id,
            "pool_balance_after": new_balance,
        }

    async def _broadcast_withdrawal_notification(
        self,
        withdrawal: Withdrawal,
        coop: Cooperative,
        authorized_member_name: str,
    ) -> None:
        """
        Send the coop_withdrawal_alert template to every active member.
        Template variables:
          {{1}} cooperative name
          {{2}} amount in naira (integer string)
          {{3}} reason
          {{4}} authorized by name
          {{5}} date e.g. "24 Mar 2026"
          {{6}} pool balance after in naira (integer string)
        """
        result = await self.db.execute(
            select(Member.phone_number, Member.full_name)
            .join(CoopMember, CoopMember.member_id == Member.id)
            .where(CoopMember.cooperative_id == withdrawal.cooperative_id)
        )
        members = result.all()

        amount_naira = str(withdrawal.amount // 100)
        balance_naira = str(withdrawal.pool_balance_after // 100)
        date_str = withdrawal.created_at.strftime("%d %b %Y")

        components = [
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "text": coop.name},
                    {"type": "text", "text": amount_naira},
                    {"type": "text", "text": withdrawal.reason},
                    {"type": "text", "text": authorized_member_name},
                    {"type": "text", "text": date_str},
                    {"type": "text", "text": balance_naira},
                ],
            }
        ]

        for phone, _name in members:
            try:
                await send_template_message(
                    to=phone,
                    template_name=TEMPLATE_WITHDRAWAL_ALERT,
                    components=components,
                )
            except Exception as exc:
                logger.warning(
                    "Withdrawal broadcast failed to %s: %s", phone, exc
                )

    async def get_withdrawals(
        self,
        coop_id: UUID,
        page: int,
        page_size: int,
    ) -> dict:
        """
        Return paginated withdrawal log for a cooperative, newest first.
        Joins the authorized member's name for display.
        Returns total count and has_more flag per D33.
        """
        offset = (page - 1) * page_size

        # Total count — separate query, cheap on indexed FK column
        count_result = await self.db.execute(
            select(func.count(Withdrawal.id)).where(
                Withdrawal.cooperative_id == coop_id
            )
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(
                Withdrawal.id,
                Withdrawal.amount,
                Withdrawal.reason,
                Withdrawal.pool_balance_after,
                Withdrawal.created_at,
                Member.full_name.label("authorized_by_name"),
            )
            .join(Member, Member.id == Withdrawal.authorized_by_member_id)
            .where(Withdrawal.cooperative_id == coop_id)
            .order_by(Withdrawal.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )

        items = [
            {
                "id": row.id,
                "amount": row.amount,
                "reason": row.reason,
                "authorized_by_name": row.authorized_by_name,
                "pool_balance_after": row.pool_balance_after,
                "created_at": row.created_at,
            }
            for row in result.all()
        ]

        return {
            "items": items,
            "total": total,
            "page": page,
            "has_more": total > page * page_size,
        }