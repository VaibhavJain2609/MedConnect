"""Tests for GET /api/v1/admin/audit-logs/export (CSV download).

The endpoint shares its filter logic with GET /api/v1/admin/audit via
_audit_filters; these tests cover the response shape, filter parity, the
50k-row cap, and the admin-only gate.
"""

import csv
import io
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.user import User

EXPORT_URL = "/api/v1/admin/audit-logs/export"

EXPECTED_HEADER = [
    "timestamp",
    "actor_id",
    "actor_name",
    "action",
    "table_name",
    "record_id",
    "old_values",
    "new_values",
]


def _parse_csv(resp) -> list[list[str]]:
    return list(csv.reader(io.StringIO(resp.text)))


def _log(
    table_name: str = "users",
    action: str = "UPDATE",
    changed_by: uuid.UUID | None = None,
    changed_at: datetime | None = None,
    old_values: dict | None = None,
    new_values: dict | None = None,
) -> AuditLog:
    return AuditLog(
        id=uuid.uuid4(),
        table_name=table_name,
        record_id=uuid.uuid4(),
        action=action,
        changed_by=changed_by,
        changed_at=changed_at or datetime.now(timezone.utc),
        old_values=old_values,
        new_values=new_values,
    )


class TestAuditLogsExport:
    async def test_csv_shape_headers_and_actor(
        self, admin_client, db: AsyncSession, admin_user: User
    ):
        db.add(_log(changed_by=admin_user.id, new_values={"email": "a@b.c"}))
        db.add(_log(table_name="prescriptions", action="INSERT"))
        await db.commit()

        resp = await admin_client.get(EXPORT_URL)
        assert resp.status_code == 200, resp.text
        assert resp.headers["content-type"].startswith("text/csv")
        disposition = resp.headers["content-disposition"]
        assert "attachment" in disposition
        assert "audit-logs-" in disposition and disposition.endswith('.csv"')

        rows = _parse_csv(resp)
        assert rows[0] == EXPECTED_HEADER

        data = rows[1:]
        assert len(data) == 2
        by_table = {r[4]: r for r in data}

        # Actor column carries the user id + joined full name.
        users_row = by_table["users"]
        assert users_row[1] == str(admin_user.id)
        assert users_row[2] == "Admin User"
        assert users_row[3] == "UPDATE"
        # Compact JSON serialization of new_values.
        assert users_row[7] == '{"email":"a@b.c"}'

        # No changed_by → "System" actor with blank id.
        rx_row = by_table["prescriptions"]
        assert rx_row[1] == ""
        assert rx_row[2] == "System"

    async def test_table_name_filter_limits_rows(
        self, admin_client, db: AsyncSession, admin_user: User
    ):
        db.add(_log(table_name="users"))
        db.add(_log(table_name="users"))
        db.add(_log(table_name="prescriptions"))
        await db.commit()

        resp = await admin_client.get(f"{EXPORT_URL}?table_name=users")
        assert resp.status_code == 200
        rows = _parse_csv(resp)[1:]
        assert len(rows) == 2
        assert all(r[4] == "users" for r in rows)

    async def test_changed_by_name_filter(
        self, admin_client, db: AsyncSession, admin_user: User
    ):
        db.add(_log(changed_by=admin_user.id))
        db.add(_log())  # system change — no actor
        await db.commit()

        resp = await admin_client.get(f"{EXPORT_URL}?changed_by_name=Admin")
        assert resp.status_code == 200
        rows = _parse_csv(resp)[1:]
        assert len(rows) == 1
        assert rows[0][2] == "Admin User"

    async def test_date_range_filter(
        self, admin_client, db: AsyncSession
    ):
        now = datetime.now(timezone.utc)
        db.add(_log(table_name="users", changed_at=now - timedelta(days=10)))
        db.add(_log(table_name="users", changed_at=now))
        await db.commit()

        from_date = (now - timedelta(days=1)).isoformat()
        # params= URL-encodes the "+" in the +00:00 tz offset.
        resp = await admin_client.get(EXPORT_URL, params={"from_date": from_date})
        assert resp.status_code == 200
        rows = _parse_csv(resp)[1:]
        assert len(rows) == 1

    async def test_newest_first_ordering(
        self, admin_client, db: AsyncSession
    ):
        now = datetime.now(timezone.utc)
        oldest = _log(table_name="users", changed_at=now - timedelta(hours=2))
        newest = _log(table_name="users", changed_at=now)
        db.add(oldest)
        db.add(newest)
        await db.commit()

        resp = await admin_client.get(EXPORT_URL)
        rows = _parse_csv(resp)[1:]
        assert rows[0][5] == str(newest.record_id)
        assert rows[-1][5] == str(oldest.record_id)

    async def test_json_cells_truncated(
        self, admin_client, db: AsyncSession
    ):
        big = {"notes": "x" * 5000}
        db.add(_log(new_values=big))
        await db.commit()

        resp = await admin_client.get(EXPORT_URL)
        rows = _parse_csv(resp)[1:]
        cell = rows[0][7]
        assert len(cell) <= 501  # 500 chars + ellipsis marker
        assert cell.endswith("…")

    async def test_export_writes_audit_row(
        self, admin_client, db: AsyncSession
    ):
        resp = await admin_client.get(EXPORT_URL)
        assert resp.status_code == 200
        logs = (
            await db.execute(
                select(AuditLog).where(
                    AuditLog.action == "EXPORT",
                    AuditLog.table_name == "audit_logs",
                )
            )
        ).scalars().all()
        assert len(logs) >= 1
        assert "row_count" in (logs[0].new_values or {})

    async def test_row_cap_respected(
        self, admin_client, db: AsyncSession, monkeypatch
    ):
        for _ in range(3):
            db.add(_log())
        await db.commit()

        monkeypatch.setattr("app.routers.admin.audit._EXPORT_MAX_ROWS", 2)
        resp = await admin_client.get(EXPORT_URL)
        assert resp.status_code == 200
        assert len(_parse_csv(resp)) == 1 + 2  # header + capped rows

    async def test_non_admin_forbidden(self, patient_client):
        resp = await patient_client.get(EXPORT_URL)
        assert resp.status_code == 403

    async def test_unauthenticated_401(self, client):
        resp = await client.get(EXPORT_URL)
        assert resp.status_code == 401
