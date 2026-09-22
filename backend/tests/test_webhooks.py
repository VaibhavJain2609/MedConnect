"""Tests for outbound clinic webhooks.

Covers:
* ``webhook_service.emit_event`` — one pending delivery + one ARQ job per
  subscribed endpoint per event (no dedup), and a complete no-op when
  ``WEBHOOKS_ENABLED`` is False.
* ``webhook_delivery.deliver_webhook`` — retry on HTTP failure with the
  delivery row marked sent/failed, and the HMAC signature header.
* Clinic-admin CRUD — owner/admin membership required; secret is returned in
  full only at creation and masked ("whsec_****last4") everywhere else.

arq/Redis and outbound HTTP are fully mocked — no servers needed. HTTP calls
go through ``httpx.MockTransport`` via the ``_new_http_client`` seam.
"""
import hashlib
import hmac
import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.workers.scheduler as scheduler
import app.workers.tasks.webhook_delivery as webhook_delivery
from app.config import settings
from app.models.clinic import Clinic, ClinicMembership
from app.models.user import User
from app.models.webhook import WebhookDelivery, WebhookEndpoint
from app.services import webhook_service
from tests.conftest import create_test_token, test_session


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def clinic(db: AsyncSession) -> Clinic:
    c = Clinic(id=uuid.uuid4(), name="Webhook Clinic", city="Pune")
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


@pytest_asyncio.fixture
async def endpoint(db: AsyncSession, clinic: Clinic) -> WebhookEndpoint:
    ep = WebhookEndpoint(
        id=uuid.uuid4(),
        clinic_id=clinic.id,
        url="https://hooks.example.com/mc",
        secret="whsec_testsecret1234",
        event_types=["appointment.booked", "appointment.status_changed"],
        is_active=True,
    )
    db.add(ep)
    await db.commit()
    await db.refresh(ep)
    return ep


@pytest.fixture
def webhooks_on(monkeypatch):
    monkeypatch.setattr(settings, "WEBHOOKS_ENABLED", True)
    return settings


@pytest.fixture
def arq_redis(monkeypatch) -> AsyncMock:
    """Replace the shared ARQ pool with a mock ArqRedis."""
    redis = AsyncMock()
    redis.enqueue_job.return_value = MagicMock(name="arq-job")
    monkeypatch.setattr(scheduler, "_get_redis_pool", AsyncMock(return_value=redis))
    return redis


async def _make_user(db: AsyncSession, sub: str) -> User:
    u = User(
        id=uuid.uuid4(),
        keycloak_sub=sub,
        full_name=f"{sub} user",
        email=f"{sub}@test.com",
        role="doctor",
    )
    db.add(u)
    await db.commit()
    return u


async def _make_member(db: AsyncSession, clinic_id, role: str, sub: str) -> User:
    u = await _make_user(db, sub)
    m = ClinicMembership(
        id=uuid.uuid4(), clinic_id=clinic_id, user_id=u.id, role=role, is_active=True
    )
    db.add(m)
    await db.commit()
    return u


def _auth(client, user: User, roles=("doctor",)) -> None:
    token = create_test_token(
        sub=user.keycloak_sub, email=user.email, name=user.full_name, roles=list(roles)
    )
    client.headers["Authorization"] = f"Bearer {token}"


# ---------------------------------------------------------------------------
# emit_event
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_emit_creates_delivery_and_enqueues_per_event(
    db: AsyncSession, clinic: Clinic, endpoint: WebhookEndpoint, webhooks_on, arq_redis
):
    payload = {"appointment_id": str(uuid.uuid4()), "status": "scheduled"}
    n1 = await webhook_service.emit_event(db, clinic.id, "appointment.booked", payload)
    n2 = await webhook_service.emit_event(db, clinic.id, "appointment.booked", payload)
    assert n1 == 1 and n2 == 1  # no dedup — fires per event

    rows = (
        await db.execute(
            select(WebhookDelivery).where(WebhookDelivery.endpoint_id == endpoint.id)
        )
    ).scalars().all()
    assert len(rows) == 2
    assert all(r.status == "pending" and r.attempts == 0 for r in rows)
    assert rows[0].payload_json["event_type"] == "appointment.booked"
    assert rows[0].payload_json["clinic_id"] == str(clinic.id)
    assert arq_redis.enqueue_job.call_count == 2
    for call in arq_redis.enqueue_job.call_args_list:
        assert call.args[0] == "deliver_webhook"


@pytest.mark.asyncio
async def test_emit_skips_unsubscribed_and_inactive(
    db: AsyncSession, clinic: Clinic, endpoint: WebhookEndpoint, webhooks_on, arq_redis
):
    # Endpoint subscribes to appointment.* only — prescription.issued finds nothing
    assert await webhook_service.emit_event(db, clinic.id, "prescription.issued", {}) == 0
    arq_redis.enqueue_job.assert_not_called()

    endpoint.is_active = False
    await db.commit()
    assert await webhook_service.emit_event(db, clinic.id, "appointment.booked", {}) == 0
    arq_redis.enqueue_job.assert_not_called()


