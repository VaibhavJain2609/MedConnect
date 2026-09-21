import uuid
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import cast, func, select
from sqlalchemy.dialects.postgresql import INTERVAL
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import (
    get_current_doctor,
    get_current_user,
    require_active_clinic,
)
from app.models.appointment import Appointment
from app.models.clinic import Clinic, ClinicBranch, ClinicMembership
from app.models.doctor import Doctor
from app.models.doctor_availability import DoctorAvailability, DoctorLeave
from app.models.user import User
from app.schemas.availability import (
    AvailabilitySlot,
    AvailabilityWindowCreate,
    AvailabilityWindowUpdate,
    DoctorLeaveCreate,
    DoctorSlotsResponse,
)

router = APIRouter(prefix="/api/v1/availability", tags=["availability"])

# Appointment statuses that occupy a slot (mirrors routers/appointments.py)
BLOCKING_STATUSES = ["scheduled", "arrived", "in-progress"]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _serialize_window(
    window: DoctorAvailability,
    doctor_name: str | None = None,
) -> dict:
    return {
        "id": str(window.id),
        "doctor_id": str(window.doctor_id),
        "doctor_name": doctor_name,
        "clinic_id": str(window.clinic_id) if window.clinic_id else None,
        "branch_id": str(window.branch_id) if window.branch_id else None,
        "weekday": window.weekday,
        "start_time": window.start_time.isoformat(timespec="minutes"),
        "end_time": window.end_time.isoformat(timespec="minutes"),
        "slot_duration_minutes": window.slot_duration_minutes,
        "is_active": window.is_active,
        "created_at": window.created_at.isoformat(),
        "updated_at": window.updated_at.isoformat(),
    }


def _serialize_leave(leave: DoctorLeave) -> dict:
    return {
        "id": str(leave.id),
        "doctor_id": str(leave.doctor_id),
        "date": leave.date.isoformat(),
        "reason": leave.reason,
        "created_at": leave.created_at.isoformat(),
        "updated_at": leave.updated_at.isoformat(),
    }


def _validate_time_range(start_time: time, end_time: time) -> None:
    if start_time >= end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_TIME_RANGE",
                    "message": "start_time must be before end_time",
                }
            },
        )


async def _validate_clinic_and_branch(
    db: AsyncSession,
    user: User,
    clinic_id: UUID | None,
    branch_id: UUID | None,
) -> UUID | None:
    """Same tenant rule as routers/appointments.py: a supplied branch must
    exist and belong to the clinic (which is derived from the branch when
    clinic_id is omitted), and the caller must hold an active membership for
    the effective clinic."""
    effective_clinic_id = clinic_id

    if branch_id is not None:
        branch_res = await db.execute(
            select(ClinicBranch).where(
                ClinicBranch.id == branch_id,
                ClinicBranch.deleted_at.is_(None),
            )
        )
        branch = branch_res.scalar_one_or_none()
        if branch is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "NOT_FOUND", "message": "Branch not found"}},
            )
        if effective_clinic_id is None:
            effective_clinic_id = branch.clinic_id
        elif branch.clinic_id != effective_clinic_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "INVALID_BRANCH",
                        "message": "branch_id does not belong to the specified clinic",
                    }
                },
            )

    if effective_clinic_id is not None:
        membership_res = await db.execute(
            select(ClinicMembership.id).where(
                ClinicMembership.clinic_id == effective_clinic_id,
                ClinicMembership.user_id == user.id,
                ClinicMembership.is_active.is_(True),
                ClinicMembership.deleted_at.is_(None),
            )
        )
        if membership_res.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "NOT_CLINIC_MEMBER", "message": "Not a member of this clinic"}},
            )

    return effective_clinic_id


async def _get_own_window(
    db: AsyncSession,
    window_id: UUID,
    doctor_id: UUID,
) -> DoctorAvailability:
    res = await db.execute(
        select(DoctorAvailability).where(
            DoctorAvailability.id == window_id,
            DoctorAvailability.doctor_id == doctor_id,
            DoctorAvailability.deleted_at.is_(None),
        )
    )
    window = res.scalar_one_or_none()
    if window is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Availability window not found"}},
        )
    return window


