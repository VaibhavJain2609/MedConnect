from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_patient
from app.models.user import User
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.record import RecordResponse, VALID_RECORD_TYPES
from app.schemas.user import MedicalHistoryUpdate, PatientProfileUpdate
from app.services.prescription_service import get_patient_prescriptions
from app.services.record_service import create_record, get_patient_timeline, get_record_detail

router = APIRouter(prefix="/api/v1/patients", tags=["patients"])


@router.get("/timeline")
async def timeline(
    type: str | None = Query(None, description="Filter by record type"),
    q: str | None = Query(None, description="Search query"),
    cursor: UUID | None = Query(None, description="Pagination cursor"),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(require_patient),
    db: AsyncSession = Depends(get_db),
):
    records, next_cursor, has_more = await get_patient_timeline(
        db=db, patient_id=user.id, record_type=type, query=q, cursor=cursor, limit=limit
    )
    return PaginatedResponse(
        data=records,
        pagination=PaginationMeta(next_cursor=next_cursor, has_more=has_more, limit=limit),
    )


@router.get("/records/{record_id}", response_model=RecordResponse)
async def get_record(
    record_id: UUID,
    user: User = Depends(require_patient),
    db: AsyncSession = Depends(get_db),
):
    record = await get_record_detail(db=db, record_id=record_id, user_id=user.id, user_role="patient")
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Record not found"}},
        )
    return record


@router.get("/prescriptions")
async def prescriptions(
    cursor: UUID | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(require_patient),
    db: AsyncSession = Depends(get_db),
):
    items, next_cursor, has_more = await get_patient_prescriptions(
        db=db, patient_id=user.id, cursor=cursor, limit=limit
    )
    return PaginatedResponse(
        data=[
            {
                "id": str(p.id),
                "record_id": str(p.record_id),
                "medicines": p.medicines,
                "diagnosis": p.diagnosis,
                "notes": p.notes,
                "valid_until": p.valid_until.isoformat() if p.valid_until else None,
                "created_at": p.created_at.isoformat(),
            }
            for p in items
        ],
        pagination=PaginationMeta(next_cursor=next_cursor, has_more=has_more, limit=limit),
    )


@router.get("/profile")
async def get_profile(user: User = Depends(require_patient)):
    return {
        "id": str(user.id),
        "full_name": user.full_name,
        "email": user.email,
        "phone": user.phone,
        "language_pref": user.language_pref,
        "emergency_contact_name": user.emergency_contact_name,
        "emergency_contact_phone": user.emergency_contact_phone,
    }


@router.put("/profile")
async def update_profile(
    body: PatientProfileUpdate,
    user: User = Depends(require_patient),
    db: AsyncSession = Depends(get_db),
):
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {
        "id": str(user.id),
        "full_name": user.full_name,
        "email": user.email,
        "phone": user.phone,
        "language_pref": user.language_pref,
        "emergency_contact_name": user.emergency_contact_name,
        "emergency_contact_phone": user.emergency_contact_phone,
    }


@router.get("/medical-history")
async def get_medical_history(user: User = Depends(require_patient)):
    return {
        "blood_group": user.blood_group,
        "allergies": user.allergies or [],
        "chronic_conditions": user.chronic_conditions or [],
        "height_cm": user.height_cm,
        "weight_kg": user.weight_kg,
    }


@router.put("/medical-history")
async def update_medical_history(
    body: MedicalHistoryUpdate,
    user: User = Depends(require_patient),
    db: AsyncSession = Depends(get_db),
):
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {
        "blood_group": user.blood_group,
        "allergies": user.allergies or [],
        "chronic_conditions": user.chronic_conditions or [],
        "height_cm": user.height_cm,
        "weight_kg": user.weight_kg,
    }


# Patient self-upload record types (subset — excludes doctor-only types)
PATIENT_UPLOAD_RECORD_TYPES = [
    "lab_report", "diagnostic_report", "discharge_summary", "imaging", "immunization",
]


class PatientRecordCreate(BaseModel):
    record_type: str
    title: str
    description: str | None = None
    document_url: str | None = None

    @field_validator("record_type")
    @classmethod
    def validate_record_type(cls, v: str) -> str:
        if v not in PATIENT_UPLOAD_RECORD_TYPES:
            raise ValueError(
                f"record_type must be one of: {', '.join(PATIENT_UPLOAD_RECORD_TYPES)}"
            )
        return v


@router.post("/records", response_model=RecordResponse, status_code=status.HTTP_201_CREATED)
async def create_patient_record(
    body: PatientRecordCreate,
    user: User = Depends(require_patient),
    db: AsyncSession = Depends(get_db),
):
    """Allow a patient to self-upload a health record with an optional document attachment."""
    try:
        record = await create_record(
            db=db,
            patient_id=user.id,
            doctor_id=None,
            record_type=body.record_type,
            title=body.title,
            description=body.description,
            document_url=body.document_url,
            source="patient_uploaded",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(e)}},
        )
    await db.commit()
    await db.refresh(record)
    return record
