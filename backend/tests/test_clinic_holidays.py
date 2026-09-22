"""Tests for clinic holidays (clinic closure days).

Covers:
* CRUD auth matrix — owner/admin memberships may manage holidays; doctor/
  receptionist members, non-members and unauthenticated callers cannot.
* Duplicate (clinic, date) → 409; soft-deleted dates can be re-added.
* Slot generation — a clinic holiday empties that day's bookable slots for
  the clinic's windows while adjacent days are unaffected.
* ``?year=`` list filter.
"""
import uuid
from datetime import date, time, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clinic import Clinic, ClinicMembership
from app.models.doctor import Doctor
from app.models.doctor_availability import DoctorAvailability
from app.models.user import User
from tests.conftest import create_test_token


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def clinic(db: AsyncSession) -> Clinic:
    c = Clinic(id=uuid.uuid4(), name="Holiday Clinic", city="Pune")
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


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


def _url(clinic_id) -> str:
    return f"/api/v1/clinics/{clinic_id}/holidays"


# ---------------------------------------------------------------------------
# Auth matrix
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_holidays_require_authentication(client, clinic: Clinic):
    assert (await client.get(_url(clinic.id))).status_code == 401
    assert (
        await client.post(_url(clinic.id), json={"date": "2026-01-26"})
    ).status_code == 401
    assert (
        await client.delete(f"{_url(clinic.id)}/{uuid.uuid4()}")
    ).status_code == 401


@pytest.mark.asyncio
async def test_holidays_forbidden_for_non_member(client, db: AsyncSession, clinic: Clinic):
    outsider = await _make_user(db, "outsider")
    _auth(client, outsider)
    assert (await client.get(_url(clinic.id))).status_code == 403
    res = await client.post(_url(clinic.id), json={"date": "2026-01-26"})
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_holidays_forbidden_for_doctor_role_member(
    client, db: AsyncSession, clinic: Clinic
):
    member = await _make_member(db, clinic.id, "doctor", "member-doctor")
    _auth(client, member)
    assert (await client.get(_url(clinic.id))).status_code == 403
    res = await client.post(_url(clinic.id), json={"date": "2026-01-26"})
    assert res.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["owner", "admin"])
async def test_holidays_crud_for_clinic_admins(
    client, db: AsyncSession, clinic: Clinic, role: str
):
    admin = await _make_member(db, clinic.id, role, f"member-{role}")
    _auth(client, admin)

    res = await client.post(
        _url(clinic.id), json={"date": "2026-01-26", "name": "Republic Day"}
    )
    assert res.status_code == 201
    body = res.json()
    assert body["date"] == "2026-01-26"
    assert body["name"] == "Republic Day"
    assert body["clinic_id"] == str(clinic.id)

    res = await client.get(_url(clinic.id))
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data) == 1 and data[0]["id"] == body["id"]

    res = await client.delete(f"{_url(clinic.id)}/{body['id']}")
    assert res.status_code == 204

    res = await client.get(_url(clinic.id))
    assert res.json()["data"] == []


# ---------------------------------------------------------------------------
# CRUD semantics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_duplicate_date_conflict_and_readd_after_delete(
    client, db: AsyncSession, clinic: Clinic
):
    owner = await _make_member(db, clinic.id, "owner", "owner-1")
    _auth(client, owner)

    res = await client.post(_url(clinic.id), json={"date": "2026-08-15"})
    assert res.status_code == 201
    holiday_id = res.json()["id"]

    # Same date again → 409
    dup = await client.post(
        _url(clinic.id), json={"date": "2026-08-15", "name": "renamed"}
    )
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "DUPLICATE_HOLIDAY"

    # Soft-delete then re-add the same date → allowed (partial unique index)
    assert (await client.delete(f"{_url(clinic.id)}/{holiday_id}")).status_code == 204
    res = await client.post(_url(clinic.id), json={"date": "2026-08-15"})
    assert res.status_code == 201


@pytest.mark.asyncio
async def test_same_date_allowed_in_other_clinic(
    client, db: AsyncSession, clinic: Clinic
):
    other = Clinic(id=uuid.uuid4(), name="Other Clinic")
    db.add(other)
    await db.commit()

    owner = await _make_member(db, clinic.id, "owner", "owner-a")
    other_owner = await _make_member(db, other.id, "owner", "owner-b")

    _auth(client, owner)
    assert (
        await client.post(_url(clinic.id), json={"date": "2026-05-01"})
    ).status_code == 201

    _auth(client, other_owner)
    assert (
        await client.post(_url(other.id), json={"date": "2026-05-01"})
    ).status_code == 201


@pytest.mark.asyncio
async def test_delete_not_found_and_cross_clinic(
    client, db: AsyncSession, clinic: Clinic
):
    other = Clinic(id=uuid.uuid4(), name="Other Clinic")
    db.add(other)
    await db.commit()

    owner = await _make_member(db, clinic.id, "owner", "owner-del")
    other_owner = await _make_member(db, other.id, "owner", "owner-del-b")
    _auth(client, owner)

    res = await client.post(_url(clinic.id), json={"date": "2026-10-02"})
    holiday_id = res.json()["id"]

    # Nonexistent id → 404
    assert (
        await client.delete(f"{_url(clinic.id)}/{uuid.uuid4()}")
    ).status_code == 404

    # Another clinic's admin cannot delete this clinic's holiday
    _auth(client, other_owner)
    assert (
        await client.delete(f"{_url(clinic.id)}/{holiday_id}")
    ).status_code == 403


