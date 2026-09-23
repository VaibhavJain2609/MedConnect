"""Tests for audit-log retention: the daily ``audit_retention`` ARQ cron task
and GET /api/v1/admin/audit-logs/archived.

Task coverage:
* old rows are copied into audit_log_archive (with archived_at stamped) and
  deleted from the live table;
* rows inside the retention window are untouched;
* re-runs are idempotent (ON CONFLICT DO NOTHING + nothing left to select);
* AUDIT_RETENTION_DAYS=0 disables the sweep entirely;
* rows move in BATCH_SIZE transactions, not one giant DELETE.

Endpoint coverage: archived rows are listed with the same filters/pagination
as the live list, live rows never leak in, and access is admin-only.

The task is invoked directly with the conftest session factory — it is a
plain coroutine that only needs ``ctx["db_session_factory"]``.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog, AuditLogArchive
from app.models.user import User
from app.workers.tasks import audit_retention as audit_retention_module
from app.workers.tasks.audit_retention import audit_retention
from tests.conftest import test_session

ARCHIVED_URL = "/api/v1/admin/audit-logs/archived"
LIVE_URL = "/api/v1/admin/audit"

# Default retention is 365d — anything older is archival-eligible.
_OLD_AGE_DAYS = 400


def _worker_ctx() -> dict:
    """ARQ ctx stand-in — the task only reads ``db_session_factory``."""
    return {"db_session_factory": test_session}


def _log(
    changed_at: datetime,
    table_name: str = "users",
    action: str = "UPDATE",
    changed_by: uuid.UUID | None = None,
    new_values: dict | None = None,
) -> AuditLog:
    return AuditLog(
        id=uuid.uuid4(),
        table_name=table_name,
        record_id=uuid.uuid4(),
        action=action,
        changed_by=changed_by,
        changed_at=changed_at,
        old_values=None,
        new_values=new_values,
    )


def _archive_row(log: AuditLog) -> AuditLogArchive:
    return AuditLogArchive(
        id=log.id,
        table_name=log.table_name,
        record_id=log.record_id,
        action=log.action,
        changed_by=log.changed_by,
        changed_at=log.changed_at,
        old_values=log.old_values,
        new_values=log.new_values,
    )


async def _count(db: AsyncSession, model) -> int:
    return await db.scalar(select(func.count()).select_from(model)) or 0


async def _old_log(
    db: AsyncSession, table_name: str = "users", **kwargs
) -> AuditLog:
    log = _log(
        changed_at=datetime.now(timezone.utc) - timedelta(days=_OLD_AGE_DAYS),
        table_name=table_name,
        **kwargs,
    )
    db.add(log)
    await db.commit()
    return log


# ---------------------------------------------------------------------------
# Retention task
# ---------------------------------------------------------------------------


async def test_archives_and_deletes_old_rows(db: AsyncSession, admin_user: User):
    old = await _old_log(db, changed_by=admin_user.id, new_values={"name": "x"})
    recent = _log(changed_at=datetime.now(timezone.utc))
    db.add(recent)
    await db.commit()

    await audit_retention(_worker_ctx())
    await db.commit()  # end read txn so subsequent SELECTs see the task's commits

    assert await _count(db, AuditLog) == 1
    assert await _count(db, AuditLogArchive) == 1

    archived = (
        await db.execute(select(AuditLogArchive))
    ).scalar_one()
    assert archived.id == old.id
    assert archived.table_name == old.table_name
    assert archived.record_id == old.record_id
    assert archived.action == old.action
    assert archived.changed_by == admin_user.id
    assert archived.changed_at == old.changed_at
    assert archived.new_values == {"name": "x"}
    assert archived.archived_at is not None

    remaining = (await db.execute(select(AuditLog))).scalar_one()
    assert remaining.id == recent.id


async def test_keeps_recent_rows(db: AsyncSession):
    for _ in range(3):
        db.add(_log(changed_at=datetime.now(timezone.utc)))
    # Just inside the window — 364 days < 365-day retention.
    db.add(
        _log(changed_at=datetime.now(timezone.utc) - timedelta(days=364))
    )
    await db.commit()

    await audit_retention(_worker_ctx())
    await db.commit()

    assert await _count(db, AuditLog) == 4
    assert await _count(db, AuditLogArchive) == 0


async def test_idempotent_rerun(db: AsyncSession):
    for _ in range(2):
        await _old_log(db)

    await audit_retention(_worker_ctx())
    await audit_retention(_worker_ctx())
    await db.commit()

    assert await _count(db, AuditLog) == 0
    assert await _count(db, AuditLogArchive) == 2


async def test_retention_disabled_when_zero(db: AsyncSession, monkeypatch):
    """AUDIT_RETENTION_DAYS=0 means keep-forever — the sweep must no-op."""
    monkeypatch.setattr(
        audit_retention_module.settings, "AUDIT_RETENTION_DAYS", 0
    )
    await _old_log(db)

    await audit_retention(_worker_ctx())
    await db.commit()

    assert await _count(db, AuditLog) == 1
    assert await _count(db, AuditLogArchive) == 0


async def test_rows_move_in_batches(db: AsyncSession, monkeypatch):
    """Batching: shrink BATCH_SIZE and verify all rows still move across
    multiple per-batch transactions."""
    monkeypatch.setattr(audit_retention_module, "BATCH_SIZE", 2)
    for _ in range(5):
        await _old_log(db)

    await audit_retention(_worker_ctx())
    await db.commit()

    assert await _count(db, AuditLog) == 0
    assert await _count(db, AuditLogArchive) == 5


async def test_max_batches_cap_leaves_remainder(db: AsyncSession, monkeypatch):
    """A run stops after MAX_BATCHES_PER_RUN batches; the rest drains on
    subsequent runs."""
    monkeypatch.setattr(audit_retention_module, "BATCH_SIZE", 1)
    monkeypatch.setattr(audit_retention_module, "MAX_BATCHES_PER_RUN", 2)
    for _ in range(5):
        await _old_log(db)

    await audit_retention(_worker_ctx())
    await db.commit()

    assert await _count(db, AuditLogArchive) == 2
    assert await _count(db, AuditLog) == 3


# ---------------------------------------------------------------------------
# Archived-logs endpoint
# ---------------------------------------------------------------------------


async def test_archived_endpoint_lists_archive_rows(
    db: AsyncSession, admin_client, admin_user: User
):
    archived = _archive_row(await _old_log(db, changed_by=admin_user.id))
    # Remove from the live table to mirror post-sweep state, keep a live row
    # that must NOT appear in the archived list.
    live_only = _log(changed_at=datetime.now(timezone.utc))
    db.add_all([archived, live_only])
    await db.delete(await db.get(AuditLog, archived.id))
    await db.commit()

    resp = await admin_client.get(ARCHIVED_URL)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    row = body["data"][0]
    assert row["id"] == str(archived.id)
    assert row["archived_at"] is not None
    assert row["changed_by_name"] == admin_user.full_name

    # The live list shows only the live row, and archived_at is null there.
    live_resp = await admin_client.get(LIVE_URL)
    assert live_resp.status_code == 200
    live_body = live_resp.json()
    assert live_body["total"] == 1
    assert live_body["data"][0]["id"] == str(live_only.id)
    assert live_body["data"][0]["archived_at"] is None


async def test_archived_endpoint_table_name_filter(
    db: AsyncSession, admin_client
):
    users_log = _archive_row(await _old_log(db, table_name="users"))
    rx_log = _archive_row(await _old_log(db, table_name="prescriptions"))
    db.add_all([users_log, rx_log])
    await db.delete(await db.get(AuditLog, users_log.id))
    await db.delete(await db.get(AuditLog, rx_log.id))
    await db.commit()

    resp = await admin_client.get(
        ARCHIVED_URL, params={"table_name": "prescriptions"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["data"][0]["table_name"] == "prescriptions"


async def test_archived_endpoint_pagination(db: AsyncSession, admin_client):
    logs = []
    for _ in range(3):
        live = await _old_log(db)
        logs.append(_archive_row(live))
        await db.delete(await db.get(AuditLog, live.id))
    db.add_all(logs)
    await db.commit()

    resp = await admin_client.get(ARCHIVED_URL, params={"page": 2, "limit": 2})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert body["totalPages"] == 2
    assert len(body["data"]) == 1


async def test_archived_endpoint_non_admin_forbidden(patient_client):
    resp = await patient_client.get(ARCHIVED_URL)
    assert resp.status_code == 403


async def test_archived_endpoint_unauthenticated_401(client):
    resp = await client.get(ARCHIVED_URL)
    assert resp.status_code == 401
