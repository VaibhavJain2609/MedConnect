"""Patient-facing data exports.

``build_records_export_bundle`` — health-record export as a FHIR R4
collection Bundle. Reuses the existing per-record FHIR generation in
``app.utils.fhir``: records that already carry a stored ``fhir_bundle``
contribute its entries verbatim (e.g. prescriptions export their
MedicationRequests); records without one get a minimal resource generated
on the fly via ``create_fhir_bundle`` / ``_map_record_type_to_fhir``.

``build_patient_data_export`` — DPDP right-to-access self export: a plain
JSON document with every section of the caller's own data (profile,
medical records, prescriptions, appointments, vitals, lab results, queue
history, notifications, family members, clinic consents). Strictly
own-scoped — every query filters on the caller's user id. Document file
binaries are NOT embedded; ``document_url`` references are included with
an explanatory note instead.
"""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment
from app.models.family import FamilyMember
from app.models.lab_result import LabResult
from app.models.medical_record import MedicalRecord
from app.models.notification import Notification
from app.models.patient_link import PatientClinicLink
from app.models.prescription import Prescription
from app.models.queue import QueueEntry
from app.models.user import User
from app.models.vital import PatientVital
from app.utils.fhir import create_fhir_bundle

EXPORT_RECORD_CAP = 500

# DPDP self-export (GET /api/v1/patients/me/export).
DATA_EXPORT_FORMAT_VERSION = "1.0"
# Per-section safety cap so a pathological account can't produce an
# unbounded dump — far above realistic per-patient row counts.
DATA_EXPORT_SECTION_CAP = 5000


def _patient_resource(user: User) -> dict:
    """Minimal FHIR R4 Patient resource for the exporting user."""
    resource: dict = {
        "resourceType": "Patient",
        "id": str(user.id),
        "name": [{"text": user.full_name}],
    }
    telecom = []
    if user.email:
        telecom.append({"system": "email", "value": user.email})
    if user.phone:
        telecom.append({"system": "phone", "value": user.phone})
    if telecom:
        resource["telecom"] = telecom
    return resource


def _record_entries(record: MedicalRecord) -> list[dict]:
    """Return bundle entries for one MedicalRecord row."""
    if record.fhir_bundle and isinstance(record.fhir_bundle.get("entry"), list):
        entries = record.fhir_bundle["entry"]
    else:
        bundle = create_fhir_bundle(
            record_type=record.record_type,
            data={
                "title": record.title,
                "description": record.description or record.title or "",
            },
            patient_id=record.patient_id,
            doctor_id=record.doctor_id,
        )
        entries = bundle["entry"]

    out = []
    for i, entry in enumerate(entries):
        suffix = "" if i == 0 else f"-{i}"
        out.append(
            {
                "fullUrl": f"urn:uuid:{record.id}{suffix}",
                "resource": entry.get("resource", entry),
            }
        )
    return out


async def build_records_export_bundle(
    db: AsyncSession,
    user: User,
    cap: int = EXPORT_RECORD_CAP,
) -> dict:
    """Build a FHIR R4 ``collection`` Bundle with the patient's own records.

    Entry 0 is the Patient resource; subsequent entries are per-record
    resources (MedicationRequest / DiagnosticReport / DocumentReference /
    etc. per ``_map_record_type_to_fhir``). Capped at ``cap`` records,
    newest first.
    """
    result = await db.execute(
        select(MedicalRecord)
        .where(
            MedicalRecord.patient_id == user.id,
            MedicalRecord.deleted_at.is_(None),
        )
        .order_by(MedicalRecord.created_at.desc())
        .limit(cap)
    )
    records = list(result.scalars().all())

    entries = [
        {"fullUrl": f"urn:uuid:{user.id}", "resource": _patient_resource(user)}
    ]
    for record in records:
        entries.extend(_record_entries(record))

    now = datetime.now(timezone.utc).isoformat()
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "timestamp": now,
        "meta": {
            "lastUpdated": now,
            "source": "MedConnect",
        },
        "total": len(entries),
        "entry": entries,
    }


# ─── DPDP right-to-access self export ────────────────────────────────────────

_DOCUMENTS_NOTE = (
    "Uploaded document file binaries are not embedded in this export; "
    "document_url values reference the stored files, downloadable while "
    "the account is active."
)


def _json_value(v: Any) -> Any:
    """Coerce a column value into a JSON-serializable primitive."""
    if v is None or isinstance(v, (str, int, float, bool, list, dict)):
        return v
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, uuid.UUID):
        return str(v)
    if isinstance(v, Decimal):
        return float(v)
    return str(v)


def _row(obj: Any, fields: tuple[str, ...]) -> dict:
    return {f: _json_value(getattr(obj, f)) for f in fields}


