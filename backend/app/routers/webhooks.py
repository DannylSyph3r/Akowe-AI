import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import PlainTextResponse

from app.core.config import get_settings
from app.core.database import AsyncSessionFactory
from app.models.conversation_session import ConversationSession
from app.repositories.member_repository import MemberRepository
from app.services.intent_service import route_message
from app.services.session_service import load_or_create_session, save_session

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
settings = get_settings()
logger = logging.getLogger("akoweai")


def _verify_meta_signature(raw_body: bytes, signature_header: str) -> bool:
    """
    Verify X-Hub-Signature-256 from Meta.
    Signature format: "sha256=<hex_digest>"
    Signed with HMAC-SHA256 of raw body using META_APP_SECRET.
    """
    if not signature_header.startswith("sha256="):
        return False
    received_sig = signature_header[len("sha256="):]
    expected_sig = hmac.new(
        settings.meta_app_secret.encode(),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected_sig, received_sig)


def extract_message_data(payload: dict) -> dict | None:
    """
    Parse the Meta webhook payload to extract sender info and message content.
    Returns None for non-message events (e.g., status updates) — caller silently ignores these.
    """
    try:
        entry = payload.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})

        messages = value.get("messages", [])
        if not messages:
            return None  # Status update or other non-message event

        msg = messages[0]
        phone = msg.get("from", "")
        msg_type = msg.get("type", "")

        result: dict = {"phone": phone, "message_type": msg_type}

        if msg_type == "text":
            result["text"] = msg.get("text", {}).get("body", "")

        elif msg_type == "button":
            result["button_payload"] = msg.get("button", {}).get("payload", "")

        elif msg_type == "interactive":
            interactive = msg.get("interactive", {})
            interactive_type = interactive.get("type", "")
            if interactive_type == "button_reply":
                result["message_type"] = "button"
                result["button_payload"] = interactive.get("button_reply", {}).get("id", "")
            elif interactive_type == "list_reply":
                result["message_type"] = "list"
                result["list_payload"] = interactive.get("list_reply", {}).get("id", "")

        return result
    except (IndexError, KeyError, TypeError):
        return None


async def _process_whatsapp_message(payload: dict) -> None:
    """
    Background task: process an incoming WhatsApp message end-to-end.
    Opens its own DB session — never uses the request session.
    """
    async with AsyncSessionFactory() as db:
        try:
            message_data = extract_message_data(payload)
            if message_data is None:
                return  # Silently ignore status updates and non-message events

            phone = message_data.get("phone", "")
            if not phone:
                return

            # Load or create conversation session
            session = await load_or_create_session(phone, db)

            # If this is a text message, store the text in flow_data so flow handlers can read it
            if message_data.get("message_type") == "text":
                session.flow_data = {
                    **session.flow_data,
                    "current_text": message_data.get("text", ""),
                }

            # Look up the member by phone number
            member_repo = MemberRepository(db)
            member = await member_repo.get_by_phone(phone)

            # Route to the correct intent
            intent, entities = await route_message(session, message_data, member)

            # Dispatch to the appropriate flow handler
            from app.flows.dispatch import dispatch_intent
            await dispatch_intent(
                phone=phone,
                intent=intent,
                entities=entities,
                session=session,
                member=member,
                db=db,
            )

            # Persist updated session state
            await save_session(session, db)
            await db.commit()

        except Exception:
            await db.rollback()
            logger.exception("Unhandled error processing WhatsApp message")


@router.get("/whatsapp")
async def whatsapp_verify(request: Request) -> PlainTextResponse:
    """
    Meta webhook verification endpoint.
    Meta sends a GET request with hub.mode, hub.verify_token, and hub.challenge.
    """
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == settings.meta_verify_token:
        return PlainTextResponse(content=challenge)

    return PlainTextResponse(content="Forbidden", status_code=403)


@router.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict:
    """
    Main WhatsApp webhook endpoint.
    Returns 200 immediately after signature verification.
    All message processing happens in a background task.
    """
    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    if not _verify_meta_signature(raw_body, signature):
        logger.warning("WhatsApp webhook signature verification failed — ignoring request")
        # Still return 200 to prevent Meta from retrying (we just don't process)
        return {"status": "ok"}

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        return {"status": "ok"}

    background_tasks.add_task(_process_whatsapp_message, payload)
    return {"status": "ok"}