"""Round-6: front-desk staff booking — receptionists (and any active clinic
membership holder) can book existing patients, advance appointment status,
and reschedule appointments at their clinic.

The receptionist shape under test: global role 'patient' + a ClinicMembership
with role='receptionist' (mirrors how front-desk staff are provisioned — no
Keycloak role, only a clinic membership).

Covers:
- POST /api/v1/appointments: staff booking for an approved-linked patient
  succeeds (created_by = staff caller, clinic tagged from X-Clinic-Id);
  an unlinked patient → 403; a doctor who is not a clinic member → 403;
  a non-member patient caller → 403.
- PUT /api/v1/appointments/{id}/status: staff advance scheduled→arrived,
  arrived→in-progress, and cancel — but NOT in-progress→completed.
- PUT /api/v1/appointments/{id}: staff reschedule a clinic appointment.
- Non-member patients get none of these powers.

Fixtures/helpers are copied from test_r5_coverage.py — no cross-test-file
imports.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment
from app.models.clinic import Clinic, ClinicMembership
from app.models.doctor import Doctor
from app.models.patient_link import PatientClinicLink
from app.models.user import User
from tests.conftest import make_auth_header

pytestmark = pytest.mark.asyncio

FUTURE = datetime.now(timezone.utc) + timedelta(days=3)
FUTURE_2 = datetime.now(timezone.utc) + timedelta(days=4)


# ---------------------------------------------------------------------------
# Fixtures / helpers (copied from test_r5_coverage.py — do not import across
# test files)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def clinic(db: AsyncSession, doctor_user: User) -> Clinic:
    c = Clinic(id=uuid.uuid4(), name="Staff Clinic", city="Delhi", created_by=doctor_user.id)
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


async def _membership(db: AsyncSession, clinic_id, user_id, role: str) -> ClinicMembership:
    m = ClinicMembership(
        id=uuid.uuid4(), clinic_id=clinic_id, user_id=user_id,
        role=role, is_active=True,
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


@pytest_asyncio.fixture
async def doctor_membership(
    db: AsyncSession, clinic: Clinic, doctor_user: User
) -> ClinicMembership:
    """The booked doctor is a 'doctor'-role member of the clinic."""
    return await _membership(db, clinic.id, doctor_user.id, "doctor")


@pytest_asyncio.fixture
async def receptionist_user(db: AsyncSession) -> User:
    """Front-desk staffer: global role 'patient', no clinical role."""
    user = User(
        keycloak_sub=f"receptionist-{uuid.uuid4()}",
        email="receptionist@test.com",
        full_name="Front Desk",
        role="patient",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def receptionist_membership(
    db: AsyncSession, clinic: Clinic, receptionist_user: User
) -> ClinicMembership:
    return await _membership(db, clinic.id, receptionist_user.id, "receptionist")


@pytest_asyncio.fixture
async def approved_link(
    db: AsyncSession, clinic: Clinic, doctor_user: User, patient_user: User
) -> PatientClinicLink:
    link = PatientClinicLink(
        id=uuid.uuid4(),
        patient_id=patient_user.id,
        clinic_id=clinic.id,
        linked_by=doctor_user.id,
        consent_status="approved",
        consented_at=datetime.now(timezone.utc),
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return link


async def _make_doctor(
    db: AsyncSession, email: str = "other-doc@test.com"
) -> tuple[User, Doctor, dict]:
    """Create an additional verified doctor (user + profile), return auth header."""
    user = User(
        keycloak_sub=f"doctor-{uuid.uuid4()}",
        email=email,
        full_name="Other Doctor",
        role="doctor",
    )
    db.add(user)
    await db.flush()
    profile = Doctor(
        id=uuid.uuid4(), user_id=user.id, verified=True, onboarding_step="completed"
    )
    db.add(profile)
    await db.commit()
    return user, profile, make_auth_header(user, roles=["doctor"])


async def _make_patient(
    db: AsyncSession, email: str = "other-patient@test.com"
) -> tuple[User, dict]:
    user = User(
        keycloak_sub=f"patient-{uuid.uuid4()}",
        email=email,
        full_name="Other Patient",
        role="patient",
    )
    db.add(user)
    await db.commit()
    return user, make_auth_header(user)


async def _make_appointment(
    db: AsyncSession,
    *,
    patient_id,
    doctor_id,
    clinic_id=None,
    created_by,
    status: str = "scheduled",
    scheduled_at=FUTURE,
) -> Appointment:
    appt = Appointment(
        id=uuid.uuid4(),
        patient_id=patient_id,
        doctor_id=doctor_id,
        clinic_id=clinic_id,
        scheduled_at=scheduled_at,
        duration_minutes=30,
        type="in-person",
        status=status,
        created_by=created_by,
    )
    db.add(appt)
    await db.commit()
    await db.refresh(appt)
    return appt


def _staff_headers(user: User, clinic: Clinic | None = None) -> dict:
    """Auth header for a staff caller, optionally with the clinic context."""
    headers = make_auth_header(user)
    if clinic is not None:
        headers["X-Clinic-Id"] = str(clinic.id)
    return headers


# ---------------------------------------------------------------------------
# POST /api/v1/appointments — staff booking
# ---------------------------------------------------------------------------


class TestStaffBooking:
    async def test_receptionist_books_linked_patient(
        self, client, clinic, receptionist_user, receptionist_membership,
        doctor_user, doctor_profile, doctor_membership, approved_link, patient_user,
    ):
        resp = await client.post(
            "/api/v1/appointments",
            json={
                "patient_id": str(patient_user.id),
                "doctor_id": str(doctor_profile.id),
                "scheduled_at": FUTURE.isoformat(),
                "type": "in-person",
            },
            headers=_staff_headers(receptionist_user, clinic),
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["created_by"] == str(receptionist_user.id)
        assert body["clinic_id"] == str(clinic.id)
        assert body["patient_id"] == str(patient_user.id)
        assert body["doctor_id"] == str(doctor_profile.id)
        assert body["status"] == "scheduled"

    async def test_receptionist_books_unlinked_patient_403(
        self, client, db, clinic, receptionist_user, receptionist_membership,
        doctor_profile, doctor_membership,
    ):
        unlinked, _ = await _make_patient(db)
        resp = await client.post(
            "/api/v1/appointments",
            json={
                "patient_id": str(unlinked.id),
                "doctor_id": str(doctor_profile.id),
                "scheduled_at": FUTURE.isoformat(),
                "type": "in-person",
            },
            headers=_staff_headers(receptionist_user, clinic),
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "CONSENT_REQUIRED"

    async def test_receptionist_books_non_member_doctor_403(
        self, client, db, clinic, receptionist_user, receptionist_membership,
        approved_link, patient_user,
    ):
        """The booked doctor must be a member of the staff clinic."""
        _doc_user, other_profile, _ = await _make_doctor(db)
        resp = await client.post(
            "/api/v1/appointments",
            json={
                "patient_id": str(patient_user.id),
                "doctor_id": str(other_profile.id),
                "scheduled_at": FUTURE.isoformat(),
                "type": "in-person",
            },
            headers=_staff_headers(receptionist_user, clinic),
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "DOCTOR_NOT_IN_CLINIC"

    async def test_non_member_patient_cannot_book_for_others(
        self, client, db, clinic, doctor_profile, doctor_membership,
        approved_link, patient_user,
    ):
        """A plain patient (no membership) sending X-Clinic-Id gets the
        unchanged 'book for themselves' 403."""
        other_patient, _ = await _make_patient(db)
        resp = await client.post(
            "/api/v1/appointments",
            json={
                "patient_id": str(other_patient.id),  # booking for another user
                "doctor_id": str(doctor_profile.id),
                "scheduled_at": FUTURE.isoformat(),
                "type": "in-person",
            },
            headers=_staff_headers(patient_user, clinic),
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"


# ---------------------------------------------------------------------------
# PUT /api/v1/appointments/{id}/status — staff transitions
# ---------------------------------------------------------------------------


class TestStaffStatusTransitions:
    async def test_receptionist_advances_scheduled_to_arrived(
        self, client, db, clinic, receptionist_user, receptionist_membership,
        doctor_user, doctor_profile, doctor_membership, patient_user,
    ):
        appt = await _make_appointment(
            db, patient_id=patient_user.id, doctor_id=doctor_profile.id,
            clinic_id=clinic.id, created_by=doctor_user.id,
        )
        # No X-Clinic-Id header — the gate is membership at the appointment's
        # clinic, not the request header.
        resp = await client.put(
            f"/api/v1/appointments/{appt.id}/status",
            json={"status": "arrived"},
            headers=_staff_headers(receptionist_user),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "arrived"

    async def test_receptionist_arrived_to_in_progress(
        self, client, db, clinic, receptionist_user, receptionist_membership,
        doctor_user, doctor_profile, doctor_membership, patient_user,
    ):
        appt = await _make_appointment(
            db, patient_id=patient_user.id, doctor_id=doctor_profile.id,
            clinic_id=clinic.id, created_by=doctor_user.id, status="arrived",
        )
        resp = await client.put(
            f"/api/v1/appointments/{appt.id}/status",
            json={"status": "in-progress"},
            headers=_staff_headers(receptionist_user),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "in-progress"

    async def test_receptionist_can_cancel(
        self, client, db, clinic, receptionist_user, receptionist_membership,
        doctor_user, doctor_profile, doctor_membership, patient_user,
    ):
        appt = await _make_appointment(
            db, patient_id=patient_user.id, doctor_id=doctor_profile.id,
            clinic_id=clinic.id, created_by=doctor_user.id,
        )
        resp = await client.put(
            f"/api/v1/appointments/{appt.id}/status",
            json={"status": "cancelled", "cancelled_reason": "patient called"},
            headers=_staff_headers(receptionist_user),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "cancelled"

    async def test_receptionist_cannot_mark_completed(
        self, client, db, clinic, receptionist_user, receptionist_membership,
        doctor_user, doctor_profile, doctor_membership, patient_user,
    ):
        """in-progress → completed is clinical — front desk is excluded."""
        appt = await _make_appointment(
            db, patient_id=patient_user.id, doctor_id=doctor_profile.id,
            clinic_id=clinic.id, created_by=doctor_user.id, status="in-progress",
        )
        resp = await client.put(
            f"/api/v1/appointments/{appt.id}/status",
            json={"status": "completed"},
            headers=_staff_headers(receptionist_user),
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "INVALID_TRANSITION"

    async def test_receptionist_cannot_skip_scheduled_to_completed(
        self, client, db, clinic, receptionist_user, receptionist_membership,
        doctor_user, doctor_profile, doctor_membership, patient_user,
    ):
        appt = await _make_appointment(
            db, patient_id=patient_user.id, doctor_id=doctor_profile.id,
            clinic_id=clinic.id, created_by=doctor_user.id,
        )
        resp = await client.put(
            f"/api/v1/appointments/{appt.id}/status",
            json={"status": "completed"},
            headers=_staff_headers(receptionist_user),
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "INVALID_TRANSITION"

    async def test_non_member_patient_cannot_advance_status(
        self, client, db, clinic, doctor_user, doctor_profile,
        doctor_membership, patient_user,
    ):
        """A patient with no clinic membership is untouched by the staff path:
        the appointment belongs to someone else → 403."""
        other_patient, other_header = await _make_patient(db)
        appt = await _make_appointment(
            db, patient_id=other_patient.id, doctor_id=doctor_profile.id,
            clinic_id=clinic.id, created_by=doctor_user.id,
        )
        resp = await client.put(
            f"/api/v1/appointments/{appt.id}/status",
            json={"status": "arrived"},
            headers=make_auth_header(patient_user),
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# PUT /api/v1/appointments/{id} — staff reschedule
# ---------------------------------------------------------------------------


class TestStaffReschedule:
    async def test_receptionist_reschedules_appointment(
        self, client, db, clinic, receptionist_user, receptionist_membership,
        doctor_user, doctor_profile, doctor_membership, patient_user,
    ):
        appt = await _make_appointment(
            db, patient_id=patient_user.id, doctor_id=doctor_profile.id,
            clinic_id=clinic.id, created_by=doctor_user.id,
        )
        resp = await client.put(
            f"/api/v1/appointments/{appt.id}",
            json={"scheduled_at": FUTURE_2.isoformat()},
            headers=_staff_headers(receptionist_user),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["scheduled_at"].startswith(FUTURE_2.date().isoformat())
        assert body["status"] == "scheduled"

    async def test_non_member_patient_cannot_reschedule(
        self, client, db, clinic, doctor_user, doctor_profile,
        doctor_membership, patient_user,
    ):
        appt = await _make_appointment(
            db, patient_id=patient_user.id, doctor_id=doctor_profile.id,
            clinic_id=clinic.id, created_by=doctor_user.id,
        )
        resp = await client.put(
            f"/api/v1/appointments/{appt.id}",
            json={"scheduled_at": FUTURE_2.isoformat()},
            headers=make_auth_header(patient_user),
        )
        assert resp.status_code == 403
