"""Tests for the DPDP right-to-access self export (GET /api/v1/patients/me/export)."""
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import make_auth_header

from app.models.appointment import Appointment
from app.models.audit import AuditLog
from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.family import FamilyMember
from app.models.lab_result import LabResult
from app.models.medical_record import MedicalRecord
from app.models.notification import Notification
from app.models.patient_link import PatientClinicLink
from app.models.prescription import Prescription
from app.models.queue import QueueEntry
from app.models.user import User
from app.models.vital import PatientVital

EXPORT_URL = "/api/v1/patients/me/export"

SECTION_KEYS = [
    "medical_records",
    "prescriptions",
    "appointments",
    "vitals",
    "lab_results",
    "queue_history",
    "notifications",
    "family_members",
    "clinic_consents",
]


async def _make_user(db: AsyncSession, sub: str, role: str = "patient") -> User:
    user = User(
        keycloak_sub=sub,
        email=f"{sub}@test.com",
        full_name=f"User {sub}",
        role=role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _make_doctor(db: AsyncSession) -> Doctor:
    doc_user = await _make_user(db, f"doc-{uuid.uuid4().hex[:8]}", role="doctor")
    doctor = Doctor(user_id=doc_user.id, specialization="General Physician")
    db.add(doctor)
    await db.commit()
    await db.refresh(doctor)
    return doctor


async def _make_clinic(db: AsyncSession) -> Clinic:
    clinic = Clinic(name=f"Clinic {uuid.uuid4().hex[:8]}")
    db.add(clinic)
    await db.commit()
    await db.refresh(clinic)
    return clinic


async def _seed_patient_data(
    db: AsyncSession, patient: User, doctor: Doctor, clinic: Clinic, tag: str
) -> dict:
    """Create one row per exported section for ``patient``. Returns the ids."""
    record = MedicalRecord(
        patient_id=patient.id,
        doctor_id=doctor.id,
        record_type="opd_note",
        title=f"{tag} record",
        description=f"{tag} description",
        document_url=f"uploads/{tag}-doc.pdf",
        source="manual",
    )
    db.add(record)
    await db.flush()

    rx = Prescription(
        record_id=record.id,
        doctor_id=doctor.id,
        patient_id=patient.id,
        medicines=[{"name": f"{tag} med", "dose": "500mg"}],
        diagnosis=f"{tag} diagnosis",
    )
    appt = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        clinic_id=clinic.id,
        scheduled_at=datetime.now(timezone.utc) + timedelta(days=1),
        duration_minutes=30,
        type="in-person",
        chief_complaint=f"{tag} complaint",
        created_by=patient.id,
    )
    vital = PatientVital(
        patient_id=patient.id,
        vital_type="weight_kg",
        value=70.5,
        unit="kg",
        recorded_by=patient.id,
    )
    lab = LabResult(
        test_id=f"T-{tag}-{uuid.uuid4().hex[:6]}",
        patient_id=patient.id,
        doctor_id=doctor.user_id,
        test_name=f"{tag} CBC",
        test_category="hematology",
        appointment_date=datetime.now(timezone.utc),
        status="completed",
        result_value="5.5",
        result_unit="mg/dL",
    )
    queue = QueueEntry(
        clinic_id=clinic.id,
        patient_id=patient.id,
        doctor_id=doctor.id,
        # uq_queue_entries_daily_number is per clinic/day — randomize so
        # seeding two patients in one clinic doesn't collide.
        queue_number=uuid.uuid4().int % 10_000 + 1,
        status="completed",
    )
    notif = Notification(
        user_id=patient.id,
        type="system",
        title=f"{tag} notification",
        message=f"{tag} message",
    )
    member = FamilyMember(
        owner_user_id=patient.id,
        full_name=f"{tag} dependent",
        dob=date(2015, 1, 1),
        relationship="child",
    )
    link = PatientClinicLink(
        patient_id=patient.id,
        clinic_id=clinic.id,
        linked_by=patient.id,
        consent_status="approved",
        consented_at=datetime.now(timezone.utc),
    )
    db.add_all([rx, appt, vital, lab, queue, notif, member, link])
    await db.commit()
    return {
        "record_id": str(record.id),
        "prescription_id": str(rx.id),
        "appointment_id": str(appt.id),
        "vital_id": str(vital.id),
        "lab_result_id": str(lab.id),
        "queue_id": str(queue.id),
        "notification_id": str(notif.id),
        "family_member_id": str(member.id),
        "clinic_link_id": str(link.id),
    }


