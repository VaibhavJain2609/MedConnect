"""Round-5 coverage push on high-risk paths with no existing tests.

Covers:
- Admin CSV exports: text/csv + Content-Disposition, admin-only, role filter,
  row cap (_EXPORT_MAX_ROWS), and the EXPORT audit-trail entry.
- Receptionist enforcement: a user with doctor role + receptionist clinic
  membership must not author encounters / records / prescriptions
  (RECEPTIONIST_NO_CLINICAL_ACCESS), but CAN do front-desk queue work.
- Clinic queue: sequential queue numbers, tenant isolation, status transition
  machine (waiting -> in_consultation -> completed), terminal-state rejection,
  soft delete, and clinic-header/membership/auth gates.
- Encounter read/update/delete authorization: patient owner, authoring doctor,
  clinic admin member, platform admin; strangers rejected.

Skipped (endpoint absent in this worktree):
- POST /api/v1/patients/erasure — the r5-dpdp erasure endpoint is not merged
  here (no route in app/routers/patients.py).
- GET /api/v1/queue/my-position — no such route in app/routers/queue.py.
"""

import csv
import io
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment
from app.models.audit import AuditLog
from app.models.clinic import Clinic, ClinicMembership
from app.models.doctor import Doctor
from app.models.encounter import Encounter
from app.models.patient_link import PatientClinicLink
from app.models.user import User
from tests.conftest import make_auth_header

pytestmark = pytest.mark.asyncio

FUTURE = datetime.now(timezone.utc) + timedelta(days=3)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def clinic(db: AsyncSession, doctor_user: User) -> Clinic:
    c = Clinic(id=uuid.uuid4(), name="Coverage Clinic", city="Delhi", created_by=doctor_user.id)
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


@pytest_asyncio.fixture
async def second_clinic(db: AsyncSession, doctor_user: User) -> Clinic:
    c = Clinic(id=uuid.uuid4(), name="Other Clinic", city="Goa", created_by=doctor_user.id)
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
async def receptionist_membership(
    db: AsyncSession, clinic: Clinic, doctor_user: User
) -> ClinicMembership:
    """doctor_user keeps global role 'doctor' + a verified profile, but holds a
    receptionist membership at this clinic — the shape the receptionist guard
    is written against."""
    return await _membership(db, clinic.id, doctor_user.id, "receptionist")


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


def _parse_csv(resp) -> list[list[str]]:
    return list(csv.reader(io.StringIO(resp.text)))


# ---------------------------------------------------------------------------
# Admin CSV exports
# ---------------------------------------------------------------------------

EXPORT_ENDPOINTS = [
    "/api/v1/admin/export/users",
    "/api/v1/admin/export/patients",
    "/api/v1/admin/export/audit-logs",
    "/api/v1/admin/export/appointments",
    "/api/v1/admin/export/medicines",
]


