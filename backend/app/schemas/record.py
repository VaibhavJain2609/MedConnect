from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, field_validator

VALID_RECORD_TYPES = [
    "prescription", "diagnostic_report", "discharge_summary",
    "opd_note", "immunization", "lab_report", "imaging", "other",
]


class RecordCreate(BaseModel):
    patient_id: Optional[UUID] = None
    record_type: str
    title: str
    description: str | None = None
    fhir_bundle: dict | None = None
    document_url: str | None = None

    @field_validator("record_type")
    @classmethod
    def validate_record_type(cls, v: str) -> str:
        if v not in VALID_RECORD_TYPES:
            raise ValueError(f"record_type must be one of: {', '.join(VALID_RECORD_TYPES)}")
        return v


class RecordResponse(BaseModel):
    id: UUID
    patient_id: UUID
    doctor_id: UUID | None
    record_type: str
    title: str
    description: str | None
    fhir_bundle: dict | None
    document_url: str | None = None
    source: str
    amended_from_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RecordListItem(BaseModel):
    id: UUID
    record_type: str
    title: str
    source: str
    doctor_name: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True
