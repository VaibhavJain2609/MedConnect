"""Tests for the list-mirroring admin CSV exports.

GET /api/v1/admin/patients/export      — mirrors GET /api/v1/admin/users?role=patient
GET /api/v1/admin/appointments/export  — mirrors the /admin/appointments page
                                         (GET /api/v1/appointments?all=true + page filters)

Both stream text/csv, honor the list endpoints' filters, cap at
app.routers.admin.exports._LIST_EXPORT_MAX_ROWS (50k), and write an
action="EXPORT" audit_logs row per download.
"""

import csv
import io
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment
from app.models.audit import AuditLog
from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.patient_link import PatientClinicLink
from app.models.user import User

PATIENTS_URL = "/api/v1/admin/patients/export"
APPOINTMENTS_URL = "/api/v1/admin/appointments/export"

PATIENTS_HEADER = ["id", "name", "email", "phone", "joined_date", "clinic_links_count"]
APPTS_HEADER = ["id", "patient_name", "doctor_name", "clinic", "scheduled_at", "status"]


def _parse_csv(resp) -> list[list[str]]:
    return list(csv.reader(io.StringIO(resp.text)))


def _patient(name: str, **kwargs) -> User:
    return User(
        keycloak_sub=f"walkin:{uuid.uuid4()}",
        full_name=name,
        role="patient",
        **kwargs,
    )


async def _make_doctor(db: AsyncSession, name: str = "Dr Strange") -> Doctor:
    user = User(
        keycloak_sub=f"doc:{uuid.uuid4()}",
        full_name=name,
        email=f"{uuid.uuid4().hex[:8]}@test.com",
        role="doctor",
    )
    db.add(user)
    await db.flush()
    doctor = Doctor(id=uuid.uuid4(), user_id=user.id)
    db.add(doctor)
    await db.flush()
    return doctor


def _appointment(
    patient_id: uuid.UUID,
    doctor_id: uuid.UUID,
    created_by: uuid.UUID,
    scheduled_at: datetime,
    **kwargs,
) -> Appointment:
    kwargs.setdefault("status", "scheduled")
    return Appointment(
        patient_id=patient_id,
        doctor_id=doctor_id,
        created_by=created_by,
        scheduled_at=scheduled_at,
        duration_minutes=30,
        type="in-person",
        **kwargs,
    )