# ─── Doctor: own availability windows ─────────────────────────────────────────

@router.get("/me")
async def list_my_availability(
    ctx: tuple = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    """List the authenticated doctor's availability windows, ordered by weekday/start."""
    _user, doctor = ctx
    res = await db.execute(
        select(DoctorAvailability)
        .where(
            DoctorAvailability.doctor_id == doctor.id,
            DoctorAvailability.deleted_at.is_(None),
        )
        .order_by(DoctorAvailability.weekday.asc(), DoctorAvailability.start_time.asc())
    )
    windows = res.scalars().all()
    return {"data": [_serialize_window(w) for w in windows]}


@router.post("/me", status_code=status.HTTP_201_CREATED)
async def create_my_availability(
    req: AvailabilityWindowCreate,
    ctx: tuple = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    """Create a recurring weekly availability window for the authenticated doctor."""
    user, doctor = ctx
    _validate_time_range(req.start_time, req.end_time)
    effective_clinic_id = await _validate_clinic_and_branch(db, user, req.clinic_id, req.branch_id)

    window = DoctorAvailability(
        id=uuid.uuid4(),
        doctor_id=doctor.id,
        clinic_id=effective_clinic_id,
        branch_id=req.branch_id,
        weekday=req.weekday,
        start_time=req.start_time,
        end_time=req.end_time,
        slot_duration_minutes=req.slot_duration_minutes,
        is_active=req.is_active,
    )
    db.add(window)
    await db.flush()
    await db.refresh(window)
    return _serialize_window(window)


@router.put("/me/{window_id}")
async def update_my_availability(
    window_id: UUID,
    req: AvailabilityWindowUpdate,
    ctx: tuple = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    """Update one of the authenticated doctor's availability windows."""
    user, doctor = ctx
    window = await _get_own_window(db, window_id, doctor.id)

    new_start = req.start_time if req.start_time is not None else window.start_time
    new_end = req.end_time if req.end_time is not None else window.end_time
    _validate_time_range(new_start, new_end)

    new_branch_id = req.branch_id if req.branch_id is not None else window.branch_id
    if req.clinic_id is not None or req.branch_id is not None:
        # Validate the merged (clinic, branch) pair — a clinic change must not
        # keep a branch from the old clinic.
        new_clinic_id = await _validate_clinic_and_branch(db, user, req.clinic_id, new_branch_id)
    else:
        new_clinic_id = window.clinic_id

    if req.weekday is not None:
        window.weekday = req.weekday
    window.start_time = new_start
    window.end_time = new_end
    if req.slot_duration_minutes is not None:
        window.slot_duration_minutes = req.slot_duration_minutes
    window.clinic_id = new_clinic_id
    window.branch_id = new_branch_id
    if req.is_active is not None:
        window.is_active = req.is_active

    await db.flush()
    await db.refresh(window)
    return _serialize_window(window)


@router.delete("/me/{window_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_availability(
    window_id: UUID,
    ctx: tuple = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete one of the authenticated doctor's availability windows."""
    _user, doctor = ctx
    window = await _get_own_window(db, window_id, doctor.id)
    window.deleted_at = datetime.now(tz=timezone.utc)
    await db.flush()
    return None


# ─── Doctor: own leaves ───────────────────────────────────────────────────────

@router.get("/me/leaves")
async def list_my_leaves(
    ctx: tuple = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    """List the authenticated doctor's leave days, upcoming first."""
    _user, doctor = ctx
    res = await db.execute(
        select(DoctorLeave)
        .where(DoctorLeave.doctor_id == doctor.id, DoctorLeave.deleted_at.is_(None))
        .order_by(DoctorLeave.date.asc())
    )
    leaves = res.scalars().all()
    return {"data": [_serialize_leave(l) for l in leaves]}


@router.post("/me/leaves", status_code=status.HTTP_201_CREATED)
async def create_my_leave(
    req: DoctorLeaveCreate,
    ctx: tuple = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    """Block a full day for the authenticated doctor (no bookable slots)."""
    _user, doctor = ctx
    dup_res = await db.execute(
        select(DoctorLeave.id).where(
            DoctorLeave.doctor_id == doctor.id,
            DoctorLeave.date == req.date,
            DoctorLeave.deleted_at.is_(None),
        )
    )
    if dup_res.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "DUPLICATE_LEAVE", "message": "Leave already exists for this date"}},
        )

    leave = DoctorLeave(
        id=uuid.uuid4(),
        doctor_id=doctor.id,
        date=req.date,
        reason=req.reason,
    )
    db.add(leave)
    try:
        await db.flush()
    except IntegrityError:
        # uq_doctor_leaves_doctor_date caught a race between the check and insert
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "DUPLICATE_LEAVE", "message": "Leave already exists for this date"}},
        )
    await db.refresh(leave)
    return _serialize_leave(leave)


