"""Tests for health/metrics endpoints — r11 coverage.

There is no routers/health_metrics.py; the health surface lives in:
  - app/main.py:            GET /livez, GET /health, GET /metrics (Instrumentator)
  - app/routers/admin/health.py: GET /api/v1/admin/system/status (admin-only)

Both /health and /admin/system/status probe ``app.database.async_session``
directly (not the get_db dependency), so tests patch those session factories
to exercise the healthy and degraded paths deterministically.
"""
import pytest
from httpx import AsyncClient

import app.database
import app.routers.admin.health as admin_health
from tests import conftest as _conftest

# Aliased without a ``test_`` prefix so pytest doesn't try to collect the
# sessionmakers as test functions.
main_session_factory = _conftest.test_session
medicine_session_factory = _conftest.test_medicine_session

pytestmark = pytest.mark.asyncio


class _FailingSession:
    """Session-factory stand-in whose __aenter__ raises (DB unreachable)."""

    async def __aenter__(self):
        raise ConnectionError("db unreachable")

    async def __aexit__(self, *exc):
        return False


def _failing_factory():
    return _FailingSession()


# ---------------------------------------------------------------------------
# Probes
# ---------------------------------------------------------------------------


@pytest.mark.smoke
async def test_livez(client: AsyncClient):
    """Shallow liveness: always 200, no dependency checks."""
    resp = await client.get("/livez")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_metrics_endpoint_exposes_prometheus(client: AsyncClient):
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "# HELP" in resp.text


async def test_health_ok_when_all_dependencies_up(
    client: AsyncClient, monkeypatch
):
    """With both DB session factories healthy (and fakeredis ping succeeding
    via the conftest patch), /health reports ok/200."""
    monkeypatch.setattr(app.database, "async_session", main_session_factory)
    monkeypatch.setattr(app.database, "medicine_async_session", medicine_session_factory)

    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert body["medicine_db"] == "ok"
    assert body["redis"] == "ok"
    assert body["version"] == "0.1.0"


async def test_health_degraded_when_main_db_down(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(app.database, "async_session", _failing_factory)
    monkeypatch.setattr(app.database, "medicine_async_session", medicine_session_factory)

    resp = await client.get("/health")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["db"] == "error"
    assert body["medicine_db"] == "ok"
    assert body["redis"] == "ok"


async def test_health_degraded_when_medicine_db_down(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(app.database, "async_session", main_session_factory)
    monkeypatch.setattr(app.database, "medicine_async_session", _failing_factory)

    resp = await client.get("/health")
    assert resp.status_code == 503
    body = resp.json()
    assert body["db"] == "ok"
    assert body["medicine_db"] == "error"


@pytest.mark.smoke
async def test_health_never_requires_auth(client: AsyncClient):
    """The readiness probe is unauthenticated (load balancer hits it)."""
    resp = await client.get("/health")
    assert resp.status_code in (200, 503)
    body = resp.json()
    assert set(body.keys()) == {"status", "db", "medicine_db", "redis", "version"}
    # status flag is consistent with the per-dependency results
    all_ok = all(body[k] == "ok" for k in ("db", "medicine_db", "redis"))
    assert (body["status"] == "ok") == all_ok
    assert (resp.status_code == 200) == all_ok


# ---------------------------------------------------------------------------
# GET /api/v1/admin/system/status
# ---------------------------------------------------------------------------

STATUS_URL = "/api/v1/admin/system/status"


async def test_system_status_requires_auth(client: AsyncClient):
    resp = await client.get(STATUS_URL)
    assert resp.status_code == 401


async def test_system_status_requires_admin(patient_client: AsyncClient):
    resp = await patient_client.get(STATUS_URL)
    assert resp.status_code == 403


async def test_system_status_requires_admin_for_doctor(doctor_client: AsyncClient):
    resp = await doctor_client.get(STATUS_URL)
    assert resp.status_code == 403


async def test_system_status_happy_path(admin_client: AsyncClient, monkeypatch):
    """Both DBs healthy → status ok, counts populated from the test DB."""
    monkeypatch.setattr(admin_health, "async_session", main_session_factory)
    monkeypatch.setattr(admin_health, "medicine_async_session", medicine_session_factory)

    resp = await admin_client.get(STATUS_URL)
    assert resp.status_code == 200
    body = resp.json()

    assert body["status"] == "ok"
    assert body["version"] == "0.1.0"
    assert "checked_at" in body
    assert "started_at" in body
    assert body["uptime_seconds"] >= 0

    deps = body["dependencies"]
    assert set(deps.keys()) == {"db", "medicine_db", "redis"}
    assert deps["db"]["status"] == "ok"
    assert deps["medicine_db"]["status"] == "ok"
    assert deps["redis"]["status"] == "ok"  # fakeredis via conftest patch
    assert deps["db"]["latency_ms"] is not None

    # Entity counts from the test DB (admin user exists → users >= 1)
    counts = body["counts"]
    assert counts is not None
    assert counts["users"] >= 1
    assert set(counts.keys()) == {
        "users", "patients", "doctors", "clinics", "appointments_today"
    }

    # ARQ queue stats come from fakeredis (empty queues)
    queue = body["queue"]
    assert queue["pending"] == 0
    assert queue["deferred"] == 0
    assert queue["in_progress"] == 0
    assert queue["worker_last_heartbeat"] is None


async def test_system_status_degraded_when_db_down(
    admin_client: AsyncClient, monkeypatch
):
    """DB failure degrades overall status and suppresses counts — the
    endpoint still returns 200 with per-dependency detail."""
    monkeypatch.setattr(admin_health, "async_session", _failing_factory)
    monkeypatch.setattr(admin_health, "medicine_async_session", _failing_factory)

    resp = await admin_client.get(STATUS_URL)
    assert resp.status_code == 200
    body = resp.json()

    assert body["status"] == "degraded"
    assert body["dependencies"]["db"]["status"] == "error"
    assert body["dependencies"]["db"]["latency_ms"] is None
    assert body["dependencies"]["medicine_db"]["status"] == "error"
    assert body["dependencies"]["redis"]["status"] == "ok"
    # Counts are only collected when the main DB probe succeeds.
    assert body["counts"] is None
    assert body["last_audit_at"] is None
