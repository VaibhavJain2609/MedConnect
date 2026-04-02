"""
ARQ Worker for MedConnect reminder jobs.

Run with:
    arq app.workers.reminder_worker.WorkerSettings
"""
import structlog
from arq import cron
from arq.connections import RedisSettings

from app.config import settings
from app.workers.tasks.appointment_reminders import send_appointment_reminder

logger = structlog.get_logger()


async def startup(ctx: dict) -> None:
    """Create the DB session factory on worker startup."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    ctx["db_session_factory"] = async_sessionmaker(engine, expire_on_commit=False)
    logger.info("reminder_worker_started")


async def shutdown(ctx: dict) -> None:
    logger.info("reminder_worker_shutdown")


class WorkerSettings:
    functions = [send_appointment_reminder]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    max_jobs = 10
    job_timeout = 60  # seconds
    keep_result = 3600  # keep results for 1 hour
