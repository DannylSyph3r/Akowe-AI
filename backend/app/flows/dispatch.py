import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Intent, Role
from app.models.conversation_session import ConversationSession
from app.models.member import Member
from app.repositories.cooperative_repository import CooperativeRepository
from app.services.whatsapp_service import (
    send_list_message,
    send_reply_buttons,
    send_text_message,
)

logger = logging.getLogger("akoweai")


async def send_member_main_menu(phone: str) -> None:
    await send_reply_buttons(
        phone,
        "Here's what I can help you with 👇",
        [
            {"id": "pay_now", "title": "💰 Pay"},
            {"id": "my_balance", "title": "📊 My Balance"},
        ],
    )


async def send_exco_main_menu(phone: str, name: str) -> None:
    greeting = f"Hello {name} 👋\nWhat would you like to do?" if name else "Here's your menu 👇"
    await send_list_message(
        phone,
        header="AkoweAI",
        body=greeting,
        button_text="View Options",
        sections=[
            {
                "title": "Member Actions",
                "rows": [
                    {"id": "pay_now", "title": "💰 Pay Contribution"},
                    {"id": "my_balance", "title": "📊 My Balance"},
                    {"id": "full_history", "title": "📜 Payment History"},
                ],
            },
            {
                "title": "Admin Actions",
                "rows": [
                    {"id": "coop_status", "title": "📈 Coop Status"},
                    {"id": "member_lookup", "title": "🔍 Member Lookup"},
                    {"id": "broadcast", "title": "📢 Broadcast Message"},
                    {"id": "ai_summary", "title": "🤖 AI Summary"},
                ],
            },
        ],
    )


async def send_cooperative_switcher(
    phone: str,
    coops: list[dict],
) -> None:
    """Send a list message asking the member to select their active cooperative."""
    rows = [
        {"id": f"switch_coop_{c['id']}", "title": c["name"]}
        for c in coops
    ]
    await send_list_message(
        phone,
        header="Select Cooperative",
        body="You belong to multiple cooperatives. Which one are you acting on?",
        button_text="Choose",
        sections=[{"title": "Your Cooperatives", "rows": rows}],
    )


async def dispatch_intent(
    phone: str,
    intent: Intent,
    entities: dict,
    session: ConversationSession,
    member: Member | None,
    db: AsyncSession,
) -> None:
    """
    Route the classified intent to the correct flow handler.
    Handles:
    - Unregistered users (member is None)
    - Cooperative context resolution (single vs multi-coop)
    - Role-based routing (member vs exco)
    """
    from app.flows.admin_flows import (
        handle_broadcast_flow,
        handle_coop_status_intent,
        handle_coop_summary_intent,
        handle_member_lookup_flow,
        handle_send_reminders_intent,
    )
    from app.flows.member_flows import (
        handle_balance_intent,
        handle_history_intent,
        handle_pay_intent,
        handle_register_flow,
    )

    # --- Unregistered user ---
    if member is None:
        if intent == Intent.REGISTER or session.current_flow == "REGISTER":
            await handle_register_flow(phone, session, db)
            return
        # Prompt them to register
        await send_text_message(
            phone,
            "Welcome to AkoweAI! 👋\n\nI manage contributions for savings cooperatives. "
            "To get started, tap the button below.",
        )
        await send_reply_buttons(
            phone,
            "Ready to join your cooperative?",
            [{"id": "get_started", "title": "🆕 Get Started"}],
        )
        return

    # --- Registered member: resolve cooperative context ---
    coop_repo = CooperativeRepository(db)
    coops = await coop_repo.get_member_cooperatives(member.id)

    if not coops:
        await send_text_message(
            phone,
            "You're not a member of any cooperative yet. "
            "Ask your exco for a join code.",
        )
        return

    # Auto-set active coop if member has only one
    if session.active_cooperative_id is None:
        if len(coops) == 1:
            coop, cm = coops[0]
            session.active_cooperative_id = coop.id
        else:
            # Store pending intent and show switcher
            session.flow_data = {
                **session.flow_data,
                "pending_intent": intent.value,
                "pending_entities": entities,
            }
            coop_list = [
                {"id": str(c.id), "name": c.name} for c, _ in coops
            ]
            await send_cooperative_switcher(phone, coop_list)
            return

    # --- Handle cooperative switcher selection ---
    if intent == Intent.SWITCH_COOP:
        coop_id_str = entities.get("coop_id")
        if coop_id_str:
            session.active_cooperative_id = UUID(coop_id_str)
        # Re-dispatch pending intent if one was saved
        pending_intent_str = session.flow_data.get("pending_intent")
        if pending_intent_str:
            pending_intent = Intent(pending_intent_str)
            pending_entities = session.flow_data.get("pending_entities", {})
            session.flow_data = {
                k: v
                for k, v in session.flow_data.items()
                if k not in ("pending_intent", "pending_entities")
            }
            await dispatch_intent(phone, pending_intent, pending_entities, session, member, db)
            return
        # No pending intent — just show the menu
        intent = Intent.UNKNOWN

    coop_id = session.active_cooperative_id

    # Determine role in active coop
    coop_member_role = next(
        (cm.role for c, cm in coops if c.id == coop_id), None
    )
    if coop_member_role is None:
        await send_text_message(phone, "Unable to verify your membership in this cooperative.")
        return

    is_exco = coop_member_role == Role.EXCO.value

    # --- Route to flow handlers ---
    if intent == Intent.REGISTER:
        # Already registered — show menu
        if is_exco:
            await send_exco_main_menu(phone, member.full_name)
        else:
            await send_member_main_menu(phone)

    elif intent == Intent.PAY:
        await handle_pay_intent(phone, member, session, coop_id, db)

    elif intent == Intent.BALANCE:
        await handle_balance_intent(phone, member, coop_id, db)

    elif intent == Intent.HISTORY or intent == Intent.SHOW_MORE:
        page = session.flow_data.get("history_page", 0) if intent == Intent.SHOW_MORE else 0
        await handle_history_intent(phone, member, coop_id, page, db)

    elif intent == Intent.COOP_STATUS and is_exco:
        await handle_coop_status_intent(phone, member, coop_id, db)

    elif intent == Intent.SEND_REMINDERS and is_exco:
        await handle_send_reminders_intent(phone, member, coop_id, db)

    elif intent == Intent.COOP_SUMMARY and is_exco:
        await handle_coop_summary_intent(phone, member, coop_id, db)

    elif intent == Intent.BROADCAST or session.current_flow == "BROADCAST":
        if is_exco:
            await handle_broadcast_flow(phone, session, coop_id, db)
        else:
            await _permission_denied(phone)

    elif intent == Intent.MEMBER_LOOKUP or session.current_flow == "MEMBER_LOOKUP":
        if is_exco:
            await handle_member_lookup_flow(phone, session, coop_id, db)
        else:
            await _permission_denied(phone)

    elif intent == Intent.VIEW_UNPAID and is_exco:
        # Handled as part of coop status — re-use the same handler
        await handle_coop_status_intent(phone, member, coop_id, db)

    elif intent == Intent.CANCEL:
        session.current_flow = None
        session.current_step = 0
        session.flow_data = {}
        await send_text_message(phone, "Cancelled. ✅")
        if is_exco:
            await send_exco_main_menu(phone, member.full_name)
        else:
            await send_member_main_menu(phone)

    else:
        # UNKNOWN or unhandled
        from app.services.intent_service import send_fallback_menu
        await send_fallback_menu(phone, coop_member_role)


async def _permission_denied(phone: str) -> None:
    await send_text_message(phone, "⛔ This action is only available to cooperative administrators.")