@pytest.mark.asyncio
async def test_emit_disabled_flag_noop(
    db: AsyncSession, clinic: Clinic, endpoint: WebhookEndpoint, monkeypatch
):
    monkeypatch.setattr(settings, "WEBHOOKS_ENABLED", False)
    pool_mock = AsyncMock()
    monkeypatch.setattr(scheduler, "_get_redis_pool", pool_mock)

    n = await webhook_service.emit_event(
        db, clinic.id, "appointment.booked", {"appointment_id": "x"}
    )
    assert n == 0
    pool_mock.assert_not_called()
    rows = (await db.execute(select(WebhookDelivery))).scalars().all()
    assert rows == []


# ---------------------------------------------------------------------------
# deliver_webhook task
# ---------------------------------------------------------------------------


async def _make_delivery(db: AsyncSession, endpoint: WebhookEndpoint) -> WebhookDelivery:
    d = WebhookDelivery(
        id=uuid.uuid4(),
        endpoint_id=endpoint.id,
        event_type="appointment.booked",
        payload_json={
            "event_type": "appointment.booked",
            "clinic_id": str(endpoint.clinic_id),
            "appointment_id": str(uuid.uuid4()),
        },
        status="pending",
        attempts=0,
    )
    db.add(d)
    await db.commit()
    await db.refresh(d)
    return d


def _patch_http(monkeypatch, handler):
    """Route the task's HTTP through an httpx.MockTransport handler."""
    monkeypatch.setattr(
        webhook_delivery,
        "_new_http_client",
        lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=5.0),
    )
    monkeypatch.setattr(webhook_delivery, "BACKOFF_BASE_SECONDS", 0)


@pytest.mark.asyncio
async def test_delivery_retries_then_succeeds(
    db: AsyncSession, endpoint: WebhookEndpoint, monkeypatch
):
    delivery = await _make_delivery(db, endpoint)
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ConnectError("connection refused")
        return httpx.Response(200, json={"ok": True})

    _patch_http(monkeypatch, handler)
    await webhook_delivery.deliver_webhook(
        {"db_session_factory": test_session}, str(delivery.id)
    )

    assert len(calls) == 2
    fresh = (
        await db.execute(select(WebhookDelivery).where(WebhookDelivery.id == delivery.id))
    ).scalar_one()
    # The task writes via a separate session — refresh past the identity map
    # (test sessions use expire_on_commit=False).
    await db.refresh(fresh)
    assert fresh.status == "sent"
    assert fresh.attempts == 2
    assert fresh.delivered_at is not None
    assert fresh.last_error is None


@pytest.mark.asyncio
async def test_delivery_exhausts_attempts_marks_failed(
    db: AsyncSession, endpoint: WebhookEndpoint, monkeypatch
):
    delivery = await _make_delivery(db, endpoint)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"err": "boom"})

    _patch_http(monkeypatch, handler)
    await webhook_delivery.deliver_webhook(
        {"db_session_factory": test_session}, str(delivery.id)
    )

    fresh = (
        await db.execute(select(WebhookDelivery).where(WebhookDelivery.id == delivery.id))
    ).scalar_one()
    # The task writes via a separate session — refresh past the identity map
    # (test sessions use expire_on_commit=False).
    await db.refresh(fresh)
    assert fresh.status == "failed"
    assert fresh.attempts == 3
    assert fresh.last_error == "HTTP 500"
    assert fresh.delivered_at is None


@pytest.mark.asyncio
async def test_delivery_hmac_signature(
    db: AsyncSession, endpoint: WebhookEndpoint, monkeypatch
):
    delivery = await _make_delivery(db, endpoint)
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["signature"] = request.headers["X-MedConnect-Signature"]
        captured["event"] = request.headers["X-MedConnect-Event"]
        captured["body"] = request.content
        return httpx.Response(200)

    _patch_http(monkeypatch, handler)
    await webhook_delivery.deliver_webhook(
        {"db_session_factory": test_session}, str(delivery.id)
    )

    expected = hmac.new(
        endpoint.secret.encode("utf-8"), captured["body"], hashlib.sha256
    ).hexdigest()
    assert captured["signature"] == f"sha256={expected}"
    assert captured["event"] == "appointment.booked"
    assert json.loads(captured["body"])["clinic_id"] == str(endpoint.clinic_id)


