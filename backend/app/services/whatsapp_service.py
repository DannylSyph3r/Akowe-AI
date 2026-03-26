import logging
import re

import httpx

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger("akoweai")

TEMPLATE_PAYMENT_RECEIPT = "payment_receipt"
TEMPLATE_WITHDRAWAL_ALERT = "coop_withdrawal_alert"
TEMPLATE_CONTRIBUTION_REMINDER = "coop_contribution_reminder"
TEMPLATE_BROADCAST = "coop_broadcast_message"


def sanitize_template_param(text: str) -> str:
    """Strip characters forbidden in WhatsApp template parameters.

    Meta rejects params that contain newlines, tabs, or 4+ consecutive spaces
    (error #132018). Replace newlines/tabs with a single space, then collapse
    runs of 4+ spaces down to 3.
    """
    text = re.sub(r"[\n\r\t]+", " ", text)
    text = re.sub(r" {4,}", "   ", text)
    return text.strip()

_GRAPH_URL = "https://graph.facebook.com/v18.0"


async def send_whatsapp_message(to: str, payload: dict) -> dict:
    """
    Base function — POSTs to the Meta Graph API messages endpoint.
    Raises on non-2xx response.
    """
    url = f"{_GRAPH_URL}/{settings.meta_phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {settings.meta_access_token}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        if not response.is_success:
            logger.error(
                "WhatsApp API error %s: %s", response.status_code, response.text
            )
            response.raise_for_status()
        return response.json()


async def send_text_message(to: str, body: str) -> None:
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }
    await send_whatsapp_message(to, payload)


async def send_reply_buttons(to: str, body: str, buttons: list[dict]) -> None:
    """
    buttons: list of {"id": str, "title": str} — max 3 buttons.
    """
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": b["id"], "title": b["title"]}}
                    for b in buttons[:3]
                ]
            },
        },
    }
    await send_whatsapp_message(to, payload)


async def send_list_message(
    to: str,
    header: str,
    body: str,
    button_text: str,
    sections: list[dict],
) -> None:
    """
    sections: list of {"title": str, "rows": [{"id": str, "title": str, "description"?: str}]}
    """
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": header},
            "body": {"text": body},
            "action": {
                "button": button_text,
                "sections": sections,
            },
        },
    }
    await send_whatsapp_message(to, payload)


async def send_cta_url_button(
    to: str, body: str, button_text: str, url: str
) -> None:
    """
    Sends an interactive CTA URL button. Opens the URL in WhatsApp IAB.
    Note: The domain in `url` must be whitelisted in your Meta App settings.
    """
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "cta_url",
            "body": {"text": body},
            "action": {
                "name": "cta_url",
                "parameters": {
                    "display_text": button_text,
                    "url": url,
                },
            },
        },
    }
    await send_whatsapp_message(to, payload)


async def send_template_message(
    to: str, template_name: str, components: list
) -> None:
    """
    Always pass a TEMPLATE_* constant as template_name — never a raw string.
    """
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": "en"},
            "components": components,
        },
    }
    await send_whatsapp_message(to, payload)


async def dispatch_payment_receipt(
    phone: str,
    transaction,
    coop_name: str,
    member_name: str,
    period_label: str
) -> None:
    """
    Send the payment_receipt template to the member after a successful payment.
    """
    amount = f"{transaction.amount / 100:,.0f}"
    date_str = transaction.updated_at.strftime('%d %b %Y') if transaction.updated_at else "Today"

    components = [
        {
            "type": "body",
            "parameters": [
                {"type": "text", "text": coop_name},
                {"type": "text", "text": member_name},
                {"type": "text", "text": period_label},
                {"type": "text", "text": amount},
                {"type": "text", "text": transaction.reference},
                {"type": "text", "text": date_str},
            ],
        }
    ]
    try:
        await send_template_message(phone, TEMPLATE_PAYMENT_RECEIPT, components)
    except Exception as exc:
        logger.error("Failed to send payment receipt to %s: %s", phone, exc)