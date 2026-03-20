"""
Admin lab results endpoints  [MD-265]

GET    /api/v1/admin/lab-results/categories  — list distinct test categories
GET    /api/v1/admin/lab-results             — list with pagination, search, status filter
GET    /api/v1/admin/lab-results/{id}        — get single lab result
POST   /api/v1/admin/lab-results             — create lab result
PUT    /api/v1/admin/lab-results/{id}        — update lab result
DELETE /api/v1/admin/lab-results/{id}        — soft delete
"""
import math
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.database import get_db
from app.dependencies import require_admin
from app.models.lab_result import LabResult
from app.models.user import User
from app.schemas.lab_result import LabResultCreate, LabResultResponse, LabResultUpdate

router = APIRouter(
    prefix="/api/v1/admin/lab-results",
    tags=["admin-lab-results"],
    dependencies=[Depends(require_admin)],
)

_LAB_RESULT_STATUSES = {"pending", "in_progress", "received", "completed"}

# Aliases for joining users table twice (patient + doctor)
PatientUser = aliased(User, flat=True)
DoctorUser = aliased(User, flat=True)


def _generate_test_id(counter: int) -> str:
    """Generate a human-readable test ID like LAB-2026-00001."""
    year = datetime.now(timezone.utc).year
    return f"LAB-{year}-{counter:05d}"


async def _next_test_id(db: AsyncSession) -> str:
    """Return the next sequential test_id string."""
    count = await db.scalar(select(func.count()).select_from(LabResult).where(LabResult.deleted_at.is_(None))) or 0
    return _generate_test_id(count + 1)


def _build_response(row) -> dict:
    """Build a LabResultResponse dict from a joined query row."""
    lr: LabResult = row.LabResult
    patient_name: str = row.patient_name
    doctor_name: Optional[str] = getattr(row, "doctor_name", None)
    return LabResultResponse(
        id=lr.id,
        test_id=lr.test_id,
        patient_id=lr.patient_id,
        patient_name=patient_name,
        patient_photo=None,
        gender=None,
        doctor_id=lr.doctor_id,
        doctor_name=doctor_name,
        doctor_photo=None,
        test_name=lr.test_name,
        test_category=lr.test_category,
        appointment_date=lr.appointment_date,
        status=lr.status,
        result_value=lr.result_value,
        result_unit=lr.result_unit,
        normal_range=lr.normal_range,
        abnormal_flag=lr.abnormal_flag,
        notes=lr.notes,
        created_at=lr.created_at,
        updated_at=lr.updated_at,
    )


def _list_query():
    """Base SELECT for list and single-item lookups: joins patient + doctor users."""
    return (
        select(
            LabResult,
            PatientUser.full_name.label("patient_name"),
            DoctorUser.full_name.label("doctor_name"),
        )
        .join(PatientUser, and_(LabResult.patient_id == PatientUser.id, PatientUser.deleted_at.is_(None)))
        .outerjoin(DoctorUser, and_(LabResult.doctor_id == DoctorUser.id, DoctorUser.deleted_at.is_(None)))
        .where(LabResult.deleted_at.is_(None))
    )


# NOTE: /categories must be declared before /{lab_result_id} to avoid route shadowing.
@router.get("/categories")
async def list_categories(db: AsyncSession = Depends(get_db)):
    """Return all distinct non-null test_category values."""
    result = await db.execute(
        select(LabResult.test_category)
        .where(LabResult.deleted_at.is_(None), LabResult.test_category.isnot(None))
        .distinct()
        .order_by(LabResult.test_category)
    )
    categories = [row[0] for row in result.all()]
    return categories


