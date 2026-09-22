"""Response models for app/routers/appointments.py.

Fields match _serialize_appointment() exactly — every key the endpoints
return is represented so FastAPI's response_model filtering drops nothing.
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AppointmentResponse(BaseModel):
    id: UUID
    patient_id: UUID
    patient_name: str | None = None
    doctor_id: UUID
    doctor_name: str | None = None
    clinic_id: UUID | None = None
    clinic_name: str | None = None
    branch_id: UUID | None = None
    branch_name: str | None = None
    scheduled_at: datetime
    duration_minutes: int
    type: str
    status: str
    chief_complaint: str | None = None
    notes: str | None = None
    cancelled_reason: str | None = None
    meeting_url: str | None = None
    teleconsult_url: str | None = None
    is_provisional: bool = False
    patient_phone: str | None = None
    created_by: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AppointmentsListResponse(BaseModel):
    data: list[AppointmentResponse]
    total: int
    limit: int
    offset: int


class LinkProvisionalResponse(BaseModel):
    """Returned by POST /appointments/link-provisional after merging a
    provisional (walk-in) patient into a real patient account."""

    real_patient_id: UUID
    full_name: str
    phone: str | None = None
    linked_count: int
