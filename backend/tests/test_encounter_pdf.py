"""Round-9: GET /api/v1/encounters/{id}/summary-pdf — visit summary export.

Covers:
- 200 + application/pdf + %PDF magic for the authoring doctor, the patient
  owner, an admin, and an owner/admin member of the encounter's clinic.
- ?download=true flips Content-Disposition inline → attachment.
- 403 for a stranger patient and a non-author doctor with no clinic
  owner/admin membership (authz mirrors GET /encounters/{id} exactly).
- 404 for a missing/soft-deleted encounter; 401 unauthenticated.
- Appointment-linked encounter exercises the visit-type + linked
  prescription (medicines JSONB) rendering path.

Fixtures/helpers are copied from test_encounters.py — no cross-test-file
imports beyond conftest helpers.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

# Register ReminderLog in Base.metadata (see test_encounters.py for why).
import app.models.reminder_log  # noqa: F401
from app.models.appointment import Appointment
from app.models.clinic import Clinic, ClinicMembership
from app.models.doctor import Doctor
from app.models.encounter import Encounter
from app.models.medical_record import MedicalRecord
from app.models.prescription import Prescription
from app.models.user import User
from tests.conftest import make_auth_header

pytestmark = pytest.mark.asyncio

FUTURE = datetime.now(timezone.utc) + timedelta(days=3)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def clinic(db: AsyncSession, doctor_user: User) -> Clinic:
    c = Clinic(id=uuid.uuid4(), name="PDF Clinic", city="Pune", created_by=doctor_user.id)
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


async def _make_doctor(
    db: AsyncSession, email: str = "other-doc@test.com"
) -> tuple[User, Doctor, dict]:
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


@pytest_asyncio.fixture
async def encounter(
    db: AsyncSession, doctor_profile: Doctor, patient_user: User, clinic: Clinic
) -> Encounter:
    """Walk-in encounter (no appointment) with a vitals snapshot."""
    enc = Encounter(
        id=uuid.uuid4(),
        patient_id=patient_user.id,
        doctor_id=doctor_profile.id,
        clinic_id=clinic.id,
        subjective="fever and sore throat for 2 days",
        objective="pharyngeal erythema; afebrile at visit",
        assessment="acute pharyngitis",
        plan="warm saline gargles; paracetamol PRN; review in 3 days",
        vitals_snapshot={"pulse": 88, "spo2": 99, "temperature_c": 37.2},
    )
    db.add(enc)
    await db.commit()
    await db.refresh(enc)
    return enc


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestEncounterSummaryPdf:
    async def test_doctor_can_download_summary_pdf(
        self, doctor_client, encounter
    ):
        resp = await doctor_client.get(
            f"/api/v1/encounters/{encounter.id}/summary-pdf"
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content[:5] == b"%PDF-"
        assert len(resp.content) > 500
        disposition = resp.headers.get("content-disposition", "")
        assert "inline" in disposition
        assert "visit-summary-" in disposition

    async def test_download_true_forces_attachment(
        self, doctor_client, encounter
    ):
        resp = await doctor_client.get(
            f"/api/v1/encounters/{encounter.id}/summary-pdf?download=true"
        )
        assert resp.status_code == 200
        assert "attachment" in resp.headers.get("content-disposition", "")

    async def test_patient_owner_can_download(
        self, patient_client, encounter
    ):
        resp = await patient_client.get(
            f"/api/v1/encounters/{encounter.id}/summary-pdf"
        )
        assert resp.status_code == 200
        assert resp.content[:5] == b"%PDF-"

    async def test_admin_can_download(self, admin_client, encounter):
        resp = await admin_client.get(
            f"/api/v1/encounters/{encounter.id}/summary-pdf"
        )
        assert resp.status_code == 200
        assert resp.content[:5] == b"%PDF-"

    async def test_clinic_admin_member_can_download(
        self, client, db, encounter, clinic
    ):
        """A non-author doctor holding an admin membership on the
        encounter's clinic can export the summary (mirrors detail authz)."""
        member, _, member_auth = await _make_doctor(db, email="clinicadmin@test.com")
        await _membership(db, clinic.id, member.id, "admin")
        resp = await client.get(
            f"/api/v1/encounters/{encounter.id}/summary-pdf", headers=member_auth
        )
        assert resp.status_code == 200
        assert resp.content[:5] == b"%PDF-"

    async def test_appointment_linked_encounter_with_prescription(
        self, doctor_client, db, doctor_user, doctor_profile, patient_user
    ):
        """Appointment-linked encounter renders visit type + the medicines
        of the prescription sharing the same appointment_id."""
        appt = Appointment(
            id=uuid.uuid4(),
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            scheduled_at=FUTURE,
            duration_minutes=30,
            type="in-person",
            status="completed",
            created_by=doctor_user.id,
        )
        record = MedicalRecord(
            id=uuid.uuid4(),
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            record_type="opd_note",
            title="Visit record",
        )
        enc = Encounter(
            id=uuid.uuid4(),
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            appointment_id=appt.id,
            subjective="follow-up",
        )
        rx = Prescription(
            id=uuid.uuid4(),
            record_id=record.id,
            doctor_id=doctor_profile.id,
            patient_id=patient_user.id,
            appointment_id=appt.id,
            medicines=[
                {
                    "brand_name": "Amoxicillin 500mg",
                    "dose": "500mg",
                    "frequency": "3 times daily",
                    "duration": "5 days",
                    "instructions": "after food",
                }
            ],
            diagnosis="pharyngitis",
        )
        db.add_all([appt, record, enc, rx])
        await db.commit()

        resp = await doctor_client.get(
            f"/api/v1/encounters/{enc.id}/summary-pdf"
        )
        assert resp.status_code == 200
        assert resp.content[:5] == b"%PDF-"

    async def test_minimal_encounter_renders(
        self, doctor_client, db, doctor_profile, patient_user
    ):
        """No clinic, no vitals, no SOAP text — the PDF still builds."""
        enc = Encounter(
            id=uuid.uuid4(),
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
        )
        db.add(enc)
        await db.commit()

        resp = await doctor_client.get(
            f"/api/v1/encounters/{enc.id}/summary-pdf"
        )
        assert resp.status_code == 200
        assert resp.content[:5] == b"%PDF-"


