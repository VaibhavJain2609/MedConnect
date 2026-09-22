"""
Appointment waitlist endpoints.

- POST   /api/v1/appointments/waitlist            — patient joins a doctor's
      waitlist for a fully-booked day (409 on duplicate pending entry)
- GET    /api/v1/appointments/waitlist/mine       — patient's own entries
- DELETE /api/v1/appointments/waitlist/{id}       — patient cancels their entry
- GET    /api/v1/appointments/waitlist            — clinic-scoped staff list
      (requires X-Clinic-Id membership; filterable by ?status= and ?date=)

The fan-out itself lives in routers/appointments.py: when an appointment is
cancelled, the earliest pending entries for that doctor+date are marked
``notified`` and the patients receive an in-app notification. Notify-only —
nothing is auto-booked.

Route-order note: this router is mounted BEFORE ``appointments.router`` in
main.py so the literal ``/waitlist`` paths win over ``/{appointment_id}``.
"""

from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_active_clinic, get_current_user, require_patient
from app.models.appointment_waitlist import AppointmentWaitlist
from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.user import User

router = APIRouter(prefix="/api/v1/appointments", tags=["waitlist"])

VALID_SLOT_WINDOWS = {"morning", "afternoon", "any"}
VALID_STATUSES = {"pending", "notified", "expired", "cancelled"}


class WaitlistJoinRequest(BaseModel):
    doctor_id: UUID
    desired_date: date
    slot_window: str = Field(default="any")
    clinic_id: UUID | None = None


def _err(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message}},
    )


def _serialize(
    entry: AppointmentWaitlist,
    *,
    patient_name: str | None = None,
    doctor_name: str | None = None,
    clinic_name: str | None = None,
) -> dict:
    return {
        "id": str(entry.id),
        "patient_id": str(entry.patient_id),
        "patient_name": patient_name,
        "doctor_id": str(entry.doctor_id),
        "doctor_name": doctor_name,
        "clinic_id": str(entry.clinic_id) if entry.clinic_id else None,
        "clinic_name": clinic_name,
        "desired_date": entry.desired_date.isoformat() if entry.desired_date else None,
        "slot_window": entry.slot_window,
        "status": entry.status,
        "notified_at": entry.notified_at.isoformat() if entry.notified_at else None,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    }


async def _serialize_batch(db: AsyncSession, entries: list[AppointmentWaitlist]) -> list[dict]:
    """Serialize entries with patient/doctor/clinic names resolved in bulk."""
    patient_ids = {e.patient_id for e in entries}
    doctor_ids = {e.doctor_id for e in entries}
    clinic_ids = {e.clinic_id for e in entries if e.clinic_id}

    patient_names: dict[UUID, str] = {}
    if patient_ids:
        res = await db.execute(select(User.id, User.full_name).where(User.id.in_(patient_ids)))
        patient_names = {row.id: row.full_name for row in res.all()}

    doctor_names: dict[UUID, str] = {}
    if doctor_ids:
        res = await db.execute(
            select(Doctor.id, User.full_name)
            .join(User, User.id == Doctor.user_id)
            .where(Doctor.id.in_(doctor_ids))
        )
        doctor_names = {row.id: row.full_name for row in res.all()}

    clinic_names: dict[UUID, str] = {}
    if clinic_ids:
        res = await db.execute(select(Clinic.id, Clinic.name).where(Clinic.id.in_(clinic_ids)))
        clinic_names = {row.id: row.name for row in res.all()}

    return [
        _serialize(
            e,
            patient_name=patient_names.get(e.patient_id),
            doctor_name=doctor_names.get(e.doctor_id),
            clinic_name=clinic_names.get(e.clinic_id) if e.clinic_id else None,
        )
        for e in entries
    ]


# ---------------------------------------------------------------------------
# Patient endpoints
# ---------------------------------------------------------------------------


