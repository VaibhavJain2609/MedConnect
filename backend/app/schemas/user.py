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
    full_name: str | None = None
    language_pref: str | None = None
    phone: str | None = None
