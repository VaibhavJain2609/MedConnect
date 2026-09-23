"""
TwilioProvider — reference CommProvider implementation.

Uses the Twilio Messages REST resource directly over httpx (no SDK):

    POST https://api.twilio.com/2010-04-01/Accounts/{SID}/Messages.json
    auth: HTTP Basic (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    body: application/x-www-form-urlencoded — To / From / Body

WhatsApp messages go through the same resource with ``whatsapp:``-prefixed
addresses (Twilio wraps the sender/recipient in the WhatsApp Business
channel; outside the 24h session window the Body must match an approved
template — Twilio returns a 4xx which maps to ``failed``).

Per-channel gating lives here rather than in the factory so a provider
built for one channel still refuses the other cleanly:
    send_sms      requires SMS_ENABLED + TWILIO_FROM_NUMBER
    send_whatsapp requires WHATSAPP_ENABLED + TWILIO_WHATSAPP_FROM

PHI note: never log message bodies or phone numbers — identifiers
(channel, status, Twilio message SID) only.
"""
import httpx
import structlog

from app.config import settings
from app.services.comms.base import CommResult

logger = structlog.get_logger()

TWILIO_API_BASE = "https://api.twilio.com/2010-04-01"

_TIMEOUT_SECONDS = 15.0


class TwilioProvider:
    """SMS + WhatsApp via the Twilio Messages API."""

    name = "twilio"

    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        from_number: str | None = None,
        whatsapp_from: str | None = None,
    ) -> None:
        self._account_sid = account_sid
        self._auth_token = auth_token
        self._from_number = from_number
        self._whatsapp_from = whatsapp_from

    async def send_sms(self, to_e164: str, body: str) -> CommResult:
        if not settings.SMS_ENABLED:
            return self._skipped("sms", "channel_disabled")
        if not self._from_number:
            return self._skipped("sms", "provider_not_configured")
        return await self._post_message(
            channel="sms", to=to_e164, from_=self._from_number, body=body
        )

    async def send_whatsapp(self, to_e164: str, template_or_body: str) -> CommResult:
        if not settings.WHATSAPP_ENABLED:
            return self._skipped("whatsapp", "channel_disabled")
        if not self._whatsapp_from:
            return self._skipped("whatsapp", "provider_not_configured")
        # Twilio addresses WhatsApp endpoints with the `whatsapp:` scheme on
        # both From and To; the sender must be a WhatsApp-enabled number.
        return await self._post_message(
            channel="whatsapp",
            to=f"whatsapp:{to_e164}",
            from_=f"whatsapp:{self._whatsapp_from}",
            body=template_or_body,
        )

    def _skipped(self, channel: str, reason: str) -> CommResult:
        logger.info(
            "comm_send_skipped", channel=channel, provider=self.name, reason=reason
        )
        return CommResult(channel=channel, status="skipped", reason=reason)

    async def _post_message(
        self, *, channel: str, to: str, from_: str, body: str
    ) -> CommResult:
        url = f"{TWILIO_API_BASE}/Accounts/{self._account_sid}/Messages.json"
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
                resp = await client.post(
                    url,
                    data={"To": to, "From": from_, "Body": body},
                    auth=(self._account_sid, self._auth_token),
                )
            if resp.status_code >= 400:
                logger.warning(
                    "comm_provider_http_error",
                    channel=channel,
                    provider=self.name,
                    status_code=resp.status_code,
                )
                return CommResult(
                    channel=channel,
                    status="failed",
                    reason=f"provider_http_{resp.status_code}",
                )
            message_sid: str | None = None
            try:
                message_sid = resp.json().get("sid")
            except Exception:
                message_sid = None
            return CommResult(
                channel=channel, status="sent", provider_message_id=message_sid
            )
        except Exception as exc:
            logger.error(
                "comm_send_failed",
                channel=channel,
                provider=self.name,
                error=str(exc),
                exc_info=True,
            )
            return CommResult(channel=channel, status="failed", reason="send_error")
