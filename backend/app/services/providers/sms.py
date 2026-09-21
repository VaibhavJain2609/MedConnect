"""
SMS provider adapter — MSG91 flow API.

POST https://control.msg91.com/api/v5/flow/ with an ``authkey`` header.
The flow endpoint delivers a pre-approved DLT template to a recipient
list; the message text is passed as a template variable (``var``) so the
rendered SMS carries the notification body.

Settings:
    MSG91_AUTHKEY     — account authkey (falls back to MSG91_AUTH_KEY).
                        Unset -> skipped(provider_not_configured).
    MSG91_SENDER_ID   — registered sender ID / DLT header.
    MSG91_TEMPLATE_ID — approved flow/template ID; a per-call
                        ``template_id`` argument overrides it.

Recipient format: MSG91 wants the mobile number with country code in the
``mobiles`` field (e.g. "91XXXXXXXXXX"); ``user.phone`` is passed through
as stored, so the value must already carry the country prefix.

PHI note: never log message bodies or phone numbers — identifiers
(user_id, channel, status) only.
"""
import httpx
import structlog

from app.config import settings

logger = structlog.get_logger()

MSG91_FLOW_URL = "https://control.msg91.com/api/v5/flow/"

_TIMEOUT_SECONDS = 15.0


async def send(user, body: str, *, template_id: str | None = None):
    """
    Send `body` to `user.phone` via the MSG91 flow API.

    Returns ChannelResult — sent on HTTP 2xx, skipped when the provider or
    the recipient is unavailable, failed on HTTP errors or transport
    failures. Never raises for provider-level failures.
    """
    # Deferred import: providers must not import notification_channels at
    # module scope (it imports this package).
    from app.services.notification_channels import ChannelResult

    authkey = settings.MSG91_AUTHKEY or settings.MSG91_AUTH_KEY
    template = template_id or settings.MSG91_TEMPLATE_ID
    if not authkey or not template:
        logger.info(
            "notification_channel_not_configured",
            channel="sms",
            provider="msg91",
            user_id=str(user.id),
        )
        return ChannelResult(
            channel="sms", status="skipped", reason="provider_not_configured"
        )
    if not user.phone:
        logger.info(
            "notification_channel_no_recipient",
            channel="sms",
            provider="msg91",
            user_id=str(user.id),
        )
        return ChannelResult(channel="sms", status="skipped", reason="no_recipient")

    payload = {
        "template_id": template,
        "sender": settings.MSG91_SENDER_ID or "",
        "short_url": "0",
        "recipients": [{"mobiles": user.phone, "var": body}],
    }
    headers = {
        "authkey": authkey,
        "accept": "application/json",
        "content-type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            resp = await client.post(MSG91_FLOW_URL, json=payload, headers=headers)
        if resp.status_code >= 400:
            logger.warning(
                "notification_channel_provider_http_error",
                channel="sms",
                provider="msg91",
                user_id=str(user.id),
                status_code=resp.status_code,
            )
            return ChannelResult(
                channel="sms",
                status="failed",
                reason=f"provider_http_{resp.status_code}",
            )
        return ChannelResult(channel="sms", status="sent")
    except Exception as exc:
        logger.error(
            "notification_channel_failed",
            channel="sms",
            provider="msg91",
            user_id=str(user.id),
            error=str(exc),
            exc_info=True,
        )
        return ChannelResult(channel="sms", status="failed", reason="send_error")
