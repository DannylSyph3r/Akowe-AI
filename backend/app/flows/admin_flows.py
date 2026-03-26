"""
WhatsApp conversation flows for cooperative executives (exco).
"""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation_session import ConversationSession
from app.models.member import Member
from app.prompts.financial_summary import (
    COOP_STATUS_INSIGHT_PROMPT,
    FINANCIAL_SUMMARY_SYSTEM_PROMPT,
)
from app.repositories.cooperative_repository import CooperativeRepository
from app.repositories.period_repository import PeriodRepository
from app.services.contribution_service import ContributionService
from app.services.gemini_service import GeminiProClient
from app.services.whatsapp_service import (
    TEMPLATE_BROADCAST,
    TEMPLATE_CONTRIBUTION_REMINDER,
    sanitize_template_param,
    send_list_message,
    send_reply_buttons,
    send_template_message,
    send_text_message,
)

logger = logging.getLogger("akoweai")

# Lazy singleton — only created on first use, never at import time
_gemini_pro: GeminiProClient | None = None


def _get_pro_client() -> GeminiProClient:
    """Return the shared GeminiProClient, creating it on first call."""
    global _gemini_pro
    if _gemini_pro is None:
        _gemini_pro = GeminiProClient()
    return _gemini_pro


def _format_naira(amount_kobo: int) -> str:
    return f"₦{amount_kobo / 100:,.0f}"


# Coop status
async def handle_coop_status_intent(
    phone: str,
    member: Member,
    coop_id: UUID,
    db: AsyncSession,
) -> None:
    coop_repo = CooperativeRepository(db)
    period_repo = PeriodRepository(db)

    coop = await coop_repo.get_by_id(coop_id)
    if not coop:
        await send_text_message(phone, "Cooperative not found.")
        return

    member_count = await coop_repo.get_member_count(coop_id)
    open_period = await period_repo.get_open_period(coop_id)

    paid_count = 0
    if open_period:
        paid_count = await coop_repo.get_paid_count_for_period(coop_id, open_period.id)

    total_expected_kobo = member_count * coop.contribution_amount
    collected_kobo = paid_count * coop.contribution_amount
    collection_pct = int((paid_count / member_count * 100)) if member_count else 0

    unpaid_members = []
    if open_period:
        unpaid_members = await coop_repo.get_unpaid_members_for_period(
            coop_id, open_period.id
        )

    insight = ""
    if unpaid_members:
        context = (
            f"Cooperative: {coop.name}\n"
            f"Members: {member_count}, Paid: {paid_count}, Unpaid: {len(unpaid_members)}\n"
            f"Collection rate: {collection_pct}%\n"
            f"Unpaid members: {', '.join(m['full_name'] for m in unpaid_members[:5])}"
        )
        try:
            insight = await _get_pro_client().generate_summary(
                context, COOP_STATUS_INSIGHT_PROMPT
            )
        except Exception as exc:
            logger.warning("Gemini insight generation failed: %s", exc)

    period_label = open_period.start_date.strftime("%B %Y") if open_period else "N/A"

    lines = [
        f"📈 *{coop.name} Status*\n",
        f"• Pool Balance: {_format_naira(coop.pool_balance)}",
        f"• Members: {member_count}",
        f"• {period_label} — {paid_count}/{member_count} paid ({collection_pct}%)",
        f"• Collected: {_format_naira(collected_kobo)} / {_format_naira(total_expected_kobo)}",
    ]
    if insight:
        lines.append(f"\n🤖 {insight}")

    await send_text_message(phone, "\n".join(lines))
    await send_reply_buttons(
        phone,
        "What would you like to do?",
        [
            {"id": "send_reminders", "title": "📢 Send Reminders"},
            {"id": "member_lookup", "title": "🔍 Member Lookup"},
        ],
    )


