from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class FollowUpCreate(BaseModel):
    """Book a follow-up appointment from an encounter.

    ``scheduled_at`` is the combined date+time (ISO-8601; naive values are
    treated as UTC). ``type`` defaults to "follow-up".
    """

    scheduled_at: datetime
    duration_minutes: int = Field(default=30, ge=5, le=480)
    type: str = "follow-up"
    notes: Optional[str] = None

    @field_validator("scheduled_at")
    @classmethod
    def _scheduled_at_utc(cls, v: datetime) -> datetime:
        return v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v


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

    model_config = ConfigDict(from_attributes=True)
