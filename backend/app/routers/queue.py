"""
Clinic queue endpoints.

Access: any active clinic member (owner | admin | doctor | receptionist) via
`require_active_clinic`. Receptionists handle front-desk queue operations —
patient check-in (add_to_queue) and status advancement — so no endpoint here
may assume the member is a doctor.
"""
import uuid
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_active_clinic, require_patient
from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.queue import QueueEntry
from app.models.user import User
from app.schemas.queue import QueueEntryCreate, QueueEntryResponse, QueueStatusUpdate

router = APIRouter(prefix="/api/v1/queue", tags=["queue"])

VALID_STATUSES = {"waiting", "in_consultation", "completed", "cancelled"}

# Statuses that still hold a place in line — completed/cancelled entries no
# longer count when computing a patient's position.
ACTIVE_STATUSES = {"waiting", "in_consultation"}

# Fallback per-patient consultation time used for wait estimates when the
# clinic has no completed consultations today to average.
DEFAULT_CONSULT_MINUTES = 15

# Status transition map: current_status -> allowed_next_statuses
STATUS_TRANSITIONS: dict[str, set[str]] = {
    "waiting": {"in_consultation", "cancelled"},
    "in_consultation": {"completed", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}


def _serialize_entry(
    entry: QueueEntry,
    patient_name: str | None = None,
    doctor_name: str | None = None,
) -> dict:
    return {
        "id": str(entry.id),
        "clinic_id": str(entry.clinic_id),
        "branch_id": str(entry.branch_id) if entry.branch_id else None,
        "patient_id": str(entry.patient_id),
        "patient_name": patient_name,
        "doctor_id": str(entry.doctor_id) if entry.doctor_id else None,
        "doctor_name": doctor_name,
        "appointment_id": str(entry.appointment_id) if entry.appointment_id else None,
        "queue_number": entry.queue_number,
        "status": entry.status,
        "notes": entry.notes,
        "called_at": entry.called_at.isoformat() if entry.called_at else None,
        "completed_at": entry.completed_at.isoformat() if entry.completed_at else None,
        "created_at": entry.created_at.isoformat(),
        "updated_at": entry.updated_at.isoformat(),
    }


async def _resolve_names(
    db: AsyncSession,
    entries: list[QueueEntry],
) -> tuple[dict[uuid.UUID, str], dict[uuid.UUID, str]]:
    """Batch-load patient and doctor names for a list of queue entries."""
    patient_ids = list({e.patient_id for e in entries})
    doctor_ids = list({e.doctor_id for e in entries if e.doctor_id})

    patient_names: dict[uuid.UUID, str] = {}
    if patient_ids:
        pr = await db.execute(
            select(User.id, User.full_name).where(User.id.in_(patient_ids))
        )
        patient_names = {row.id: row.full_name for row in pr.all()}

    doctor_names: dict[uuid.UUID, str] = {}
    if doctor_ids:
        dr = await db.execute(
            select(Doctor.id, User.full_name)
            .join(User, User.id == Doctor.user_id)
            .where(Doctor.id.in_(doctor_ids))
        )
        doctor_names = {row.id: row.full_name for row in dr.all()}

    return patient_names, doctor_names


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_to_queue(
    req: QueueEntryCreate,
    clinic_ctx: tuple = Depends(require_active_clinic),
    db: AsyncSession = Depends(get_db),
):
    """Add a patient to the clinic queue. Auto-assigns queue number for the day."""
    clinic_id, _clinic_role = clinic_ctx

    # Verify patient exists
    patient_res = await db.execute(
        select(User).where(User.id == req.patient_id, User.deleted_at.is_(None), User.is_active.is_(True))
    )
    if not patient_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Patient not found"}},
        )

    # Verify doctor exists if provided
    if req.doctor_id is not None:
        doctor_res = await db.execute(
            select(Doctor).where(Doctor.id == req.doctor_id, Doctor.deleted_at.is_(None))
        )
        if not doctor_res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "NOT_FOUND", "message": "Doctor not found"}},
            )

    # Auto-assign queue number: max for today at this clinic + 1
    today = datetime.now(tz=timezone.utc).date()
    day_start = datetime(today.year, today.month, today.day, 0, 0, 0, tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)  # half-open — matches queue_date

    max_num_res = await db.execute(
        select(func.max(QueueEntry.queue_number)).where(
            QueueEntry.clinic_id == clinic_id,
            QueueEntry.deleted_at.is_(None),
            QueueEntry.created_at >= day_start,
            QueueEntry.created_at < day_end,
        )
    )
    max_num = max_num_res.scalar_one_or_none() or 0
    next_number = max_num + 1

    entry = QueueEntry(
        id=uuid.uuid4(),
        clinic_id=clinic_id,
        patient_id=req.patient_id,
        doctor_id=req.doctor_id,
        appointment_id=req.appointment_id,
        queue_number=next_number,
        status="waiting",
        notes=req.notes,
    )
    db.add(entry)
    try:
        await db.flush()
    except IntegrityError:
        # uq_queue_entries_daily_number caught a same-second race — retry once
        await db.rollback()
        max_num_res = await db.execute(
            select(func.max(QueueEntry.queue_number)).where(
                QueueEntry.clinic_id == clinic_id,
                QueueEntry.deleted_at.is_(None),
                QueueEntry.created_at >= day_start,
                QueueEntry.created_at < day_end,
            )
        )
        entry.queue_number = (max_num_res.scalar_one_or_none() or 0) + 1
        db.add(entry)
        await db.flush()
    await db.refresh(entry)

    # Audit the check-in — ids/status only, no notes text.
    from app.services.audit_service import log_change
    await log_change(
        db=db,
        table_name="queue_entries",
        record_id=entry.id,
        action="INSERT",
        old_values=None,
        new_values={
            "clinic_id": str(entry.clinic_id),
            "patient_id": str(entry.patient_id),
            "doctor_id": str(entry.doctor_id) if entry.doctor_id else None,
            "appointment_id": str(entry.appointment_id) if entry.appointment_id else None,
            "queue_number": entry.queue_number,
            "status": entry.status,
        },
    )

    patient_names, doctor_names = await _resolve_names(db, [entry])
    return _serialize_entry(
        entry,
        patient_name=patient_names.get(entry.patient_id),
        doctor_name=doctor_names.get(entry.doctor_id) if entry.doctor_id else None,
    )


