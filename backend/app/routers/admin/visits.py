"""
Admin visits (encounters) endpoints.

GET    /api/v1/admin/visits        — paginated list w/ patient & doctor names
GET    /api/v1/admin/visits/{id}   — single visit detail
DELETE /api/v1/admin/visits/{id}   — soft delete
"""
import math
import uuid
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.database import get_db
from app.dependencies import require_admin
from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.encounter import Encounter
from app.models.user import User

router = APIRouter(
    prefix="/api/v1/admin/visits",
    tags=["admin-visits"],
    dependencies=[Depends(require_admin)],
)

# Aliases for joining users twice (patient + doctor's user account)
PatientUser = aliased(User, flat=True)
DoctorUser = aliased(User, flat=True)


def _build_visit(row) -> dict:
    """Serialize a joined encounter row for the admin visits table."""
    enc: Encounter = row.Encounter
    return {
        "id": str(enc.id),
        "patient_id": str(enc.patient_id),
        "patient_name": row.patient_name,
        "doctor_id": str(enc.doctor_id),
        "doctor_name": row.doctor_name,
        "clinic_id": str(enc.clinic_id) if enc.clinic_id else None,
        "clinic_name": row.clinic_name,
        "appointment_id": str(enc.appointment_id) if enc.appointment_id else None,
        "subjective": enc.subjective,
        "objective": enc.objective,
        "assessment": enc.assessment,
        "plan": enc.plan,
        "vitals_snapshot": enc.vitals_snapshot,
        "created_at": enc.created_at.isoformat(),
        "updated_at": enc.updated_at.isoformat(),
    }


def _list_query():
    """Base SELECT joining patient user, doctor's user account, and clinic."""
    return (
        select(
            Encounter,
            PatientUser.full_name.label("patient_name"),
            DoctorUser.full_name.label("doctor_name"),
            Clinic.name.label("clinic_name"),
        )
        .join(PatientUser, and_(Encounter.patient_id == PatientUser.id, PatientUser.deleted_at.is_(None)))
        .join(Doctor, and_(Encounter.doctor_id == Doctor.id, Doctor.deleted_at.is_(None)))
        .outerjoin(DoctorUser, and_(Doctor.user_id == DoctorUser.id, DoctorUser.deleted_at.is_(None)))
        .outerjoin(Clinic, and_(Encounter.clinic_id == Clinic.id, Clinic.deleted_at.is_(None)))
        .where(Encounter.deleted_at.is_(None))
    )


@router.get("")
async def list_visits(
    search: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    patient_id: Optional[UUID] = Query(None),
    doctor_id: Optional[UUID] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List encounters (visits) with optional search/filters and pagination."""
    query = _list_query()

    if search:
        query = query.where(
            or_(
                PatientUser.full_name.ilike(f"%{search}%"),
                DoctorUser.full_name.ilike(f"%{search}%"),
                Clinic.name.ilike(f"%{search}%"),
            )
        )
    if patient_id:
        query = query.where(Encounter.patient_id == patient_id)
    if doctor_id:
        query = query.where(Encounter.doctor_id == doctor_id)
    if date:
        try:
            filter_date = datetime.strptime(date, "%Y-%m-%d").date()
            query = query.where(func.date(Encounter.created_at) == filter_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "INVALID_DATE", "message": "Invalid date format. Use YYYY-MM-DD"}},
            )

    total = await db.scalar(select(func.count()).select_from(query.subquery())) or 0

    result = await db.execute(
        query.order_by(Encounter.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    rows = result.all()

    return {
        "visits": [_build_visit(row) for row in rows],
        "total": total,
        "page": page,
        "limit": limit,
        "totalPages": math.ceil(total / limit) if total else 0,
    }


@router.get("/{visit_id}")
async def get_visit(
    visit_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        rid = uuid.UUID(visit_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "INVALID_ID", "message": "Invalid visit ID"}},
        )

    result = await db.execute(_list_query().where(Encounter.id == rid))
    row = result.one_or_none()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Visit not found"}},
        )
    return _build_visit(row)


@router.delete("/{visit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_visit(
    visit_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        rid = uuid.UUID(visit_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "INVALID_ID", "message": "Invalid visit ID"}},
        )

    enc = await db.scalar(
        select(Encounter).where(Encounter.id == rid, Encounter.deleted_at.is_(None))
    )
    if not enc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Visit not found"}},
        )

    enc.deleted_at = datetime.now(timezone.utc)
    enc.updated_at = datetime.now(timezone.utc)
    await db.flush()