@router.post("/waitlist", status_code=status.HTTP_201_CREATED)
async def join_waitlist(
    req: WaitlistJoinRequest,
    user: User = Depends(require_patient),
    db: AsyncSession = Depends(get_db),
):
    """Join a doctor's waitlist for a fully-booked day.

    Validates that the doctor exists and the date is not in the past. A second
    pending entry for the same (patient, doctor, day) is rejected with 409,
    and a partial unique index enforces it under races.
    """
    if req.slot_window not in VALID_SLOT_WINDOWS:
        raise _err(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "INVALID_SLOT_WINDOW",
            f"slot_window must be one of: {', '.join(sorted(VALID_SLOT_WINDOWS))}",
        )

    if req.desired_date < datetime.now(tz=timezone.utc).date():
        raise _err(
            status.HTTP_400_BAD_REQUEST,
            "INVALID_DATE",
            "desired_date cannot be in the past",
        )

    doctor_res = await db.execute(
        select(Doctor).where(Doctor.id == req.doctor_id, Doctor.deleted_at.is_(None))
    )
    if doctor_res.scalar_one_or_none() is None:
        raise _err(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Doctor not found")

    if req.clinic_id is not None:
        clinic_res = await db.execute(
            select(Clinic.id).where(Clinic.id == req.clinic_id, Clinic.deleted_at.is_(None))
        )
        if clinic_res.scalar_one_or_none() is None:
            raise _err(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Clinic not found")

    pending = await db.execute(
        select(AppointmentWaitlist.id).where(
            AppointmentWaitlist.patient_id == user.id,
            AppointmentWaitlist.doctor_id == req.doctor_id,
            AppointmentWaitlist.desired_date == req.desired_date,
            AppointmentWaitlist.status == "pending",
            AppointmentWaitlist.deleted_at.is_(None),
        )
    )
    if pending.scalar_one_or_none() is not None:
        raise _err(
            status.HTTP_409_CONFLICT,
            "WAITLIST_ALREADY_PENDING",
            "You are already on the waitlist for this doctor on this date",
        )

    entry = AppointmentWaitlist(
        patient_id=user.id,
        doctor_id=req.doctor_id,
        clinic_id=req.clinic_id,
        desired_date=req.desired_date,
        slot_window=req.slot_window,
    )
    db.add(entry)
    try:
        await db.flush()
    except IntegrityError:
        # Lost a race against the partial unique index — a pending entry
        # was created concurrently.
        await db.rollback()
        raise _err(
            status.HTTP_409_CONFLICT,
            "WAITLIST_ALREADY_PENDING",
            "You are already on the waitlist for this doctor on this date",
        )

    return _serialize(entry)


@router.get("/waitlist/mine")
async def my_waitlist_entries(
    status_filter: str | None = Query(None, alias="status"),
    user: User = Depends(require_patient),
    db: AsyncSession = Depends(get_db),
):
    """List the current patient's waitlist entries (newest first, capped)."""
    if status_filter is not None and status_filter not in VALID_STATUSES:
        raise _err(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "INVALID_STATUS",
            f"status must be one of: {', '.join(sorted(VALID_STATUSES))}",
        )

    stmt = (
        select(AppointmentWaitlist)
        .where(
            AppointmentWaitlist.patient_id == user.id,
            AppointmentWaitlist.deleted_at.is_(None),
        )
        .order_by(AppointmentWaitlist.created_at.desc())
        .limit(200)
    )
    if status_filter:
        stmt = stmt.where(AppointmentWaitlist.status == status_filter)

    result = await db.execute(stmt)
    return {"data": await _serialize_batch(db, result.scalars().all())}


@router.delete("/waitlist/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_waitlist_entry(
    entry_id: UUID,
    user: User = Depends(require_patient),
    db: AsyncSession = Depends(get_db),
):
    """Cancel one of the patient's own waitlist entries (soft-delete)."""
    result = await db.execute(
        select(AppointmentWaitlist).where(
            AppointmentWaitlist.id == entry_id,
            AppointmentWaitlist.deleted_at.is_(None),
        )
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise _err(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Waitlist entry not found")
    if entry.patient_id != user.id:
        raise _err(status.HTTP_403_FORBIDDEN, "FORBIDDEN", "Access denied")

    entry.status = "cancelled"
    entry.deleted_at = datetime.now(tz=timezone.utc)
    await db.flush()


# ---------------------------------------------------------------------------
# Staff endpoint
# ---------------------------------------------------------------------------


@router.get("/waitlist")
async def list_clinic_waitlist(
    status_filter: str | None = Query(None, alias="status"),
    date_filter: str | None = Query(None, alias="date"),
    user: User = Depends(get_current_user),
    clinic_ctx: tuple | None = Depends(get_active_clinic),
    db: AsyncSession = Depends(get_db),
):
    """Clinic-scoped waitlist for front-desk staff.

    Requires the X-Clinic-Id header — ``get_active_clinic`` verifies the
    caller holds an active ClinicMembership (any role incl. receptionist)
    and raises 403 otherwise.
    """
    if clinic_ctx is None:
        raise _err(
            status.HTTP_400_BAD_REQUEST,
            "MISSING_CLINIC",
            "X-Clinic-Id header required",
        )
    clinic_id, _membership_role = clinic_ctx

    if status_filter is not None and status_filter not in VALID_STATUSES:
        raise _err(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "INVALID_STATUS",
            f"status must be one of: {', '.join(sorted(VALID_STATUSES))}",
        )

    stmt = (
        select(AppointmentWaitlist)
        .where(
            AppointmentWaitlist.clinic_id == clinic_id,
            AppointmentWaitlist.deleted_at.is_(None),
        )
        .order_by(AppointmentWaitlist.desired_date.asc(), AppointmentWaitlist.created_at.asc())
        .limit(500)
    )
    if status_filter:
        stmt = stmt.where(AppointmentWaitlist.status == status_filter)
    if date_filter:
        try:
            target = date.fromisoformat(date_filter)
        except ValueError:
            raise _err(
                status.HTTP_400_BAD_REQUEST,
                "INVALID_DATE",
                "date must be YYYY-MM-DD",
            )
        stmt = stmt.where(AppointmentWaitlist.desired_date == target)

    result = await db.execute(stmt)
    return {"data": await _serialize_batch(db, result.scalars().all())}
