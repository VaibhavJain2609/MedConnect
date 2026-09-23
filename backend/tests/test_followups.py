"""Round-14 coverage: POST /api/v1/encounters/{id}/follow-up.

Covers:
- Happy path: creates a scheduled appointment for the encounter's patient /
  doctor / clinic, linked back via appointments.source_encounter_id; the
  encounter GET then exposes it under ``follow_up``.
- Idempotency: a second POST returns 200 with the SAME appointment — no
  duplicate rows.
- Auth scoping: unrelated doctor 403, patient 403, unauthenticated 401/403;
  a verified doctor who is a clinic member (not the author) IS allowed.
- Linkage: the appointment shows source_encounter_id in GET /appointments/{id}
  and appears in the patient's normal appointment list.
- Scheduling guards mirror POST /appointments: past time 400, invalid type
  400, doctor double-booking 409, unknown encounter 404.

Fixture/helper style mirrors test_encounters.py.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import app.models.reminder_log  # noqa: F401 — register table for drop_all teardown
from app.models.appointment import Appointment
from app.models.clinic import Clinic, ClinicMembership
from app.models.doctor import Doctor
from app.models.encounter import Encounter
from app.models.patient_link import PatientClinicLink
from app.models.user import User
from tests.conftest import make_auth_header

pytestmark = pytest.mark.asyncio

FUTURE = datetime.now(timezone.utc) + timedelta(days=10)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


async def _make_encounter(
    db: AsyncSession,
    *,
    patient_id,
    doctor_id,
    clinic_id=None,
) -> Encounter:
    enc = Encounter(
        id=uuid.uuid4(),
        patient_id=patient_id,
        doctor_id=doctor_id,
        clinic_id=clinic_id,
        subjective="routine visit",
    )
    db.add(enc)
    await db.commit()
    await db.refresh(enc)
    return enc


async def _count_followups(db: AsyncSession, encounter_id) -> int:
    return (
        await db.scalar(
            select(func.count())
            .select_from(Appointment)
            .where(
                Appointment.source_encounter_id == encounter_id,
                Appointment.deleted_at.is_(None),
            )
        )
        or 0
    )


# ---------------------------------------------------------------------------
# POST /api/v1/encounters/{id}/follow-up
# ---------------------------------------------------------------------------


class TestFollowUpCreate:
    async def test_create_follow_up_success(
        self, doctor_client, db, doctor_user, doctor_profile, patient_user
    ):
        enc = await _make_encounter(
            db, patient_id=patient_user.id, doctor_id=doctor_profile.id
        )
        resp = await doctor_client.post(
            f"/api/v1/encounters/{enc.id}/follow-up",
            json={
                "scheduled_at": FUTURE.isoformat(),
                "duration_minutes": 20,
                "notes": "recheck BP",
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["patient_id"] == str(patient_user.id)
        assert body["doctor_id"] == str(doctor_profile.id)
        assert body["type"] == "follow-up"
        assert body["status"] == "scheduled"
        assert body["duration_minutes"] == 20
        assert body["notes"] == "recheck BP"
        assert body["source_encounter_id"] == str(enc.id)
        assert body["created_by"] == str(doctor_user.id)

        # The encounter GET now exposes the follow-up summary.
        enc_resp = await doctor_client.get(f"/api/v1/encounters/{enc.id}")
        assert enc_resp.status_code == 200
        follow_up = enc_resp.json()["follow_up"]
        assert follow_up is not None
        assert follow_up["id"] == body["id"]
        assert follow_up["status"] == "scheduled"
        assert follow_up["type"] == "follow-up"

    async def test_follow_up_inherits_clinic(
        self, doctor_client, db, doctor_user, doctor_profile, patient_user
    ):
        clinic = Clinic(
            id=uuid.uuid4(), name="FU Clinic", city="Delhi", created_by=doctor_user.id
        )
        db.add(clinic)
        await db.flush()
        db.add(
            ClinicMembership(
                id=uuid.uuid4(),
                clinic_id=clinic.id,
                user_id=doctor_user.id,
                role="owner",
                is_active=True,
            )
        )
        await db.commit()

        enc = await _make_encounter(
            db,
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            clinic_id=clinic.id,
        )
        resp = await doctor_client.post(
            f"/api/v1/encounters/{enc.id}/follow-up",
            json={"scheduled_at": FUTURE.isoformat()},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["clinic_id"] == str(clinic.id)

    async def test_idempotent_second_call_returns_existing(
        self, doctor_client, db, doctor_profile, patient_user
    ):
        enc = await _make_encounter(
            db, patient_id=patient_user.id, doctor_id=doctor_profile.id
        )
        first = await doctor_client.post(
            f"/api/v1/encounters/{enc.id}/follow-up",
            json={"scheduled_at": FUTURE.isoformat()},
        )
        assert first.status_code == 201, first.text

        # A second call — even with different payload — returns the existing
        # appointment unchanged (no duplicate booking).
        second = await doctor_client.post(
            f"/api/v1/encounters/{enc.id}/follow-up",
            json={
                "scheduled_at": (FUTURE + timedelta(days=2)).isoformat(),
                "notes": "different notes",
            },
        )
        assert second.status_code == 200, second.text
        assert second.json()["id"] == first.json()["id"]
        assert second.json()["scheduled_at"] == first.json()["scheduled_at"]
        assert await _count_followups(db, enc.id) == 1

    async def test_other_doctor_forbidden(
        self, client, db, doctor_user, doctor_profile, patient_user
    ):
        enc = await _make_encounter(
            db, patient_id=patient_user.id, doctor_id=doctor_profile.id
        )
        _, _, other_header = await _make_doctor(db)
        resp = await client.post(
            f"/api/v1/encounters/{enc.id}/follow-up",
            json={"scheduled_at": FUTURE.isoformat()},
            headers=other_header,
        )
        assert resp.status_code == 403, resp.text
        assert await _count_followups(db, enc.id) == 0

    async def test_clinic_member_doctor_allowed(
        self, client, db, doctor_user, doctor_profile, patient_user
    ):
        """A verified doctor who isn't the author but holds an active
        membership on the encounter's clinic may book the follow-up; the
        appointment still belongs to the encounter's doctor."""
        clinic = Clinic(
            id=uuid.uuid4(), name="FU Clinic", city="Delhi", created_by=doctor_user.id
        )
        db.add(clinic)
        await db.flush()
        db.add(
            ClinicMembership(
                id=uuid.uuid4(),
                clinic_id=clinic.id,
                user_id=doctor_user.id,
                role="owner",
                is_active=True,
            )
        )
        other_user, _, other_header = await _make_doctor(db)
        db.add(
            ClinicMembership(
                id=uuid.uuid4(),
                clinic_id=clinic.id,
                user_id=other_user.id,
                role="doctor",
                is_active=True,
            )
        )
        await db.commit()

        enc = await _make_encounter(
            db,
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            clinic_id=clinic.id,
        )
        resp = await client.post(
            f"/api/v1/encounters/{enc.id}/follow-up",
            json={"scheduled_at": FUTURE.isoformat()},
            headers=other_header,
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["doctor_id"] == str(doctor_profile.id)  # encounter's doctor
        assert body["created_by"] == str(other_user.id)

    async def test_patient_forbidden(
        self, patient_client, db, doctor_profile, patient_user
    ):
        enc = await _make_encounter(
            db, patient_id=patient_user.id, doctor_id=doctor_profile.id
        )
        resp = await patient_client.post(
            f"/api/v1/encounters/{enc.id}/follow-up",
            json={"scheduled_at": FUTURE.isoformat()},
        )
        assert resp.status_code == 403, resp.text

    async def test_unauthenticated_rejected(
        self, client, db, doctor_profile, patient_user
    ):
        enc = await _make_encounter(
            db, patient_id=patient_user.id, doctor_id=doctor_profile.id
        )
        resp = await client.post(
            f"/api/v1/encounters/{enc.id}/follow-up",
            json={"scheduled_at": FUTURE.isoformat()},
        )
        assert resp.status_code in (401, 403), resp.text

    async def test_appointment_linkage_and_patient_visibility(
        self, client, db, doctor_user, doctor_profile, patient_user
    ):
        """The follow-up is a normal appointment: the patient sees it in
        their list and the detail carries source_encounter_id.

        NB: doctor_client/patient_client share one httpx client's headers, so
        this test drives both roles through ``client`` with explicit headers.
        """
        doctor_header = make_auth_header(doctor_user, roles=["doctor"])
        patient_header = make_auth_header(patient_user)

        enc = await _make_encounter(
            db, patient_id=patient_user.id, doctor_id=doctor_profile.id
        )
        created = await client.post(
            f"/api/v1/encounters/{enc.id}/follow-up",
            json={"scheduled_at": FUTURE.isoformat()},
            headers=doctor_header,
        )
        assert created.status_code == 201, created.text
        appt_id = created.json()["id"]

        detail = await client.get(
            f"/api/v1/appointments/{appt_id}", headers=doctor_header
        )
        assert detail.status_code == 200, detail.text
        assert detail.json()["source_encounter_id"] == str(enc.id)

        listed = await client.get(
            "/api/v1/appointments?upcoming=true", headers=patient_header
        )
        assert listed.status_code == 200, listed.text
        ids = [a["id"] for a in listed.json()["data"]]
        assert appt_id in ids

    async def test_encounter_not_found(self, doctor_client):
        resp = await doctor_client.post(
            f"/api/v1/encounters/{uuid.uuid4()}/follow-up",
            json={"scheduled_at": FUTURE.isoformat()},
        )
        assert resp.status_code == 404, resp.text

    async def test_invalid_type_400(
        self, doctor_client, db, doctor_profile, patient_user
    ):
        enc = await _make_encounter(
            db, patient_id=patient_user.id, doctor_id=doctor_profile.id
        )
        resp = await doctor_client.post(
            f"/api/v1/encounters/{enc.id}/follow-up",
            json={"scheduled_at": FUTURE.isoformat(), "type": "emergency"},
        )
        assert resp.status_code == 400, resp.text

    async def test_past_scheduled_at_400(
        self, doctor_client, db, doctor_profile, patient_user
    ):
        enc = await _make_encounter(
            db, patient_id=patient_user.id, doctor_id=doctor_profile.id
        )
        past = datetime.now(timezone.utc) - timedelta(days=1)
        resp = await doctor_client.post(
            f"/api/v1/encounters/{enc.id}/follow-up",
            json={"scheduled_at": past.isoformat()},
        )
        assert resp.status_code == 400, resp.text

    async def test_doctor_double_booking_409(
        self, doctor_client, db, doctor_user, doctor_profile, patient_user
    ):
        """An overlapping active appointment on the doctor's calendar blocks
        the follow-up — same guard as POST /appointments."""
        db.add(
            Appointment(
                id=uuid.uuid4(),
                patient_id=patient_user.id,
                doctor_id=doctor_profile.id,
                scheduled_at=FUTURE,
                duration_minutes=30,
                type="in-person",
                status="scheduled",
                created_by=doctor_user.id,
            )
        )
        enc = await _make_encounter(
            db, patient_id=patient_user.id, doctor_id=doctor_profile.id
        )
        await db.commit()

        resp = await doctor_client.post(
            f"/api/v1/encounters/{enc.id}/follow-up",
            json={"scheduled_at": (FUTURE + timedelta(minutes=10)).isoformat()},
        )
        assert resp.status_code == 409, resp.text
