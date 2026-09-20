"""
Scheduler helpers for enqueuing appointment reminder jobs.

Usage (from appointment creation endpoint):
    import asyncio
    from app.workers.scheduler import schedule_appointment_reminders
    asyncio.create_task(schedule_appointment_reminders(str(appointment.id), appointment.scheduled_at))
"""
import asyncio
from datetime import datetime, timedelta, timezone

import structlog
from arq.connections import ArqRedis, RedisSettings, create_pool

from app.config import settings

logger = structlog.get_logger()

# Shared ARQ pool — created lazily on first use and reused across calls so
# enqueueing a reminder doesn't pay a fresh connection handshake each time.
_redis_pool: ArqRedis | None = None
_pool_lock = asyncio.Lock()


async def _get_redis_pool() -> ArqRedis:
    global _redis_pool
    if _redis_pool is None:
        async with _pool_lock:
            if _redis_pool is None:
                _redis_pool = await create_pool(
                    RedisSettings.from_dsn(settings.REDIS_URL)
                )
    return _redis_pool


async def schedule_appointment_reminders(
    appointment_id: str,
    scheduled_at: datetime,
) -> None:
    """
    Enqueue 24h and 2h reminder jobs for an appointment.

    Jobs are deferred until:
        - 24h before scheduled_at
        - 2h before scheduled_at

    Each job uses a deterministic id (``rem:{appointment_id}:{hours}h``) so
    re-scheduling the same reminder is deduplicated by ARQ instead of
    creating duplicate jobs.

    Jobs in the past (i.e. scheduled_at < now + margin) are skipped silently.
    """
    now = datetime.now(tz=timezone.utc)

    if scheduled_at.tzinfo is None:
        scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)

    jobs = [
        (24, scheduled_at - timedelta(hours=24)),
        (2, scheduled_at - timedelta(hours=2)),
    ]

    try:
        redis = await _get_redis_pool()
        for hours_before, run_at in jobs:
            if run_at <= now:
                logger.info(
                    "reminder_skipped_past",
                    appointment_id=appointment_id,
                    hours_before=hours_before,
                )
                continue
            job = await redis.enqueue_job(
                "send_appointment_reminder",
                appointment_id,
                hours_before,
                _defer_until=run_at,
                _job_id=f"rem:{appointment_id}:{hours_before}h",
            )
            if job is None:
                logger.info(
                    "reminder_already_enqueued",
                    appointment_id=appointment_id,
                    hours_before=hours_before,
                )
            else:
                logger.info(
                    "reminder_scheduled",
                    appointment_id=appointment_id,
                    hours_before=hours_before,
                    run_at=run_at.isoformat(),
                )
    except Exception as exc:
        # Non-critical — log and continue so appointment creation is not blocked
        logger.error(
            "reminder_schedule_failed",
            appointment_id=appointment_id,
            error=str(exc),
        )
