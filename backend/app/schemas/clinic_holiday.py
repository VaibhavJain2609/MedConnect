from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ClinicHolidayCreate(BaseModel):
    date: date
    name: str | None = Field(default=None, max_length=255)


class ClinicHolidayResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    date: date
    name: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
