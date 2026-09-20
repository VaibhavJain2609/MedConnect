from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class MedicineItem(BaseModel):
    name: str
    salt: str | None = None
    dosage: str
    frequency: str
    duration: str
    timing: str | None = None
    notes: str | None = None


class PrescriptionMedicineItem(BaseModel):
    brand_name: str
    salt_id: Optional[str] = None
    brand_id: Optional[str] = None
    dose: str
    frequency: str  # "BD" | "TDS" | "OD" | "1-0-1" | "SOS" | "QID" | "HS"
    duration: str   # "7 days" | "1 month" | "Ongoing"
    route: str = "oral"  # oral | topical | IV | IM | SC | inhaled | sublingual
    instructions: Optional[str] = None


class PrescriptionCreate(BaseModel):
    patient_id: UUID
    medicines: list[PrescriptionMedicineItem]
    diagnosis: str | None = None
    notes: str | None = None
    valid_until: date | None = None
    appointment_id: Optional[UUID] = None
    clinic_id: Optional[UUID] = None
    branch_id: Optional[UUID] = None
    # Required when the clinical safety gate reports a "major" alert;
    # recorded verbatim in PrescriptionAudit rows.
    safety_override_reason: Optional[str] = None


class SafetyAlert(BaseModel):
    """One clinical-safety finding surfaced by the prescription safety gate."""

    severity: str  # minor | moderate | major | contraindicated
    kind: str      # interaction | allergy | duplicate_therapy | contraindication
    detail: str
    salts: Optional[list[str]] = None
    medicine: Optional[str] = None


class SafetyResult(BaseModel):
    """Safety-gate outcome attached to prescription creation responses."""

    checked: bool = True
    alerts: list[SafetyAlert] = []
    overrides_applied: bool = False


class PrescriptionResponse(BaseModel):
    id: UUID
    record_id: UUID
    doctor_id: UUID
    patient_id: UUID
    clinic_id: Optional[UUID] = None
    branch_id: Optional[UUID] = None
    appointment_id: Optional[UUID] = None
    medicines: list[dict]
    diagnosis: str | None
    notes: str | None
    translated: dict | None
    valid_until: date | None
    created_at: datetime
    # Populated only on POST /prescriptions (clinical safety gate outcome)
    safety: Optional[SafetyResult] = None

    class Config:
        from_attributes = True
