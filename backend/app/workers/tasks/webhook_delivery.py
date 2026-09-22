"""Outbound webhook delivery task executed by the ARQ worker.

``deliver_webhook`` POSTs a delivery's stored payload to its endpoint with an
HMAC-SHA256 signature header:

    X-MedConnect-Signature: sha256=<hex HMAC of raw request body, key=secret>
    X-MedConnect-Event: <event_type>

Retries up to ``settings.WEBHOOK_MAX_ATTEMPTS`` (default 3) with exponential
backoff inside the job, 5s request timeout (``WEBHOOK_TIMEOUT_SECONDS``), then
marks the delivery ``sent`` or ``failed``.

Testability seam: ``_new_http_client`` is monkeypatched in tests to return an
``httpx.AsyncClient`` backed by ``httpx.MockTransport``.
"""
import asyncio
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.webhook import WebhookDelivery, WebhookEndpoint

logger = structlog.get_logger()

# Backoff between attempts: BASE, BASE*2, ... (attempts beyond MAX sleep none).
BACKOFF_BASE_SECONDS = 1.0


def sign_payload(secret: str, body: bytes) -> str:
    """Return the ``X-MedConnect-Signature`` header value for a request body."""
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _new_http_client() -> httpx.AsyncClient:
    """Build the delivery HTTP client — seam for tests (httpx.MockTransport)."""
    return httpx.AsyncClient(timeout=httpx.Timeout(settings.WEBHOOK_TIMEOUT_SECONDS))


async def deliver_webhook(ctx: dict, delivery_id: str) -> None:
    """
    ARQ task: deliver one webhook delivery row.

    Args:
        ctx: ARQ worker context dict; must contain 'db_session_factory'.
        delivery_id: UUID string of the webhook_deliveries row.
    """
    session_factory = ctx["db_session_factory"]

    async with session_factory() as db:
        try:
            await _process_delivery(db, delivery_id)
        except Exception as exc:
            logger.error(
                "webhook_task_failed",
                delivery_id=delivery_id,
                error=str(exc),
                exc_info=True,
            )
            raise


async def _process_delivery(db: AsyncSession, delivery_id: str) -> None:
    """Load the delivery + endpoint, attempt the POST, persist the outcome."""
    result = await db.execute(
        select(WebhookDelivery, WebhookEndpoint)
        .join(WebhookEndpoint, WebhookDelivery.endpoint_id == WebhookEndpoint.id)
        .where(WebhookDelivery.id == uuid.UUID(delivery_id))
    )
    row = result.first()
    if row is None:
        logger.warning("webhook_skipped_delivery_not_found", delivery_id=delivery_id)
        return
    delivery, endpoint = row

    # Idempotent re-delivery: an already-sent row is left untouched.
    if delivery.status == "sent":
        logger.info("webhook_skipped_already_sent", delivery_id=delivery_id)
        return

    if endpoint.deleted_at is not None or not endpoint.is_active:
        delivery.status = "failed"
        delivery.last_error = "endpoint deactivated"
        await db.commit()
        logger.info("webhook_skipped_endpoint_inactive", delivery_id=delivery_id)
        return

    # Deterministic serialization — the signature covers exactly these bytes.
    body = json.dumps(
        delivery.payload_json, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-MedConnect-Signature": sign_payload(endpoint.secret, body),
        "X-MedConnect-Event": delivery.event_type,
    }

    max_attempts = max(1, settings.WEBHOOK_MAX_ATTEMPTS)
    async with _new_http_client() as client:
        for attempt in range(1, max_attempts + 1):
            try:
                resp = await client.post(endpoint.url, content=body, headers=headers)
                if 200 <= resp.status_code < 300:
                    delivery.status = "sent"
                    delivery.attempts = attempt
                    delivery.delivered_at = datetime.now(timezone.utc)
                    delivery.last_error = None
                    await db.commit()
                    logger.info(
                        "webhook_delivered",
                        delivery_id=delivery_id,
                        endpoint_id=str(endpoint.id),
                        attempts=attempt,
                    )
                    return
                delivery.last_error = f"HTTP {resp.status_code}"
            except Exception as exc:
                delivery.last_error = f"{type(exc).__name__}: {exc}"
            delivery.attempts = attempt
            if attempt < max_attempts:
                await asyncio.sleep(BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)))

    delivery.status = "failed"
    await db.commit()
    logger.warning(
        "webhook_delivery_failed",
        delivery_id=delivery_id,
        endpoint_id=str(endpoint.id),
        attempts=delivery.attempts,
        last_error=delivery.last_error,
    )
