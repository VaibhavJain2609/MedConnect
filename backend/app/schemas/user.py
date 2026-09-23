from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.record import _validate_document_url

VALID_SEX_VALUES = {"male", "female", "other"}


class DoctorProfileCreate(BaseModel):
    specialization: str | None = None
    license_number: str | None = None
    facility_name: str | None = None
    facility_city: str | None = None
    qualifications: str | None = Field(None, max_length=255)
    registration_number: str | None = Field(None, max_length=50)
    signature_url: str | None = None

    @field_validator("registration_number")
    @classmethod
    def validate_registration_number(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        if len(v) < 3:
            raise ValueError("registration_number must be at least 3 characters")
        return v

    @field_validator("signature_url")
    @classmethod
    def validate_signature_url(cls, v: str | None) -> str | None:
        # Same rules as record document_url: relative object key or https:// —
        # the value is embedded in generated PDFs / rendered into links.
        return _validate_document_url(v)


class DoctorProfileResponse(BaseModel):
    id: UUID
    user_id: UUID
    specialization: str | None
    license_number: str | None
    facility_name: str | None
    facility_city: str | None
    qualifications: str | None = None
    registration_number: str | None = None
    signature_url: str | None = None
    verified: bool

    model_config = ConfigDict(from_attributes=True)


class PatientProfileUpdate(BaseModel):
    phone: str | None = Field(None, max_length=20)
    language_pref: str | None = None
    emergency_contact_name: str | None = Field(None, max_length=255)
    emergency_contact_phone: str | None = Field(None, max_length=20)
    date_of_birth: date | None = None
    sex: str | None = None

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, v: date | None) -> date | None:
        if v is not None and v > date.today():
            raise ValueError("date_of_birth cannot be in the future")
        return v

    @field_validator("sex")
    @classmethod
    def validate_sex(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip().lower()
        if not v:
            return None
        if v not in VALID_SEX_VALUES:
            raise ValueError("sex must be one of: male, female, other")
        return v


class PatientProfileResponse(BaseModel):
    id: str
    full_name: str
    email: str | None
    phone: str | None
    language_pref: str
    emergency_contact_name: str | None
    emergency_contact_phone: str | None
    date_of_birth: date | None = None
    sex: str | None = None

    model_config = ConfigDict(from_attributes=True)


class MedicalHistoryUpdate(BaseModel):
    blood_group: str | None = None
    allergies: list[str] | None = None
    chronic_conditions: list[str] | None = None
    height_cm: float | None = None
    weight_kg: float | None = None


# Admin user management schemas

class AdminUserListItem(BaseModel):
    id: str
    full_name: str
    email: str | None
    phone: str | None
    role: str
    is_active: bool
    created_at: datetime
    consent_status: str | None = None

    model_config = ConfigDict(from_attributes=True)


class AdminUsersListResponse(BaseModel):
    data: list[AdminUserListItem]
    total: int
    page: int
    limit: int
    totalPages: int


class AdminUserDetailResponse(BaseModel):
    id: str
    full_name: str
    email: str | None
    phone: str | None
    role: str
    is_active: bool
    language_pref: str
    blood_group: str | None
    emergency_contact_name: str | None
    emergency_contact_phone: str | None
    created_at: datetime
    updated_at: datetime
    doctor_profile: DoctorProfileResponse | None
    records_count: int
    prescriptions_count: int
    allergies: list[str] | None = None
    chronic_conditions: list[str] | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    last_visit: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AdminCreatePatientRequest(BaseModel):
    full_name: str = Field(max_length=255)
    phone: str | None = Field(None, max_length=20)
    email: str | None = Field(None, max_length=255)


class AdminCreatePatientResponse(BaseModel):
    id: str
    full_name: str
    phone: str | None
    email: str | None
    role: str
    is_active: bool
    created_at: datetime

    @field_validator("id", mode="before")
    @classmethod
    def _id_to_str(cls, v):
        return str(v)

    model_config = ConfigDict(from_attributes=True)


class AdminUserUpdateRequest(BaseModel):
    full_name: str | None = Field(None, max_length=255)
    email: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=20)
    role: str | None = None
    is_active: bool | None = None
    language_pref: str | None = None


class AdminUserUpdateResponse(BaseModel):
    id: str
    full_name: str
    email: str | None
    phone: str | None
    role: str
    is_active: bool
    language_pref: str | None
    message: str


class AdminUserDeleteResponse(BaseModel):
    id: str
    message: str


class AdminUserPrescriptionItem(BaseModel):
    id: str
    doctor_name: str
    diagnosis: str | None
    notes: str | None
    medicines: list | dict
    valid_until: date | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminUserPrescriptionsResponse(BaseModel):
    data: list[AdminUserPrescriptionItem]
    total: int
    page: int
    limit: int
    totalPages: int


class AdminUserRecordItem(BaseModel):
    id: str
    record_type: str
    title: str
    description: str | None
    source: str
    doctor_name: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminUserRecordsResponse(BaseModel):
    data: list[AdminUserRecordItem]
    total: int
    page: int
    limit: int
    totalPages: int
