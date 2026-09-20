"""
Notification channel dispatch abstraction.

`send()` routes a single notification to one delivery channel and returns a
`ChannelResult`; `enabled_channels()` / `channel_enabled()` read the user's
`NotificationPreferences` (JSONB `preferences` dict) to decide which channels
to attempt. The reminder worker writes one `ReminderLog` row per attempted
channel with the real `channel` value and a sent/failed/skipped status.

Channels:
    in_app   — writes a Notification row via notification_service (always
               available; the baseline channel — there is no preference key
               that disables it, only per-type opt-outs such as
               ``appointment_reminders`` which the caller checks).
    email    — SMTP via stdlib ``smtplib`` in ``asyncio.to_thread`` (no extra
               dependency). Requires ``SMTP_HOST`` + ``SMTP_FROM`` and a
               ``user.email``; unconfigured -> skipped(channel_unavailable).
    sms      — MSG91 provider stub, gated on ``MSG91_AUTH_KEY``. Real HTTP
               wiring lands later; the interface, preference lookup and
               availability checks are real.
    whatsapp — WhatsApp Business Cloud API stub, gated on ``WHATSAPP_*``
               settings. Same story as sms.

PHI note: never log message bodies, names, emails or phone numbers —
identifiers (user_id, channel, status) only.
"""
import asyncio
import smtplib
import ssl
import uuid
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Literal, Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.notification import NotificationPreferences, NotificationType
from app.models.user import User
from app.services import notification_service

logger = structlog.get_logger()

Channel = Literal["in_app", "email", "sms", "whatsapp"]

# Dispatch order — in_app first so the baseline notification lands even if an
# external channel misbehaves.
CHANNELS: tuple[str, ...] = ("in_app", "email", "sms", "whatsapp")

# NotificationPreferences.preferences keys gating each channel. ``in_app``
# intentionally has no key — it is the baseline channel and is only skipped
# when the caller honours a per-type opt-out (e.g. appointment_reminders).
CHANNEL_PREF_KEYS: dict[str, str] = {
    "email": "email_notifications",
    "sms": "sms_notifications",
    "whatsapp": "whatsapp_notifications",
}

ChannelStatus = Literal["sent", "failed", "skipped"]


@dataclass
class ChannelResult:
    """Outcome of a single channel attempt."""

    channel: str
    status: ChannelStatus
    reason: Optional[str] = None  # machine-readable: channel_unavailable, no_recipient, ...


async def get_preferences(user_id: uuid.UUID, *, db: AsyncSession) -> dict:
    """Load the user's NotificationPreferences dict ({} if no row exists)."""
    res = await db.execute(
        select(NotificationPreferences.preferences).where(
            NotificationPreferences.user_id == user_id
        )
    )
    return res.scalar_one_or_none() or {}


def channel_enabled(channel: str, prefs: dict) -> bool:
    """True if `prefs` allows `channel`. Missing keys default to enabled."""
    key = CHANNEL_PREF_KEYS.get(channel)
    if key is None:
        return True  # in_app — baseline channel, always enabled
    return bool(prefs.get(key, True))


async def enabled_channels(user: User, *, db: AsyncSession) -> list[str]:
    """Channels enabled for `user` per their stored preferences."""
    prefs = await get_preferences(user.id, db=db)
    return [c for c in CHANNELS if channel_enabled(c, prefs)]


async def send(
    user: User,
    kind: str,
    title: str,
    body: str,
    *,
    db: AsyncSession,
    notif_type: str = NotificationType.SYSTEM.value,
    action_url: Optional[str] = None,
    metadata: Optional[dict] = None,
    prefs: Optional[dict] = None,
) -> ChannelResult:
    """
    Send `title`/`body` to `user` over channel `kind`.

    Args:
        user: recipient User row (needs email/phone for external channels).
        kind: one of CHANNELS ("in_app" | "email" | "sms" | "whatsapp").
        title/body: rendered notification content.
        db: async session (used for prefs lookup and the in_app channel).
        notif_type/action_url/metadata: in_app-only extras forwarded to
            notification_service.create_notification.
        prefs: optional pre-fetched preferences dict; fetched when omitted.

    Returns:
        ChannelResult with status sent/failed/skipped — never raises for
        channel-level failures; infrastructure errors (DB) still propagate.
    """
    if kind not in CHANNELS:
        logger.warning(
            "notification_channel_unknown",
            channel=kind,
            user_id=str(user.id),
        )
        return ChannelResult(channel=kind, status="skipped", reason="unknown_channel")

    if prefs is None:
        prefs = await get_preferences(user.id, db=db)
    if not channel_enabled(kind, prefs):
        logger.info(
            "notification_channel_disabled_by_pref",
            channel=kind,
            user_id=str(user.id),
        )
        return ChannelResult(channel=kind, status="skipped", reason="channel_disabled")

    if kind == "in_app":
        return await _send_in_app(
            user,
            title,
            body,
            db=db,
            notif_type=notif_type,
            action_url=action_url,
            metadata=metadata,
        )
    if kind == "email":
        return await _send_email(user, title, body)
    if kind == "sms":
        return _send_sms(user, body)
    return _send_whatsapp(user, body)


