"""
Central intent dispatcher for WhatsApp conversation flows.
Routes intents to the correct flow handler based on member presence and role.
"""

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


async def send_member_main_menu(phone: str, multi_coop: bool = False) -> None:
    buttons = [
        {"id": "pay_now", "title": "💰 Pay"},
        {"id": "my_balance", "title": "📊 My Balance"},
    ]
    if multi_coop:
        buttons.append({"id": "show_switcher", "title": "🔄 Switch Coop"})
    await send_reply_buttons(
        phone,
        "Here's what I can help you with 👇",
        buttons,
    )


async def send_exco_main_menu(
    phone: str,
    name: str,
    coop_name: str = "",
    multi_coop: bool = False,
) -> None:
    greeting = (
        f"Hello {name} 👋\nWhat would you like to do?"
        if name
        else "Here's your menu 👇"
    )
    if coop_name:
        greeting = f"🏦 *{coop_name}*\n{greeting}"

    sections = [
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
    ]

    if multi_coop:
        sections.append({
            "title": "Account",
            "rows": [
                {"id": "show_switcher", "title": "🔄 Switch Cooperative"},
            ],
        })

    await send_list_message(
        phone,
        header="AkoweAI",
        body=greeting,
        button_text="View Options",
        sections=sections,
    )


async def send_cooperative_switcher(phone: str, coops: list[dict]) -> None:
    rows = [{"id": f"switch_coop_{c['id']}", "title": c["name"]} for c in coops]
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
    # Import flow handlers inside function to avoid circular imports at module load
    from app.flows.admin_flows import (
        handle_broadcast_flow,
        handle_coop_status_intent,
        handle_coop_summary_intent,
        handle_member_lookup_flow,
        handle_send_reminders_intent,
    )
    from app.flows.member_flows import (
        handle_add_period,
        handle_balance_intent,
        handle_confirm_pay,
        handle_history_intent,
        handle_pay_intent,
        handle_pay_period_selected,
        handle_register_flow,
    )

    # --- Unregistered user ---
    if member is None:
        if intent == Intent.REGISTER or session.current_flow == "REGISTER":
            await handle_register_flow(phone, session, db)
            return
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
            "You're not a member of any cooperative yet. Ask your exco for a join code.",
        )
        return

    # Auto-set active coop when member has only one
    if session.active_cooperative_id is None:
        if len(coops) == 1:
            coop, cm = coops[0]
            session.active_cooperative_id = coop.id
        else:
            session.flow_data = {
                **session.flow_data,
                "pending_intent": intent.value,
                "pending_entities": entities,
            }
            coop_list = [{"id": str(c.id), "name": c.name} for c, _ in coops]
            await send_cooperative_switcher(phone, coop_list)
            return

    # --- Handle cooperative switcher selection ---
    if intent == Intent.SWITCH_COOP:
        coop_id_str = entities.get("coop_id")
        if coop_id_str:
            session.active_cooperative_id = UUID(coop_id_str)
        pending_intent_str = session.flow_data.get("pending_intent")
        if pending_intent_str:
            pending_intent = Intent(pending_intent_str)
            pending_entities = session.flow_data.get("pending_entities", {})
            session.flow_data = {
                k: v
                for k, v in session.flow_data.items()
                if k not in ("pending_intent", "pending_entities")
            }
            await dispatch_intent(
                phone, pending_intent, pending_entities, session, member, db
            )
            return
        # On-demand switch — show menu scoped to the newly selected coop
        new_coop_id = session.active_cooperative_id
        new_coop_obj = next((c for c, _ in coops if c.id == new_coop_id), None)
        new_coop_name = new_coop_obj.name if new_coop_obj else ""
        new_coop_role = next(
            (cm.role for c, cm in coops if c.id == new_coop_id), None
        )
        if new_coop_role == Role.EXCO.value:
            await send_exco_main_menu(
                phone, member.full_name,
                coop_name=new_coop_name,
                multi_coop=len(coops) > 1,
            )
        else:
            await send_member_main_menu(phone, multi_coop=len(coops) > 1)
        return

    coop_id = session.active_cooperative_id

    # Derive active coop name for context display in menus
    active_coop_obj = next((c for c, _ in coops if c.id == coop_id), None)
    active_coop_name = active_coop_obj.name if active_coop_obj else ""

    # Determine role in the active cooperative
    coop_member_role = next(
        (cm.role for c, cm in coops if c.id == coop_id), None
    )
    if coop_member_role is None:
        await send_text_message(
            phone, "Unable to verify your membership in this cooperative."
        )
        return

    is_exco = coop_member_role == Role.EXCO.value

    # --- Route to flow handlers ---

    if intent == Intent.REGISTER:
        # Already registered — show appropriate menu
        if is_exco:
            await send_exco_main_menu(
                phone, member.full_name,
                coop_name=active_coop_name,
                multi_coop=len(coops) > 1,
            )
        else:
            await send_member_main_menu(phone, multi_coop=len(coops) > 1)

    elif intent == Intent.PAY:
        # If we're in PAY_SELECTION and a period row was selected from the list,
        # entities["row_id"] carries the row identifier
        row_id = entities.get("row_id")
        if session.current_flow == "PAY_SELECTION" and row_id:
            await handle_pay_period_selected(phone, member, coop_id, row_id, session, db)
        else:
            await handle_pay_intent(phone, member, session, coop_id, db)

    elif intent == Intent.ADD_PERIOD:
        # User wants to add another period to their selection
        if session.current_flow == "PAY_SELECTION":
            await handle_add_period(phone, member, coop_id, session, db)
        else:
            # No active selection — start fresh pay flow
            await handle_pay_intent(phone, member, session, coop_id, db)

    elif intent == Intent.CONFIRM_PAY:
        await handle_confirm_pay(phone, member, coop_id, session, db)

    elif intent == Intent.BALANCE:
        await handle_balance_intent(phone, member, coop_id, db)

    elif intent == Intent.HISTORY:
        # Reset page when user explicitly requests history
        session.flow_data.pop("history_page", None)
        has_more = await handle_history_intent(phone, member, coop_id, 0, db)
        if has_more:
            session.flow_data["history_page"] = 1

    elif intent == Intent.SHOW_MORE:
        page = session.flow_data.get("history_page", 0)
        has_more = await handle_history_intent(phone, member, coop_id, page, db)
        if has_more:
            session.flow_data["history_page"] = page + 1
        else:
            session.flow_data.pop("history_page", None)

    elif intent in (Intent.COOP_STATUS, Intent.VIEW_UNPAID, Intent.SEND_REMINDERS, Intent.COOP_SUMMARY):
        if is_exco:
            if intent in (Intent.COOP_STATUS, Intent.VIEW_UNPAID):
                await handle_coop_status_intent(phone, member, coop_id, db)
            elif intent == Intent.SEND_REMINDERS:
                await handle_send_reminders_intent(phone, member, coop_id, db)
            else:
                await handle_coop_summary_intent(phone, member, coop_id, db)
        else:
            await _permission_denied(phone)

    elif (
        intent == Intent.BROADCAST
        or intent == Intent.CONFIRM_BROADCAST
        or session.current_flow == "BROADCAST"
    ):
        if is_exco:
            await handle_broadcast_flow(phone, session, coop_id, db)
        else:
            await _permission_denied(phone)

    elif (
        intent == Intent.MEMBER_LOOKUP
        or session.current_flow == "MEMBER_LOOKUP"
    ):
        if is_exco:
            await handle_member_lookup_flow(phone, session, coop_id, db, entities)
        else:
            await _permission_denied(phone)

    elif intent == Intent.CANCEL:
        session.current_flow = None
        session.current_step = 0
        session.flow_data = {}
        await send_text_message(phone, "Cancelled. ✅")
        if is_exco:
            await send_exco_main_menu(
                phone, member.full_name,
                coop_name=active_coop_name,
                multi_coop=len(coops) > 1,
            )
        else:
            await send_member_main_menu(phone, multi_coop=len(coops) > 1)

    elif intent == Intent.GREETING:
        await send_text_message(
            phone,
            "Hey there! 👋 Great to hear from you.\n\nUse the menu below to pay contributions, check your balance, or manage your cooperative.",
        )
        if is_exco:
            await send_exco_main_menu(
                phone, "",
                coop_name=active_coop_name,
                multi_coop=len(coops) > 1,
            )
        else:
            await send_member_main_menu(phone, multi_coop=len(coops) > 1)

    elif intent == Intent.SHOW_SWITCHER:
        # Don't clear active_cooperative_id — it stays set so SWITCH_COOP
        # can update it correctly when the user picks from the list
        session.current_flow = None
        session.current_step = 0
        session.flow_data = {}
        if len(coops) > 1:
            coop_list = [{"id": str(c.id), "name": c.name} for c, _ in coops]
            await send_cooperative_switcher(phone, coop_list)
        else:
            # Single coop — nothing to switch, just show menu
            if is_exco:
                await send_exco_main_menu(
                    phone, member.full_name,
                    coop_name=active_coop_name,
                    multi_coop=False,
                )
            else:
                await send_member_main_menu(phone, multi_coop=False)

    else:
        from app.services.intent_service import send_fallback_menu
        await send_fallback_menu(phone, coop_member_role)


async def _permission_denied(phone: str) -> None:
    await send_text_message(
        phone, "⛔ This action is only available to cooperative administrators."
    )