# Member lookup flow
async def handle_member_lookup_flow(
    phone: str,
    session: ConversationSession,
    coop_id: UUID,
    db: AsyncSession,
    entities: dict | None = None,
) -> None:
    """
    Step 0: Ask for member name (blocking flow)
    Step 1: Search and display results (or list if multiple)
    Step 2: Handle list selection when multiple results returned
    """
    step = session.current_step if session.current_flow == "MEMBER_LOOKUP" else 0
    entities = entities or {}

    # Step 2: User selected a member from the multi-result list
    if step == 2:
        row_id = entities.get("row_id", "")
        lookup_results: dict = session.flow_data.get("lookup_results", {})
        member_data = lookup_results.get(row_id)
        if member_data:
            await _send_member_detail(phone, member_data, coop_id, db)
        else:
            await send_text_message(phone, "Member not found. Please try again.")
        session.current_flow = None
        session.current_step = 0
        session.flow_data = {}
        return

    # Step 0: Initiate flow
    if step == 0:
        session.current_flow = "MEMBER_LOOKUP"
        session.current_step = 1
        session.flow_data = {}
        await send_text_message(phone, "🔍 Enter the member's name to look up:")
        return

    # Step 1: Receive name, search
    query = session.flow_data.get("current_text", "").strip()
    if not query:
        await send_text_message(phone, "Please enter a name to search.")
        return

    coop_repo = CooperativeRepository(db)
    results = await coop_repo.search_members_by_name(coop_id, query)

    if not results:
        await send_text_message(phone, f"No members found matching *{query}*.")
        session.current_flow = None
        session.current_step = 0
        session.flow_data = {}
        return

    if len(results) == 1:
        await _send_member_detail(phone, results[0], coop_id, db)
        session.current_flow = None
        session.current_step = 0
        session.flow_data = {}
    else:
        rows = [
            {"id": f"lookup_{r['member_id']}", "title": r["full_name"]}
            for r in results[:10]
        ]
        session.flow_data["lookup_results"] = {
            f"lookup_{r['member_id']}": r for r in results
        }
        session.current_step = 2
        await send_list_message(
            phone,
            header="Multiple Results",
            body=f"Found {len(results)} members. Select one to view details:",
            button_text="Select Member",
            sections=[{"title": "Members", "rows": rows}],
        )


async def _send_member_detail(
    phone: str, member_data: dict, coop_id: UUID, db: AsyncSession
) -> None:
    """Fetch and format a member's contribution summary."""
    contrib_svc = ContributionService(db)
    member_id = member_data["member_id"]

    try:
        balance = await contrib_svc.get_member_balance(member_id, coop_id)
    except Exception:
        balance = None

    lines = [
        f"👤 *{member_data['full_name']}*",
        f"• Role: {member_data.get('role', 'member').title()}",
    ]
    if balance:
        lines.append(f"• Total contributed: {_format_naira(balance['total_contributed_kobo'])}")
        lines.append(f"• Periods paid: {balance['periods_paid']}/{balance['periods_total']}")
        if balance.get("recent_activity"):
            lines.append("\n*Recent:*")
            for item in balance["recent_activity"][:3]:
                icon = "✅" if item["status"] == "paid" else "❌"
                lines.append(f"{icon} {item['period_label']}")

    await send_text_message(phone, "\n".join(lines))


# Broadcast flow
async def handle_broadcast_flow(
    phone: str,
    session: ConversationSession,
    coop_id: UUID,
    db: AsyncSession,
) -> None:
    """
    Step 0: Ask for message text (blocking flow)
    Step 1: Show confirmation with member count
    Step 2: Send to all members
    """
    step = session.current_step if session.current_flow == "BROADCAST" else 0

    if step == 0:
        session.current_flow = "BROADCAST"
        session.current_step = 1
        session.flow_data = {}
        await send_text_message(
            phone,
            "📢 Type the message to broadcast to all members of this cooperative:",
        )
        return

    if step == 1:
        message_text = session.flow_data.get("current_text", "").strip()
        if not message_text:
            await send_text_message(phone, "Please enter the message to broadcast.")
            return

        coop_repo = CooperativeRepository(db)
        member_count = await coop_repo.get_member_count(coop_id)
        session.flow_data["broadcast_message"] = message_text
        session.current_step = 2

        await send_reply_buttons(
            phone,
            f"Ready to send this message to *{member_count} members*:\n\n_{message_text}_",
            [
                {"id": "confirm_broadcast", "title": f"✅ Send to {member_count}"},
                {"id": "cancel", "title": "❌ Cancel"},
            ],
        )
        return

    if step == 2:
        message_text = session.flow_data.get("broadcast_message", "")
        if not message_text:
            session.current_flow = None
            await send_text_message(phone, "No message found. Please start again.")
            return

        coop_repo = CooperativeRepository(db)
        coop = await coop_repo.get_by_id(coop_id)
        coop_name = coop.name if coop else "your cooperative"
        
        member_phones = await coop_repo.get_active_member_phones(coop_id)

        sent_count = 0
        for member_phone, member_name in member_phones:
            if member_phone == phone:
                continue
            try:
                await send_template_message(
                    to=member_phone,
                    template_name=TEMPLATE_BROADCAST,
                    components=[
                        {
                            "type": "body",
                            "parameters": [
                                {"type": "text", "text": sanitize_template_param(coop_name)},
                                {"type": "text", "text": sanitize_template_param(message_text)},
                            ],
                        }
                    ],
                )
                sent_count += 1
            except Exception as exc:
                logger.warning("Broadcast send failed to %s: %s", member_phone, exc)

        session.current_flow = None
        session.current_step = 0
        session.flow_data = {}
        await send_text_message(phone, f"✅ Broadcast sent to {sent_count} member(s).")


