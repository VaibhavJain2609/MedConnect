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
from app.workers.tasks.prescription_expiry import check_prescription_expiry
from app.workers.tasks.webhook_delivery import deliver_webhook

logger = structlog.get_logger()


async def startup(ctx: dict) -> None:
    """Init Sentry (if configured) and create the DB session factory."""
    if settings.SENTRY_DSN:
        import sentry_sdk

        sentry_sdk.init(dsn=settings.SENTRY_DSN, traces_sample_rate=0.1)
        logger.info("sentry_initialized")

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    # statement_cache_size=0 is required when DATABASE_URL goes through
    # PgBouncer transaction pooling — mirrors app/database.py.
    connect_args = (
        {"statement_cache_size": 0} if settings.DB_TRANSACTION_POOLING else {}
    )
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)
    ctx["db_engine"] = engine
    ctx["db_session_factory"] = async_sessionmaker(engine, expire_on_commit=False)
    logger.info("reminder_worker_started")


async def shutdown(ctx: dict) -> None:
    """Dispose the DB engine so pooled connections are closed cleanly."""
    engine = ctx.get("db_engine")
    if engine is not None:
        await engine.dispose()
    logger.info("reminder_worker_shutdown")


_redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
# arq 0.26 maps conn_timeout onto redis-py's socket_connect_timeout; there is
# no separate socket_timeout field on RedisSettings in this version.
_redis_settings.conn_timeout = 5
_redis_settings.conn_retry_delay = 1
# arq's from_dsn ignores the ?ssl_cert_reqs= query param — ElastiCache uses an
# AWS-internal CA, so disable cert verification explicitly for rediss:// URLs.
if settings.REDIS_URL.startswith("rediss://"):
    _redis_settings.ssl_cert_reqs = "none"


class WorkerSettings:
    functions = [send_appointment_reminder, deliver_webhook]
    # Daily prescription-expiry sweep. arq cron uses the worker machine's
    # local time — containers run UTC, so hour=8 == 08:00 UTC. The explicit
    # timeout overrides job_timeout (60s): a 500-row sweep with external
    # channel sends needs more headroom.
    cron_jobs = [cron(check_prescription_expiry, hour=8, minute=0, timeout=300)]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = _redis_settings
    max_jobs = 10
    job_timeout = 60  # seconds
    keep_result = 3600  # keep results for 1 hour
    health_check_key = "arq:health:reminder-worker"
