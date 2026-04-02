"""
Scheduler helpers for enqueuing appointment reminder jobs.

Usage (from appointment creation endpoint):
    import asyncio
    from app.workers.scheduler import schedule_appointment_reminders
    asyncio.create_task(schedule_appointment_reminders(str(appointment.id), appointment.scheduled_at))
"""
import structlog
from arq.connections import ArqRedis, RedisSettings, create_pool
from datetime import datetime, timedelta, timezone

from app.config import settings

logger = structlog.get_logger()


async def schedule_appointment_reminders(
    appointment_id: str,
    scheduled_at: datetime,
) -> None:
    """
    Enqueue 24h and 2h reminder jobs for an appointment.

    Jobs are deferred until:
        - 24h before scheduled_at
        - 2h before scheduled_at

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
        redis: ArqRedis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        for hours_before, run_at in jobs:
            if run_at <= now:
                logger.info(
                    "reminder_skipped_past",
                    appointment_id=appointment_id,
                    hours_before=hours_before,
                )
                continue
            await redis.enqueue_job(
                "send_appointment_reminder",
                appointment_id,
                hours_before,
                _defer_until=run_at,
            )
            logger.info(
                "reminder_scheduled",
                appointment_id=appointment_id,
                hours_before=hours_before,
                run_at=run_at.isoformat(),
            )
        await redis.aclose()
    except Exception as exc:
        # Non-critical — log and continue so appointment creation is not blocked
        logger.error(
            "reminder_schedule_failed",
            appointment_id=appointment_id,
            error=str(exc),
        )