@router.delete("/me/leaves/{leave_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_leave(
    leave_id: UUID,
    ctx: tuple = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete one of the authenticated doctor's leave days."""
    _user, doctor = ctx
    res = await db.execute(
        select(DoctorLeave).where(
            DoctorLeave.id == leave_id,
            DoctorLeave.doctor_id == doctor.id,
            DoctorLeave.deleted_at.is_(None),
        )
    )
    leave = res.scalar_one_or_none()
    if leave is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Leave not found"}},
        )
    leave.deleted_at = datetime.now(tz=timezone.utc)
    await db.flush()
    return None


# ─── Clinic: member doctors' availability ─────────────────────────────────────

@router.get("/clinic")
async def list_clinic_availability(
    clinic_ctx: tuple = Depends(require_active_clinic),
    db: AsyncSession = Depends(get_db),
):
    """List availability windows for all doctor members of the active clinic
    (requires X-Clinic-Id header)."""
    clinic_id, _role = clinic_ctx
    res = await db.execute(
        select(DoctorAvailability, User.full_name)
        .join(Doctor, Doctor.id == DoctorAvailability.doctor_id)
        .join(User, User.id == Doctor.user_id)
        .join(
            ClinicMembership,
            (ClinicMembership.user_id == Doctor.user_id)
            & (ClinicMembership.clinic_id == clinic_id)
            & (ClinicMembership.is_active.is_(True))
            & (ClinicMembership.deleted_at.is_(None)),
        )
        .where(DoctorAvailability.deleted_at.is_(None))
        .order_by(DoctorAvailability.weekday.asc(), DoctorAvailability.start_time.asc())
    )
    data = [
        _serialize_window(window, doctor_name=full_name)
        for window, full_name in res.all()
    ]
    return {"data": data}


# ─── Slot computation ─────────────────────────────────────────────────────────

