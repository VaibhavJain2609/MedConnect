"""Round-8 coverage: /api/v1/encounters lifecycle + record amendment semantics.

Covers what test_r5_coverage.py's TestEncounterAccess did not:
- POST /encounters: full SOAP field echo, appointment-as-relationship
  short-circuit (non-terminal statuses only), appointment mismatch / unknown
  appointment / unknown patient / non-patient target, no-relationship 403,
  clinic membership gate, inherited clinic from appointment.
- GET /encounters: patient_id / appointment_id / date filters, invalid date
  400, pagination, doctor-without-profile 404.
- PATCH /encounters: in-place update semantics (no version row — unlike
  medical-record amendments), clinic_id cannot be cleared once set.
- DELETE /encounters: author soft-delete removes it from list + detail.
- Clinic-member visibility: owner/admin members read; a plain "doctor"-role
  member who is not the author cannot.
- POST /doctors/records/{id}/amend: amendment semantics verified directly —
  amend creates a NEW row linked via amended_from_id (original preserved),
  chained amendments rejected (422 CANNOT_AMEND_AMENDMENT), non-author 403.

Fixtures/helpers are copied from test_r5_coverage.py — no cross-test-file
imports beyond conftest helpers.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

# Register ReminderLog in Base.metadata: the shared test DB may contain a
# stale reminder_logs table (created by migrations or a concurrent run on a
# branch whose metadata includes it). Its FK to appointments would otherwise
# make this file's teardown drop_all fail with DependentObjectsStillExist.
import app.models.reminder_log  # noqa: F401
from app.models.appointment import Appointment
from app.models.clinic import Clinic, ClinicMembership
from app.models.doctor import Doctor
from app.models.encounter import Encounter
from app.models.medical_record import MedicalRecord
from app.models.patient_link import PatientClinicLink
from app.models.user import User
from tests.conftest import grant_doctor_patient_relationship, make_auth_header

pytestmark = pytest.mark.asyncio

FUTURE = datetime.now(timezone.utc) + timedelta(days=3)


# ---------------------------------------------------------------------------
# Fixtures / helpers (copied from test_r5_coverage.py)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def clinic(db: AsyncSession, doctor_user: User) -> Clinic:
    c = Clinic(id=uuid.uuid4(), name="Enc Clinic", city="Delhi", created_by=doctor_user.id)
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
async def owner_membership(db: AsyncSession, clinic: Clinic, doctor_user: User) -> ClinicMembership:
    return await _membership(db, clinic.id, doctor_user.id, "owner")


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
) -> Appointment:
    appt = Appointment(
        id=uuid.uuid4(),
        patient_id=patient_id,
        doctor_id=doctor_id,
        clinic_id=clinic_id,
        scheduled_at=FUTURE,
        duration_minutes=30,
        type="in-person",
        status=status,
        created_by=created_by,
    )
    db.add(appt)
    await db.commit()
    await db.refresh(appt)
    return appt


async def _count_encounters(db: AsyncSession) -> int:
    return await db.scalar(select(func.count()).select_from(Encounter)) or 0


# ---------------------------------------------------------------------------
# POST /api/v1/encounters — create
# ---------------------------------------------------------------------------


class TestEncounterCreate:
    @pytest.mark.smoke
    async def test_create_full_soap_fields(
        self, doctor_client, doctor_profile, clinic, owner_membership,
        approved_link, patient_user,
    ):
        vitals = {"bp": "120/80", "hr": 72, "spo2": 98}
        resp = await doctor_client.post(
            "/api/v1/encounters",
            json={
                "patient_id": str(patient_user.id),
                "clinic_id": str(clinic.id),
                "subjective": "headache for 3 days",
                "objective": "afebrile, no focal deficits",
                "assessment": "tension headache",
                "plan": "rest, hydration, paracetamol PRN",
                "vitals_snapshot": vitals,
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["patient_id"] == str(patient_user.id)
        assert body["doctor_id"] == str(doctor_profile.id)
        assert body["clinic_id"] == str(clinic.id)
        assert body["subjective"] == "headache for 3 days"
        assert body["objective"] == "afebrile, no focal deficits"
        assert body["assessment"] == "tension headache"
        assert body["plan"] == "rest, hydration, paracetamol PRN"
        assert body["vitals_snapshot"] == vitals
        # Denormalized display names populated by _load_encounter_with_names
        assert body["patient_name"] == "Patient User"
        assert body["doctor_name"] == "Doctor User"
        assert body["clinic_name"] == "Enc Clinic"
        assert body["appointment_id"] is None
        assert body["created_at"] and body["updated_at"]

    async def test_create_via_appointment_short_circuits_relationship(
        self, doctor_client, db, doctor_user, doctor_profile, patient_user
    ):
        """A non-terminal appointment IS the relationship proof — no prior
        record or clinic link needed."""
        appt = await _make_appointment(
            db, patient_id=patient_user.id, doctor_id=doctor_profile.id,
            created_by=doctor_user.id,
        )
        resp = await doctor_client.post(
            "/api/v1/encounters",
            json={
                "patient_id": str(patient_user.id),
                "appointment_id": str(appt.id),
                "subjective": "follow-up visit",
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["appointment_id"] == str(appt.id)
        assert body["clinic_id"] is None  # appointment had no clinic

    async def test_create_inherits_clinic_from_appointment(
        self, doctor_client, db, doctor_user, doctor_profile,
        clinic, owner_membership, patient_user,
    ):
        """clinic_id omitted → inherited from the appointment's clinic
        (doctor must be a member of it)."""
        appt = await _make_appointment(
            db, patient_id=patient_user.id, doctor_id=doctor_profile.id,
            clinic_id=clinic.id, created_by=doctor_user.id,
        )
        resp = await doctor_client.post(
            "/api/v1/encounters",
            json={
                "patient_id": str(patient_user.id),
                "appointment_id": str(appt.id),
                "subjective": "clinic visit",
            },
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["clinic_id"] == str(clinic.id)
        assert resp.json()["clinic_name"] == "Enc Clinic"

    async def test_create_terminal_appointment_denied(
        self, doctor_client, db, doctor_user, doctor_profile, patient_user
    ):
        """A cancelled appointment is not an active relationship — with no
        other relationship the write is denied."""
        appt = await _make_appointment(
            db, patient_id=patient_user.id, doctor_id=doctor_profile.id,
            created_by=doctor_user.id, status="cancelled",
        )
        resp = await doctor_client.post(
            "/api/v1/encounters",
            json={
                "patient_id": str(patient_user.id),
                "appointment_id": str(appt.id),
                "subjective": "stale booking",
            },
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "PATIENT_ACCESS_DENIED"

    async def test_create_appointment_mismatch_403(
        self, doctor_client, db, doctor_user, doctor_profile, patient_user
    ):
        """Appointment must belong to THIS doctor + THIS patient."""
        _, other_profile, _ = await _make_doctor(db)
        appt = await _make_appointment(
            db, patient_id=patient_user.id, doctor_id=other_profile.id,
            created_by=doctor_user.id,
        )
        resp = await doctor_client.post(
            "/api/v1/encounters",
            json={
                "patient_id": str(patient_user.id),
                "appointment_id": str(appt.id),
            },
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "APPOINTMENT_MISMATCH"

    async def test_create_unknown_appointment_404(
        self, doctor_client, patient_user
    ):
        resp = await doctor_client.post(
            "/api/v1/encounters",
            json={
                "patient_id": str(patient_user.id),
                "appointment_id": str(uuid.uuid4()),
            },
        )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "NOT_FOUND"

    async def test_create_unknown_patient_404(self, doctor_client):
        resp = await doctor_client.post(
            "/api/v1/encounters",
            json={"patient_id": str(uuid.uuid4()), "subjective": "x"},
        )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "NOT_FOUND"

    async def test_create_rejects_non_patient_target(
        self, doctor_client, db, doctor_user
    ):
        """patient_id pointing at a doctor-role user is a 404, not a 403 —
        the patient lookup filters on role='patient'."""
        resp = await doctor_client.post(
            "/api/v1/encounters",
            json={"patient_id": str(doctor_user.id), "subjective": "x"},
        )
        assert resp.status_code == 404

    async def test_create_no_relationship_403(
        self, doctor_client, patient_user
    ):
        """Verified doctor, real patient, but no record/link/appointment."""
        resp = await doctor_client.post(
            "/api/v1/encounters",
            json={"patient_id": str(patient_user.id), "subjective": "x"},
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "PATIENT_ACCESS_DENIED"

    async def test_create_non_member_clinic_403(
        self, doctor_client, db, doctor_user, doctor_profile,
        clinic, patient_user,
    ):
        """Relationship exists (authored record) but the doctor holds no
        membership at the requested clinic."""
        await grant_doctor_patient_relationship(
            db, doctor_user.keycloak_sub, patient_user.id
        )
        resp = await doctor_client.post(
            "/api/v1/encounters",
            json={
                "patient_id": str(patient_user.id),
                "clinic_id": str(clinic.id),
            },
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "NOT_CLINIC_MEMBER"

    async def test_create_patient_caller_403(
        self, patient_client, patient_user
    ):
        """Encounters are doctor-authored — a patient caller fails the
        get_verified_doctor gate."""
        resp = await patient_client.post(
            "/api/v1/encounters",
            json={"patient_id": str(patient_user.id), "subjective": "x"},
        )
        assert resp.status_code == 403

    async def test_create_requires_auth(self, client, patient_user):
        resp = await client.post(
            "/api/v1/encounters",
            json={"patient_id": str(patient_user.id)},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v1/encounters — list + filters
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def encounter(
    db: AsyncSession, doctor_profile: Doctor, patient_user: User, clinic: Clinic
) -> Encounter:
    enc = Encounter(
        id=uuid.uuid4(),
        patient_id=patient_user.id,
        doctor_id=doctor_profile.id,
        clinic_id=clinic.id,
        subjective="chest pain",
        assessment="muscular strain",
    )
    db.add(enc)
    await db.commit()
    await db.refresh(enc)
    return enc


class TestEncounterList:
    async def test_list_patient_id_filter_scoped_to_doctor(
        self, doctor_client, db, doctor_profile, patient_user, encounter
    ):
        """?patient_id narrows within the doctor's own encounters only."""
        other_patient, _ = await _make_patient(db)
        db.add(
            Encounter(
                id=uuid.uuid4(),
                patient_id=other_patient.id,
                doctor_id=doctor_profile.id,
                subjective="other",
            )
        )
        await db.commit()

        filtered = await doctor_client.get(
            f"/api/v1/encounters?patient_id={patient_user.id}"
        )
        assert filtered.status_code == 200
        body = filtered.json()
        assert body["total"] == 1
        assert body["data"][0]["patient_id"] == str(patient_user.id)
        assert body["data"][0]["patient_name"] == "Patient User"

        empty = await doctor_client.get(
            f"/api/v1/encounters?patient_id={uuid.uuid4()}"
        )
        assert empty.json()["total"] == 0

    async def test_list_appointment_id_filter(
        self, doctor_client, db, doctor_user, doctor_profile, patient_user, encounter
    ):
        appt = await _make_appointment(
            db, patient_id=patient_user.id, doctor_id=doctor_profile.id,
            created_by=doctor_user.id,
        )
        db.add(
            Encounter(
                id=uuid.uuid4(),
                patient_id=patient_user.id,
                doctor_id=doctor_profile.id,
                appointment_id=appt.id,
                subjective="linked",
            )
        )
        await db.commit()

        resp = await doctor_client.get(
            f"/api/v1/encounters?appointment_id={appt.id}"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["data"][0]["subjective"] == "linked"

        miss = await doctor_client.get(
            f"/api/v1/encounters?appointment_id={uuid.uuid4()}"
        )
        assert miss.json()["total"] == 0

    async def test_list_date_filter(
        self, doctor_client, encounter
    ):
        today = datetime.now(timezone.utc).date().isoformat()
        resp = await doctor_client.get(f"/api/v1/encounters?date={today}")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

        old = await doctor_client.get("/api/v1/encounters?date=1999-01-01")
        assert old.json()["total"] == 0

    async def test_list_invalid_date_400(self, doctor_client):
        resp = await doctor_client.get("/api/v1/encounters?date=not-a-date")
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_DATE"

    async def test_list_pagination(
        self, doctor_client, db, doctor_profile, patient_user
    ):
        # created_at is server_default=func.now() — a transaction timestamp —
        # so rows committed together tie; assign explicit times to test the
        # newest-first ordering deterministically.
        base = datetime.now(timezone.utc) - timedelta(minutes=10)
        for i in range(3):
            db.add(
                Encounter(
                    id=uuid.uuid4(),
                    patient_id=patient_user.id,
                    doctor_id=doctor_profile.id,
                    subjective=f"visit {i}",
                    created_at=base + timedelta(minutes=i),
                )
            )
        await db.commit()

        page1 = await doctor_client.get("/api/v1/encounters?limit=2&offset=0")
        assert page1.status_code == 200
        assert page1.json()["total"] == 3
        assert len(page1.json()["data"]) == 2

        page2 = await doctor_client.get("/api/v1/encounters?limit=2&offset=2")
        assert len(page2.json()["data"]) == 1

        # newest first
        assert page1.json()["data"][0]["subjective"] == "visit 2"

        # limit bound enforced by query validation (le=100)
        too_many = await doctor_client.get("/api/v1/encounters?limit=101")
        assert too_many.status_code == 422

    async def test_list_doctor_without_profile_404(self, client, db):
        """A doctor-role user with no Doctor row gets NOT_FOUND, not an
        empty list — the profile is required to scope the query."""
        user = User(
            keycloak_sub=f"doctor-{uuid.uuid4()}",
            email="noprof@test.com",
            full_name="No Profile",
            role="doctor",
        )
        db.add(user)
        await db.commit()
        resp = await client.get(
            "/api/v1/encounters", headers=make_auth_header(user, roles=["doctor"])
        )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "NOT_FOUND"

    async def test_list_patient_filter_for_admin(
        self, admin_client, db, doctor_profile, patient_user, encounter
    ):
        """Admin sees all encounters; patient_id filter applies globally."""
        other_patient, _ = await _make_patient(db)
        db.add(
            Encounter(
                id=uuid.uuid4(),
                patient_id=other_patient.id,
                doctor_id=doctor_profile.id,
                subjective="admin-visible",
            )
        )
        await db.commit()

        all_resp = await admin_client.get("/api/v1/encounters")
        assert all_resp.json()["total"] == 2

        filtered = await admin_client.get(
            f"/api/v1/encounters?patient_id={other_patient.id}"
        )
        assert filtered.json()["total"] == 1
        assert filtered.json()["data"][0]["subjective"] == "admin-visible"


# ---------------------------------------------------------------------------
# GET /api/v1/encounters/{id} — detail + clinic-member visibility
# ---------------------------------------------------------------------------


class TestEncounterDetail:
    async def test_detail_includes_display_names(
        self, doctor_client, encounter, patient_user, clinic
    ):
        resp = await doctor_client.get(f"/api/v1/encounters/{encounter.id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["patient_name"] == "Patient User"
        assert body["doctor_name"] == "Doctor User"
        assert body["clinic_name"] == "Enc Clinic"
        assert body["subjective"] == "chest pain"

    async def test_detail_without_clinic(
        self, doctor_client, db, doctor_profile, patient_user
    ):
        enc = Encounter(
            id=uuid.uuid4(),
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            subjective="walk-in",
        )
        db.add(enc)
        await db.commit()
        resp = await doctor_client.get(f"/api/v1/encounters/{enc.id}")
        assert resp.status_code == 200
        assert resp.json()["clinic_id"] is None
        assert resp.json()["clinic_name"] is None

    async def test_doctor_role_member_not_author_403(
        self, client, db, encounter, clinic
    ):
        """Clinic-member visibility is owner/admin only — a 'doctor'-role
        member of the encounter's clinic who is not the author is denied."""
        member, _, member_auth = await _make_doctor(db, email="member@test.com")
        await _membership(db, clinic.id, member.id, "doctor")
        resp = await client.get(
            f"/api/v1/encounters/{encounter.id}", headers=member_auth
        )
        assert resp.status_code == 403

    async def test_receptionist_member_not_author_403(
        self, client, db, encounter, clinic
    ):
        """Same for a receptionist membership — front desk does not read
        clinical notes."""
        recep, _, recep_auth = await _make_doctor(db, email="recep@test.com")
        await _membership(db, clinic.id, recep.id, "receptionist")
        resp = await client.get(
            f"/api/v1/encounters/{encounter.id}", headers=recep_auth
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# PATCH /api/v1/encounters/{id} — in-place amend (no versioning)
# ---------------------------------------------------------------------------


class TestEncounterUpdate:
    async def test_patch_updates_in_place(
        self, doctor_client, db, encounter
    ):
        """Encounter 'amend' is an in-place PATCH — the same row is mutated,
        no version row is created (contrast with record amendments below)."""
        before_count = await _count_encounters(db)
        resp = await doctor_client.patch(
            f"/api/v1/encounters/{encounter.id}",
            json={
                "plan": "rest and ibuprofen",
                "vitals_snapshot": {"bp": "118/76"},
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["id"] == str(encounter.id)  # same row, not a new version
        assert body["plan"] == "rest and ibuprofen"
        assert body["vitals_snapshot"] == {"bp": "118/76"}
        assert body["assessment"] == "muscular strain"  # untouched field
        assert await _count_encounters(db) == before_count

    async def test_patch_cannot_clear_clinic_id(
        self, doctor_client, encounter
    ):
        """Clearing clinic_id would hide the note from clinic admins —
        the API refuses with a domain 400."""
        resp = await doctor_client.patch(
            f"/api/v1/encounters/{encounter.id}",
            json={"clinic_id": None},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

    async def test_patch_relink_appointment_mismatch_403(
        self, doctor_client, db, doctor_user, doctor_profile, encounter
    ):
        other_patient, _ = await _make_patient(db)
        appt = await _make_appointment(
            db, patient_id=other_patient.id, doctor_id=doctor_profile.id,
            created_by=doctor_user.id,
        )
        resp = await doctor_client.patch(
            f"/api/v1/encounters/{encounter.id}",
            json={"appointment_id": str(appt.id)},
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "APPOINTMENT_MISMATCH"

    async def test_patch_missing_404(self, doctor_client):
        resp = await doctor_client.patch(
            f"/api/v1/encounters/{uuid.uuid4()}", json={"plan": "x"}
        )
        assert resp.status_code == 404

    async def test_patch_patient_caller_403(self, patient_client, encounter):
        resp = await patient_client.patch(
            f"/api/v1/encounters/{encounter.id}", json={"plan": "tampered"}
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# DELETE /api/v1/encounters/{id} — soft delete
# ---------------------------------------------------------------------------


class TestEncounterDelete:
    async def test_author_soft_delete_excludes_from_list(
        self, doctor_client, db, encounter
    ):
        resp = await doctor_client.delete(f"/api/v1/encounters/{encounter.id}")
        assert resp.status_code == 204

        # Row still exists but is tombstoned
        await db.refresh(encounter)
        assert encounter.deleted_at is not None

        # ...and is invisible to list + detail
        listing = await doctor_client.get("/api/v1/encounters")
        assert listing.json()["total"] == 0
        gone = await doctor_client.get(f"/api/v1/encounters/{encounter.id}")
        assert gone.status_code == 404

    async def test_soft_deleted_encounter_hidden_from_patient_list(
        self, client, encounter, doctor_user, patient_user
    ):
        # NOTE: doctor_client/patient_client share one AsyncClient — mixing
        # them in a single test makes the last-built fixture's Authorization
        # header win. Use explicit per-request headers instead.
        deleted = await client.delete(
            f"/api/v1/encounters/{encounter.id}",
            headers=make_auth_header(doctor_user, roles=["doctor"]),
        )
        assert deleted.status_code == 204
        listing = await client.get(
            "/api/v1/encounters", headers=make_auth_header(patient_user)
        )
        assert listing.json()["total"] == 0

    async def test_non_author_doctor_cannot_delete(
        self, client, db, encounter
    ):
        _, _, outsider_auth = await _make_doctor(db)
        resp = await client.delete(
            f"/api/v1/encounters/{encounter.id}", headers=outsider_auth
        )
        assert resp.status_code == 403

    async def test_delete_missing_404(self, doctor_client):
        resp = await doctor_client.delete(f"/api/v1/encounters/{uuid.uuid4()}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/v1/doctors/records/{id}/amend — amendment semantics
# (the only "amend" surface: encounters PATCH in place, records version)
# ---------------------------------------------------------------------------


class TestRecordAmendment:
    async def _seed_record(
        self, db: AsyncSession, patient_id, doctor_id, **kwargs
    ) -> MedicalRecord:
        rec = MedicalRecord(
            id=uuid.uuid4(),
            patient_id=patient_id,
            doctor_id=doctor_id,
            record_type=kwargs.pop("record_type", "opd_note"),
            title=kwargs.pop("title", "Original note"),
            **kwargs,
        )
        db.add(rec)
        await db.commit()
        await db.refresh(rec)
        return rec

    async def test_amend_creates_new_version_row(
        self, doctor_client, db, doctor_profile, patient_user
    ):
        """amend_record does NOT update in place — it inserts a new
        MedicalRecord linked back via amended_from_id, source='amended',
        and leaves the original untouched."""
        original = await self._seed_record(
            db, patient_user.id, doctor_profile.id
        )
        resp = await doctor_client.post(
            f"/api/v1/doctors/records/{original.id}/amend",
            json={
                "record_type": "opd_note",
                "title": "Corrected note",
                "description": "fixed the dosage text",
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["id"] != str(original.id)
        assert body["amended_from_id"] == str(original.id)
        assert body["source"] == "amended"
        assert body["title"] == "Corrected note"
        assert body["patient_id"] == str(patient_user.id)
        assert body["doctor_id"] == str(doctor_profile.id)

        # Two rows now exist; the original is preserved byte-for-byte.
        rows = (
            await db.execute(
                select(MedicalRecord).where(MedicalRecord.deleted_at.is_(None))
            )
        ).scalars().all()
        assert len(rows) == 2
        await db.refresh(original)
        assert original.title == "Original note"
        assert original.amended_from_id is None
        assert original.source == "manual"

    async def test_cannot_amend_an_amendment(
        self, doctor_client, db, doctor_profile, patient_user
    ):
        """MD-392: amendments are terminal — amend the original instead."""
        original = await self._seed_record(
            db, patient_user.id, doctor_profile.id
        )
        first = await doctor_client.post(
            f"/api/v1/doctors/records/{original.id}/amend",
            json={"record_type": "opd_note", "title": "v2"},
        )
        assert first.status_code == 201
        chained = await doctor_client.post(
            f"/api/v1/doctors/records/{first.json()['id']}/amend",
            json={"record_type": "opd_note", "title": "v3"},
        )
        # Deliberate HTTPException(422) domain envelope passes through
        # (main.py validation_exception_handler).
        assert chained.status_code == 422
        assert chained.json()["error"]["code"] == "CANNOT_AMEND_AMENDMENT"

    async def test_non_author_cannot_amend(
        self, client, db, doctor_profile, patient_user
    ):
        original = await self._seed_record(
            db, patient_user.id, doctor_profile.id
        )
        _, _, outsider_auth = await _make_doctor(db)
        resp = await client.post(
            f"/api/v1/doctors/records/{original.id}/amend",
            json={"record_type": "opd_note", "title": "hostile edit"},
            headers=outsider_auth,
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "NOT_AUTHOR"

    async def test_amend_missing_record_404(self, doctor_client):
        resp = await doctor_client.post(
            f"/api/v1/doctors/records/{uuid.uuid4()}/amend",
            json={"record_type": "opd_note", "title": "ghost"},
        )
        assert resp.status_code == 404

    async def test_amendments_listed_in_order(
        self, doctor_client, db, doctor_profile, patient_user
    ):
        original = await self._seed_record(
            db, patient_user.id, doctor_profile.id
        )
        for title in ("v2", "v3"):
            resp = await doctor_client.post(
                f"/api/v1/doctors/records/{original.id}/amend",
                json={"record_type": "opd_note", "title": title},
            )
            assert resp.status_code == 201

        listing = await doctor_client.get(
            f"/api/v1/doctors/records/{original.id}/amendments"
        )
        assert listing.status_code == 200, listing.text
        body = listing.json()
        assert body["total"] == 2
        assert body["original_record_id"] == str(original.id)
        titles = [a["title"] for a in body["data"]]
        assert titles == ["v2", "v3"]  # ascending created_at
        assert all(
            a["amended_from_id"] == str(original.id) for a in body["data"]
        )
