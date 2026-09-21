import json
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_patient
from app.models.doctor import Doctor
from app.models.lab_result import LabResult
from app.models.user import User
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.record import RecordResponse, VALID_RECORD_TYPES, _validate_document_url
from app.schemas.user import MedicalHistoryUpdate, PatientProfileUpdate
from app.services.export_service import build_records_export_bundle
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


@router.get("/records")
async def list_records(
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


# NOTE: must be declared before /records/{record_id} so "export" isn't
# captured by the UUID path parameter.
@router.get("/records/export")
async def export_records(
    format: str = Query("json", description="Export format (only 'json' is supported)"),
    user: User = Depends(require_patient),
    db: AsyncSession = Depends(get_db),
):
    """Download all of the caller's records as a FHIR R4 collection Bundle."""
    if format != "json":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Only format=json is supported",
                }
            },
        )
    bundle = await build_records_export_bundle(db=db, user=user)
    filename = f"medconnect-records-{datetime.now(timezone.utc).date().isoformat()}.json"
    return Response(
        content=json.dumps(bundle),
        media_type="application/fhir+json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
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

    # Batch-load prescriber names (Prescription.doctor_id -> Doctor -> User)
    doctor_ids = list({p.doctor_id for p in items})
    doctor_names: dict[UUID, str] = {}
    if doctor_ids:
        dr = await db.execute(
            select(Doctor.id, User.full_name)
            .join(User, Doctor.user_id == User.id)
            .where(Doctor.id.in_(doctor_ids))
        )
        doctor_names = {row.id: row.full_name for row in dr.all()}

    return PaginatedResponse(
        data=[
            {
                "id": str(p.id),
                "record_id": str(p.record_id),
                "medicines": p.medicines,
                "diagnosis": p.diagnosis,
                "notes": p.notes,
                "doctor_id": str(p.doctor_id),
                "doctor_name": doctor_names.get(p.doctor_id),
                "valid_until": p.valid_until.isoformat() if p.valid_until else None,
                "created_at": p.created_at.isoformat(),
            }
            for p in items
        ],
        pagination=PaginationMeta(next_cursor=next_cursor, has_more=has_more, limit=limit),
    )


# ─── Lab results (patient-facing) ────────────────────────────────────────────


def _serialize_lab_result(lr: LabResult, doctor_name: str | None = None) -> dict:
    return {
        "id": str(lr.id),
        "test_id": lr.test_id,
        "test_name": lr.test_name,
        "test_category": lr.test_category,
        "appointment_date": lr.appointment_date.isoformat(),
        "status": lr.status,
        "result_value": lr.result_value,
        "result_unit": lr.result_unit,
        "normal_range": lr.normal_range,
        "abnormal_flag": lr.abnormal_flag,
        "notes": lr.notes,
        "doctor_id": str(lr.doctor_id) if lr.doctor_id else None,
        "doctor_name": doctor_name,
        "created_at": lr.created_at.isoformat(),
    }


@router.get("/lab-results")
async def list_lab_results(
    category: str | None = Query(None, description="Filter by test category"),
    cursor: UUID | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(require_patient),
    db: AsyncSession = Depends(get_db),
):
    """List the current patient's lab results, newest first."""
    stmt = (
        select(LabResult)
        .where(LabResult.patient_id == user.id, LabResult.deleted_at.is_(None))
        .order_by(LabResult.appointment_date.desc(), LabResult.id.desc())
        .limit(limit + 1)
    )

    if category:
        stmt = stmt.where(LabResult.test_category == category)

    if cursor:
        cursor_result = await db.execute(
            select(LabResult.appointment_date).where(
                LabResult.id == cursor, LabResult.patient_id == user.id
            )
        )
        cursor_time = cursor_result.scalar_one_or_none()
        if cursor_time:
            stmt = stmt.where(
                LabResult.appointment_date <= cursor_time, LabResult.id != cursor
            )

    result = await db.execute(stmt)
    items = list(result.scalars().all())

    has_more = len(items) > limit
    results = items[:limit]
    next_cursor = str(results[-1].id) if results and has_more else None

    # Batch-load ordering-doctor names (LabResult.doctor_id -> users.id)
    doctor_ids = list({lr.doctor_id for lr in results if lr.doctor_id})
    doctor_names: dict[UUID, str] = {}
    if doctor_ids:
        dr = await db.execute(select(User.id, User.full_name).where(User.id.in_(doctor_ids)))
        doctor_names = {row.id: row.full_name for row in dr.all()}

    return PaginatedResponse(
        data=[
            _serialize_lab_result(lr, doctor_names.get(lr.doctor_id))
            for lr in results
        ],
        pagination=PaginationMeta(next_cursor=next_cursor, has_more=has_more, limit=limit),
    )


@router.get("/lab-results/{lab_result_id}")
async def get_lab_result(
    lab_result_id: UUID,
    user: User = Depends(require_patient),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a single lab result owned by the current patient."""
    result = await db.execute(
        select(LabResult).where(
            LabResult.id == lab_result_id,
            LabResult.patient_id == user.id,
            LabResult.deleted_at.is_(None),
        )
    )
    lr = result.scalar_one_or_none()
    if not lr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Lab result not found"}},
        )

    doctor_name: str | None = None
    if lr.doctor_id:
        doctor_name = await db.scalar(
            select(User.full_name).where(User.id == lr.doctor_id)
        )

    return _serialize_lab_result(lr, doctor_name)


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
    data = body.model_dump(exclude_unset=True)
    if "phone" in data:
        user.phone = data["phone"]
    if "language_pref" in data:
        user.language_pref = data["language_pref"]
    if "emergency_contact_name" in data:
        user.emergency_contact_name = data["emergency_contact_name"]
    if "emergency_contact_phone" in data:
        user.emergency_contact_phone = data["emergency_contact_phone"]
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
    data = body.model_dump(exclude_unset=True)
    if "blood_group" in data:
        user.blood_group = data["blood_group"]
    if "allergies" in data:
        user.allergies = data["allergies"]
    if "chronic_conditions" in data:
        user.chronic_conditions = data["chronic_conditions"]
    if "height_cm" in data:
        user.height_cm = data["height_cm"]
    if "weight_kg" in data:
        user.weight_kg = data["weight_kg"]
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

    @field_validator("document_url")
    @classmethod
    def validate_document_url(cls, v: str | None) -> str | None:
        return _validate_document_url(v)


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


@router.get("/doctors/search")
async def search_doctors(
    q: str = Query(..., min_length=2),
    user: User = Depends(require_patient),
    db: AsyncSession = Depends(get_db),
):
    """Search verified doctors by name or specialization for patient appointment booking."""
    search_term = f"%{q.lower()}%"
    stmt = (
        select(Doctor, User.full_name, User.email)
        .join(User, Doctor.user_id == User.id)
        .where(
            Doctor.deleted_at.is_(None),
            User.deleted_at.is_(None),
            User.is_active.is_(True),
            Doctor.verified == True,
            or_(
                func.lower(User.full_name).like(search_term),
                func.lower(Doctor.specialization).like(search_term),
                func.lower(Doctor.facility_name).like(search_term),
            ),
        )
        .order_by(User.full_name.asc())
        .limit(20)
    )
    result = await db.execute(stmt)
    rows = result.all()

    return {
        "data": [
            {
                "id": str(row.Doctor.id),
                "full_name": row.full_name,
                "specialization": row.Doctor.specialization,
                "facility_name": row.Doctor.facility_name,
                "facility_city": row.Doctor.facility_city,
                "verified": bool(row.Doctor.verified),
            }
            for row in rows
        ]
    }