class TestPatientsExport:
    async def test_csv_shape_headers_and_links_count(
        self, admin_client, db: AsyncSession, admin_user: User
    ):
        alice = _patient("Alice Rao", email="alice@test.com", phone="9999999999")
        bob = _patient("Bob Shah")
        db.add_all([alice, bob])
        clinic = Clinic(name="City Clinic")
        db.add(clinic)
        await db.flush()
        db.add(
            PatientClinicLink(
                patient_id=alice.id,
                clinic_id=clinic.id,
                linked_by=admin_user.id,
                consent_status="approved",
            )
        )
        await db.commit()

        resp = await admin_client.get(PATIENTS_URL)
        assert resp.status_code == 200, resp.text
        assert resp.headers["content-type"].startswith("text/csv")
        disposition = resp.headers["content-disposition"]
        assert "attachment" in disposition
        assert "patients-export-" in disposition and disposition.endswith('.csv"')

        rows = _parse_csv(resp)
        assert rows[0] == PATIENTS_HEADER

        data = {r[1]: r for r in rows[1:]}
        assert len(data) == 2
        assert data["Alice Rao"][0] == str(alice.id)
        assert data["Alice Rao"][2] == "alice@test.com"
        assert data["Alice Rao"][3] == "9999999999"
        assert data["Alice Rao"][5] == "1"  # one clinic link
        assert data["Bob Shah"][5] == "0"

    async def test_search_filter(
        self, admin_client, db: AsyncSession
    ):
        db.add_all([_patient("Alice Rao"), _patient("Bob Shah")])
        await db.commit()

        resp = await admin_client.get(PATIENTS_URL, params={"search": "alice"})
        assert resp.status_code == 200
        rows = _parse_csv(resp)[1:]
        assert len(rows) == 1
        assert rows[0][1] == "Alice Rao"

    async def test_is_active_and_status_filters(
        self, admin_client, db: AsyncSession
    ):
        db.add_all([_patient("Active Pat", is_active=True), _patient("Inactive Pat", is_active=False)])
        await db.commit()

        resp = await admin_client.get(PATIENTS_URL, params={"is_active": "false"})
        rows = _parse_csv(resp)[1:]
        assert len(rows) == 1
        assert rows[0][1] == "Inactive Pat"

        # Page's status dropdown values map onto is_active (completed→active).
        resp = await admin_client.get(PATIENTS_URL, params={"status": "completed"})
        rows = _parse_csv(resp)[1:]
        assert len(rows) == 1
        assert rows[0][1] == "Active Pat"

    async def test_clinic_id_filter(
        self, admin_client, db: AsyncSession, admin_user: User
    ):
        linked = _patient("Linked Pat")
        unlinked = _patient("Unlinked Pat")
        db.add_all([linked, unlinked])
        clinic = Clinic(name="City Clinic")
        db.add(clinic)
        await db.flush()
        db.add(
            PatientClinicLink(
                patient_id=linked.id,
                clinic_id=clinic.id,
                linked_by=admin_user.id,
                consent_status="approved",
            )
        )
        await db.commit()

        resp = await admin_client.get(PATIENTS_URL, params={"clinic_id": str(clinic.id)})
        rows = _parse_csv(resp)[1:]
        assert len(rows) == 1
        assert rows[0][1] == "Linked Pat"

        resp = await admin_client.get(PATIENTS_URL, params={"clinic_id": "not-a-uuid"})
        assert resp.status_code == 400

    async def test_excludes_non_patients_and_deleted(
        self, admin_client, db: AsyncSession, admin_user: User
    ):
        db.add(_patient("Real Patient"))
        deleted = _patient("Gone Patient")
        deleted.deleted_at = datetime.now(timezone.utc)
        db.add(deleted)
        # admin_user itself must not appear in the export
        await db.commit()

        resp = await admin_client.get(PATIENTS_URL)
        names = [r[1] for r in _parse_csv(resp)[1:]]
        assert names == ["Real Patient"]

    async def test_export_writes_audit_row(
        self, admin_client, db: AsyncSession
    ):
        resp = await admin_client.get(PATIENTS_URL)
        assert resp.status_code == 200
        logs = (
            await db.execute(
                select(AuditLog).where(
                    AuditLog.action == "EXPORT",
                    AuditLog.table_name == "users",
                )
            )
        ).scalars().all()
        assert len(logs) >= 1
        new_values = logs[0].new_values or {}
        assert new_values.get("filters", {}).get("role") == "patient"
        assert "row_count" in new_values

    async def test_row_cap_respected(self, admin_client, db: AsyncSession, monkeypatch):
        for i in range(3):
            db.add(_patient(f"Pat {i}"))
        await db.commit()

        monkeypatch.setattr("app.routers.admin.exports._LIST_EXPORT_MAX_ROWS", 2)
        resp = await admin_client.get(PATIENTS_URL)
        assert resp.status_code == 200
        assert len(_parse_csv(resp)) == 1 + 2  # header + capped rows

    async def test_non_admin_forbidden(self, patient_client):
        resp = await patient_client.get(PATIENTS_URL)
        assert resp.status_code == 403

    async def test_unauthenticated_401(self, client):
        resp = await client.get(PATIENTS_URL)
        assert resp.status_code == 401