async def _own_rows(
    db: AsyncSession,
    model: Any,
    owner_col: Any,
    owner_id: uuid.UUID,
    order_col: Any,
    cap: int = DATA_EXPORT_SECTION_CAP,
) -> list[Any]:
    """Fetch the caller's own live rows for one section, newest first."""
    stmt = (
        select(model)
        .where(owner_col == owner_id, model.deleted_at.is_(None))
        .order_by(order_col.desc(), model.id.desc())
        .limit(cap)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def build_patient_data_export(
    db: AsyncSession,
    user: User,
    cap: int = DATA_EXPORT_SECTION_CAP,
) -> dict:
    """Build the DPDP right-to-access export document for ``user``.

    Every section is strictly own-scoped: rows are selected on the
    patient_id / user_id / owner_user_id column that points at the caller.
    No document file binaries — only ``document_url`` references (see
    ``documents_note``). Each section is capped at ``cap`` rows.
    """
    records, prescriptions, appointments, vitals, lab_results = (
        await _own_rows(db, MedicalRecord, MedicalRecord.patient_id, user.id, MedicalRecord.created_at, cap),
        await _own_rows(db, Prescription, Prescription.patient_id, user.id, Prescription.created_at, cap),
        await _own_rows(db, Appointment, Appointment.patient_id, user.id, Appointment.scheduled_at, cap),
        await _own_rows(db, PatientVital, PatientVital.patient_id, user.id, PatientVital.recorded_at, cap),
        await _own_rows(db, LabResult, LabResult.patient_id, user.id, LabResult.appointment_date, cap),
    )
    queue_entries, notifications, family_members, clinic_links = (
        await _own_rows(db, QueueEntry, QueueEntry.patient_id, user.id, QueueEntry.created_at, cap),
        await _own_rows(db, Notification, Notification.user_id, user.id, Notification.created_at, cap),
        await _own_rows(db, FamilyMember, FamilyMember.owner_user_id, user.id, FamilyMember.created_at, cap),
        await _own_rows(db, PatientClinicLink, PatientClinicLink.patient_id, user.id, PatientClinicLink.created_at, cap),
    )

    return {
        "format_version": DATA_EXPORT_FORMAT_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "patient_id": str(user.id),
        "documents_note": _DOCUMENTS_NOTE,
        "profile": {
            "id": str(user.id),
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone,
            "language_pref": user.language_pref,
            "emergency_contact_name": user.emergency_contact_name,
            "emergency_contact_phone": user.emergency_contact_phone,
            "role": user.role,
            "is_active": user.is_active,
            "consent_at": _json_value(user.consent_at),
            "consent_version": user.consent_version,
            "erasure_requested_at": _json_value(user.erasure_requested_at),
            "erased_at": _json_value(user.erased_at),
            "created_at": _json_value(user.created_at),
        },
        "medical_history": {
            "blood_group": user.blood_group,
            "allergies": user.allergies or [],
            "chronic_conditions": user.chronic_conditions or [],
            "height_cm": _json_value(user.height_cm),
            "weight_kg": _json_value(user.weight_kg),
        },
        "medical_records": [
            _row(
                r,
                (
                    "id", "record_type", "title", "description", "raw_text",
                    "ai_summary", "fhir_bundle", "source", "document_url",
                    "doctor_id", "clinic_id", "family_member_id",
                    "amended_from_id", "created_at", "updated_at",
                ),
            )
            for r in records
        ],
        "prescriptions": [
            _row(
                p,
                (
                    "id", "record_id", "doctor_id", "clinic_id", "branch_id",
                    "appointment_id", "medicines", "diagnosis", "notes",
                    "valid_until", "created_at",
                ),
            )
            for p in prescriptions
        ],
        "appointments": [
            _row(
                a,
                (
                    "id", "doctor_id", "clinic_id", "branch_id", "scheduled_at",
                    "duration_minutes", "type", "status", "chief_complaint",
                    "notes", "cancelled_reason", "meeting_url", "created_at",
                ),
            )
            for a in appointments
        ],
        "vitals": [
            _row(
                v,
                (
                    "id", "vital_type", "value", "unit", "recorded_at",
                    "recorded_by", "notes", "created_at",
                ),
            )
            for v in vitals
        ],
        "lab_results": [
            _row(
                lr,
                (
                    "id", "test_id", "test_name", "test_category",
                    "appointment_date", "status", "result_value", "result_unit",
                    "normal_range", "abnormal_flag", "notes", "doctor_id",
                    "created_at",
                ),
            )
            for lr in lab_results
        ],
        "queue_history": [
            _row(
                q,
                (
                    "id", "clinic_id", "branch_id", "doctor_id",
                    "appointment_id", "queue_number", "queue_date", "status",
                    "notes", "called_at", "completed_at", "created_at",
                ),
            )
            for q in queue_entries
        ],
        "notifications": [
            _row(
                n,
                (
                    "id", "type", "title", "message", "read", "action_url",
                    "meta", "created_at", "read_at",
                ),
            )
            for n in notifications
        ],
        "family_members": [
            _row(
                fm,
                (
                    "id", "full_name", "dob", "gender", "relationship",
                    "blood_group", "notes", "created_at",
                ),
            )
            for fm in family_members
        ],
        "clinic_consents": [
            _row(
                link,
                (
                    "id", "clinic_id", "consent_status", "consented_at",
                    "revoked_at", "created_at",
                ),
            )
            for link in clinic_links
        ],
    }