async def send_all(
    user: User,
    channels: list[str],
    title: str,
    body: str,
    *,
    db: AsyncSession,
    **kwargs,
) -> list[ChannelResult]:
    """Send the same notification over several channels, in order."""
    results: list[ChannelResult] = []
    for channel in channels:
        results.append(await send(user, channel, title, body, db=db, **kwargs))
    return results


# ----------------------------------------------------------------------
# Channel implementations
# ----------------------------------------------------------------------


async def _send_in_app(
    user: User,
    title: str,
    body: str,
    *,
    db: AsyncSession,
    notif_type: str,
    action_url: Optional[str],
    metadata: Optional[dict],
) -> ChannelResult:
    """In-app notification — a row in the notifications table."""
    try:
        await notification_service.create_notification(
            db,
            user_id=user.id,
            notif_type=notif_type,
            title=title,
            body=body,
            action_url=action_url,
            metadata=metadata,
        )
        return ChannelResult(channel="in_app", status="sent")
    except Exception as exc:
        logger.error(
            "notification_channel_failed",
            channel="in_app",
            user_id=str(user.id),
            error=str(exc),
            exc_info=True,
        )
        return ChannelResult(channel="in_app", status="failed", reason="send_error")


def _smtp_send(msg: EmailMessage) -> None:
    """Blocking SMTP send — run via asyncio.to_thread."""
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
        smtp.ehlo()
        if settings.SMTP_TLS:
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()
        if settings.SMTP_USER:
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD or "")
        smtp.send_message(msg)


async def _send_email(user: User, title: str, body: str) -> ChannelResult:
    """Email via SMTP (stdlib smtplib offloaded to a worker thread)."""
    if not settings.SMTP_HOST or not settings.SMTP_FROM:
        logger.info(
            "notification_channel_not_configured",
            channel="email",
            user_id=str(user.id),
        )
        return ChannelResult(channel="email", status="skipped", reason="channel_unavailable")
    if not user.email:
        logger.info(
            "notification_channel_no_recipient",
            channel="email",
            user_id=str(user.id),
        )
        return ChannelResult(channel="email", status="skipped", reason="no_recipient")

    msg = EmailMessage()
    msg["From"] = settings.SMTP_FROM
    msg["To"] = user.email
    msg["Subject"] = title
    msg.set_content(body)

    try:
        await asyncio.to_thread(_smtp_send, msg)
        return ChannelResult(channel="email", status="sent")
    except Exception as exc:
        logger.error(
            "notification_channel_failed",
            channel="email",
            user_id=str(user.id),
            error=str(exc),
            exc_info=True,
        )
        return ChannelResult(channel="email", status="failed", reason="send_error")


def _send_sms(user: User, body: str) -> ChannelResult:
    """
    SMS via MSG91 — provider stub.

    Interface, preference gating and availability checks are real; the HTTP
    call (POST https://control.msg91.com/api/v5/flow/ with MSG91_AUTH_KEY +
    MSG91_TEMPLATE_ID) is intentionally not wired yet.
    """
    if not settings.MSG91_AUTH_KEY:
        logger.info(
            "notification_channel_not_configured",
            channel="sms",
            provider="msg91",
            user_id=str(user.id),
        )
        return ChannelResult(channel="sms", status="skipped", reason="channel_unavailable")
    if not user.phone:
        logger.info(
            "notification_channel_no_recipient",
            channel="sms",
            user_id=str(user.id),
        )
        return ChannelResult(channel="sms", status="skipped", reason="no_recipient")

    # TODO(msg91): implement flow API call once sender/template IDs are live.
    logger.info(
        "notification_channel_provider_stub",
        channel="sms",
        provider="msg91",
        user_id=str(user.id),
    )
    return ChannelResult(channel="sms", status="skipped", reason="provider_not_implemented")


def _send_whatsapp(user: User, body: str) -> ChannelResult:
    """
    WhatsApp via the Business Cloud API — provider stub.

    Gated on WHATSAPP_ACCESS_TOKEN + WHATSAPP_PHONE_NUMBER_ID; the Graph API
    call (POST /{phone_number_id}/messages) is intentionally not wired yet.
    """
    if not settings.WHATSAPP_ACCESS_TOKEN or not settings.WHATSAPP_PHONE_NUMBER_ID:
        logger.info(
            "notification_channel_not_configured",
            channel="whatsapp",
            provider="meta",
            user_id=str(user.id),
        )
        return ChannelResult(channel="whatsapp", status="skipped", reason="channel_unavailable")
    if not user.phone:
        logger.info(
            "notification_channel_no_recipient",
            channel="whatsapp",
            user_id=str(user.id),
        )
        return ChannelResult(channel="whatsapp", status="skipped", reason="no_recipient")

    # TODO(whatsapp): implement Graph API messages call with an approved template.
    logger.info(
        "notification_channel_provider_stub",
        channel="whatsapp",
        provider="meta",
        user_id=str(user.id),
    )
    return ChannelResult(channel="whatsapp", status="skipped", reason="provider_not_implemented")
