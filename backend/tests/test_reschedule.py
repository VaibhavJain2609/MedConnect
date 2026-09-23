"""Patient-initiated appointment rescheduling.

POST /api/v1/appointments/{id}/reschedule (require_patient)

Covers:
- Happy path: patient moves their own scheduled appointment; doctor/clinic/
  type unchanged; optional duration override applied.
- State guard: only 'scheduled' appointments can move — every other status
  (arrived / in-progress / completed / cancelled / no-show) → 409 INVALID_STATE.
- New time must be in the future → 400 INVALID_SCHEDULED_AT.
- Ownership: another patient's appointment → 403; non-patient role → 403;
  unknown id → 404.
- Doctor double-booking → 409 DOCTOR_UNAVAILABLE (same overlap rules as create).
- Clinic-scoped appointments require the patient's clinic link to still be
  approved (revoked → 403 ACCESS_REVOKED, missing → 403 CONSENT_REQUIRED).
- The doctor receives a Notification when a patient reschedules.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment
from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.notification import Notification
from app.models.patient_link import PatientClinicLink
from app.models.user import User
from tests.conftest import make_auth_header

pytestmark = pytest.mark.asyncio

FUTURE = datetime.now(timezone.utc) + timedelta(days=7)
NEW_TIME = datetime.now(timezone.utc) + timedelta(days=10)
PAST = datetime.now(timezone.utc) - timedelta(days=1)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


async def _make_appointment(
    db: AsyncSession,
    *,
    patient_id: uuid.UUID,
    doctor_id: uuid.UUID,
    created_by: uuid.UUID,
    status: str = "scheduled",
    scheduled_at: datetime | None = None,
    duration_minutes: int = 30,
    clinic_id: uuid.UUID | None = None,
    type: str = "in-person",
) -> Appointment:
    appt = Appointment(
        id=uuid.uuid4(),
        patient_id=patient_id,
        doctor_id=doctor_id,
        clinic_id=clinic_id,
        scheduled_at=scheduled_at or FUTURE,
        duration_minutes=duration_minutes,
        type=type,
        status=status,
        created_by=created_by,
    )
    db.add(appt)
    await db.commit()
    await db.refresh(appt)
    return appt


async def _make_other_patient(db: AsyncSession) -> tuple[User, dict]:
    user = User(
        keycloak_sub=f"patient-{uuid.uuid4()}",
        email="other-patient@test.com",
        full_name="Other Patient",
        role="patient",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user, make_auth_header(user)


@pytest_asyncio.fixture
async def clinic(db: AsyncSession, doctor_user: User) -> Clinic:
    c = Clinic(id=uuid.uuid4(), name="Reschedule Clinic", city="Delhi", created_by=doctor_user.id)
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


async def _link(
    db: AsyncSession, clinic_id, patient_id, linked_by, consent_status: str
) -> PatientClinicLink:
    link = PatientClinicLink(
        id=uuid.uuid4(),
        patient_id=patient_id,
        clinic_id=clinic_id,
        linked_by=linked_by,
        consent_status=consent_status,
        consented_at=datetime.now(timezone.utc) if consent_status == "approved" else None,
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return link


def _url(appt: Appointment) -> str:
    return f"/api/v1/appointments/{appt.id}/reschedule"


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestRescheduleHappyPath:
    async def test_patient_reschedules_own_appointment(
        self, patient_client, db, patient_user, doctor_user, doctor_profile
    ):
        appt = await _make_appointment(
            db,
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            created_by=patient_user.id,
            type="teleconsult",
        )
        resp = await patient_client.post(
            _url(appt), json={"scheduled_at": NEW_TIME.isoformat()}
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["id"] == str(appt.id)
        assert body["status"] == "scheduled"
        # Only the time changes — doctor/clinic/type untouched.
        assert body["scheduled_at"].startswith(NEW_TIME.date().isoformat())
        assert body["doctor_id"] == str(doctor_profile.id)
        assert body["type"] == "teleconsult"
        assert body["clinic_id"] is None

    async def test_duration_override(
        self, patient_client, db, patient_user, doctor_user, doctor_profile
    ):
        appt = await _make_appointment(
            db,
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            created_by=patient_user.id,
            duration_minutes=30,
        )
        resp = await patient_client.post(
            _url(appt),
            json={"scheduled_at": NEW_TIME.isoformat(), "duration_minutes": 60},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["duration_minutes"] == 60

    async def test_reschedule_same_slot_is_allowed(
        self, patient_client, db, patient_user, doctor_user, doctor_profile
    ):
        """exclude_id keeps the appointment from conflicting with itself."""
        appt = await _make_appointment(
            db,
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            created_by=patient_user.id,
            scheduled_at=FUTURE,
        )
        resp = await patient_client.post(
            _url(appt), json={"scheduled_at": FUTURE.isoformat()}
        )
        assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# State guard — only 'scheduled' may move
# ---------------------------------------------------------------------------


class TestRescheduleStateGuard:
    @pytest.mark.parametrize(
        "status", ["arrived", "in-progress", "completed", "cancelled", "no-show"]
    )
    async def test_non_scheduled_status_rejected(
        self, patient_client, db, patient_user, doctor_user, doctor_profile, status
    ):
        appt = await _make_appointment(
            db,
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            created_by=patient_user.id,
            status=status,
        )
        resp = await patient_client.post(
            _url(appt), json={"scheduled_at": NEW_TIME.isoformat()}
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "INVALID_STATE"


# ---------------------------------------------------------------------------
# Validation guards
# ---------------------------------------------------------------------------


class TestRescheduleValidation:
    async def test_past_time_rejected(
        self, patient_client, db, patient_user, doctor_user, doctor_profile
    ):
        appt = await _make_appointment(
            db,
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            created_by=patient_user.id,
        )
        resp = await patient_client.post(
            _url(appt), json={"scheduled_at": PAST.isoformat()}
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_SCHEDULED_AT"

    async def test_doctor_conflict_rejected(
        self, patient_client, db, patient_user, doctor_user, doctor_profile
    ):
        """Another active appointment for the same doctor overlapping the
        requested slot → 409 DOCTOR_UNAVAILABLE."""
        other_patient, _ = await _make_other_patient(db)
        await _make_appointment(
            db,
            patient_id=other_patient.id,
            doctor_id=doctor_profile.id,
            created_by=doctor_user.id,
            scheduled_at=NEW_TIME,
        )
        appt = await _make_appointment(
            db,
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            created_by=patient_user.id,
        )
        resp = await patient_client.post(
            _url(appt), json={"scheduled_at": NEW_TIME.isoformat()}
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "DOCTOR_UNAVAILABLE"

    async def test_doctor_conflict_with_new_duration(
        self, patient_client, db, patient_user, doctor_user, doctor_profile
    ):
        """A longer requested duration can itself create the overlap."""
        other_patient, _ = await _make_other_patient(db)
        # Existing appointment starts 45 min after NEW_TIME.
        await _make_appointment(
            db,
            patient_id=other_patient.id,
            doctor_id=doctor_profile.id,
            created_by=doctor_user.id,
            scheduled_at=NEW_TIME + timedelta(minutes=45),
        )
        appt = await _make_appointment(
            db,
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            created_by=patient_user.id,
        )
        # 30 min would fit before the 45-min mark; 60 min overlaps it.
        resp = await patient_client.post(
            _url(appt),
            json={"scheduled_at": NEW_TIME.isoformat(), "duration_minutes": 60},
        )
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Ownership / role guards
# ---------------------------------------------------------------------------


class TestRescheduleAuth:
    async def test_other_patients_appointment_forbidden(
        self, client, db, patient_user, doctor_user, doctor_profile
    ):
        other_patient, headers = await _make_other_patient(db)
        appt = await _make_appointment(
            db,
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            created_by=patient_user.id,
        )
        resp = await client.post(
            _url(appt),
            json={"scheduled_at": NEW_TIME.isoformat()},
            headers=headers,
        )
        assert resp.status_code == 403
        assert other_patient.id != patient_user.id  # sanity

    async def test_doctor_role_rejected(
        self, doctor_client, db, patient_user, doctor_user, doctor_profile
    ):
        """require_patient — doctors use PUT /{id} instead."""
        appt = await _make_appointment(
            db,
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            created_by=doctor_user.id,
        )
        resp = await doctor_client.post(
            _url(appt), json={"scheduled_at": NEW_TIME.isoformat()}
        )
        assert resp.status_code == 403

    async def test_unknown_appointment_404(self, patient_client):
        resp = await patient_client.post(
            f"/api/v1/appointments/{uuid.uuid4()}/reschedule",
            json={"scheduled_at": NEW_TIME.isoformat()},
        )
        assert resp.status_code == 404

    async def test_unauthenticated_401(self, client, db, patient_user, doctor_user, doctor_profile):
        appt = await _make_appointment(
            db,
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            created_by=patient_user.id,
        )
        resp = await client.post(_url(appt), json={"scheduled_at": NEW_TIME.isoformat()})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Clinic-scoped link guard
# ---------------------------------------------------------------------------


class TestRescheduleClinicLink:
    async def test_approved_link_allows_reschedule(
        self, patient_client, db, clinic, patient_user, doctor_user, doctor_profile
    ):
        await _link(db, clinic.id, patient_user.id, doctor_user.id, "approved")
        appt = await _make_appointment(
            db,
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            clinic_id=clinic.id,
            created_by=doctor_user.id,
        )
        resp = await patient_client.post(
            _url(appt), json={"scheduled_at": NEW_TIME.isoformat()}
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["clinic_id"] == str(clinic.id)

    async def test_revoked_link_blocks_reschedule(
        self, patient_client, db, clinic, patient_user, doctor_user, doctor_profile
    ):
        await _link(db, clinic.id, patient_user.id, doctor_user.id, "revoked")
        appt = await _make_appointment(
            db,
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            clinic_id=clinic.id,
            created_by=doctor_user.id,
        )
        resp = await patient_client.post(
            _url(appt), json={"scheduled_at": NEW_TIME.isoformat()}
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "ACCESS_REVOKED"

    async def test_missing_link_blocks_reschedule(
        self, patient_client, db, clinic, patient_user, doctor_user, doctor_profile
    ):
        appt = await _make_appointment(
            db,
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            clinic_id=clinic.id,
            created_by=doctor_user.id,
        )
        resp = await patient_client.post(
            _url(appt), json={"scheduled_at": NEW_TIME.isoformat()}
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "CONSENT_REQUIRED"


# ---------------------------------------------------------------------------
# Doctor notification
# ---------------------------------------------------------------------------


class TestDoctorNotified:
    async def test_doctor_receives_notification(
        self, patient_client, db, patient_user, doctor_user, doctor_profile
    ):
        appt = await _make_appointment(
            db,
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            created_by=patient_user.id,
        )
        resp = await patient_client.post(
            _url(appt), json={"scheduled_at": NEW_TIME.isoformat()}
        )
        assert resp.status_code == 200, resp.text

        notif = (
            await db.execute(
                select(Notification).where(
                    Notification.user_id == doctor_user.id,
                    Notification.type == "appointment",
                    Notification.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        assert notif is not None
        assert "rescheduled" in notif.title.lower()
        assert notif.meta["appointment_id"] == str(appt.id)
        assert notif.action_url == "/doctor/appointments"
