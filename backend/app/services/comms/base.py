"""
Comm provider protocol and shared types.

A ``CommProvider`` is a messaging backend that can deliver an SMS and/or a
WhatsApp message to an E.164 phone number. Implementations own their
credential checks and HTTP plumbing; both methods return a ``CommResult``
and must never raise for provider-level failures (transport errors,
HTTP 4xx/5xx, missing configuration all map to failed/skipped results).
"""
import re
from dataclasses import dataclass
from typing import Literal, Optional, Protocol, runtime_checkable

CommStatus = Literal["sent", "failed", "skipped"]


@dataclass
class CommResult:
    """Outcome of a single SMS/WhatsApp send attempt."""

    channel: str  # "sms" | "whatsapp"
    status: CommStatus
    # Machine-readable reason for non-sent outcomes:
    # provider_not_configured, channel_disabled, no_recipient,
    # provider_http_<code>, send_error.
    reason: Optional[str] = None
    # Provider-side message identifier (e.g. Twilio SMxxx SID) — safe to
    # persist/log; it is not PHI.
    provider_message_id: Optional[str] = None


@runtime_checkable
class CommProvider(Protocol):
    """Messaging backend contract — SMS + WhatsApp over E.164 recipients."""

    async def send_sms(self, to_e164: str, body: str) -> CommResult:
        """Send a plain-text SMS. `to_e164` is the recipient in E.164 form."""
        ...

    async def send_whatsapp(self, to_e164: str, template_or_body: str) -> CommResult:
        """Send a WhatsApp message — a template name or body text depending
        on the provider's capabilities."""
        ...


def to_e164(phone: Optional[str]) -> Optional[str]:
    """
    Normalise a stored phone number to E.164-ish form (``+`` + digits).

    Returns ``None`` when the input has no dialable digits. Accepts numbers
    already carrying a ``+`` as well as bare digits (a leading ``+`` is
    added). Extension/separator characters (spaces, dashes, parentheses)
    are stripped.
    """
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if not digits:
        return None
    return f"+{digits}"