# ---------------------------------------------------------------------------
# Authz / errors
# ---------------------------------------------------------------------------


class TestEncounterSummaryPdfAuthz:
    async def test_other_patient_403(self, client, db, encounter):
        _, stranger_auth = await _make_patient(db)
        resp = await client.get(
            f"/api/v1/encounters/{encounter.id}/summary-pdf",
            headers=stranger_auth,
        )
        assert resp.status_code == 403

    async def test_non_author_doctor_without_clinic_role_403(
        self, client, db, encounter, clinic
    ):
        """A plain 'doctor'-role clinic member who did not author the note
        is denied — same rule as GET /encounters/{id}."""
        member, _, member_auth = await _make_doctor(db, email="member@test.com")
        await _membership(db, clinic.id, member.id, "doctor")
        resp = await client.get(
            f"/api/v1/encounters/{encounter.id}/summary-pdf", headers=member_auth
        )
        assert resp.status_code == 403

    async def test_missing_encounter_404(self, doctor_client):
        resp = await doctor_client.get(
            f"/api/v1/encounters/{uuid.uuid4()}/summary-pdf"
        )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "NOT_FOUND"

    async def test_soft_deleted_encounter_404(
        self, doctor_client, db, encounter
    ):
        encounter.deleted_at = datetime.now(timezone.utc)
        await db.commit()
        resp = await doctor_client.get(
            f"/api/v1/encounters/{encounter.id}/summary-pdf"
        )
        assert resp.status_code == 404

    async def test_unauthenticated_401(self, client, encounter):
        client.headers.pop("Authorization", None)
        resp = await client.get(f"/api/v1/encounters/{encounter.id}/summary-pdf")
        assert resp.status_code == 401