class TestAppointmentsExport:
    async def test_csv_shape_headers(
        self, admin_client, db: AsyncSession, admin_user: User
    ):
        patient = _patient("Alice Rao")
        doctor = await _make_doctor(db)
        clinic = Clinic(name="City Clinic")
        db.add_all([patient, clinic])
        await db.flush()
        when = datetime.now(timezone.utc) + timedelta(days=1)
        appt = _appointment(patient.id, doctor.id, admin_user.id, when, clinic_id=clinic.id)
        db.add(appt)
        await db.commit()

        resp = await admin_client.get(APPOINTMENTS_URL)
        assert resp.status_code == 200, resp.text
        assert resp.headers["content-type"].startswith("text/csv")
        disposition = resp.headers["content-disposition"]
        assert "attachment" in disposition
        assert "appointments-export-" in disposition and disposition.endswith('.csv"')

        rows = _parse_csv(resp)
        assert rows[0] == APPTS_HEADER
        data = rows[1:]
        assert len(data) == 1
        row = data[0]
        assert row[0] == str(appt.id)
        assert row[1] == "Alice Rao"
        assert row[2] == "Dr Strange"
        assert row[3] == "City Clinic"
        assert row[5] == "scheduled"

    async def test_status_filter(
        self, admin_client, db: AsyncSession, admin_user: User
    ):
        patient = _patient("Pat")
        doctor = await _make_doctor(db)
        db.add(patient)
        await db.flush()
        when = datetime.now(timezone.utc) + timedelta(days=1)
        db.add_all([
            _appointment(patient.id, doctor.id, admin_user.id, when, status="scheduled"),
            _appointment(patient.id, doctor.id, admin_user.id, when + timedelta(hours=3), status="cancelled"),
        ])
        await db.commit()

        resp = await admin_client.get(APPOINTMENTS_URL, params={"status": "cancelled"})
        rows = _parse_csv(resp)[1:]
        assert len(rows) == 1
        assert rows[0][5] == "cancelled"

    async def test_date_range_filter(
        self, admin_client, db: AsyncSession, admin_user: User
    ):
        patient = _patient("Pat")
        doctor = await _make_doctor(db)
        db.add(patient)
        await db.flush()
        now = datetime.now(timezone.utc)
        in_range = _appointment(patient.id, doctor.id, admin_user.id, now + timedelta(days=5))
        out_range = _appointment(patient.id, doctor.id, admin_user.id, now + timedelta(days=30))
        db.add_all([in_range, out_range])
        await db.commit()

        resp = await admin_client.get(
            APPOINTMENTS_URL,
            params={
                "from": (now + timedelta(days=1)).date().isoformat(),
                "to": (now + timedelta(days=10)).date().isoformat(),
            },
        )
        rows = _parse_csv(resp)[1:]
        assert len(rows) == 1
        assert rows[0][0] == str(in_range.id)

        # from > to is a 400, same as the list endpoint
        resp = await admin_client.get(
            APPOINTMENTS_URL,
            params={"from": "2026-01-10", "to": "2026-01-01"},
        )
        assert resp.status_code == 400

    async def test_clinic_name_and_search_filters(
        self, admin_client, db: AsyncSession, admin_user: User
    ):
        patient = _patient("Alice Rao")
        doctor = await _make_doctor(db)
        clinic_a = Clinic(name="City Clinic")
        clinic_b = Clinic(name="Metro Clinic")
        db.add_all([patient, clinic_a, clinic_b])
        await db.flush()
        when = datetime.now(timezone.utc) + timedelta(days=1)
        db.add_all([
            _appointment(patient.id, doctor.id, admin_user.id, when, clinic_id=clinic_a.id),
            _appointment(patient.id, doctor.id, admin_user.id, when + timedelta(hours=2), clinic_id=clinic_b.id),
        ])
        await db.commit()

        # Clinic name filter (the page's dropdown filters by name)
        resp = await admin_client.get(APPOINTMENTS_URL, params={"clinic": "Metro Clinic"})
        rows = _parse_csv(resp)[1:]
        assert len(rows) == 1
        assert rows[0][3] == "Metro Clinic"

        # Search matches the doctor name
        resp = await admin_client.get(APPOINTMENTS_URL, params={"search": "strange"})
        rows = _parse_csv(resp)[1:]
        assert len(rows) == 2

        resp = await admin_client.get(APPOINTMENTS_URL, params={"search": "no-such-person"})
        assert len(_parse_csv(resp)) == 1  # header only

    async def test_export_writes_audit_row(
        self, admin_client, db: AsyncSession
    ):
        resp = await admin_client.get(APPOINTMENTS_URL)
        assert resp.status_code == 200
        logs = (
            await db.execute(
                select(AuditLog).where(
                    AuditLog.action == "EXPORT",
                    AuditLog.table_name == "appointments",
                )
            )
        ).scalars().all()
        assert len(logs) >= 1
        assert "row_count" in (logs[0].new_values or {})

    async def test_row_cap_respected(self, admin_client, db: AsyncSession, admin_user: User, monkeypatch):
        patient = _patient("Pat")
        doctor = await _make_doctor(db)
        db.add(patient)
        await db.flush()
        when = datetime.now(timezone.utc) + timedelta(days=1)
        for i in range(3):
            db.add(_appointment(patient.id, doctor.id, admin_user.id, when + timedelta(hours=i)))
        await db.commit()

        monkeypatch.setattr("app.routers.admin.exports._LIST_EXPORT_MAX_ROWS", 2)
        resp = await admin_client.get(APPOINTMENTS_URL)
        assert resp.status_code == 200
        assert len(_parse_csv(resp)) == 1 + 2

    async def test_non_admin_forbidden(self, patient_client):
        resp = await patient_client.get(APPOINTMENTS_URL)
        assert resp.status_code == 403

    async def test_unauthenticated_401(self, client):
        resp = await client.get(APPOINTMENTS_URL)
        assert resp.status_code == 401
