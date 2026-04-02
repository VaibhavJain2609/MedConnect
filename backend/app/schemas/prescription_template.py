from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class TemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    medicines: list[dict] = Field(..., min_length=1)
    diagnosis: str | None = None
    notes: str | None = None

    @field_validator("medicines")
    @classmethod
    def validate_medicines(cls, v):
        if not v:
            raise ValueError("At least one medicine is required")
        for med in v:
            if not med.get("name"):
                raise ValueError("Each medicine must have a name")
        return v


class TemplateUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    medicines: list[dict] | None = Field(None, min_length=1)
    diagnosis: str | None = None
    notes: str | None = None

    @field_validator("medicines")
    @classmethod
    def validate_medicines(cls, v):
        if v is not None and not v:
            raise ValueError("At least one medicine is required")
        if v:
            for med in v:
                if not med.get("name"):
                    raise ValueError("Each medicine must have a name")
        return v


class TemplateResponse(BaseModel):
    id: UUID
    doctor_id: UUID
    name: str
    medicines: list[dict]
    diagnosis: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
