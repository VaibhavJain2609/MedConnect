"""Tests for teleconsult (Jitsi) meeting-room wiring on appointments.

Covers:
- Deterministic room URL ``{JITSI_BASE_URL}/mc-{appointment.id hex}`` on create
- Idempotency: status transitions and link regeneration keep the same room
- Backfill on status→arrived/in-progress for rows created without a room
- No room when JITSI_BASE_URL is unset (empty)
- Room only for ``type == "teleconsult"`` appointments
- URL scoping: patient, doctor, clinic members and admin see it; other users don't
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.appointment import Appointment
from app.models.clinic import Clinic, ClinicMembership
from app.models.doctor import Doctor
from app.models.user import User
from tests.conftest import create_test_token, make_auth_header

pytestmark = pytest.mark.asyncio

FUTURE = datetime.now(timezone.utc) + timedelta(days=3)

BOOK_PAYLOAD = {
    "scheduled_at": FUTURE.isoformat(),
    "duration_minutes": 30,
    "type": "teleconsult",
}


def _expected_url(appointment_id: uuid.UUID | str) -> str:
    base = settings.JITSI_BASE_URL.strip().rstrip("/")
    return f"{base}/mc-{uuid.UUID(str(appointment_id)).hex}"


async def _make_appointment(
    db: AsyncSession,
    *,
    patient_id: uuid.UUID,
    doctor_id: uuid.UUID,
    created_by: uuid.UUID,
    type: str = "teleconsult",
    status: str = "scheduled",
    clinic_id: uuid.UUID | None = None,
    meeting_url: str | None = None,
) -> Appointment:
    appt = Appointment(
        id=uuid.uuid4(),
        patient_id=patient_id,
        doctor_id=doctor_id,
        clinic_id=clinic_id,
        scheduled_at=FUTURE,
        duration_minutes=30,
        type=type,
        status=status,
        meeting_url=meeting_url,
        created_by=created_by,
    )
    db.add(appt)
    await db.commit()
    await db.refresh(appt)
    return appt


async def _make_other_patient(db: AsyncSession) -> User:
    user = User(
        keycloak_sub=f"patient-{uuid.uuid4()}",
        email="other-patient@test.com",
        full_name="Other Patient",
        role="patient",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _make_other_doctor(db: AsyncSession) -> tuple[User, Doctor]:
    user = User(
        keycloak_sub=f"doctor-{uuid.uuid4()}",
        email="other-doctor@test.com",
        full_name="Other Doctor",
        role="doctor",
    )
    db.add(user)
    await db.flush()
    profile = Doctor(
        id=uuid.uuid4(),
        user_id=user.id,
        specialization="Dermatology",
        verified=True,
        onboarding_step="completed",
    )
    db.add(profile)
    await db.commit()
    await db.refresh(user)
    await db.refresh(profile)
    return user, profile


class TestRoomGeneration:
    async def test_create_generates_deterministic_room(
        self, doctor_client, doctor_profile, patient_user, db
    ):
        from tests.conftest import grant_doctor_patient_relationship

        await grant_doctor_patient_relationship(db, "doctor-123", patient_user.id)
        res = await doctor_client.post(
            "/api/v1/appointments",
            json={
                "patient_id": str(patient_user.id),
                "doctor_id": str(doctor_profile.id),
                **BOOK_PAYLOAD,
            },
        )
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["teleconsult_url"] == _expected_url(body["id"])
        assert body["meeting_url"] == body["teleconsult_url"]

    async def test_room_is_idempotent_across_transitions_and_regenerate(
        self, doctor_client, doctor_profile, patient_user, db
    ):
        appt = await _make_appointment(
            db,
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            created_by=doctor_profile.user_id,
        )
        url = _expected_url(appt.id)

        arrived = await doctor_client.put(
            f"/api/v1/appointments/{appt.id}/status", json={"status": "arrived"}
        )
        assert arrived.status_code == 200, arrived.text
        assert arrived.json()["teleconsult_url"] == url

        in_progress = await doctor_client.put(
            f"/api/v1/appointments/{appt.id}/status", json={"status": "in-progress"}
        )
        assert in_progress.status_code == 200, in_progress.text
        assert in_progress.json()["teleconsult_url"] == url

        # "Regenerate" returns the same deterministic room
        regen = await doctor_client.post(f"/api/v1/appointments/{appt.id}/meeting-link")
        assert regen.status_code == 200, regen.text
        assert regen.json()["teleconsult_url"] == url

    async def test_arrived_backfills_missing_room(
        self, doctor_client, doctor_profile, patient_user, db
    ):
        """Rows created while JITSI_BASE_URL was unset get a room on arrival."""
        appt = await _make_appointment(
            db,
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            created_by=doctor_profile.user_id,
            meeting_url=None,
        )
        res = await doctor_client.put(
            f"/api/v1/appointments/{appt.id}/status", json={"status": "arrived"}
        )
        assert res.status_code == 200, res.text
        assert res.json()["teleconsult_url"] == _expected_url(appt.id)

    async def test_no_room_when_jitsi_base_url_unset(
        self, doctor_client, doctor_profile, patient_user, db, monkeypatch
    ):
        monkeypatch.setattr(settings, "JITSI_BASE_URL", "")
        from tests.conftest import grant_doctor_patient_relationship

        await grant_doctor_patient_relationship(db, "doctor-123", patient_user.id)
        res = await doctor_client.post(
            "/api/v1/appointments",
            json={
                "patient_id": str(patient_user.id),
                "doctor_id": str(doctor_profile.id),
                **BOOK_PAYLOAD,
            },
        )
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["teleconsult_url"] is None
        assert body["meeting_url"] is None

        # No room on status transition either while unset
        appt_id = body["id"]
        arrived = await doctor_client.put(
            f"/api/v1/appointments/{appt_id}/status", json={"status": "arrived"}
        )
        assert arrived.status_code == 200, arrived.text
        assert arrived.json()["teleconsult_url"] is None

    async def test_in_person_appointment_gets_no_room(
        self, doctor_client, doctor_profile, patient_user, db
    ):
        from tests.conftest import grant_doctor_patient_relationship

        await grant_doctor_patient_relationship(db, "doctor-123", patient_user.id)
        res = await doctor_client.post(
            "/api/v1/appointments",
            json={
                "patient_id": str(patient_user.id),
                "doctor_id": str(doctor_profile.id),
                **{**BOOK_PAYLOAD, "type": "in-person"},
            },
        )
        assert res.status_code == 201, res.text
        assert res.json()["teleconsult_url"] is None


class TestUrlScoping:
    """teleconsult_url must only reach the appointment's patient, its doctor,
    clinic members, and admins — never other users."""

    async def test_participants_see_url_others_forbidden(
        self, client, db, doctor_profile, doctor_user, patient_user, admin_user
    ):
        appt = await _make_appointment(
            db,
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            created_by=doctor_user.id,
            meeting_url=None,
        )
        # Give it the deterministic room directly
        appt.meeting_url = _expected_url(appt.id)
        await db.commit()

        # Patient sees it
        res = await client.get(
            f"/api/v1/appointments/{appt.id}", headers=make_auth_header(patient_user)
        )
        assert res.status_code == 200, res.text
        assert res.json()["teleconsult_url"] == _expected_url(appt.id)

        # Doctor sees it
        res = await client.get(
            f"/api/v1/appointments/{appt.id}", headers=make_auth_header(doctor_user, ["doctor"])
        )
        assert res.status_code == 200, res.text
        assert res.json()["teleconsult_url"] == _expected_url(appt.id)

        # Admin sees it
        res = await client.get(
            f"/api/v1/appointments/{appt.id}", headers=make_auth_header(admin_user, ["admin"])
        )
        assert res.status_code == 200, res.text
        assert res.json()["teleconsult_url"] == _expected_url(appt.id)

        # Another patient cannot read the appointment at all
        other_patient = await _make_other_patient(db)
        res = await client.get(
            f"/api/v1/appointments/{appt.id}", headers=make_auth_header(other_patient)
        )
        assert res.status_code == 403

        # Another doctor cannot read the appointment at all
        other_doctor_user, _ = await _make_other_doctor(db)
        res = await client.get(
            f"/api/v1/appointments/{appt.id}",
            headers=make_auth_header(other_doctor_user, ["doctor"]),
        )
        assert res.status_code == 403

    async def test_clinic_member_sees_url_in_clinic_list(
        self, client, db, doctor_profile, doctor_user, patient_user
    ):
        """Clinic members (e.g. receptionist role) see teleconsult_url on the
        clinic-scoped appointment list — the X-Clinic-Id membership gate."""
        clinic = Clinic(
            id=uuid.uuid4(), name="Tele Clinic", city="Pune", created_by=doctor_user.id
        )
        db.add(clinic)
        await db.flush()
        receptionist = User(
            keycloak_sub=f"staff-{uuid.uuid4()}",
            email="receptionist@test.com",
            full_name="Front Desk",
            role="patient",  # global role irrelevant — membership grants access
        )
        db.add(receptionist)
        await db.flush()
        db.add(
            ClinicMembership(
                id=uuid.uuid4(),
                clinic_id=clinic.id,
                user_id=receptionist.id,
                role="receptionist",
                is_active=True,
            )
        )
        appt = await _make_appointment(
            db,
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            clinic_id=clinic.id,
            created_by=doctor_user.id,
            meeting_url=None,
        )
        appt.meeting_url = _expected_url(appt.id)
        await db.commit()

        res = await client.get(
            "/api/v1/appointments?upcoming=true",
            headers={**make_auth_header(receptionist), "X-Clinic-Id": str(clinic.id)},
        )
        assert res.status_code == 200, res.text
        rows = [a for a in res.json()["data"] if a["id"] == str(appt.id)]
        assert len(rows) == 1
        assert rows[0]["teleconsult_url"] == _expected_url(appt.id)

        # A non-member patient cannot list the clinic's appointments —
        # get_active_clinic rejects the header outright with NOT_CLINIC_MEMBER
        stranger = await _make_other_patient(db)
        res = await client.get(
            "/api/v1/appointments",
            headers={**make_auth_header(stranger), "X-Clinic-Id": str(clinic.id)},
        )
        assert res.status_code == 403
        assert res.json()["error"]["code"] == "NOT_CLINIC_MEMBER"

    async def test_meeting_link_endpoint_rejects_non_participants(
        self, client, db, doctor_profile, doctor_user, patient_user
    ):
        appt = await _make_appointment(
            db,
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            created_by=doctor_user.id,
        )
        other_patient = await _make_other_patient(db)
        res = await client.post(
            f"/api/v1/appointments/{appt.id}/meeting-link",
            headers=make_auth_header(other_patient),
        )
        assert res.status_code == 403

        other_doctor_user, _ = await _make_other_doctor(db)
        res = await client.post(
            f"/api/v1/appointments/{appt.id}/meeting-link",
            headers=make_auth_header(other_doctor_user, ["doctor"]),
        )
        assert res.status_code == 403
