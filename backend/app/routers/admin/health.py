"""Admin-only system health & diagnostics.

GET /api/v1/admin/system/status — richer than the public /health probe:
per-dependency check latency, ARQ queue depth + worker heartbeat, entity
counts, last audit timestamp, and process uptime.

The public /health endpoint stays the load-balancer readiness probe; this
endpoint is what the admin System Health page renders.
"""
import asyncio
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text

from app.database import async_session, medicine_async_session
from app.dependencies import require_admin
from app.models.appointment import Appointment
from app.models.audit import AuditLog
from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.user import User

router = APIRouter(prefix="/api/v1/admin", tags=["admin", "system"])

_STARTED_AT = datetime.now(timezone.utc)
_STARTED_MONO = time.monotonic()

# ARQ 0.26 key layout: the queue itself is a list; deferred and in-progress
# jobs live in sorted sets; the worker periodically writes
# "<unix_ts> <job summary>" into its health_check_key.
_ARQ_QUEUE_KEY = "arq:queue"
_ARQ_DEFERRED_KEY = "arq:queue:deferred"
_ARQ_IN_PROGRESS_KEY = "arq:queue:in-progress"
_ARQ_WORKER_HEALTH_KEY = "arq:health:reminder-worker"


async def _probe(session_factory) -> tuple[bool, float | None]:
    """SELECT 1 against a session factory; return (ok, latency_ms)."""
    start = time.monotonic()
    try:
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
        return True, round((time.monotonic() - start) * 1000, 1)
    except Exception:
        return False, None


def _dep(ok: bool, latency_ms: float | None) -> dict:
    return {"status": "ok" if ok else "error", "latency_ms": latency_ms}


async def _collect_counts() -> dict:
    """Entity counts + last audit timestamp. Caller guarantees db is up."""
    today = datetime.now(timezone.utc).date()
    day_start = datetime.combine(today, datetime.min.time())
    day_end = day_start + timedelta(days=1)

    async with async_session() as db:
        users = await db.scalar(
            select(func.count()).select_from(User).where(User.deleted_at.is_(None))
        ) or 0
        patients = await db.scalar(
            select(func.count()).select_from(User).where(
                User.role == "patient",
                User.deleted_at.is_(None),
                User.is_active.is_(True),
            )
        ) or 0
        doctors = await db.scalar(
            select(func.count()).select_from(Doctor).where(Doctor.deleted_at.is_(None))
        ) or 0
        clinics = await db.scalar(
            select(func.count()).select_from(Clinic).where(Clinic.deleted_at.is_(None))
        ) or 0
        appointments_today = await db.scalar(
            select(func.count()).select_from(Appointment).where(
                Appointment.deleted_at.is_(None),
                Appointment.scheduled_at >= day_start,
                Appointment.scheduled_at < day_end,
            )
        ) or 0
        last_audit_at = await db.scalar(select(func.max(AuditLog.changed_at)))

    return {
        "counts": {
            "users": users,
            "patients": patients,
            "doctors": doctors,
            "clinics": clinics,
            "appointments_today": appointments_today,
        },
        "last_audit_at": last_audit_at.isoformat() if last_audit_at else None,
    }


@router.get("/system/status")
async def get_system_status(admin: User = Depends(require_admin)):
    """Deep system diagnostics for the admin System Health page."""
    from app.middleware.rate_limit import _get_redis

    db_ok, db_ms = await _probe(async_session)
    medicine_db_ok, medicine_db_ms = await _probe(medicine_async_session)

    redis_ok = False
    redis_ms = None
    queue = {"pending": None, "deferred": None, "in_progress": None}
    worker_last_heartbeat = None
    redis_client = None
    try:
        redis_client = _get_redis()
        start = time.monotonic()
        await redis_client.ping()
        redis_ok = True
        redis_ms = round((time.monotonic() - start) * 1000, 1)
    except Exception:
        redis_client = None

    if redis_client is not None:
        try:
            pending, deferred, in_progress, heartbeat = await asyncio.gather(
                redis_client.llen(_ARQ_QUEUE_KEY),
                redis_client.zcard(_ARQ_DEFERRED_KEY),
                redis_client.zcard(_ARQ_IN_PROGRESS_KEY),
                redis_client.get(_ARQ_WORKER_HEALTH_KEY),
            )
            queue = {
                "pending": pending,
                "deferred": deferred,
                "in_progress": in_progress,
            }
            if heartbeat:
                # arq writes "<unix_ts> <job summary>" — first token is the ts
                ts = float(str(heartbeat).split()[0])
                worker_last_heartbeat = datetime.fromtimestamp(
                    ts, tz=timezone.utc
                ).isoformat()
        except Exception:
            pass

    counts = None
    last_audit_at = None
    if db_ok:
        try:
            extra = await _collect_counts()
            counts = extra["counts"]
            last_audit_at = extra["last_audit_at"]
        except Exception:
            pass

    all_ok = db_ok and medicine_db_ok and redis_ok
    return {
        "status": "ok" if all_ok else "degraded",
        "version": "0.1.0",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "started_at": _STARTED_AT.isoformat(),
        "uptime_seconds": int(time.monotonic() - _STARTED_MONO),
        "dependencies": {
            "db": _dep(db_ok, db_ms),
            "medicine_db": _dep(medicine_db_ok, medicine_db_ms),
            "redis": _dep(redis_ok, redis_ms),
        },
        "queue": {**queue, "worker_last_heartbeat": worker_last_heartbeat},
        "counts": counts,
        "last_audit_at": last_audit_at,
    }
