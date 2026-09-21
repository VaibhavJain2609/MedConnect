"""Patient-facing health-record export as a FHIR R4 collection Bundle.

Reuses the existing per-record FHIR generation in ``app.utils.fhir``:
records that already carry a stored ``fhir_bundle`` contribute its
entries verbatim (e.g. prescriptions export their MedicationRequests);
records without one get a minimal resource generated on the fly via
``create_fhir_bundle`` / ``_map_record_type_to_fhir``.
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.medical_record import MedicalRecord
from app.models.user import User
from app.utils.fhir import create_fhir_bundle

EXPORT_RECORD_CAP = 500


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
