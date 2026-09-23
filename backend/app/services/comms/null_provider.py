"""
NullProvider — the default comm backend.

Selected by ``get_comm_provider()`` when the SMS/WhatsApp feature flags are
off or no provider credentials exist. Every call is logged (identifiers
only — never the body or the recipient number) and returns
``skipped(provider_not_configured)`` so reminder runs record a real
per-channel outcome instead of silently dropping the send.
"""
import structlog

from app.services.comms.base import CommResult

logger = structlog.get_logger()


class NullProvider:
    """No-op comm provider — logs the attempt, always returns skipped."""

    name = "null"

    async def send_sms(self, to_e164: str, body: str) -> CommResult:
        logger.info("comm_provider_not_configured", channel="sms", provider=self.name)
        return CommResult(
            channel="sms", status="skipped", reason="provider_not_configured"
        )

    async def send_whatsapp(self, to_e164: str, template_or_body: str) -> CommResult:
        logger.info(
            "comm_provider_not_configured", channel="whatsapp", provider=self.name
        )
        return CommResult(
            channel="whatsapp", status="skipped", reason="provider_not_configured"
        )