@router.get("")
async def get_queue(
    status_filter: str | None = Query(None, alias="status"),
    doctor_id: UUID | None = Query(None),
    clinic_ctx: tuple = Depends(require_active_clinic),
    db: AsyncSession = Depends(get_db),
):
    """Get today's queue for the clinic, ordered by queue_number."""
    clinic_id, _clinic_role = clinic_ctx

    today = datetime.now(tz=timezone.utc).date()
    day_start = datetime(today.year, today.month, today.day, 0, 0, 0, tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)

    stmt = select(QueueEntry).where(
        QueueEntry.clinic_id == clinic_id,
        QueueEntry.deleted_at.is_(None),
        QueueEntry.created_at >= day_start,
        QueueEntry.created_at < day_end,
    )

    if status_filter:
        if status_filter not in VALID_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "INVALID_STATUS",
                        "message": f"status must be one of: {', '.join(sorted(VALID_STATUSES))}",
                    }
                },
            )
        stmt = stmt.where(QueueEntry.status == status_filter)

    if doctor_id is not None:
        stmt = stmt.where(QueueEntry.doctor_id == doctor_id)

    stmt = stmt.order_by(QueueEntry.queue_number.asc())
    result = await db.execute(stmt)
    entries = result.scalars().all()

    patient_names, doctor_names = await _resolve_names(db, list(entries))

    data = [
        _serialize_entry(
            e,
            patient_name=patient_names.get(e.patient_id),
            doctor_name=doctor_names.get(e.doctor_id) if e.doctor_id else None,
        )
        for e in entries
    ]
    return {"data": data, "total": len(data)}


@router.get("/my-position")
async def get_my_queue_position(
    user: User = Depends(require_patient),
    db: AsyncSession = Depends(get_db),
):
    """
    Patient-facing: the caller's own queue entry for today, with live position.

    PHI-safe — returns only the authenticated patient's row; no other
    patients' data is exposed. When the patient has no queue entry today,
    returns a 200 with a null-position payload (the frontend treats this as
    "not checked in") rather than a 404.
    """
    today = datetime.now(tz=timezone.utc).date()
    day_start = datetime(today.year, today.month, today.day, 0, 0, 0, tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)

    # Latest live entry for this patient today (any clinic).
    result = await db.execute(
        select(QueueEntry)
        .where(
            QueueEntry.patient_id == user.id,
            QueueEntry.deleted_at.is_(None),
            QueueEntry.created_at >= day_start,
            QueueEntry.created_at < day_end,
        )
        .order_by(QueueEntry.created_at.desc())
        .limit(1)
    )
    entry = result.scalar_one_or_none()

    empty = {
        "queue_entry_id": None,
        "clinic_id": None,
        "clinic_name": None,
        "doctor_name": None,
        "queue_number": None,
        "position": None,
        "status": None,
        "ahead_count": 0,
        "estimated_wait_minutes": None,
    }
    if not entry:
        return empty

    clinic_res = await db.execute(
        select(Clinic.name).where(Clinic.id == entry.clinic_id)
    )
    clinic_name = clinic_res.scalar_one_or_none()

    doctor_name = None
    if entry.doctor_id:
        dr = await db.execute(
            select(User.full_name)
            .join(Doctor, Doctor.user_id == User.id)
            .where(Doctor.id == entry.doctor_id)
        )
        doctor_name = dr.scalar_one_or_none()

    ahead_count = 0
    position: int | None = None
    estimated_wait: int | None = None

    if entry.status in ACTIVE_STATUSES:
        # Entries still holding a place in line ahead of this one, same
        # clinic + day, ordered by queue_number.
        ahead_res = await db.execute(
            select(func.count(QueueEntry.id)).where(
                QueueEntry.clinic_id == entry.clinic_id,
                QueueEntry.deleted_at.is_(None),
                QueueEntry.created_at >= day_start,
                QueueEntry.created_at < day_end,
                QueueEntry.status.in_(ACTIVE_STATUSES),
                QueueEntry.queue_number < entry.queue_number,
            )
        )
        ahead_count = ahead_res.scalar_one()
        position = ahead_count + 1

        # Estimated wait = people ahead * average consultation length today
        # (completed entries with both called_at and completed_at), falling
        # back to a flat default when no data exists yet.
        avg_res = await db.execute(
            select(
                func.avg(
                    func.extract("epoch", QueueEntry.completed_at - QueueEntry.called_at) / 60
                )
            ).where(
                QueueEntry.clinic_id == entry.clinic_id,
                QueueEntry.deleted_at.is_(None),
                QueueEntry.created_at >= day_start,
                QueueEntry.created_at < day_end,
                QueueEntry.status == "completed",
                QueueEntry.called_at.isnot(None),
                QueueEntry.completed_at.isnot(None),
            )
        )
        avg_minutes = avg_res.scalar_one_or_none() or DEFAULT_CONSULT_MINUTES
        estimated_wait = int(round(ahead_count * float(avg_minutes)))

    return {
        "queue_entry_id": str(entry.id),
        "clinic_id": str(entry.clinic_id),
        "clinic_name": clinic_name,
        "doctor_name": doctor_name,
        "queue_number": entry.queue_number,
        "position": position,
        "status": entry.status,
        "ahead_count": ahead_count,
        "estimated_wait_minutes": estimated_wait,
    }