@pytest.mark.asyncio
async def test_year_filter(client, db: AsyncSession, clinic: Clinic):
    owner = await _make_member(db, clinic.id, "owner", "owner-year")
    _auth(client, owner)

    for d in ("2025-12-25", "2026-01-26", "2026-08-15"):
        res = await client.post(_url(clinic.id), json={"date": d})
        assert res.status_code == 201

    res = await client.get(_url(clinic.id), params={"year": 2026})
    dates = [h["date"] for h in res.json()["data"]]
    assert dates == ["2026-01-26", "2026-08-15"]

    res = await client.get(_url(clinic.id), params={"year": 2025})
    assert [h["date"] for h in res.json()["data"]] == ["2025-12-25"]

    res = await client.get(_url(clinic.id))
    assert len(res.json()["data"]) == 3


# ---------------------------------------------------------------------------
# Slot generation excludes holiday dates
# ---------------------------------------------------------------------------


async def _make_doctor_with_windows(
    db: AsyncSession, clinic: Clinic, days: list[date]
) -> Doctor:
    user = await _make_user(db, f"slots-doc-{uuid.uuid4().hex[:8]}")
    doctor = Doctor(id=uuid.uuid4(), user_id=user.id, verified=True, onboarding_step="completed")
    db.add(doctor)
    db.add(
        ClinicMembership(
            id=uuid.uuid4(), clinic_id=clinic.id, user_id=user.id, role="doctor", is_active=True
        )
    )
    for d in days:
        db.add(
            DoctorAvailability(
                id=uuid.uuid4(),
                doctor_id=doctor.id,
                clinic_id=clinic.id,
                weekday=d.weekday(),
                start_time=time(9, 0),
                end_time=time(12, 0),
                slot_duration_minutes=30,
                is_active=True,
            )
        )
    await db.commit()
    await db.refresh(doctor)
    return doctor


@pytest.mark.asyncio
async def test_slots_excluded_on_holiday_adjacent_day_unaffected(
    client, db: AsyncSession, clinic: Clinic
):
    # Far-future dates keep every generated slot bookable (5-min skew rule).
    holiday_date = date.today() + timedelta(days=14)
    next_day = holiday_date + timedelta(days=1)
    doctor = await _make_doctor_with_windows(db, clinic, [holiday_date, next_day])

    owner = await _make_member(db, clinic.id, "owner", "owner-slots")
    _auth(client, owner)

    slots_url = f"/api/v1/availability/doctors/{doctor.id}/slots"

    # No holiday yet — both days return slots
    res = await client.get(
        slots_url, params={"date": holiday_date.isoformat(), "clinic_id": str(clinic.id)}
    )
    assert res.status_code == 200 and len(res.json()["slots"]) == 6

    # Close the clinic on the holiday date
    res = await client.post(
        _url(clinic.id), json={"date": holiday_date.isoformat(), "name": "Closed"}
    )
    assert res.status_code == 201

    res = await client.get(
        slots_url, params={"date": holiday_date.isoformat(), "clinic_id": str(clinic.id)}
    )
    assert res.status_code == 200
    assert res.json()["slots"] == []

    # Adjacent day unaffected
    res = await client.get(
        slots_url, params={"date": next_day.isoformat(), "clinic_id": str(clinic.id)}
    )
    assert res.status_code == 200
    assert len(res.json()["slots"]) == 6


@pytest.mark.asyncio
async def test_deleted_holiday_restores_slots(
    client, db: AsyncSession, clinic: Clinic
):
    holiday_date = date.today() + timedelta(days=14)
    doctor = await _make_doctor_with_windows(db, clinic, [holiday_date])
    owner = await _make_member(db, clinic.id, "owner", "owner-restore")
    _auth(client, owner)

    res = await client.post(_url(clinic.id), json={"date": holiday_date.isoformat()})
    holiday_id = res.json()["id"]

    slots_url = f"/api/v1/availability/doctors/{doctor.id}/slots"
    params = {"date": holiday_date.isoformat(), "clinic_id": str(clinic.id)}
    assert (await client.get(slots_url, params=params)).json()["slots"] == []

    assert (await client.delete(f"{_url(clinic.id)}/{holiday_id}")).status_code == 204
    res = await client.get(slots_url, params=params)
    assert len(res.json()["slots"]) == 6


@pytest.mark.asyncio
async def test_holiday_scoped_to_own_clinic(
    client, db: AsyncSession, clinic: Clinic
):
    """A holiday at clinic A must not block a doctor's clinic-B windows."""
    other = Clinic(id=uuid.uuid4(), name="Other Clinic")
    db.add(other)
    await db.commit()

    holiday_date = date.today() + timedelta(days=14)
    doctor = await _make_doctor_with_windows(db, other, [holiday_date])

    owner = await _make_member(db, clinic.id, "owner", "owner-scope")
    _auth(client, owner)
    assert (
        await client.post(_url(clinic.id), json={"date": holiday_date.isoformat()})
    ).status_code == 201

    # Doctor's windows belong to `other` — still bookable
    res = await client.get(
        f"/api/v1/availability/doctors/{doctor.id}/slots",
        params={"date": holiday_date.isoformat(), "clinic_id": str(other.id)},
    )
    assert len(res.json()["slots"]) == 6