async def test_export_requires_auth(client):
    resp = await client.get(EXPORT_URL)
    assert resp.status_code == 401


async def test_export_requires_patient_role(client, doctor_user):
    """A doctor token must not reach the patient self-export."""
    resp = await client.get(EXPORT_URL, headers=make_auth_header(doctor_user, roles=["doctor"]))
    assert resp.status_code == 403


async def test_export_all_sections_present(patient_client, patient_user, db):
    doctor = await _make_doctor(db)
    clinic = await _make_clinic(db)
    await _seed_patient_data(db, patient_user, doctor, clinic, "own")

    resp = await patient_client.get(EXPORT_URL)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    assert "attachment" in resp.headers["content-disposition"]

    body = resp.json()
    assert body["format_version"] == "1.0"
    assert "exported_at" in body
    assert body["patient_id"] == str(patient_user.id)
    assert "documents_note" in body

    assert body["profile"]["id"] == str(patient_user.id)
    assert body["profile"]["email"] == patient_user.email
    assert "medical_history" in body
    for key in SECTION_KEYS:
        assert key in body, f"missing section {key}"
        assert isinstance(body[key], list)


async def test_export_contains_only_own_data(patient_client, patient_user, db):
    doctor = await _make_doctor(db)
    clinic = await _make_clinic(db)
    other = await _make_user(db, "other-patient")

    own = await _seed_patient_data(db, patient_user, doctor, clinic, "own")
    other_ids = await _seed_patient_data(db, other, doctor, clinic, "other")

    resp = await patient_client.get(EXPORT_URL)
    assert resp.status_code == 200
    body = resp.json()

    def ids(section):
        return {row["id"] for row in body[section]}

    assert own["record_id"] in ids("medical_records")
    assert own["prescription_id"] in ids("prescriptions")
    assert own["appointment_id"] in ids("appointments")
    assert own["vital_id"] in ids("vitals")
    assert own["lab_result_id"] in ids("lab_results")
    assert own["queue_id"] in ids("queue_history")
    assert own["notification_id"] in ids("notifications")
    assert own["family_member_id"] in ids("family_members")
    assert own["clinic_link_id"] in ids("clinic_consents")

    # Nothing from the other patient leaks into any section.
    for section in SECTION_KEYS:
        for oid in other_ids.values():
            assert oid not in ids(section), f"{oid} leaked into {section}"
    assert body["profile"]["id"] != str(other.id)


async def test_export_document_url_reference_not_binary(patient_client, patient_user, db):
    doctor = await _make_doctor(db)
    clinic = await _make_clinic(db)
    await _seed_patient_data(db, patient_user, doctor, clinic, "own")

    body = (await patient_client.get(EXPORT_URL)).json()
    record = next(r for r in body["medical_records"] if r["title"] == "own record")
    assert record["document_url"] == "uploads/own-doc.pdf"
    assert "document_url" in body["documents_note"] or "document" in body["documents_note"]


async def test_export_writes_audit_row_and_self_notification(
    patient_client, patient_user, db
):
    resp = await patient_client.get(EXPORT_URL)
    assert resp.status_code == 200

    audits = (
        await db.execute(
            select(AuditLog).where(
                AuditLog.action == "EXPORT",
                AuditLog.table_name == "patient_data_export",
                AuditLog.record_id == patient_user.id,
            )
        )
    ).scalars().all()
    assert len(audits) == 1
    # Audit payload is metadata only — section counts, no PHI rows.
    assert audits[0].new_values["path"] == EXPORT_URL
    assert "sections" in audits[0].new_values

    notifs = (
        await db.execute(
            select(Notification).where(
                Notification.user_id == patient_user.id,
                Notification.title == "Your data was exported",
            )
        )
    ).scalars().all()
    assert len(notifs) == 1
    assert notifs[0].type == "system"


async def test_export_rate_limited(patient_client):
    """Endpoint limit is 3/hour — the 4th request in the window 429s."""
    for _ in range(3):
        resp = await patient_client.get(EXPORT_URL)
        assert resp.status_code == 200

    resp = await patient_client.get(EXPORT_URL)
    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert "3" in resp.json()["error"]["message"]
    assert "hour" in resp.json()["error"]["message"]
    assert "retry-after" in resp.headers
