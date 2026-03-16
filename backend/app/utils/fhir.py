from datetime import datetime, timezone
from uuid import UUID


def create_fhir_bundle(record_type: str, data: dict, patient_id: UUID, doctor_id: UUID | None = None) -> dict:
    """Create a minimal FHIR R4 Bundle for a medical record."""
    now = datetime.now(timezone.utc).isoformat()

    bundle = {
        "resourceType": "Bundle",
        "type": "document",
        "timestamp": now,
        "meta": {
            "lastUpdated": now,
            "source": "MedConnect",
        },
        "entry": [],
    }

    if record_type == "prescription":
        for med in data.get("medicines", []):
            # Support both old shape (name/dosage) and current shape (brand_name/dose)
            med_name = med.get("brand_name") or med.get("name", "")
            med_dose = med.get("dose") or med.get("dosage", "")
            entry = {
                "resource": {
                    "resourceType": "MedicationRequest",
                    "status": "active",
                    "intent": "order",
                    "medicationCodeableConcept": {
                        "text": med_name,
                        "coding": [{"display": med.get("salt", med_name)}],
                    },
                    "dosageInstruction": [
                        {
                            "text": f"{med_dose} {med.get('frequency', '')} for {med.get('duration', '')}",
                            "timing": {"code": {"text": med.get("frequency", "")}},
                            "doseAndRate": [{"doseQuantity": {"value": med_dose}}],
                            "additionalInstruction": [{"text": med.get("instructions", "")}] if med.get("instructions") else [],
                        }
                    ],
                    "note": [{"text": med.get("notes", "")}] if med.get("notes") else [],
                    "subject": {"reference": f"Patient/{patient_id}"},
                    "requester": {"reference": f"Practitioner/{doctor_id}"} if doctor_id else {},
                }
            }
            bundle["entry"].append(entry)
    else:
        entry = {
            "resource": {
                "resourceType": _map_record_type_to_fhir(record_type),
                "status": "final",
                "subject": {"reference": f"Patient/{patient_id}"},
                "date": now,
                "text": {"status": "generated", "div": data.get("description", "")},
            }
        }
        if doctor_id:
            entry["resource"]["performer"] = [{"reference": f"Practitioner/{doctor_id}"}]
        bundle["entry"].append(entry)

    return bundle


def _map_record_type_to_fhir(record_type: str) -> str:
    mapping = {
        "diagnostic_report": "DiagnosticReport",
        "discharge_summary": "Composition",
        "opd_note": "Encounter",
        "immunization": "Immunization",
        "lab_report": "DiagnosticReport",
        "imaging": "ImagingStudy",
        "other": "DocumentReference",
    }
    return mapping.get(record_type, "DocumentReference")
