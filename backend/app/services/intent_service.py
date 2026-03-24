import logging

from app.core.enums import ConversationFlow, Intent
from app.models.conversation_session import ConversationSession
from app.models.member import Member
from app.prompts.intent_classification import INTENT_CLASSIFICATION_PROMPT
from app.services.gemini_service import GeminiFlashClient
from app.services.whatsapp_service import send_reply_buttons, send_text_message

logger = logging.getLogger("akoweai")

BUTTON_INTENT_MAP: dict[str, Intent] = {
    "pay_now": Intent.PAY,
    "my_balance": Intent.BALANCE,
    "get_started": Intent.REGISTER,
    "full_history": Intent.HISTORY,
    "show_more_history": Intent.SHOW_MORE,
    "coop_status": Intent.COOP_STATUS,
    "send_reminders": Intent.SEND_REMINDERS,
    "ai_summary": Intent.COOP_SUMMARY,
    "broadcast": Intent.BROADCAST,
    "member_lookup": Intent.MEMBER_LOOKUP,
    "view_unpaid": Intent.VIEW_UNPAID,
    "add_period": Intent.ADD_PERIOD,
    "confirm_pay": Intent.CONFIRM_PAY,
    "confirm_broadcast": Intent.CONFIRM_BROADCAST,
    "cancel": Intent.CANCEL,
}

# Blocking flows capture all free text — the user must complete the flow
_BLOCKING_FLOWS = {
    ConversationFlow.REGISTER.value,
    ConversationFlow.BROADCAST.value,
    ConversationFlow.MEMBER_LOOKUP.value,
}

_gemini_flash = GeminiFlashClient()


def classify_button_intent(button_payload: str) -> Intent:
    return BUTTON_INTENT_MAP.get(button_payload, Intent.UNKNOWN)


async def classify_text_intent(
    text: str, member_role: str
) -> tuple[Intent, dict]:
    """
    Use Gemini Flash to classify free text. Returns (Intent, entities dict).
    Falls back to UNKNOWN on any parse failure.
    """
    prompt = f"User role: {member_role}\nUser message: {text}"
    try:
        result = await _gemini_flash.classify_intent(prompt, INTENT_CLASSIFICATION_PROMPT)
        intent_str = result.get("intent", "UNKNOWN")
        entities = result.get("entities", {})
        try:
            return Intent(intent_str), entities
        except ValueError:
            return Intent.UNKNOWN, {}
    except Exception as exc:
        logger.warning("Intent classification failed: %s", exc)
        return Intent.UNKNOWN, {}


async def route_message(
    session: ConversationSession,
    message_data: dict,
    member: Member | None,
) -> tuple[Intent, dict]:
    """
    Determine the intent and entities from an incoming message.

    Priority:
    1. Button reply → direct lookup in BUTTON_INTENT_MAP
    2. List selection → check for coop switcher prefix, else BUTTON_INTENT_MAP
    3. Text + active blocking flow → return flow intent (user is mid-flow)
    4. Free text → Gemini Flash classification
    """
    message_type = message_data.get("message_type")
    member_role = "exco" if member else "member"

    if message_type == "button":
        button_payload = message_data.get("button_payload", "")
        return classify_button_intent(button_payload), {}

    if message_type == "list":
        row_id = message_data.get("list_payload", "")
        # Cooperative switcher rows are prefixed with "switch_coop_"
        if row_id.startswith("switch_coop_"):
            coop_id_str = row_id.removeprefix("switch_coop_")
            return Intent.SWITCH_COOP, {"coop_id": coop_id_str}
        # Otherwise treat as a standard button intent (same IDs for menu items)
        intent = classify_button_intent(row_id)
        return intent, {}

    if message_type == "text":
        text = message_data.get("text", "")

        # Active blocking flow: redirect text back to the flow without LLM
        if session.current_flow in _BLOCKING_FLOWS:
            try:
                return Intent(session.current_flow), {}
            except ValueError:
                pass

        # Free text with no active blocking flow → Gemini Flash
        return await classify_text_intent(text, member_role)

    return Intent.UNKNOWN, {}


async def send_fallback_menu(phone: str, role: str) -> None:
    """Send fallback message when intent is UNKNOWN."""
    await send_text_message(
        phone,
        "I didn't quite catch that. Here's what I can help with 👇",
    )
    if role == "exco":
        await send_list_message_exco_menu(phone)
    else:
        await send_reply_buttons(
            phone,
            "What would you like to do?",
            [
                {"id": "pay_now", "title": "💰 Pay"},
                {"id": "my_balance", "title": "📊 My Balance"},
            ],
        )


async def send_list_message_exco_menu(phone: str) -> None:
    """Helper to avoid circular import — sends exco menu as a list."""
    from app.flows.dispatch import send_exco_main_menu
    await send_exco_main_menu(phone, "")