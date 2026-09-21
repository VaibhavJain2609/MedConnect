"""
WhatsApp provider adapter — WhatsApp Business Cloud API.

POST https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_NUMBER_ID}/messages
with a ``Bearer WHATSAPP_ACCESS_TOKEN``. Outside the 24h customer-service
window only pre-approved *template* messages are deliverable, so the
adapter sends a template whose single body parameter carries the
notification text.

Settings:
    WHATSAPP_ACCESS_TOKEN    — system-user / permanent token. Unset ->
                               skipped(provider_not_configured).
    WHATSAPP_PHONE_NUMBER_ID — sender phone-number ID from the app
                               dashboard. Unset -> skipped.
    WHATSAPP_TEMPLATE_NAME   — approved template name; a per-call
                               ``template_name`` argument overrides it.
    WHATSAPP_TEMPLATE_LANG   — template language code ("en_US").

Recipient format: the ``to`` field wants the full international number
with country code and no '+'/spaces (e.g. "91XXXXXXXXXX");
``user.phone`` is normalised by stripping non-digits.

PHI note: never log message bodies or phone numbers — identifiers
(user_id, channel, status) only.
"""
import re

import httpx
import structlog

from app.config import settings

logger = structlog.get_logger()

GRAPH_API_VERSION = "v19.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

_TIMEOUT_SECONDS = 15.0


async def send(user, body: str, *, template_name: str | None = None):
    """
    Send `body` to `user.phone` as a WhatsApp template message.

    Returns ChannelResult — sent on HTTP 2xx, skipped when the provider or
    the recipient is unavailable, failed on HTTP errors or transport
    failures. Never raises for provider-level failures.
    """
    # Deferred import: providers must not import notification_channels at
    # module scope (it imports this package).
    from app.services.notification_channels import ChannelResult

    token = settings.WHATSAPP_ACCESS_TOKEN
    phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
    template = template_name or settings.WHATSAPP_TEMPLATE_NAME
    if not token or not phone_number_id or not template:
        logger.info(
            "notification_channel_not_configured",
            channel="whatsapp",
            provider="meta",
            user_id=str(user.id),
        )
        return ChannelResult(
            channel="whatsapp", status="skipped", reason="provider_not_configured"
        )

    to = re.sub(r"\D", "", user.phone or "")
    if not to:
        logger.info(
            "notification_channel_no_recipient",
            channel="whatsapp",
            provider="meta",
            user_id=str(user.id),
        )
        return ChannelResult(
            channel="whatsapp", status="skipped", reason="no_recipient"
        )

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": {
            "name": template,
            "language": {"code": settings.WHATSAPP_TEMPLATE_LANG},
            "components": [
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": body}],
                }
            ],
        },
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    url = f"{GRAPH_API_BASE}/{phone_number_id}/messages"

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code >= 400:
            logger.warning(
                "notification_channel_provider_http_error",
                channel="whatsapp",
                provider="meta",
                user_id=str(user.id),
                status_code=resp.status_code,
            )
            return ChannelResult(
                channel="whatsapp",
                status="failed",
                reason=f"provider_http_{resp.status_code}",
            )
        return ChannelResult(channel="whatsapp", status="sent")
    except Exception as exc:
        logger.error(
            "notification_channel_failed",
            channel="whatsapp",
            provider="meta",
            user_id=str(user.id),
            error=str(exc),
            exc_info=True,
        )
        return ChannelResult(channel="whatsapp", status="failed", reason="send_error")