@router.get("/{entry_id}")
async def get_queue_entry(
    entry_id: UUID,
    clinic_ctx: tuple = Depends(require_active_clinic),
    db: AsyncSession = Depends(get_db),
):
    """Get a single queue entry by ID."""
    clinic_id, _clinic_role = clinic_ctx

    result = await db.execute(
        select(QueueEntry).where(
            QueueEntry.id == entry_id,
            QueueEntry.clinic_id == clinic_id,
            QueueEntry.deleted_at.is_(None),
        )
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Queue entry not found"}},
        )

    patient_names, doctor_names = await _resolve_names(db, [entry])
    return _serialize_entry(
        entry,
        patient_name=patient_names.get(entry.patient_id),
        doctor_name=doctor_names.get(entry.doctor_id) if entry.doctor_id else None,
    )


@router.patch("/{entry_id}/status")
async def update_queue_status(
    entry_id: UUID,
    req: QueueStatusUpdate,
    clinic_ctx: tuple = Depends(require_active_clinic),
    db: AsyncSession = Depends(get_db),
):
    """Update the status of a queue entry."""
    clinic_id, _clinic_role = clinic_ctx

    if req.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_STATUS",
                    "message": f"status must be one of: {', '.join(sorted(VALID_STATUSES))}",
                }
            },
        )

    result = await db.execute(
        select(QueueEntry).where(
            QueueEntry.id == entry_id,
            QueueEntry.clinic_id == clinic_id,
            QueueEntry.deleted_at.is_(None),
        )
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Queue entry not found"}},
        )

    allowed = STATUS_TRANSITIONS.get(entry.status, set())
    if req.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "INVALID_TRANSITION",
                    "message": f"Cannot transition from '{entry.status}' to '{req.status}'",
                }
            },
        )

    old_status = entry.status
    now = datetime.now(tz=timezone.utc)
    entry.status = req.status
    if req.status == "in_consultation":
        entry.called_at = now
    elif req.status == "completed":
        entry.completed_at = now

    await db.flush()
    await db.refresh(entry)

    # Audit the status transition (old -> new).
    from app.services.audit_service import log_change
    await log_change(
        db=db,
        table_name="queue_entries",
        record_id=entry.id,
        action="UPDATE",
        old_values={"status": old_status},
        new_values={"status": entry.status},
    )

    patient_names, doctor_names = await _resolve_names(db, [entry])
    return _serialize_entry(
        entry,
        patient_name=patient_names.get(entry.patient_id),
        doctor_name=doctor_names.get(entry.doctor_id) if entry.doctor_id else None,
    )


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_queue(
    entry_id: UUID,
    clinic_ctx: tuple = Depends(require_active_clinic),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a queue entry (remove from queue)."""
    clinic_id, _clinic_role = clinic_ctx

    result = await db.execute(
        select(QueueEntry).where(
            QueueEntry.id == entry_id,
            QueueEntry.clinic_id == clinic_id,
            QueueEntry.deleted_at.is_(None),
        )
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Queue entry not found"}},
        )

    entry.deleted_at = datetime.now(tz=timezone.utc)

    # Audit the removal — ids/status only.
    from app.services.audit_service import log_change
    await log_change(
        db=db,
        table_name="queue_entries",
        record_id=entry.id,
        action="DELETE",
        old_values={
            "clinic_id": str(entry.clinic_id),
            "patient_id": str(entry.patient_id),
            "status": entry.status,
        },
        new_values={"deleted": True},
    )

    await db.flush()
