from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class EncounterCreate(BaseModel):
    patient_id: UUID
    appointment_id: Optional[UUID] = None  # optional — walk-ins allowed
    clinic_id: Optional[UUID] = None
    subjective: Optional[str] = None
    objective: Optional[str] = None
    assessment: Optional[str] = None
    plan: Optional[str] = None
    vitals_snapshot: Optional[dict] = None


class EncounterUpdate(BaseModel):
    appointment_id: Optional[UUID] = None
    clinic_id: Optional[UUID] = None
    subjective: Optional[str] = None
    objective: Optional[str] = None
    assessment: Optional[str] = None
    plan: Optional[str] = None
    vitals_snapshot: Optional[dict] = None


class EncounterResponse(BaseModel):
    id: UUID
    patient_id: UUID
    patient_name: Optional[str] = None
    doctor_id: UUID
    doctor_name: Optional[str] = None
    appointment_id: Optional[UUID] = None
    clinic_id: Optional[UUID] = None
    clinic_name: Optional[str] = None
    subjective: Optional[str] = None
    objective: Optional[str] = None
    assessment: Optional[str] = None
    plan: Optional[str] = None
    vitals_snapshot: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
