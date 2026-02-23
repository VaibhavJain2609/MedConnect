from datetime import date, datetime
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


class PrescriptionCreate(BaseModel):
    patient_id: UUID
    medicines: list[MedicineItem]
    diagnosis: str | None = None
    notes: str | None = None
    valid_until: date | None = None


class PrescriptionResponse(BaseModel):
    id: UUID
    record_id: UUID
    doctor_id: UUID
    patient_id: UUID
    medicines: list[dict]
    diagnosis: str | None
    notes: str | None
    translated: dict | None
    valid_until: date | None
    created_at: datetime

    class Config:
        from_attributes = True
