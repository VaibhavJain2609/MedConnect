"""
Provider-agnostic SMS/WhatsApp comm adapters.

``CommProvider`` is the protocol every messaging backend implements —
``send_sms(to_e164, body)`` and ``send_whatsapp(to_e164, template_or_body)``
return a ``CommResult`` and never raise for provider-level failures.

``get_comm_provider()`` is the factory the channel dispatcher
(``app.services.notification_channels``) calls. It is driven by the
``SMS_ENABLED`` / ``WHATSAPP_ENABLED`` feature flags plus the ``TWILIO_*``
credentials: both default off, so the factory returns ``NullProvider``
(logs the attempt, returns ``skipped``) until a real account is wired in.
``TwilioProvider`` is the reference implementation (httpx only — no SDK).

This package deliberately knows nothing about ``User`` rows, preferences,
or ``ChannelResult`` — it takes an E.164 string and returns a neutral
result; the channel layer owns recipient lookup and result mapping.

PHI note: never log message bodies or phone numbers — identifiers
(channel, status) only.
"""
from app.services.comms.base import CommProvider, CommResult, to_e164
from app.services.comms.factory import get_comm_provider
from app.services.comms.null_provider import NullProvider
from app.services.comms.twilio import TwilioProvider

__all__ = [
    "CommProvider",
    "CommResult",
    "NullProvider",
    "TwilioProvider",
    "get_comm_provider",
    "to_e164",
]
