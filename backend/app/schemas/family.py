from datetime import date

from pydantic import BaseModel, field_validator

from app.models.family import FAMILY_RELATIONSHIPS

BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]


def _validate_relationship(v: str) -> str:
    if v not in FAMILY_RELATIONSHIPS:
        raise ValueError(
            f"relationship must be one of: {', '.join(FAMILY_RELATIONSHIPS)}"
        )
    return v


def _validate_dob(v: date) -> date:
    if v > date.today():
        raise ValueError("dob cannot be in the future")
    return v


def _validate_blood_group(v: str | None) -> str | None:
    if v is None:
        return v
    v = v.strip().upper()
    if not v:
        return None
    if v not in BLOOD_GROUPS:
        raise ValueError(f"blood_group must be one of: {', '.join(BLOOD_GROUPS)}")
    return v


class FamilyMemberCreate(BaseModel):
    full_name: str
    dob: date
    relationship: str
    gender: str | None = None
    blood_group: str | None = None
    notes: str | None = None

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > 255:
            raise ValueError("full_name must be 1-255 characters")
        return v

    @field_validator("dob")
    @classmethod
    def validate_dob(cls, v: date) -> date:
        return _validate_dob(v)

    @field_validator("relationship")
    @classmethod
    def validate_relationship(cls, v: str) -> str:
        return _validate_relationship(v)

    @field_validator("blood_group")
    @classmethod
    def validate_blood_group(cls, v: str | None) -> str | None:
        return _validate_blood_group(v)


class FamilyMemberUpdate(BaseModel):
    full_name: str | None = None
    dob: date | None = None
    relationship: str | None = None
    gender: str | None = None
    blood_group: str | None = None
    notes: str | None = None

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v or len(v) > 255:
            raise ValueError("full_name must be 1-255 characters")
        return v

    @field_validator("dob")
    @classmethod
    def validate_dob(cls, v: date | None) -> date | None:
        if v is None:
            return v
        return _validate_dob(v)

    @field_validator("relationship")
    @classmethod
    def validate_relationship(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return _validate_relationship(v)

    @field_validator("blood_group")
    @classmethod
    def validate_blood_group(cls, v: str | None) -> str | None:
        return _validate_blood_group(v)


def compute_age(dob: date, today: date | None = None) -> int:
    """Whole years elapsed since dob."""
    today = today or date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def serialize_member(member) -> dict:
    return {
        "id": str(member.id),
        "member_id": str(member.id),
        "full_name": member.full_name,
        "dob": member.dob.isoformat(),
        "age": compute_age(member.dob),
        "gender": member.gender,
        "relationship": member.relationship,
        "blood_group": member.blood_group,
        "notes": member.notes,
        "created_at": member.created_at.isoformat() if member.created_at else None,
        "updated_at": member.updated_at.isoformat() if member.updated_at else None,
    }
