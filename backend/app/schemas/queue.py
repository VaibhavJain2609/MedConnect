from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class QueueEntryCreate(BaseModel):
    patient_id: UUID
    doctor_id: UUID | None = None
    appointment_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=1000)


class QueueStatusUpdate(BaseModel):
    status: str  # in_consultation | completed | cancelled


class QueueEntryResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    branch_id: UUID | None = None
    patient_id: UUID
    patient_name: str | None = None
    doctor_id: UUID | None = None
    doctor_name: str | None = None
    appointment_id: UUID | None = None
    queue_number: int
    status: str
    notes: str | None = None
    called_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class QueueListResponse(BaseModel):
    data: list[QueueEntryResponse]
    total: int


class QueuePositionResponse(BaseModel):
    """Patient-facing live queue position (GET /queue/my-position).

    All fields are null/empty (ahead_count=0) when the patient has no queue
    entry today — the endpoint returns 200, not 404, in that case."""

    queue_entry_id: UUID | None
    clinic_id: UUID | None
    clinic_name: str | None
    doctor_name: str | None
    queue_number: int | None
    position: int | None
    status: str | None
    ahead_count: int
    estimated_wait_minutes: int | None
