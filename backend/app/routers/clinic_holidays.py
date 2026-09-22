"""
Clinic holiday endpoints — CRUD for clinic closure days.

GET    /api/v1/clinics/{clinic_id}/holidays          — list (?year= filter)
POST   /api/v1/clinics/{clinic_id}/holidays          — add a closure date
DELETE /api/v1/clinics/{clinic_id}/holidays/{id}     — remove (soft delete)

All routes require an active clinic membership with role owner|admin
(clinic-scoped admin). Holidays block slot generation in
``routers/availability.py:get_doctor_slots`` — they do NOT block direct
appointment creation (phone bookings stay allowed).
"""
import uuid
from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.clinic_holiday import ClinicHoliday
from app.models.user import User
from app.schemas.clinic_holiday import ClinicHolidayCreate, ClinicHolidayResponse
from app.services import access_service

router = APIRouter(prefix="/api/v1/clinics/{clinic_id}/holidays", tags=["clinic-holidays"])

CLINIC_ADMIN_ROLES = {"owner", "admin"}


@router.get("", response_model=dict)
async def list_clinic_holidays(
    clinic_id: UUID,
    year: int | None = Query(None, ge=1900, le=2100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List the clinic's holidays, ordered by date. ``?year=2026`` filters
    to that calendar year (clinic-local dates)."""
    await access_service.require_membership_role(db, user, clinic_id, allowed_roles=CLINIC_ADMIN_ROLES)
    stmt = (
        select(ClinicHoliday)
        .where(
            ClinicHoliday.clinic_id == clinic_id,
            ClinicHoliday.deleted_at.is_(None),
        )
        .order_by(ClinicHoliday.date.asc())
    )
    if year is not None:
        stmt = stmt.where(
            ClinicHoliday.date >= date(year, 1, 1),
            ClinicHoliday.date <= date(year, 12, 31),
        )
    res = await db.execute(stmt)
    return {"data": [ClinicHolidayResponse.model_validate(h) for h in res.scalars().all()]}


@router.post("", response_model=ClinicHolidayResponse, status_code=status.HTTP_201_CREATED)
async def create_clinic_holiday(
    clinic_id: UUID,
    data: ClinicHolidayCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a closure date for the clinic. 409 when the date already exists."""
    await access_service.require_membership_role(db, user, clinic_id, allowed_roles=CLINIC_ADMIN_ROLES)

    dup_res = await db.execute(
        select(ClinicHoliday.id).where(
            ClinicHoliday.clinic_id == clinic_id,
            ClinicHoliday.date == data.date,
            ClinicHoliday.deleted_at.is_(None),
        )
    )
    if dup_res.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "DUPLICATE_HOLIDAY",
                    "message": "A holiday already exists for this date",
                }
            },
        )

    holiday = ClinicHoliday(
        id=uuid.uuid4(),
        clinic_id=clinic_id,
        date=data.date,
        name=data.name,
    )
    db.add(holiday)
    try:
        await db.flush()
    except IntegrityError:
        # uq_clinic_holidays_clinic_date caught a race between check and insert
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "DUPLICATE_HOLIDAY",
                    "message": "A holiday already exists for this date",
                }
            },
        )
    await db.refresh(holiday)
    return holiday


@router.delete("/{holiday_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_clinic_holiday(
    clinic_id: UUID,
    holiday_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete one of the clinic's holidays."""
    await access_service.require_membership_role(db, user, clinic_id, allowed_roles=CLINIC_ADMIN_ROLES)
    res = await db.execute(
        select(ClinicHoliday).where(
            ClinicHoliday.id == holiday_id,
            ClinicHoliday.clinic_id == clinic_id,
            ClinicHoliday.deleted_at.is_(None),
        )
    )
    holiday = res.scalar_one_or_none()
    if holiday is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Holiday not found"}},
        )
    holiday.deleted_at = datetime.now(tz=timezone.utc)
    await db.flush()
    return None
