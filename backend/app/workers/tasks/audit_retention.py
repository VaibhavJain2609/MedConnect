"""
Audit-log retention — daily ARQ cron task.

Copies ``audit_logs`` rows older than ``settings.AUDIT_RETENTION_DAYS`` into
``audit_log_archive`` (append-only cold storage), then deletes them from the
live table. Each batch of ``BATCH_SIZE`` rows is archived+deleted in its own
transaction — a multi-million-row backlog never becomes one giant DELETE or
one giant commit.

Idempotency: the archive insert uses ``ON CONFLICT DO NOTHING`` on the
primary key, so a re-run after a mid-run crash cannot duplicate archived
rows; rows already deleted are simply not re-selected.

Set ``AUDIT_RETENTION_DAYS=0`` to disable retention entirely (keep forever).

PHI note: logs carry identifiers and counts only — never old/new values.
"""
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import settings
from app.models.audit import AuditLog, AuditLogArchive

logger = structlog.get_logger()

# Rows copied+deleted per transaction — never one giant DELETE.
BATCH_SIZE = 1000
# Bound a single run (100 batches × 1000 = 100k rows); a bigger backlog is
# drained over subsequent daily runs instead of holding the worker hostage.
MAX_BATCHES_PER_RUN = 100

# Columns copied verbatim into audit_log_archive. ``archived_at`` is omitted
# on purpose — its server_default (now()) stamps the archive time.
_ARCHIVE_COPY_COLUMNS = [
    "id",
    "table_name",
    "record_id",
    "action",
    "changed_by",
    "changed_at",
    "old_values",
    "new_values",
]


async def audit_retention(ctx: dict) -> None:
    """ARQ cron task: archive+delete audit_logs rows past the retention window.

    Args:
        ctx: ARQ worker context dict; must contain 'db_session_factory'.
    """
    retention_days = settings.AUDIT_RETENTION_DAYS
    if retention_days <= 0:
        logger.info("audit_retention_disabled", retention_days=retention_days)
        return

    session_factory = ctx["db_session_factory"]
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=retention_days)

    total_archived = 0
    batches = 0
    capped = False
    async with session_factory() as db:
        while True:
            if batches >= MAX_BATCHES_PER_RUN:
                capped = True
                break

            res = await db.execute(
                select(AuditLog.id)
                .where(AuditLog.changed_at < cutoff)
                .order_by(AuditLog.changed_at)
                .limit(BATCH_SIZE)
            )
            batch_ids = res.scalars().all()
            if not batch_ids:
                break

            # INSERT INTO audit_log_archive (cols) SELECT cols FROM audit_logs
            # WHERE id IN (batch) ON CONFLICT DO NOTHING — archived_at comes
            # from the column default.
            await db.execute(
                pg_insert(AuditLogArchive)
                .from_select(
                    _ARCHIVE_COPY_COLUMNS,
                    select(
                        *[getattr(AuditLog, c) for c in _ARCHIVE_COPY_COLUMNS]
                    ).where(AuditLog.id.in_(batch_ids)),
                )
                .on_conflict_do_nothing()
            )
            await db.execute(delete(AuditLog).where(AuditLog.id.in_(batch_ids)))
            await db.commit()

            total_archived += len(batch_ids)
            batches += 1
            if len(batch_ids) < BATCH_SIZE:
                break

    # Ids/counts only — no PHI (old/new values) in logs.
    logger.info(
        "audit_retention_run_complete",
        cutoff=cutoff.isoformat(),
        retention_days=retention_days,
        archived=total_archived,
        batches=batches,
        capped=capped,
    )
