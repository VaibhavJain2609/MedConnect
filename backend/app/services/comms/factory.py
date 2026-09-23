"""
Comm provider selection.

``get_comm_provider()`` picks the messaging backend for the process:

- ``SMS_ENABLED`` / ``WHATSAPP_ENABLED`` both False  -> ``NullProvider``
  (channel plumbing disabled — attempts are logged and skipped).
- Either flag on but Twilio credentials incomplete    -> ``NullProvider``
  (misconfiguration must not crash reminder runs; per-channel results are
  ``skipped(provider_not_configured)``).
- Flag(s) on + TWILIO_ACCOUNT_SID + TWILIO_AUTH_TOKEN -> ``TwilioProvider``
  (per-channel gating still applies inside the provider: SMS needs
  SMS_ENABLED + TWILIO_FROM_NUMBER, WhatsApp needs WHATSAPP_ENABLED +
  TWILIO_WHATSAPP_FROM).

Adding another backend (MSG91, Meta Cloud API, etc.) means implementing
``CommProvider`` and extending the selection below — callers only ever
see the protocol.
"""
from app.config import settings
from app.services.comms.base import CommProvider
from app.services.comms.null_provider import NullProvider
from app.services.comms.twilio import TwilioProvider


def get_comm_provider() -> CommProvider:
    """Return the configured comm provider, or NullProvider when disabled."""
    if not (settings.SMS_ENABLED or settings.WHATSAPP_ENABLED):
        return NullProvider()
    if not (settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN):
        return NullProvider()
    return TwilioProvider(
        account_sid=settings.TWILIO_ACCOUNT_SID,
        auth_token=settings.TWILIO_AUTH_TOKEN,
        from_number=settings.TWILIO_FROM_NUMBER,
        whatsapp_from=settings.TWILIO_WHATSAPP_FROM,
    )
