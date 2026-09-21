"""
Web Push provider adapter — Push API via VAPID-signed requests (pywebpush).

Sends one encrypted push message per active ``PushSubscription`` row for the
recipient. ``pywebpush.webpush`` is synchronous (``requests`` under the hood),
so each send is offloaded with ``asyncio.to_thread`` — the same pattern the
email channel uses for ``smtplib``.

Settings:
    VAPID_SUBJECT     — contact URI embedded in the VAPID JWT ``sub`` claim
                        (``mailto:ops@example.com``). Unset ->
                        skipped(provider_not_configured).
    VAPID_PRIVATE_KEY — base64url VAPID private key. Unset -> skipped.
    VAPID_PUBLIC_KEY  — base64url public key; also served to browsers at
                        GET /api/v1/push/vapid-public so they can subscribe.

Generate a keypair with ``npx web-push generate-vapid-keys`` — never commit
keys. All three settings must be present for the channel to attempt delivery.

Payload contents: ``{"title": ..., "url": ...}`` — title and click-through URL
ONLY. The notification body is deliberately excluded: bodies can carry PHI
(patient/doctor names) and push payloads transit third-party push services
(Google FCM, Mozilla autopush, Apple APNs).

Dead endpoints: push services return 404/410 for expired subscriptions; those
rows are soft-deleted so later sends don't waste attempts on them.

PHI note: never log message bodies, endpoints or subscription keys —
identifiers (user_id, subscription count, status) only.
"""
import asyncio
import json
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.push_subscription import PushSubscription

logger = structlog.get_logger()

_TIMEOUT_SECONDS = 15.0

# Push-service responses that mean the subscription is permanently gone.
_GONE_STATUS_CODES = {404, 410}


def _deliver(subscription_info: dict, payload: str) -> int:
    """Blocking push send — run via asyncio.to_thread. Returns HTTP status."""
    from pywebpush import WebPushException, webpush

    try:
        resp = webpush(
            subscription_info=subscription_info,
            data=payload,
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={"sub": settings.VAPID_SUBJECT},
            timeout=_TIMEOUT_SECONDS,
        )
        return resp.status_code
    except WebPushException as exc:
        # Provider-level failure with an HTTP response (gone, auth rejected…)
        if exc.response is not None:
            return exc.response.status_code
        raise


async def send(
    user,
    title: str,
    url: str | None = None,
    *,
    db: AsyncSession,
):
    """
    Push `title` (+ click-through `url`) to every active subscription of `user`.

    Returns ChannelResult — sent when at least one endpoint accepted, skipped
    when VAPID is unconfigured or the user has no subscriptions, failed when
    every endpoint errored. Never raises for provider-level failures.
    """
    # Deferred import: providers must not import notification_channels at
    # module scope (it imports this package).
    from app.services.notification_channels import ChannelResult

    if not (
        settings.VAPID_SUBJECT
        and settings.VAPID_PRIVATE_KEY
        and settings.VAPID_PUBLIC_KEY
    ):
        logger.info(
            "notification_channel_not_configured",
            channel="push",
            provider="webpush",
            user_id=str(user.id),
        )
        return ChannelResult(
            channel="push", status="skipped", reason="provider_not_configured"
        )

    subs_res = await db.execute(
        select(PushSubscription).where(
            PushSubscription.user_id == user.id,
            PushSubscription.deleted_at.is_(None),
        )
    )
    subs = subs_res.scalars().all()
    if not subs:
        logger.info(
            "notification_channel_no_recipient",
            channel="push",
            provider="webpush",
            user_id=str(user.id),
        )
        return ChannelResult(channel="push", status="skipped", reason="no_recipient")

    # Payload is title + url only — never the body (see module docstring).
    payload = json.dumps({"title": title, "url": url or "/"})

    sent = 0
    for sub in subs:
        subscription_info = {
            "endpoint": sub.endpoint,
            "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
        }
        try:
            status_code = await asyncio.to_thread(
                _deliver, subscription_info, payload
            )
        except Exception as exc:
            logger.error(
                "notification_channel_failed",
                channel="push",
                provider="webpush",
                user_id=str(user.id),
                error=str(exc),
                exc_info=True,
            )
            continue

        if status_code in _GONE_STATUS_CODES:
            # Endpoint expired — soft-delete so future sends skip it.
            sub.deleted_at = datetime.now(tz=timezone.utc)
            logger.info(
                "push_subscription_gone",
                user_id=str(user.id),
                status_code=status_code,
            )
        elif status_code >= 400:
            logger.warning(
                "notification_channel_provider_http_error",
                channel="push",
                provider="webpush",
                user_id=str(user.id),
                status_code=status_code,
            )
        else:
            sent += 1

    if sent:
        return ChannelResult(channel="push", status="sent")
    return ChannelResult(channel="push", status="failed", reason="send_error")
