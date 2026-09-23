"""Tests for doctor leave days (doctor_leaves).

Covers:
* CRUD auth matrix — only the owning doctor may manage their leaves;
  patients, other doctors and unauthenticated callers cannot.
* Duplicate (doctor, date) → 409; soft-deleted dates can be re-added.
* Slot generation — a leave day empties that doctor's bookable slots
  (doctor-scoped: blocks windows across all clinics) while adjacent days
  are unaffected.
"""
import uuid
from datetime import date, time, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.doctor_availability import DoctorAvailability
from app.models.user import User
from tests.conftest import create_test_token

LEAVES_URL = "/api/v1/availability/me/leaves"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


async def _make_user(db: AsyncSession, sub: str, role: str = "doctor") -> User:
    u = User(
        id=uuid.uuid4(),
        keycloak_sub=sub,
        full_name=f"{sub} user",
        email=f"{sub}@test.com",
        role=role,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def _make_doctor(db: AsyncSession, sub: str) -> tuple[User, Doctor]:
    u = await _make_user(db, sub)
    d = Doctor(id=uuid.uuid4(), user_id=u.id, verified=True, onboarding_step="completed")
    db.add(d)
    await db.commit()
    await db.refresh(d)
    return u, d


def _auth(client, user: User, roles=("doctor",)) -> None:
    token = create_test_token(
        sub=user.keycloak_sub, email=user.email, name=user.full_name, roles=list(roles)
    )
    client.headers["Authorization"] = f"Bearer {token}"


# ---------------------------------------------------------------------------
# Auth matrix
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_leaves_require_authentication(client):
    assert (await client.get(LEAVES_URL)).status_code == 401
    assert (
        await client.post(LEAVES_URL, json={"date": "2026-01-26"})
    ).status_code == 401
    assert (
        await client.delete(f"{LEAVES_URL}/{uuid.uuid4()}")
    ).status_code == 401


@pytest.mark.asyncio
async def test_leaves_forbidden_for_patient(client, db: AsyncSession):
    patient = await _make_user(db, "patient-1", role="patient")
    _auth(client, patient, roles=("patient",))
    assert (await client.get(LEAVES_URL)).status_code == 403
    res = await client.post(LEAVES_URL, json={"date": "2026-01-26"})
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_leaves_crud_for_owning_doctor(client, db: AsyncSession):
    user, doctor = await _make_doctor(db, "doc-crud")
    _auth(client, user)

    res = await client.post(
        LEAVES_URL, json={"date": "2026-03-17", "reason": "Conference"}
    )
    assert res.status_code == 201
    body = res.json()
    assert body["date"] == "2026-03-17"
    assert body["reason"] == "Conference"
    assert body["doctor_id"] == str(doctor.id)

    res = await client.get(LEAVES_URL)
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data) == 1 and data[0]["id"] == body["id"]

    res = await client.delete(f"{LEAVES_URL}/{body['id']}")
    assert res.status_code == 204

    res = await client.get(LEAVES_URL)
    assert res.json()["data"] == []


# ---------------------------------------------------------------------------
# CRUD semantics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_duplicate_date_conflict_and_readd_after_delete(
    client, db: AsyncSession
):
    user, _doctor = await _make_doctor(db, "doc-dup")
    _auth(client, user)

    res = await client.post(LEAVES_URL, json={"date": "2026-08-15"})
    assert res.status_code == 201
    leave_id = res.json()["id"]

    # Same date again → 409
    dup = await client.post(
        LEAVES_URL, json={"date": "2026-08-15", "reason": "renamed"}
    )
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "DUPLICATE_LEAVE"

    # Soft-delete then re-add the same date → allowed (partial unique index)
    assert (await client.delete(f"{LEAVES_URL}/{leave_id}")).status_code == 204
    res = await client.post(LEAVES_URL, json={"date": "2026-08-15"})
    assert res.status_code == 201


@pytest.mark.asyncio
async def test_same_date_allowed_for_other_doctor(client, db: AsyncSession):
    user_a, _ = await _make_doctor(db, "doc-a")
    user_b, _ = await _make_doctor(db, "doc-b")

    _auth(client, user_a)
    assert (
        await client.post(LEAVES_URL, json={"date": "2026-05-01"})
    ).status_code == 201

    _auth(client, user_b)
    assert (
        await client.post(LEAVES_URL, json={"date": "2026-05-01"})
    ).status_code == 201


@pytest.mark.asyncio
async def test_delete_not_found_and_cross_doctor(client, db: AsyncSession):
    user_a, _ = await _make_doctor(db, "doc-del-a")
    user_b, _ = await _make_doctor(db, "doc-del-b")

    _auth(client, user_a)
    res = await client.post(LEAVES_URL, json={"date": "2026-10-02"})
    leave_id = res.json()["id"]

    # Nonexistent id → 404
    assert (
        await client.delete(f"{LEAVES_URL}/{uuid.uuid4()}")
    ).status_code == 404

    # Another doctor cannot delete this doctor's leave (404, not 403 —
    # the row is scoped to the caller's doctor id so it simply isn't found)
    _auth(client, user_b)
    assert (await client.delete(f"{LEAVES_URL}/{leave_id}")).status_code == 404