@pytest.mark.asyncio
async def test_delivery_inactive_endpoint_fails_without_http(
    db: AsyncSession, endpoint: WebhookEndpoint, monkeypatch
):
    delivery = await _make_delivery(db, endpoint)
    endpoint.is_active = False
    await db.commit()

    def handler(request: httpx.Request) -> httpx.Response:  # must not be called
        raise AssertionError("HTTP attempted for inactive endpoint")

    _patch_http(monkeypatch, handler)
    await webhook_delivery.deliver_webhook(
        {"db_session_factory": test_session}, str(delivery.id)
    )
    fresh = (
        await db.execute(select(WebhookDelivery).where(WebhookDelivery.id == delivery.id))
    ).scalar_one()
    # The task writes via a separate session — refresh past the identity map
    # (test sessions use expire_on_commit=False).
    await db.refresh(fresh)
    assert fresh.status == "failed"
    assert fresh.last_error == "endpoint deactivated"


# ---------------------------------------------------------------------------
# Clinic-admin CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_webhook_crud_requires_clinic_admin(
    client, db: AsyncSession, clinic: Clinic
):
    url = f"/api/v1/clinics/{clinic.id}/webhooks"

    # Unauthenticated → 401/403
    resp = await client.get(url)
    assert resp.status_code in (401, 403)

    # Non-member → 403
    outsider = await _make_user(db, "outsider-1")
    _auth(client, outsider)
    resp = await client.get(url)
    assert resp.status_code == 403

    # Plain 'doctor' membership → 403 (owner|admin only)
    member_doc = await _make_member(db, clinic.id, "doctor", "member-doc")
    _auth(client, member_doc)
    resp = await client.get(url)
    assert resp.status_code == 403

    # Owner → 200
    owner = await _make_member(db, clinic.id, "owner", "clinic-owner")
    _auth(client, owner)
    resp = await client.get(url)
    assert resp.status_code == 200
    assert resp.json()["data"] == []


@pytest.mark.asyncio
async def test_webhook_crud_secret_masked(
    client, db: AsyncSession, clinic: Clinic
):
    owner = await _make_member(db, clinic.id, "admin", "clinic-admin")
    _auth(client, owner)
    url = f"/api/v1/clinics/{clinic.id}/webhooks"

    # Create — full secret returned once
    resp = await client.post(
        url,
        json={
            "url": "https://hooks.example.com/mc",
            "event_types": ["appointment.booked"],
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["secret"].startswith("whsec_")
    assert body["secret_masked"].startswith("whsec_****")
    assert body["secret_masked"].endswith(body["secret"][-4:])
    ep_id = body["id"]

    # List — masked only
    resp = await client.get(url)
    assert resp.status_code == 200
    item = resp.json()["data"][0]
    assert "secret" not in item
    assert item["secret_masked"].endswith(body["secret"][-4:])

    # Detail — masked only
    resp = await client.get(f"{url}/{ep_id}")
    assert resp.status_code == 200
    assert "secret" not in resp.json()

    # Update — masked only
    resp = await client.patch(f"{url}/{ep_id}", json={"is_active": False})
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False
    assert "secret" not in resp.json()

    # Cross-clinic access → 404
    other = Clinic(id=uuid.uuid4(), name="Other Clinic")
    db.add(other)
    await db.commit()
    resp = await client.get(f"/api/v1/clinics/{other.id}/webhooks/{ep_id}")
    assert resp.status_code in (403, 404)  # 403: not a member of other clinic

    # Delete → 204, then detail 404
    resp = await client.delete(f"{url}/{ep_id}")
    assert resp.status_code == 204
    resp = await client.get(f"{url}/{ep_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_deliveries_list_paginated_and_filtered(
    client, db: AsyncSession, clinic: Clinic
):
    owner = await _make_member(db, clinic.id, "owner", "deliv-owner")
    _auth(client, owner)

    ep = WebhookEndpoint(
        id=uuid.uuid4(),
        clinic_id=clinic.id,
        url="https://hooks.example.com/x",
        secret="whsec_abc",
        event_types=["appointment.booked"],
        is_active=True,
    )
    db.add(ep)
    await db.flush()
    for i, st in enumerate(["pending", "sent", "failed"]):
        db.add(
            WebhookDelivery(
                endpoint_id=ep.id,
                event_type="appointment.booked",
                payload_json={"i": i},
                status=st,
                attempts=1,
            )
        )
    await db.commit()

    base = f"/api/v1/clinics/{clinic.id}/webhooks/deliveries"
    resp = await client.get(base)
    assert resp.status_code == 200, resp.text
    assert resp.json()["total"] == 3

    resp = await client.get(base, params={"status": "failed"})
    assert resp.json()["total"] == 1
    assert resp.json()["data"][0]["status"] == "failed"

    resp = await client.get(base, params={"limit": 2, "page": 2})
    assert resp.json()["total"] == 3
    assert len(resp.json()["data"]) == 1

    # Deliveries log requires clinic-admin too
    _auth(client, await _make_user(db, "nobody-1"))
    resp = await client.get(base)
    assert resp.status_code == 403