class TestAdminExports:
    async def test_export_users_csv_shape(
        self, admin_client, admin_user, patient_user
    ):
        resp = await admin_client.get("/api/v1/admin/export/users")
        assert resp.status_code == 200, resp.text
        assert resp.headers["content-type"].startswith("text/csv")
        disposition = resp.headers["content-disposition"]
        assert "attachment" in disposition
        assert "users-export-" in disposition and disposition.endswith('.csv"')

        rows = _parse_csv(resp)
        assert rows[0] == [
            "id", "full_name", "email", "phone", "role", "is_active", "created_at",
        ]
        emails = {r[2] for r in rows[1:]}
        assert "admin@test.com" in emails
        assert "patient@test.com" in emails

    async def test_export_users_role_filter(
        self, admin_client, admin_user, patient_user
    ):
        resp = await admin_client.get("/api/v1/admin/export/users?role=patient")
        assert resp.status_code == 200
        rows = _parse_csv(resp)[1:]
        assert len(rows) == 1
        assert rows[0][2] == "patient@test.com"
        assert rows[0][4] == "patient"

    async def test_export_patients_only_contains_patients(
        self, admin_client, admin_user, patient_user, doctor_user
    ):
        resp = await admin_client.get("/api/v1/admin/export/patients")
        assert resp.status_code == 200
        rows = _parse_csv(resp)[1:]
        assert len(rows) == 1
        assert rows[0][4] == "patient"

    async def test_export_appointments_csv(
        self, admin_client, db, patient_user, doctor_profile, admin_user
    ):
        appt = Appointment(
            id=uuid.uuid4(),
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            scheduled_at=FUTURE,
            duration_minutes=30,
            type="in-person",
            status="scheduled",
            created_by=admin_user.id,
        )
        db.add(appt)
        await db.commit()

        resp = await admin_client.get("/api/v1/admin/export/appointments")
        assert resp.status_code == 200, resp.text
        assert "appointments-export-" in resp.headers["content-disposition"]
        rows = _parse_csv(resp)
        assert rows[0] == [
            "id", "patient_name", "doctor_name", "clinic",
            "scheduled_at", "status", "type",
        ]
        data = rows[1:]
        assert len(data) == 1
        assert data[0][0] == str(appt.id)
        assert data[0][1] == "Patient User"
        assert data[0][5] == "scheduled"

        # status filter excludes non-matching rows
        filtered = await admin_client.get(
            "/api/v1/admin/export/appointments?status=cancelled"
        )
        assert len(_parse_csv(filtered)) == 1  # header only

    async def test_export_audit_logs_csv(self, admin_client):
        resp = await admin_client.get("/api/v1/admin/export/audit-logs")
        assert resp.status_code == 200, resp.text
        assert "audit-logs-export-" in resp.headers["content-disposition"]
        rows = _parse_csv(resp)
        assert rows[0] == [
            "id", "table_name", "record_id", "action", "changed_by",
            "created_at", "old_values", "new_values",
        ]

    async def test_export_medicines_csv(
        self, admin_client, sample_brand
    ):
        resp = await admin_client.get("/api/v1/admin/export/medicines")
        assert resp.status_code == 200, resp.text
        assert "medicines-export-" in resp.headers["content-disposition"]
        rows = _parse_csv(resp)
        assert rows[0] == [
            "brand_name", "manufacturer", "salt_composition",
            "schedule", "dosage_form",
        ]
        data = rows[1:]
        assert len(data) == 1
        assert data[0][0] == "Crocin"
        assert data[0][1] == "GSK Pharmaceuticals"

    async def test_export_row_cap_respected(
        self, admin_client, admin_user, patient_user, doctor_user, monkeypatch
    ):
        """_EXPORT_MAX_ROWS caps the CSV even when more rows exist."""
        monkeypatch.setattr("app.routers.admin.exports._EXPORT_MAX_ROWS", 2)
        resp = await admin_client.get("/api/v1/admin/export/users")
        assert resp.status_code == 200
        assert len(_parse_csv(resp)) == 1 + 2  # header + capped rows

    async def test_export_writes_audit_entry(self, admin_client, db, admin_user):
        resp = await admin_client.get("/api/v1/admin/export/users")
        assert resp.status_code == 200
        logs = (
            await db.execute(
                select(AuditLog).where(
                    AuditLog.action == "EXPORT", AuditLog.table_name == "users"
                )
            )
        ).scalars().all()
        assert len(logs) >= 1
        assert logs[0].new_values["row_count"] >= 1

    @pytest.mark.parametrize("endpoint", EXPORT_ENDPOINTS)
    async def test_export_requires_admin(self, patient_client, endpoint):
        resp = await patient_client.get(endpoint)
        assert resp.status_code == 403

    @pytest.mark.parametrize("endpoint", EXPORT_ENDPOINTS)
    async def test_export_requires_auth(self, client, endpoint):
        resp = await client.get(endpoint)
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Receptionist enforcement (access_service membership-role checks)
# ---------------------------------------------------------------------------


