"""Waiting-room display board endpoint (GET /api/v1/queue/display).

Covers:
- now_serving / up_next split of today's active entries, ordered by
  queue_number, with anonymized "Q-<n>" token labels.
- completed / cancelled / soft-deleted entries are excluded.
- ``limit`` truncates up_next while waiting_count reports the full total.
- PHI safety: the payload never contains patient ids, names, or notes —
  the board is visible to everyone in the waiting room.
- Auth: X-Clinic-Id required (400), non-member rejected (403),
  unauthenticated rejected (401).
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clinic import Clinic, ClinicMembership
from app.models.user import User
from tests.conftest import make_auth_header

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def clinic(db: AsyncSession, doctor_user: User) -> Clinic:
    c = Clinic(id=uuid.uuid4(), name="Display Clinic", city="Pune", created_by=doctor_user.id)
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


@pytest_asyncio.fixture
async def owner_membership(db: AsyncSession, clinic: Clinic, doctor_user: User) -> ClinicMembership:
    m = ClinicMembership(
        id=uuid.uuid4(), clinic_id=clinic.id, user_id=doctor_user.id, role="owner", is_active=True
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


async def _make_patient(db: AsyncSession, email: str, name: str) -> User:
    user = User(
        keycloak_sub=f"patient-{uuid.uuid4()}",
        email=email,
        full_name=name,
        role="patient",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def _headers(clinic: Clinic) -> dict[str, str]:
    return {"X-Clinic-Id": str(clinic.id)}


async def _check_in(client, clinic: Clinic, patient_id, notes: str | None = None) -> dict:
    body: dict = {"patient_id": str(patient_id)}
    if notes:
        body["notes"] = notes
    resp = await client.post("/api/v1/queue", json=body, headers=_headers(clinic))
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _set_status(client, clinic: Clinic, entry_id: str, status: str) -> None:
    resp = await client.patch(
        f"/api/v1/queue/{entry_id}/status",
        json={"status": status},
        headers=_headers(clinic),
    )
    assert resp.status_code == 200, resp.text


async def _display(client, clinic: Clinic, **params) -> dict:
    resp = await client.get("/api/v1/queue/display", headers=_headers(clinic), params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Board content
# ---------------------------------------------------------------------------


class TestDisplayBoard:
    async def test_empty_queue(self, doctor_client, clinic, owner_membership):
        data = await _display(doctor_client, clinic)
        assert data["now_serving"] == []
        assert data["up_next"] == []
        assert data["waiting_count"] == 0
        assert data["generated_at"]

    async def test_now_serving_and_up_next_split(
        self, doctor_client, db, clinic, owner_membership, patient_user
    ):
        other = await _make_patient(db, "d2@test.com", "Second Patient")
        third = await _make_patient(db, "d3@test.com", "Third Patient")

        first = await _check_in(doctor_client, clinic, patient_user.id)
        await _check_in(doctor_client, clinic, other.id)
        await _check_in(doctor_client, clinic, third.id)
        await _set_status(doctor_client, clinic, first["id"], "in_consultation")

        data = await _display(doctor_client, clinic)

        assert [t["token"] for t in data["now_serving"]] == ["Q-1"]
        assert data["now_serving"][0]["status"] == "in_consultation"
        assert data["now_serving"][0]["called_at"] is not None

        assert [t["token"] for t in data["up_next"]] == ["Q-2", "Q-3"]
        assert [t["position"] for t in data["up_next"]] == [1, 2]
        assert data["waiting_count"] == 2

    async def test_completed_cancelled_and_deleted_excluded(
        self, doctor_client, db, clinic, owner_membership, patient_user
    ):
        other = await _make_patient(db, "d4@test.com", "Fourth Patient")
        third = await _make_patient(db, "d5@test.com", "Fifth Patient")

        done = await _check_in(doctor_client, clinic, patient_user.id)
        cancelled = await _check_in(doctor_client, clinic, other.id)
        removed = await _check_in(doctor_client, clinic, third.id)

        await _set_status(doctor_client, clinic, done["id"], "in_consultation")
        await _set_status(doctor_client, clinic, done["id"], "completed")
        await _set_status(doctor_client, clinic, cancelled["id"], "cancelled")

        resp = await doctor_client.delete(
            f"/api/v1/queue/{removed['id']}", headers=_headers(clinic)
        )
        assert resp.status_code == 204

        data = await _display(doctor_client, clinic)
        assert data["now_serving"] == []
        assert data["up_next"] == []
        assert data["waiting_count"] == 0

    async def test_limit_truncates_up_next_not_count(
        self, doctor_client, db, clinic, owner_membership
    ):
        for i in range(5):
            p = await _make_patient(db, f"bulk{i}@test.com", f"Bulk {i}")
            await _check_in(doctor_client, clinic, p.id)

        data = await _display(doctor_client, clinic, limit=2)
        assert [t["token"] for t in data["up_next"]] == ["Q-1", "Q-2"]
        assert data["waiting_count"] == 5

    async def test_no_phi_in_payload(
        self, doctor_client, db, clinic, owner_membership, patient_user
    ):
        """The board is public — no patient id/name/notes may leak."""
        entry = await _check_in(
            doctor_client, clinic, patient_user.id, notes="SECRET-HIV-STATUS"
        )
        await _set_status(doctor_client, clinic, entry["id"], "in_consultation")

        resp = await doctor_client.get("/api/v1/queue/display", headers=_headers(clinic))
        assert resp.status_code == 200
        body = resp.text
        assert patient_user.full_name not in body
        assert str(patient_user.id) not in body
        assert str(entry["id"]) not in body
        assert "SECRET-HIV-STATUS" not in body
        # Only token/status/position/called_at keys per item.
        for item in resp.json()["now_serving"]:
            assert set(item.keys()) == {"token", "status", "position", "called_at"}


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class TestDisplayAuth:
    async def test_missing_clinic_header_400(self, doctor_client):
        resp = await doctor_client.get("/api/v1/queue/display")
        assert resp.status_code == 400

    async def test_non_member_403(self, client, doctor_client, db, clinic, owner_membership, patient_user):
        resp = await client.get(
            "/api/v1/queue/display",
            headers={**_headers(clinic), **make_auth_header(patient_user)},
        )
        assert resp.status_code == 403

    async def test_unauthenticated_401(self, client, clinic):
        resp = await client.get("/api/v1/queue/display", headers=_headers(clinic))
        assert resp.status_code == 401

    async def test_receptionist_member_allowed(
        self, doctor_client, db, clinic, doctor_user, patient_user
    ):
        """Any clinic staff role (incl. receptionist) may view the board —
        the TV is usually driven by the front desk."""
        m = ClinicMembership(
            id=uuid.uuid4(), clinic_id=clinic.id, user_id=doctor_user.id,
            role="receptionist", is_active=True,
        )
        db.add(m)
        await db.commit()

        await _check_in(doctor_client, clinic, patient_user.id)
        data = await _display(doctor_client, clinic)
        assert [t["token"] for t in data["up_next"]] == ["Q-1"]