@router.get("/doctors/{doctor_id}/slots")
async def get_doctor_slots(
    doctor_id: UUID,
    date_param: str = Query(..., alias="date"),
    clinic_id: UUID | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compute bookable slots for a doctor on a date.

    slots = active availability windows for that weekday
          − days on leave
          − existing non-cancelled appointments (scheduled/arrived/in-progress)

    Readable by any authenticated user (patients booking, clinic members
    scheduling).

    Window times are naive clinic-local wall-clock times (see
    models/doctor_availability.py); each window is interpreted in its
    clinic's `timezone` (default Asia/Kolkata) and converted to UTC for
    overlap checks against timestamptz Appointment.scheduled_at.
    """
    try:
        target_date = date.fromisoformat(date_param)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_DATE", "message": "date must be YYYY-MM-DD"}},
        )

    doctor_res = await db.execute(
        select(Doctor).where(Doctor.id == doctor_id, Doctor.deleted_at.is_(None))
    )
    if doctor_res.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Doctor not found"}},
        )

    empty = DoctorSlotsResponse(doctor_id=doctor_id, date=target_date, slots=[])

    # Leave blocks the whole day
    leave_res = await db.execute(
        select(DoctorLeave.id).where(
            DoctorLeave.doctor_id == doctor_id,
            DoctorLeave.date == target_date,
            DoctorLeave.deleted_at.is_(None),
        )
    )
    if leave_res.scalar_one_or_none() is not None:
        return empty

    weekday = target_date.weekday()  # 0=Monday .. 6=Sunday
    win_stmt = select(DoctorAvailability).where(
        DoctorAvailability.doctor_id == doctor_id,
        DoctorAvailability.weekday == weekday,
        DoctorAvailability.is_active.is_(True),
        DoctorAvailability.deleted_at.is_(None),
    )
    if clinic_id is not None:
        win_stmt = win_stmt.where(DoctorAvailability.clinic_id == clinic_id)
    windows = (await db.execute(win_stmt)).scalars().all()
    if not windows:
        return empty

    # Resolve each window's clinic timezone — naive window wall-times are
    # interpreted in the clinic's zone, not UTC.
    clinic_tz: dict[UUID | None, ZoneInfo] = {}
    clinic_ids = {w.clinic_id for w in windows if w.clinic_id is not None}
    if clinic_ids:
        clinic_res = await db.execute(
            select(Clinic.id, Clinic.timezone).where(Clinic.id.in_(clinic_ids))
        )
        for cid, tzname in clinic_res.all():
            try:
                clinic_tz[cid] = ZoneInfo(tzname or "Asia/Kolkata")
            except Exception:
                clinic_tz[cid] = ZoneInfo("Asia/Kolkata")
    default_tz = ZoneInfo("Asia/Kolkata")

    def _tz_for(window) -> ZoneInfo:
        return clinic_tz.get(window.clinic_id, default_tz)

    # Appointments occupying time that day. Day bounds are clinic-local —
    # cover the union of local midnights across involved zones.
    local_starts = [
        datetime.combine(target_date, time(0, 0), tzinfo=_tz_for(w)) for w in windows
    ]
    day_start = min(local_starts).astimezone(timezone.utc)
    day_end = max(local_starts).astimezone(timezone.utc) + timedelta(days=1)
    # Half-open interval overlap — also catches appointments that started the
    # previous day but still occupy time today (e.g. 23:30 + 60min).
    appt_end = Appointment.scheduled_at + cast(
        func.concat(Appointment.duration_minutes, " minutes"), INTERVAL
    )
    appt_res = await db.execute(
        select(Appointment.scheduled_at, Appointment.duration_minutes).where(
            Appointment.doctor_id == doctor_id,
            Appointment.deleted_at.is_(None),
            Appointment.status.in_(BLOCKING_STATUSES),
            Appointment.scheduled_at < day_end,
            appt_end > day_start,
        )
    )
    booked = [
        (row.scheduled_at, row.scheduled_at + timedelta(minutes=row.duration_minutes))
        for row in appt_res.all()
    ]

    now = datetime.now(tz=timezone.utc)
    slots: list[AvailabilitySlot] = []
    seen: set[tuple[datetime, datetime]] = set()
    for window in windows:
        duration = timedelta(minutes=window.slot_duration_minutes)
        wtz = _tz_for(window)
        cursor = datetime.combine(target_date, window.start_time, tzinfo=wtz)
        window_end = datetime.combine(target_date, window.end_time, tzinfo=wtz)
        while cursor + duration <= window_end:
            slot_end = cursor + duration
            overlaps = any(cursor < b_end and slot_end > b_start for b_start, b_end in booked)
            # Exclude slots that can no longer be booked (same 5-min skew as _ensure_not_in_past)
            bookable = cursor >= now - timedelta(minutes=5)
            if not overlaps and bookable and (cursor, slot_end) not in seen:
                seen.add((cursor, slot_end))
                slots.append(
                    AvailabilitySlot(
                        start=cursor,
                        end=slot_end,
                        start_time=time(cursor.hour, cursor.minute),
                        end_time=time(slot_end.hour, slot_end.minute),
                        clinic_id=window.clinic_id,
                        branch_id=window.branch_id,
                    )
                )
            cursor += duration

    slots.sort(key=lambda s: s.start)
    return DoctorSlotsResponse(doctor_id=doctor_id, date=target_date, slots=slots)
