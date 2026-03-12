from datetime import datetime

from pydantic import BaseModel


class DoctorProfileCreate(BaseModel):
    specialization: str | None = None
    license_number: str | None = None
    facility_name: str | None = None
    facility_city: str | None = None


class DoctorProfileResponse(BaseModel):
    id: str
    user_id: str
    specialization: str | None
    license_number: str | None
    facility_name: str | None
    facility_city: str | None
    verified: bool

    class Config:
        from_attributes = True


class PatientProfileUpdate(BaseModel):
    phone: str | None = None
    language_pref: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None


class PatientProfileResponse(BaseModel):
    id: str
    full_name: str
    email: str | None
    phone: str | None
    language_pref: str
    emergency_contact_name: str | None
    emergency_contact_phone: str | None

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True


class AdminUserUpdateRequest(BaseModel):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
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
