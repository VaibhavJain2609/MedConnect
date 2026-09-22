"""Tests for the appointment waitlist.

Covers:
- POST /api/v1/appointments/waitlist — join, duplicate 409, validation
- GET  /api/v1/appointments/waitlist/mine — patient's own entries
- DELETE /api/v1/appointments/waitlist/{id} — cancel own entry
- GET  /api/v1/appointments/waitlist — clinic-scoped staff list
- Cancellation fan-out: cancelling an appointment marks matching pending
  waitlist entries ``notified`` and creates an in-app Notification
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment
from app.models.appointment_waitlist import AppointmentWaitlist
from app.models.clinic import Clinic, ClinicMembership
from app.models.doctor import Doctor
from app.models.notification import Notification
from app.models.user import User
from tests.conftest import create_test_token

pytestmark = pytest.mark.asyncio

NEXT_WEEK = datetime.now(timezone.utc) + timedelta(days=7)
NEXT_WEEK_DATE = NEXT_WEEK.date().isoformat()


def _auth(token: str, clinic_id: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if clinic_id:
        headers["X-Clinic-Id"] = str(clinic_id)
    return headers


def _token_for(user: User, roles: list[str] | None = None) -> str:
    return create_test_token(
        sub=user.keycloak_sub,
        email=user.email,
        name=user.full_name,
        roles=roles or [user.role],
    )


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


async def _make_appointment(
    db: AsyncSession,
    *,
    patient_id: uuid.UUID,
    doctor_id: uuid.UUID,
    created_by: uuid.UUID,
    scheduled_at: datetime | None = None,
    clinic_id: uuid.UUID | None = None,
) -> Appointment:
    appt = Appointment(
        id=uuid.uuid4(),
        patient_id=patient_id,
        doctor_id=doctor_id,
        clinic_id=clinic_id,
        scheduled_at=scheduled_at or NEXT_WEEK,
        duration_minutes=30,
        type="in-person",
        status="scheduled",
        created_by=created_by,
    )
    db.add(appt)
    await db.commit()
    await db.refresh(appt)
    return appt


async def _make_clinic(db: AsyncSession, *, user_id: uuid.UUID, role: str = "owner") -> Clinic:
    clinic = Clinic(name="Waitlist Clinic")
    db.add(clinic)
    await db.flush()
    db.add(ClinicMembership(clinic_id=clinic.id, user_id=user_id, role=role))
    await db.commit()
    await db.refresh(clinic)
    return clinic


# ---------------------------------------------------------------------------
# Join
# ---------------------------------------------------------------------------


async def test_join_waitlist_creates_pending(
    client: AsyncClient, db, patient_user, doctor_user, doctor_profile
):
    resp = await client.post(
        "/api/v1/appointments/waitlist",
        json={
            "doctor_id": str(doctor_profile.id),
            "desired_date": NEXT_WEEK_DATE,
            "slot_window": "morning",
        },
        headers=_auth(_token_for(patient_user)),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "pending"
    assert body["desired_date"] == NEXT_WEEK_DATE
    assert body["slot_window"] == "morning"
    assert body["doctor_id"] == str(doctor_profile.id)
    assert body["patient_id"] == str(patient_user.id)


async def test_join_waitlist_duplicate_409(client: AsyncClient, db, patient_user, doctor_profile):
    payload = {"doctor_id": str(doctor_profile.id), "desired_date": NEXT_WEEK_DATE}
    first = await client.post(
        "/api/v1/appointments/waitlist", json=payload, headers=_auth(_token_for(patient_user))
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/appointments/waitlist", json=payload, headers=_auth(_token_for(patient_user))
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "WAITLIST_ALREADY_PENDING"


async def test_join_waitlist_past_date_400(client: AsyncClient, db, patient_user, doctor_profile):
    past = (datetime.now(timezone.utc) - timedelta(days=2)).date().isoformat()
    resp = await client.post(
        "/api/v1/appointments/waitlist",
        json={"doctor_id": str(doctor_profile.id), "desired_date": past},
        headers=_auth(_token_for(patient_user)),
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_DATE"


async def test_join_waitlist_unknown_doctor_404(client: AsyncClient, db, patient_user):
    resp = await client.post(
        "/api/v1/appointments/waitlist",
        json={"doctor_id": str(uuid.uuid4()), "desired_date": NEXT_WEEK_DATE},
        headers=_auth(_token_for(patient_user)),
    )
    assert resp.status_code == 404


async def test_join_waitlist_invalid_slot_window_422(
    client: AsyncClient, db, patient_user, doctor_profile
):
    resp = await client.post(
        "/api/v1/appointments/waitlist",
        json={
            "doctor_id": str(doctor_profile.id),
            "desired_date": NEXT_WEEK_DATE,
            "slot_window": "evening",
        },
        headers=_auth(_token_for(patient_user)),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_SLOT_WINDOW"


async def test_join_waitlist_requires_patient_role(client: AsyncClient, db, doctor_user, doctor_profile):
    resp = await client.post(
        "/api/v1/appointments/waitlist",
        json={"doctor_id": str(doctor_profile.id), "desired_date": NEXT_WEEK_DATE},
        headers=_auth(_token_for(doctor_user)),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Mine + cancel
# ---------------------------------------------------------------------------


async def test_my_waitlist_lists_entries(client: AsyncClient, db, patient_user, doctor_profile):
    await client.post(
        "/api/v1/appointments/waitlist",
        json={"doctor_id": str(doctor_profile.id), "desired_date": NEXT_WEEK_DATE},
        headers=_auth(_token_for(patient_user)),
    )
    mine = await client.get(
        "/api/v1/appointments/waitlist/mine", headers=_auth(_token_for(patient_user))
    )
    assert mine.status_code == 200
    data = mine.json()["data"]
    assert len(data) == 1
    assert data[0]["status"] == "pending"
    assert data[0]["doctor_id"] == str(doctor_profile.id)


async def test_cancel_waitlist_entry(client: AsyncClient, db, patient_user, doctor_profile):
    join = await client.post(
        "/api/v1/appointments/waitlist",
        json={"doctor_id": str(doctor_profile.id), "desired_date": NEXT_WEEK_DATE},
        headers=_auth(_token_for(patient_user)),
    )
    entry_id = join.json()["id"]

    resp = await client.delete(
        f"/api/v1/appointments/waitlist/{entry_id}", headers=_auth(_token_for(patient_user))
    )
    assert resp.status_code == 204

    mine = await client.get(
        "/api/v1/appointments/waitlist/mine", headers=_auth(_token_for(patient_user))
    )
    assert mine.json()["data"] == []

    # Cancelling frees the (patient, doctor, date) slot — re-join is allowed
    rejoin = await client.post(
        "/api/v1/appointments/waitlist",
        json={"doctor_id": str(doctor_profile.id), "desired_date": NEXT_WEEK_DATE},
        headers=_auth(_token_for(patient_user)),
    )
    assert rejoin.status_code == 201


async def test_cancel_other_patients_entry_403(
    client: AsyncClient, db, patient_user, doctor_profile
):
    other = await _make_patient(db, "other@waitlist.com", "Other Patient")
    join = await client.post(
        "/api/v1/appointments/waitlist",
        json={"doctor_id": str(doctor_profile.id), "desired_date": NEXT_WEEK_DATE},
        headers=_auth(_token_for(other)),
    )
    entry_id = join.json()["id"]

    resp = await client.delete(
        f"/api/v1/appointments/waitlist/{entry_id}", headers=_auth(_token_for(patient_user))
    )
    assert resp.status_code == 403


async def test_cancel_missing_entry_404(client: AsyncClient, db, patient_user):
    resp = await client.delete(
        f"/api/v1/appointments/waitlist/{uuid.uuid4()}",
        headers=_auth(_token_for(patient_user)),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Cancellation fan-out
# ---------------------------------------------------------------------------


async def test_cancellation_notifies_waitlisted_patient(
    client: AsyncClient, db, doctor_user, doctor_profile, doctor_client, patient_user
):
    waiting = await _make_patient(db, "waiter@waitlist.com", "Waiting Patient")

    # Patient joins the waitlist for the doctor on NEXT_WEEK's date
    join = await client.post(
        "/api/v1/appointments/waitlist",
        json={"doctor_id": str(doctor_profile.id), "desired_date": NEXT_WEEK_DATE},
        headers=_auth(_token_for(waiting)),
    )
    assert join.status_code == 201
    entry_id = join.json()["id"]

    # Doctor cancels an appointment on that date — slot freed
    appt = await _make_appointment(
        db,
        patient_id=patient_user.id,
        doctor_id=doctor_profile.id,
        created_by=doctor_user.id,
        scheduled_at=NEXT_WEEK,
    )
    resp = await doctor_client.put(
        f"/api/v1/appointments/{appt.id}/status", json={"status": "cancelled"}
    )
    assert resp.status_code == 200, resp.text

    # Waitlist entry flipped to notified
    entry = (
        await db.execute(
            select(AppointmentWaitlist).where(AppointmentWaitlist.id == uuid.UUID(entry_id))
        )
    ).scalar_one()
    assert entry.status == "notified"
    assert entry.notified_at is not None

    # In-app notification with a deep link to the booking page
    notifs = (
        await db.execute(select(Notification).where(Notification.user_id == waiting.id))
    ).scalars().all()
    assert len(notifs) == 1
    assert "slot opened" in notifs[0].title.lower()
    assert notifs[0].action_url == "/patient/appointments"
    assert notifs[0].meta["waitlist_id"] == entry_id


async def test_cancellation_does_not_notify_other_dates(
    client: AsyncClient, db, doctor_user, doctor_profile, doctor_client, patient_user
):
    waiting = await _make_patient(db, "waiter2@waitlist.com", "Waiting Patient 2")
    other_date = (NEXT_WEEK + timedelta(days=1)).date().isoformat()

    join = await client.post(
        "/api/v1/appointments/waitlist",
        json={"doctor_id": str(doctor_profile.id), "desired_date": other_date},
        headers=_auth(_token_for(waiting)),
    )
    assert join.status_code == 201

    appt = await _make_appointment(
        db,
        patient_id=patient_user.id,
        doctor_id=doctor_profile.id,
        created_by=doctor_user.id,
        scheduled_at=NEXT_WEEK,
    )
    resp = await doctor_client.put(
        f"/api/v1/appointments/{appt.id}/status", json={"status": "cancelled"}
    )
    assert resp.status_code == 200

    # Different desired_date → still pending, no notification
    entry = (
        await db.execute(
            select(AppointmentWaitlist).where(
                AppointmentWaitlist.id == uuid.UUID(join.json()["id"])
            )
        )
    ).scalar_one()
    assert entry.status == "pending"
    notifs = (
        await db.execute(select(Notification).where(Notification.user_id == waiting.id))
    ).scalars().all()
    assert notifs == []


async def test_cancellation_no_waitlist_still_succeeds(
    client: AsyncClient, db, doctor_user, doctor_profile, doctor_client, patient_user
):
    """The guard: cancellation works normally when nobody is waiting."""
    appt = await _make_appointment(
        db,
        patient_id=patient_user.id,
        doctor_id=doctor_profile.id,
        created_by=doctor_user.id,
        scheduled_at=NEXT_WEEK,
    )
    resp = await doctor_client.put(
        f"/api/v1/appointments/{appt.id}/status", json={"status": "cancelled"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


async def test_delete_appointment_also_notifies(
    client: AsyncClient, db, doctor_user, doctor_profile, doctor_client, patient_user
):
    """DELETE /{id} (soft-delete cancel) triggers the same fan-out."""
    waiting = await _make_patient(db, "waiter3@waitlist.com", "Waiting Patient 3")
    await client.post(
        "/api/v1/appointments/waitlist",
        json={"doctor_id": str(doctor_profile.id), "desired_date": NEXT_WEEK_DATE},
        headers=_auth(_token_for(waiting)),
    )
    appt = await _make_appointment(
        db,
        patient_id=patient_user.id,
        doctor_id=doctor_profile.id,
        created_by=doctor_user.id,
        scheduled_at=NEXT_WEEK,
    )
    resp = await doctor_client.delete(f"/api/v1/appointments/{appt.id}")
    assert resp.status_code == 204

    notifs = (
        await db.execute(select(Notification).where(Notification.user_id == waiting.id))
    ).scalars().all()
    assert len(notifs) == 1


# ---------------------------------------------------------------------------
# Staff list (clinic-scoped)
# ---------------------------------------------------------------------------


async def test_staff_list_scoped_to_clinic(
    client: AsyncClient, db, doctor_user, doctor_profile, patient_user
):
    clinic = await _make_clinic(db, user_id=doctor_user.id)
    other_clinic = await _make_clinic(db, user_id=doctor_user.id)

    # Entry attached to `clinic`; entry with no clinic must NOT leak in
    await client.post(
        "/api/v1/appointments/waitlist",
        json={
            "doctor_id": str(doctor_profile.id),
            "desired_date": NEXT_WEEK_DATE,
            "clinic_id": str(clinic.id),
        },
        headers=_auth(_token_for(patient_user)),
    )
    other_patient = await _make_patient(db, "noclinic@waitlist.com", "No Clinic Patient")
    other_doctor_user = User(
        keycloak_sub=f"doctor-{uuid.uuid4()}",
        email="doc2@waitlist.com",
        full_name="Doc Two",
        role="doctor",
    )
    db.add(other_doctor_user)
    await db.flush()
    other_doctor = Doctor(id=uuid.uuid4(), user_id=other_doctor_user.id)
    db.add(other_doctor)
    await db.commit()
    await client.post(
        "/api/v1/appointments/waitlist",
        json={"doctor_id": str(other_doctor.id), "desired_date": NEXT_WEEK_DATE},
        headers=_auth(_token_for(other_patient)),
    )

    listing = await client.get(
        "/api/v1/appointments/waitlist",
        headers=_auth(_token_for(doctor_user), clinic.id),
    )
    assert listing.status_code == 200, listing.text
    data = listing.json()["data"]
    assert len(data) == 1
    assert data[0]["clinic_id"] == str(clinic.id)
    assert data[0]["patient_name"] == patient_user.full_name
    assert data[0]["doctor_name"] == doctor_user.full_name

    # Different clinic → empty
    listing2 = await client.get(
        "/api/v1/appointments/waitlist",
        headers=_auth(_token_for(doctor_user), other_clinic.id),
    )
    assert listing2.json()["data"] == []


async def test_staff_list_requires_clinic_header(client: AsyncClient, db, doctor_user):
    resp = await client.get(
        "/api/v1/appointments/waitlist", headers=_auth(_token_for(doctor_user))
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "MISSING_CLINIC"


async def test_staff_list_non_member_403(client: AsyncClient, db, doctor_user, patient_user):
    clinic = await _make_clinic(db, user_id=doctor_user.id)
    # patient_user is not a member of the clinic
    resp = await client.get(
        "/api/v1/appointments/waitlist",
        headers=_auth(_token_for(patient_user), clinic.id),
    )
    assert resp.status_code == 403


async def test_staff_list_status_filter(
    client: AsyncClient, db, doctor_user, doctor_profile, patient_user
):
    clinic = await _make_clinic(db, user_id=doctor_user.id)
    await client.post(
        "/api/v1/appointments/waitlist",
        json={
            "doctor_id": str(doctor_profile.id),
            "desired_date": NEXT_WEEK_DATE,
            "clinic_id": str(clinic.id),
        },
        headers=_auth(_token_for(patient_user)),
    )
    pending = await client.get(
        "/api/v1/appointments/waitlist?status=pending",
        headers=_auth(_token_for(doctor_user), clinic.id),
    )
    assert len(pending.json()["data"]) == 1
    notified = await client.get(
        "/api/v1/appointments/waitlist?status=notified",
        headers=_auth(_token_for(doctor_user), clinic.id),
    )
    assert notified.json()["data"] == []