# AI financial summary
async def handle_coop_summary_intent(
    phone: str,
    member: Member,
    coop_id: UUID,
    db: AsyncSession,
) -> None:
    coop_repo = CooperativeRepository(db)
    coop = await coop_repo.get_by_id(coop_id)
    if not coop:
        await send_text_message(phone, "Cooperative not found.")
        return

    summary_data = await coop_repo.get_financial_summary(coop_id, days=30)
    member_count = await coop_repo.get_member_count(coop_id)

    context = (
        f"Cooperative: {coop.name}\n"
        f"Pool balance: ₦{coop.pool_balance / 100:,.0f}\n"
        f"Total members: {member_count}\n"
        f"Contributions received (last 30 days): ₦{summary_data['contributions_kobo'] / 100:,.0f}\n"
        f"Withdrawals (last 30 days): ₦{summary_data['withdrawals_kobo'] / 100:,.0f}\n"
        f"Members who paid this period: {summary_data['paid_count']}/{member_count}\n"
        f"Outstanding debt: ₦{summary_data['outstanding_debt_kobo'] / 100:,.0f}\n"
        f"Collection rate: {summary_data['collection_rate_pct']}%"
    )

    await send_text_message(phone, "🤖 Generating financial summary...")

    try:
        summary = await _get_pro_client().generate_summary(
            context, FINANCIAL_SUMMARY_SYSTEM_PROMPT
        )
    except Exception as exc:
        logger.warning("Gemini summary generation failed: %s", exc)
        summary = "Unable to generate summary at this time."

    await send_text_message(phone, f"📊 *Financial Summary*\n\n{summary}")


# Send reminders
async def handle_send_reminders_intent(
    phone: str,
    member: Member,
    coop_id: UUID,
    db: AsyncSession,
) -> None:
    period_repo = PeriodRepository(db)
    coop_repo = CooperativeRepository(db)

    open_period = await period_repo.get_open_period(coop_id)
    if not open_period:
        await send_text_message(phone, "No open period found. Nothing to remind.")
        return

    unpaid_members = await coop_repo.get_unpaid_members_for_period(coop_id, open_period.id)

    if not unpaid_members:
        await send_text_message(phone, "✅ All members have paid for this period!")
        return

    coop = await coop_repo.get_by_id(coop_id)
    
    amount = f"{coop.contribution_amount / 100:,.0f}" if coop else "0" 
    due_date_str = open_period.due_date.strftime("%d %b %Y")
    period_label = open_period.start_date.strftime("%B %Y")

    sent_count = 0
    for m in unpaid_members:
        try:
            await send_template_message(
                to=m["phone_number"],
                template_name=TEMPLATE_CONTRIBUTION_REMINDER,
                components=[
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": m["full_name"].split()[0]},
                            {"type": "text", "text": amount},
                            {"type": "text", "text": period_label},
                            {"type": "text", "text": due_date_str},
                        ],
                    }
                ],
            )
            sent_count += 1
        except Exception as exc:
            logger.warning("Reminder send failed to %s: %s", m["phone_number"], exc)

    await send_text_message(
        phone,
        f"📢 Reminders sent to *{sent_count}* member(s) with outstanding contributions.",
    )