class TestReceptionistClinicalAccess:
    async def test_receptionist_cannot_create_encounter(
        self, doctor_client, clinic, receptionist_membership, approved_link, patient_user
    ):
        """Relationship + membership both pass; only the role gate blocks."""
        resp = await doctor_client.post(
            "/api/v1/encounters",
            json={
                "patient_id": str(patient_user.id),
                "clinic_id": str(clinic.id),
                "subjective": "front desk note",
            },
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "RECEPTIONIST_NO_CLINICAL_ACCESS"

    async def test_receptionist_cannot_create_medical_record(
        self, doctor_client, clinic, receptionist_membership, approved_link, patient_user
    ):
        resp = await doctor_client.post(
            "/api/v1/doctors/records",
            json={
                "patient_id": str(patient_user.id),
                "record_type": "opd_note",
                "title": "Receptionist note",
            },
            headers={"X-Clinic-Id": str(clinic.id)},
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "RECEPTIONIST_NO_CLINICAL_ACCESS"

    async def test_receptionist_cannot_create_prescription(
        self, doctor_client, clinic, receptionist_membership, approved_link, patient_user
    ):
        resp = await doctor_client.post(
            "/api/v1/doctors/prescriptions",
            json={
                "patient_id": str(patient_user.id),
                "medicines": [
                    {"brand_name": "Crocin", "dose": "500mg",
                     "frequency": "BD", "duration": "5 days"}
                ],
            },
            headers={"X-Clinic-Id": str(clinic.id)},
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "RECEPTIONIST_NO_CLINICAL_ACCESS"

    async def test_doctor_member_can_create_encounter(
        self, doctor_client, clinic, owner_membership, approved_link, patient_user
    ):
        """Control: an owner membership + approved link clears every gate."""
        resp = await doctor_client.post(
            "/api/v1/encounters",
            json={
                "patient_id": str(patient_user.id),
                "clinic_id": str(clinic.id),
                "subjective": "headache",
                "assessment": "migraine",
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["clinic_id"] == str(clinic.id)
        assert body["patient_name"] == "Patient User"
        assert body["doctor_name"] == "Doctor User"

    async def test_receptionist_can_run_front_desk_queue(
        self, doctor_client, clinic, receptionist_membership, patient_user
    ):
        """Receptionists handle check-in — queue endpoints must NOT block them."""
        resp = await doctor_client.post(
            "/api/v1/queue",
            json={"patient_id": str(patient_user.id)},
            headers={"X-Clinic-Id": str(clinic.id)},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["queue_number"] == 1
        assert resp.json()["status"] == "waiting"


# ---------------------------------------------------------------------------
# Clinic queue
# ---------------------------------------------------------------------------


class TestQueueOperations:
    async def test_sequential_queue_numbers(
        self, doctor_client, db, clinic, owner_membership, patient_user
    ):
        other_patient, _ = await _make_patient(db)
        headers = {"X-Clinic-Id": str(clinic.id)}

        first = await doctor_client.post(
            "/api/v1/queue", json={"patient_id": str(patient_user.id)}, headers=headers
        )
        second = await doctor_client.post(
            "/api/v1/queue", json={"patient_id": str(other_patient.id)}, headers=headers
        )
        assert first.status_code == 201 and second.status_code == 201
        assert first.json()["queue_number"] == 1
        assert second.json()["queue_number"] == 2
        assert second.json()["patient_name"] == "Other Patient"

    async def test_add_unknown_patient_404(
        self, doctor_client, clinic, owner_membership
    ):
        resp = await doctor_client.post(
            "/api/v1/queue",
            json={"patient_id": str(uuid.uuid4())},
            headers={"X-Clinic-Id": str(clinic.id)},
        )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "NOT_FOUND"

    async def test_add_unknown_doctor_404(
        self, doctor_client, clinic, owner_membership, patient_user
    ):
        resp = await doctor_client.post(
            "/api/v1/queue",
            json={
                "patient_id": str(patient_user.id),
                "doctor_id": str(uuid.uuid4()),
            },
            headers={"X-Clinic-Id": str(clinic.id)},
        )
        assert resp.status_code == 404

    async def test_add_inactive_patient_404(
        self, doctor_client, db, clinic, owner_membership
    ):
        ghost, _ = await _make_patient(db)
        ghost.is_active = False
        await db.commit()
        resp = await doctor_client.post(
            "/api/v1/queue",
            json={"patient_id": str(ghost.id)},
            headers={"X-Clinic-Id": str(clinic.id)},
        )
        assert resp.status_code == 404

    async def test_get_queue_lists_today_and_filters(
        self, doctor_client, db, clinic, owner_membership, patient_user
    ):
        headers = {"X-Clinic-Id": str(clinic.id)}
        await doctor_client.post(
            "/api/v1/queue", json={"patient_id": str(patient_user.id)}, headers=headers
        )

        listing = await doctor_client.get("/api/v1/queue", headers=headers)
        assert listing.status_code == 200
        body = listing.json()
        assert body["total"] == 1
        assert body["data"][0]["status"] == "waiting"

        waiting = await doctor_client.get(
            "/api/v1/queue?status=waiting", headers=headers
        )
        assert waiting.json()["total"] == 1
        done = await doctor_client.get(
            "/api/v1/queue?status=completed", headers=headers
        )
        assert done.json()["total"] == 0

        bad = await doctor_client.get(
            "/api/v1/queue?status=bogus", headers=headers
        )
        assert bad.status_code == 400
        assert bad.json()["error"]["code"] == "INVALID_STATUS"

    async def test_status_transition_happy_path(
        self, doctor_client, clinic, owner_membership, patient_user
    ):
        headers = {"X-Clinic-Id": str(clinic.id)}
        created = await doctor_client.post(
            "/api/v1/queue", json={"patient_id": str(patient_user.id)}, headers=headers
        )
        entry_id = created.json()["id"]

        called = await doctor_client.patch(
            f"/api/v1/queue/{entry_id}/status",
            json={"status": "in_consultation"},
            headers=headers,
        )
        assert called.status_code == 200
        assert called.json()["status"] == "in_consultation"
        assert called.json()["called_at"] is not None

        completed = await doctor_client.patch(
            f"/api/v1/queue/{entry_id}/status",
            json={"status": "completed"},
            headers=headers,
        )
        assert completed.status_code == 200
        assert completed.json()["completed_at"] is not None

    async def test_invalid_transition_rejected(
        self, doctor_client, clinic, owner_membership, patient_user
    ):
        headers = {"X-Clinic-Id": str(clinic.id)}
        created = await doctor_client.post(
            "/api/v1/queue", json={"patient_id": str(patient_user.id)}, headers=headers
        )
        entry_id = created.json()["id"]

        # waiting -> completed is not a legal transition.
        # NB: the endpoint raises 422 INVALID_TRANSITION, but the global
        # @app.exception_handler(422) (MD-395) flattens every 422 —
        # including deliberate domain errors — to 400 VALIDATION_ERROR,
        # so the specific code never reaches the client.
        skip = await doctor_client.patch(
            f"/api/v1/queue/{entry_id}/status",
            json={"status": "completed"},
            headers=headers,
        )
        assert skip.status_code == 400
        assert skip.json()["error"]["code"] == "VALIDATION_ERROR"

    async def test_terminal_state_rejected(
        self, doctor_client, clinic, owner_membership, patient_user
    ):
        headers = {"X-Clinic-Id": str(clinic.id)}
        created = await doctor_client.post(
            "/api/v1/queue", json={"patient_id": str(patient_user.id)}, headers=headers
        )
        entry_id = created.json()["id"]
        await doctor_client.patch(
            f"/api/v1/queue/{entry_id}/status",
            json={"status": "cancelled"},
            headers=headers,
        )
        # cancelled is terminal — any further transition is rejected.
        # (422 INVALID_TRANSITION -> flattened to 400 VALIDATION_ERROR, see above)
        again = await doctor_client.patch(
            f"/api/v1/queue/{entry_id}/status",
            json={"status": "in_consultation"},
            headers=headers,
        )
        assert again.status_code == 400
        assert again.json()["error"]["code"] == "VALIDATION_ERROR"

    async def test_queue_entry_tenant_isolation(
        self, doctor_client, db, clinic, second_clinic, owner_membership, patient_user
    ):
        """An entry in clinic A is invisible to a member acting under clinic B."""
        await _membership(db, second_clinic.id, owner_membership.user_id, "doctor")
        created = await doctor_client.post(
            "/api/v1/queue",
            json={"patient_id": str(patient_user.id)},
            headers={"X-Clinic-Id": str(clinic.id)},
        )
        entry_id = created.json()["id"]

        cross = await doctor_client.get(
            f"/api/v1/queue/{entry_id}",
            headers={"X-Clinic-Id": str(second_clinic.id)},
        )
        assert cross.status_code == 404

        same = await doctor_client.get(
            f"/api/v1/queue/{entry_id}",
            headers={"X-Clinic-Id": str(clinic.id)},
        )
        assert same.status_code == 200
        assert same.json()["id"] == entry_id

    async def test_remove_from_queue(
        self, doctor_client, clinic, owner_membership, patient_user
    ):
        headers = {"X-Clinic-Id": str(clinic.id)}
        created = await doctor_client.post(
            "/api/v1/queue", json={"patient_id": str(patient_user.id)}, headers=headers
        )
        entry_id = created.json()["id"]

        removed = await doctor_client.delete(f"/api/v1/queue/{entry_id}", headers=headers)
        assert removed.status_code == 204

        gone = await doctor_client.get(f"/api/v1/queue/{entry_id}", headers=headers)
        assert gone.status_code == 404

        # soft-deleted entry no longer appears in today's list
        listing = await doctor_client.get("/api/v1/queue", headers=headers)
        assert listing.json()["total"] == 0

    async def test_missing_clinic_header_400(self, doctor_client):
        resp = await doctor_client.get("/api/v1/queue")
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "MISSING_CLINIC"

    async def test_non_member_rejected(
        self, client, db, clinic, owner_membership
    ):
        _, _, outsider_auth = await _make_doctor(db)
        resp = await client.get(
            "/api/v1/queue",
            headers={**outsider_auth, "X-Clinic-Id": str(clinic.id)},
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "NOT_CLINIC_MEMBER"

    async def test_unauthenticated_401(self, client, clinic):
        resp = await client.get(
            "/api/v1/queue", headers={"X-Clinic-Id": str(clinic.id)}
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Encounter read/update/delete authorization
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


class TestEncounterAccess:
    async def test_patient_reads_own_encounter(
        self, patient_client, encounter, patient_user
    ):
        resp = await patient_client.get(f"/api/v1/encounters/{encounter.id}")
        assert resp.status_code == 200
        assert resp.json()["patient_id"] == str(patient_user.id)

    async def test_other_patient_cannot_read(
        self, client, db, encounter
    ):
        _, stranger_auth = await _make_patient(db)
        resp = await client.get(
            f"/api/v1/encounters/{encounter.id}", headers=stranger_auth
        )
        assert resp.status_code == 403

    async def test_other_doctor_cannot_read(
        self, client, db, encounter, owner_membership
    ):
        _, _, outsider_auth = await _make_doctor(db)
        resp = await client.get(
            f"/api/v1/encounters/{encounter.id}", headers=outsider_auth
        )
        assert resp.status_code == 403

    async def test_clinic_admin_member_can_read(
        self, client, db, encounter, clinic
    ):
        """A non-authoring doctor with owner/admin membership on the
        encounter's clinic may read it (clinic-admin path)."""
        clinic_admin, _, clinic_admin_auth = await _make_doctor(
            db, email="clinic-admin@test.com"
        )
        await _membership(db, clinic.id, clinic_admin.id, "admin")

        resp = await client.get(
            f"/api/v1/encounters/{encounter.id}", headers=clinic_admin_auth
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == str(encounter.id)

    async def test_admin_can_read_and_delete(
        self, admin_client, encounter
    ):
        got = await admin_client.get(f"/api/v1/encounters/{encounter.id}")
        assert got.status_code == 200

        deleted = await admin_client.delete(f"/api/v1/encounters/{encounter.id}")
        assert deleted.status_code == 204

        gone = await admin_client.get(f"/api/v1/encounters/{encounter.id}")
        assert gone.status_code == 404

    async def test_author_can_update(
        self, doctor_client, encounter
    ):
        resp = await doctor_client.patch(
            f"/api/v1/encounters/{encounter.id}",
            json={"plan": "rest and ibuprofen"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["plan"] == "rest and ibuprofen"

    async def test_non_author_cannot_update(
        self, client, db, encounter
    ):
        _, _, outsider_auth = await _make_doctor(db)
        resp = await client.patch(
            f"/api/v1/encounters/{encounter.id}",
            json={"plan": "tampered"},
            headers=outsider_auth,
        )
        assert resp.status_code == 403

    async def test_patient_cannot_delete(
        self, patient_client, encounter
    ):
        resp = await patient_client.delete(f"/api/v1/encounters/{encounter.id}")
        assert resp.status_code == 403

    @pytest.mark.xfail(
        strict=True,
        reason="BUG: list_encounters calls _load_encounters_with_names() which is "
               "not defined — only the singular _load_encounter_with_names exists "
               "(app/routers/encounters.py:337). GET /api/v1/encounters always 500s.",
    )
    async def test_list_encounters_scoped_by_role(
        self, doctor_client, patient_client, client, db, encounter
    ):
        mine = await doctor_client.get("/api/v1/encounters")
        assert mine.status_code == 200
        assert mine.json()["total"] == 1

        patient_view = await patient_client.get("/api/v1/encounters")
        assert patient_view.json()["total"] == 1

        _, _, outsider_auth = await _make_doctor(db)
        stranger = await client.get("/api/v1/encounters", headers=outsider_auth)
        assert stranger.status_code == 200
        assert stranger.json()["total"] == 0

    async def test_get_missing_encounter_404(self, doctor_client):
        resp = await doctor_client.get(f"/api/v1/encounters/{uuid.uuid4()}")
        assert resp.status_code == 404
