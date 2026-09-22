"""Outbound webhook fan-out — ``emit_event`` queues deliveries via ARQ.

Flow:
    API call site → emit_event(db, clinic_id, event_type, payload)
        → one ``webhook_deliveries`` row per matching active endpoint
        → one ARQ ``deliver_webhook`` job per delivery
    ARQ worker → app.workers.tasks.webhook_delivery.deliver_webhook
        → POST payload with X-MedConnect-Signature HMAC header.

Feature flag: ``settings.WEBHOOKS_ENABLED`` (default False) — when off,
``emit_event`` is a no-op (no rows, no jobs).

PHI minimization: payloads must carry IDs, statuses and timestamps ONLY —
never names, diagnoses, notes or other free text. Enforced by convention at
the emit call sites; see RUNBOOK.md § webhooks.
"""
import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.webhook import WebhookDelivery, WebhookEndpoint

logger = structlog.get_logger()


async def emit_event(
    db: AsyncSession,
    clinic_id: uuid.UUID | str | None,
    event_type: str,
    payload: dict,
) -> int:
    """Fan out a clinic-scoped event to all subscribed active endpoints.

    Creates one pending ``WebhookDelivery`` per matching endpoint and enqueues
    an ARQ ``deliver_webhook`` job for each. Returns the number of jobs queued.

    May raise — call sites must use ``emit_event_safe`` (or their own
    try/except) so webhook failures can never break the API path.
    """
    if not settings.WEBHOOKS_ENABLED:
        return 0
    if clinic_id is None:
        return 0

    cid = uuid.UUID(str(clinic_id))
    result = await db.execute(
        select(WebhookEndpoint).where(
            WebhookEndpoint.clinic_id == cid,
            WebhookEndpoint.is_active.is_(True),
            WebhookEndpoint.deleted_at.is_(None),
            WebhookEndpoint.event_types.any(event_type),
        )
    )
    endpoints = result.scalars().all()
    if not endpoints:
        return 0

    # Shared ARQ pool from the reminder scheduler — one Redis connection per
    # process for all enqueue paths.
    from app.workers import scheduler

    redis = await scheduler._get_redis_pool()

    queued = 0
    for endpoint in endpoints:
        delivery = WebhookDelivery(
            endpoint_id=endpoint.id,
            event_type=event_type,
            payload_json={
                "event_type": event_type,
                "clinic_id": str(cid),
                **payload,
            },
            status="pending",
            attempts=0,
        )
        db.add(delivery)
        await db.flush()
        try:
            # Per-delivery try: a failed enqueue must not skip the remaining
            # endpoints (the row stays 'pending' for debugging/replay).
            await redis.enqueue_job("deliver_webhook", str(delivery.id))
            queued += 1
        except Exception as exc:
            logger.error(
                "webhook_enqueue_failed",
                delivery_id=str(delivery.id),
                endpoint_id=str(endpoint.id),
                error=str(exc),
            )
    logger.info(
        "webhook_event_emitted",
        clinic_id=str(cid),
        event_type=event_type,
        endpoints=len(endpoints),
        queued=queued,
    )
    return queued


async def emit_event_safe(
    db: AsyncSession,
    clinic_id: uuid.UUID | str | None,
    event_type: str,
    payload: dict,
) -> int:
    """Fire-and-forget wrapper — never raises; logs and returns 0 on failure.

    Use this at API call sites: webhook dispatch must never break booking,
    status transitions or prescription issuance.
    """
    try:
        return await emit_event(db, clinic_id, event_type, payload)
    except Exception as exc:
        logger.error(
            "webhook_emit_failed",
            clinic_id=str(clinic_id),
            event_type=event_type,
            error=str(exc),
            exc_info=True,
        )
        return 0
