import hashlib
import hmac
import json
import logging
import time

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import PlainTextResponse

from app.core.config import get_settings
from app.core.database import AsyncSessionFactory
from app.models.conversation_session import ConversationSession
from app.repositories.member_repository import MemberRepository
from app.services.intent_service import route_message
from app.services.session_service import load_or_create_session, save_session
from app.services.whatsapp_service import send_text_message


_processed_message_ids: dict[str, float] = {}
_DEDUP_TTL_SECONDS = 60.0


def _is_duplicate(message_id: str) -> bool:
    """Return True if this message_id was already processed within the TTL window."""
    if not message_id:
        return False
    now = time.time()
    stale_keys = [k for k, t in _processed_message_ids.items() if now - t > _DEDUP_TTL_SECONDS]
    for k in stale_keys:
        del _processed_message_ids[k]
    if message_id in _processed_message_ids:
        return True
    _processed_message_ids[message_id] = now
    return False


router = APIRouter(prefix="/webhooks", tags=["webhooks"])
settings = get_settings()
logger = logging.getLogger("akoweai")


def _verify_meta_signature(raw_body: bytes, signature_header: str) -> bool:
    """Verify X-Hub-Signature-256 using HMAC-SHA256."""
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
    """Extract sender and message content from Meta webhook payload."""
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

        result: dict = {"phone": phone, "message_type": msg_type, "message_id": msg.get("id", "")}

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
    """Process an incoming WhatsApp message end-to-end."""
    async with AsyncSessionFactory() as db:
        try:
            message_data = extract_message_data(payload)
            if message_data is None:
                return

            message_id = message_data.get("message_id", "")
            if _is_duplicate(message_id):
                logger.info("Skipping duplicate webhook delivery for message %s", message_id)
                return

            phone = message_data.get("phone", "")
            if not phone:
                return

            session, was_expired = await load_or_create_session(phone, db)

            if was_expired:
                await send_text_message(
                    phone,
                    "⏱ Your session expired after a period of inactivity. Picking up where you left off — your menu is on its way! 👇",
                )

            if message_data.get("message_type") == "text":
                session.flow_data = {
                    **session.flow_data,
                    "current_text": message_data.get("text", ""),
                }

            member_repo = MemberRepository(db)
            member = await member_repo.get_by_phone(phone)

            intent, entities = await route_message(session, message_data, member)

            from app.flows.dispatch import dispatch_intent
            await dispatch_intent(
                phone=phone,
                intent=intent,
                entities=entities,
                session=session,
                member=member,
                db=db,
            )

            await save_session(session, db)
            await db.commit()

        except Exception:
            await db.rollback()
            logger.exception("Unhandled error processing WhatsApp message")


@router.get("/whatsapp")
async def whatsapp_verify(request: Request) -> PlainTextResponse:
    """Verify Meta webhook subscription."""
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
    """Receive and process WhatsApp webhook events."""
    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    if not _verify_meta_signature(raw_body, signature):
        logger.warning("WhatsApp webhook signature verification failed — ignoring request")
        return {"status": "ok"}

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        return {"status": "ok"}

    background_tasks.add_task(_process_whatsapp_message, payload)
    return {"status": "ok"}