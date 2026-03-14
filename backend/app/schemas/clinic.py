from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_validator


# ── Branch schemas ─────────────────────────────────────────────────────────

class ClinicBranchCreate(BaseModel):
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    phone: Optional[str] = None


class ClinicBranchResponse(BaseModel):
    id: str
    clinic_id: str
    name: str
    address: Optional[str]
    city: Optional[str]
    state: Optional[str]
    phone: Optional[str]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("id", "clinic_id", mode="before")
    @classmethod
    def stringify_uuid(cls, v):
        return str(v) if v is not None else v


# ── Membership schemas ─────────────────────────────────────────────────────

class ClinicMemberResponse(BaseModel):
    id: str
    user_id: str
    full_name: str
    email: Optional[str]
    role: str
    branch_id: Optional[str]
    is_active: bool
    joined_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("id", "user_id", "branch_id", mode="before")
    @classmethod
    def stringify_uuid(cls, v):
        return str(v) if v is not None else v


class ClinicMemberListResponse(BaseModel):
    data: list[ClinicMemberResponse]
    total: int


# ── Clinic schemas ─────────────────────────────────────────────────────────

class ClinicCreate(BaseModel):
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class ClinicUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    logo_url: Optional[str] = None
    is_active: Optional[bool] = None


class ClinicSettingsUpdate(BaseModel):
    record_sharing_mode: str

    @field_validator("record_sharing_mode")
    @classmethod
    def validate_mode(cls, v):
        allowed = {"per_clinic", "per_doctor"}
        if v not in allowed:
            raise ValueError(f"record_sharing_mode must be one of {allowed}")
        return v


class ClinicResponse(BaseModel):
    id: str
    name: str
    address: Optional[str]
    city: Optional[str]
    state: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    logo_url: Optional[str]
    is_active: bool
    record_sharing_mode: str
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("id", "created_by", mode="before")
    @classmethod
    def stringify_uuid(cls, v):
        return str(v) if v is not None else v


class ClinicListResponse(BaseModel):
    data: list[ClinicResponse]
    total: int


# ── Admin schemas ──────────────────────────────────────────────────────────

class AdminClinicListItem(BaseModel):
    id: str
    name: str
    city: Optional[str]
    state: Optional[str]
    is_active: bool
    record_sharing_mode: str
    member_count: int
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("id", mode="before")
    @classmethod
    def stringify_uuid(cls, v):
        return str(v) if v is not None else v


class AdminClinicDetailResponse(ClinicResponse):
    member_count: int
    record_count: int
    prescription_count: int
    branches: list[ClinicBranchResponse] = []
