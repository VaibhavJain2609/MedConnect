from datetime import date, datetime, time
from uuid import UUID

from pydantic import BaseModel, Field


class AvailabilityWindowCreate(BaseModel):
    weekday: int = Field(ge=0, le=6)  # 0=Monday .. 6=Sunday (date.weekday())
    start_time: time
    end_time: time
    slot_duration_minutes: int = Field(default=15, ge=5, le=240)
    clinic_id: UUID | None = None
    branch_id: UUID | None = None
    is_active: bool = True


class AvailabilityWindowUpdate(BaseModel):
    weekday: int | None = Field(default=None, ge=0, le=6)
    start_time: time | None = None
    end_time: time | None = None
    slot_duration_minutes: int | None = Field(default=None, ge=5, le=240)
    clinic_id: UUID | None = None
    branch_id: UUID | None = None
    is_active: bool | None = None


class AvailabilityWindowResponse(BaseModel):
    id: UUID
    doctor_id: UUID
    doctor_name: str | None = None
    clinic_id: UUID | None = None
    branch_id: UUID | None = None
    weekday: int
    start_time: time
    end_time: time
    slot_duration_minutes: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DoctorLeaveCreate(BaseModel):
    date: date
    reason: str | None = Field(default=None, max_length=255)


class DoctorLeaveResponse(BaseModel):
    id: UUID
    doctor_id: UUID
    date: date
    reason: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AvailabilitySlot(BaseModel):
    """One bookable slot. start/end are datetimes built from the availability
    window's naive local times (see timezone note in
    models/doctor_availability.py); start_time/end_time are the HH:MM wall
    clock values for display."""

    start: datetime
    end: datetime
    start_time: time
    end_time: time
    clinic_id: UUID | None = None
    branch_id: UUID | None = None


class DoctorSlotsResponse(BaseModel):
    doctor_id: UUID
    date: date
    slots: list[AvailabilitySlot]
