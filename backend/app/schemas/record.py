import re
from datetime import datetime
from typing import Optional
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, field_validator

VALID_RECORD_TYPES = [
    "prescription", "diagnostic_report", "discharge_summary",
    "opd_note", "immunization", "lab_report", "imaging", "other",
]

# Relative object keys look like "{uuid}/{sanitized_filename}" — word chars,
# dots, dashes and slashes only.
_OBJECT_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-/]*$")


def _validate_document_url(v: str | None) -> str | None:
    """Allow only relative object keys or https:// URLs.

    document_url is rendered into <a href> by the frontend — permitting
    arbitrary schemes (javascript:, data:) is stored XSS.
    """
    if v is None:
        return v
    v = v.strip()
    if not v:
        return None
    if len(v) > 500:
        raise ValueError("document_url is too long")
    scheme = urlsplit(v).scheme
    if scheme:
        if scheme != "https" or not urlsplit(v).netloc:
            raise ValueError("document_url must be a relative object key or an https:// URL")
        return v
    # No scheme — must be a plain relative object key (no //, /, or .. tricks)
    if (
        v.startswith("/")
        or ".." in v
        or not _OBJECT_KEY_RE.match(v)
    ):
        raise ValueError("document_url must be a relative object key or an https:// URL")
    return v


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

    @field_validator("document_url")
    @classmethod
    def validate_document_url(cls, v: str | None) -> str | None:
        return _validate_document_url(v)


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