@router.get("")
async def list_lab_results(
    search: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    test_category: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List lab results with optional filters and pagination."""
    query = _list_query()

    if search:
        query = query.where(
            or_(
                PatientUser.full_name.ilike(f"%{search}%"),
                LabResult.test_name.ilike(f"%{search}%"),
            )
        )
    if status_filter:
        query = query.where(LabResult.status == status_filter)
    if test_category:
        query = query.where(LabResult.test_category == test_category)
    if date:
        # Filter by appointment_date calendar day (date string like "2026-03-15")
        try:
            filter_date = datetime.strptime(date, "%Y-%m-%d").date()
            query = query.where(func.date(LabResult.appointment_date) == filter_date)
        except ValueError:
            pass  # Silently ignore malformed date filters

    total = await db.scalar(select(func.count()).select_from(query.subquery())) or 0

    result = await db.execute(
        query.order_by(LabResult.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    rows = result.all()

    return {
        "results": [_build_response(row) for row in rows],
        "total": total,
        "page": page,
        "limit": limit,
        "totalPages": math.ceil(total / limit) if total else 0,
    }


@router.get("/{lab_result_id}", response_model=LabResultResponse)
async def get_lab_result(
    lab_result_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        rid = uuid.UUID(lab_result_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "INVALID_ID", "message": "Invalid lab result ID"}},
        )

    result = await db.execute(_list_query().where(LabResult.id == rid))
    row = result.one_or_none()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Lab result not found"}},
        )
    return _build_response(row)


@router.post("", response_model=LabResultResponse, status_code=status.HTTP_201_CREATED)
async def create_lab_result(
    data: LabResultCreate,
    db: AsyncSession = Depends(get_db),
):
    # Validate patient exists
    patient = await db.scalar(
        select(User).where(User.id == data.patient_id, User.deleted_at.is_(None))
    )
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "PATIENT_NOT_FOUND", "message": "Patient not found"}},
        )

    # Validate doctor if provided
    if data.doctor_id:
        doctor = await db.scalar(
            select(User).where(User.id == data.doctor_id, User.deleted_at.is_(None))
        )
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "DOCTOR_NOT_FOUND", "message": "Doctor not found"}},
            )

    test_id = await _next_test_id(db)
    lab_result = LabResult(
        test_id=test_id,
        patient_id=data.patient_id,
        doctor_id=data.doctor_id,
        test_name=data.test_name,
        test_category=data.test_category,
        appointment_date=data.appointment_date,
        status="pending",
        notes=data.notes,
    )
    db.add(lab_result)
    await db.commit()
    await db.refresh(lab_result)

    result = await db.execute(_list_query().where(LabResult.id == lab_result.id))
    row = result.one()
    return _build_response(row)


@router.put("/{lab_result_id}", response_model=LabResultResponse)
async def update_lab_result(
    lab_result_id: str,
    data: LabResultUpdate,
    db: AsyncSession = Depends(get_db),
):
    try:
        rid = uuid.UUID(lab_result_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "INVALID_ID", "message": "Invalid lab result ID"}},
        )

    lab_result = await db.scalar(
        select(LabResult).where(LabResult.id == rid, LabResult.deleted_at.is_(None))
    )
    if not lab_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Lab result not found"}},
        )

    if data.status is not None and data.status not in _LAB_RESULT_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_STATUS",
                    "message": f"Status must be one of: {', '.join(sorted(_LAB_RESULT_STATUSES))}",
                }
            },
        )

    # Validate doctor if being changed
    if data.doctor_id is not None:
        doctor = await db.scalar(
            select(User).where(User.id == data.doctor_id, User.deleted_at.is_(None))
        )
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "DOCTOR_NOT_FOUND", "message": "Doctor not found"}},
            )

    update_fields = data.model_dump(exclude_unset=True)
    if "status" in update_fields:
        lab_result.status = update_fields["status"]
    if "result_value" in update_fields:
        lab_result.result_value = update_fields["result_value"]
    if "result_unit" in update_fields:
        lab_result.result_unit = update_fields["result_unit"]
    if "normal_range" in update_fields:
        lab_result.normal_range = update_fields["normal_range"]
    if "abnormal_flag" in update_fields:
        lab_result.abnormal_flag = update_fields["abnormal_flag"]
    if "notes" in update_fields:
        lab_result.notes = update_fields["notes"]
    if "test_name" in update_fields:
        lab_result.test_name = update_fields["test_name"]
    if "test_category" in update_fields:
        lab_result.test_category = update_fields["test_category"]
    if "appointment_date" in update_fields:
        lab_result.appointment_date = update_fields["appointment_date"]
    if "doctor_id" in update_fields:
        lab_result.doctor_id = update_fields["doctor_id"]
    lab_result.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(lab_result)

    result = await db.execute(_list_query().where(LabResult.id == lab_result.id))
    row = result.one()
    return _build_response(row)


@router.delete("/{lab_result_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lab_result(
    lab_result_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        rid = uuid.UUID(lab_result_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "INVALID_ID", "message": "Invalid lab result ID"}},
        )

    lab_result = await db.scalar(
        select(LabResult).where(LabResult.id == rid, LabResult.deleted_at.is_(None))
    )
    if not lab_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Lab result not found"}},
        )

    lab_result.deleted_at = datetime.now(timezone.utc)
    lab_result.updated_at = datetime.now(timezone.utc)
    await db.commit()