@pytest.mark.asyncio
async def test_list_scoped_to_owning_doctor(client, db: AsyncSession):
    user_a, _ = await _make_doctor(db, "doc-list-a")
    user_b, _ = await _make_doctor(db, "doc-list-b")

    _auth(client, user_a)
    for d in ("2026-01-26", "2026-02-14"):
        res = await client.post(LEAVES_URL, json={"date": d})
        assert res.status_code == 201

    _auth(client, user_b)
    assert (
        await client.post(LEAVES_URL, json={"date": "2026-03-01"})
    ).status_code == 201

    res = await client.get(LEAVES_URL)
    dates = [l["date"] for l in res.json()["data"]]
    assert dates == ["2026-03-01"]

    _auth(client, user_a)
    res = await client.get(LEAVES_URL)
    dates = [l["date"] for l in res.json()["data"]]
    assert dates == ["2026-01-26", "2026-02-14"]


# ---------------------------------------------------------------------------
# Slot generation excludes leave dates
# ---------------------------------------------------------------------------


async def _make_doctor_with_windows(
    db: AsyncSession,
    days: list[date],
    sub: str | None = None,
    clinic_id=None,
) -> tuple[User, Doctor]:
    user, doctor = await _make_doctor(db, sub or f"slots-doc-{uuid.uuid4().hex[:8]}")
    for d in days:
        db.add(
            DoctorAvailability(
                id=uuid.uuid4(),
                doctor_id=doctor.id,
                clinic_id=clinic_id,
                weekday=d.weekday(),
                start_time=time(9, 0),
                end_time=time(12, 0),
                slot_duration_minutes=30,
                is_active=True,
            )
        )
    await db.commit()
    await db.refresh(doctor)
    return user, doctor


@pytest.mark.asyncio
async def test_slots_excluded_on_leave_adjacent_day_unaffected(
    client, db: AsyncSession
):
    # Far-future dates keep every generated slot bookable (5-min skew rule).
    leave_date = date.today() + timedelta(days=14)
    next_day = leave_date + timedelta(days=1)
    user, doctor = await _make_doctor_with_windows(db, [leave_date, next_day])
    _auth(client, user)

    slots_url = f"/api/v1/availability/doctors/{doctor.id}/slots"

    # No leave yet — both days return slots
    res = await client.get(slots_url, params={"date": leave_date.isoformat()})
    assert res.status_code == 200 and len(res.json()["slots"]) == 6

    # Take leave on that date
    res = await client.post(
        LEAVES_URL, json={"date": leave_date.isoformat(), "reason": "Off"}
    )
    assert res.status_code == 201

    res = await client.get(slots_url, params={"date": leave_date.isoformat()})
    assert res.status_code == 200
    assert res.json()["slots"] == []

    # Adjacent day unaffected
    res = await client.get(slots_url, params={"date": next_day.isoformat()})
    assert res.status_code == 200
    assert len(res.json()["slots"]) == 6


@pytest.mark.asyncio
async def test_deleted_leave_restores_slots(client, db: AsyncSession):
    leave_date = date.today() + timedelta(days=14)
    user, doctor = await _make_doctor_with_windows(db, [leave_date])
    _auth(client, user)

    res = await client.post(LEAVES_URL, json={"date": leave_date.isoformat()})
    leave_id = res.json()["id"]

    slots_url = f"/api/v1/availability/doctors/{doctor.id}/slots"
    params = {"date": leave_date.isoformat()}
    assert (await client.get(slots_url, params=params)).json()["slots"] == []

    assert (await client.delete(f"{LEAVES_URL}/{leave_id}")).status_code == 204
    res = await client.get(slots_url, params=params)
    assert len(res.json()["slots"]) == 6


@pytest.mark.asyncio
async def test_leave_blocks_slots_across_clinics(client, db: AsyncSession):
    """Leave is doctor-scoped (not clinic-scoped): a leave day blocks the
    doctor's windows even when a clinic_id filter is supplied — unlike a
    clinic holiday which only closes that clinic's windows."""
    clinic = Clinic(id=uuid.uuid4(), name="Scope Clinic")
    db.add(clinic)
    await db.commit()

    leave_date = date.today() + timedelta(days=14)
    user, doctor = await _make_doctor_with_windows(
        db, [leave_date], clinic_id=clinic.id
    )

    _auth(client, user)
    assert (
        await client.post(LEAVES_URL, json={"date": leave_date.isoformat()})
    ).status_code == 201

    res = await client.get(
        f"/api/v1/availability/doctors/{doctor.id}/slots",
        params={"date": leave_date.isoformat(), "clinic_id": str(clinic.id)},
    )
    assert res.json()["slots"] == []
