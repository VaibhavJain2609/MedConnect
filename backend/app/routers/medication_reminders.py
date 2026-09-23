"""Patient opt-in medication adherence reminders.

- POST   /api/v1/medication-reminders        — create or replace the reminder
                                               schedule on one of the
                                               patient's own prescriptions
                                               (idempotent upsert).
- GET    /api/v1/medication-reminders        — list the patient's reminders
                                               (optional ?prescription_id=).
- PATCH  /api/v1/medication-reminders/{id}   — change times and/or pause.
- DELETE /api/v1/medication-reminders/{id}   — soft-delete (turn off for good).

All endpoints are patient-scoped: a reminder can only be read/ mutated by its
owner, and the target prescription must belong to the calling patient. The
actual notifications are emitted by the ``send_medication_reminders`` ARQ
cron task (workers/tasks/medication_reminders.py), deduped per
(reminder, day, timeslot) via Notification.meta.
"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_patient
from app.models.medication_reminder import MedicationReminder
from app.models.prescription import Prescription
from app.models.user import User
from app.schemas.medication_reminder import (
    MedicationReminderCreate,
    MedicationReminderUpdate,
)

router = APIRouter(prefix="/api/v1/medication-reminders", tags=["medication-reminders"])


def _err(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message}},
    )


def _serialize(r: MedicationReminder) -> dict:
    return {
        "id": str(r.id),
        "user_id": str(r.user_id),
        "prescription_id": str(r.prescription_id),
        "times_of_day": r.times_of_day or [],
        "enabled": r.enabled,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


async def _get_owned_reminder(
    db: AsyncSession, reminder_id: UUID, user: User
) -> MedicationReminder:
    """Fetch a live reminder owned by ``user`` or raise 404.

    Not-owned rows return 404 (not 403) so the endpoint doesn't confirm the
    existence of other patients' reminder ids.
    """
    res = await db.execute(
        select(MedicationReminder).where(
            MedicationReminder.id == reminder_id,
            MedicationReminder.user_id == user.id,
            MedicationReminder.deleted_at.is_(None),
        )
    )
    reminder = res.scalar_one_or_none()
    if reminder is None:
        raise _err(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Reminder not found")
    return reminder


@router.post("", status_code=status.HTTP_201_CREATED)
async def upsert_reminder(
    req: MedicationReminderCreate,
    response: Response,
    user: User = Depends(require_patient),
    db: AsyncSession = Depends(get_db),
):
    """Create a reminder for a prescription — or update the existing one.

    One live reminder per (patient, prescription); a repeated POST replaces
    the schedule and returns 200 instead of 201 so the "Remind me" toggle
    stays idempotent.
    """
    rx_res = await db.execute(
        select(Prescription).where(
            Prescription.id == req.prescription_id,
            Prescription.deleted_at.is_(None),
        )
    )
    rx = rx_res.scalar_one_or_none()
    if rx is None:
        raise _err(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Prescription not found")
    if rx.patient_id != user.id:
        raise _err(status.HTTP_403_FORBIDDEN, "FORBIDDEN", "Not your prescription")

    existing_res = await db.execute(
        select(MedicationReminder).where(
            MedicationReminder.user_id == user.id,
            MedicationReminder.prescription_id == rx.id,
            MedicationReminder.deleted_at.is_(None),
        )
    )
    reminder = existing_res.scalar_one_or_none()

    if reminder is not None:
        reminder.times_of_day = req.times_of_day
        reminder.enabled = req.enabled
        response.status_code = status.HTTP_200_OK
    else:
        reminder = MedicationReminder(
            user_id=user.id,
            prescription_id=rx.id,
            times_of_day=req.times_of_day,
            enabled=req.enabled,
        )
        db.add(reminder)

    try:
        await db.flush()
        await db.refresh(reminder)
    except IntegrityError:
        # Lost a race against the partial unique index — a live reminder for
        # this (user, prescription) was created concurrently.
        await db.rollback()
        raise _err(
            status.HTTP_409_CONFLICT,
            "REMINDER_ALREADY_EXISTS",
            "A reminder for this prescription already exists",
        )

    return _serialize(reminder)


@router.get("")
async def list_reminders(
    prescription_id: UUID | None = Query(None),
    user: User = Depends(require_patient),
    db: AsyncSession = Depends(get_db),
):
    """List the patient's own reminders (newest first, capped)."""
    stmt = (
        select(MedicationReminder)
        .where(
            MedicationReminder.user_id == user.id,
            MedicationReminder.deleted_at.is_(None),
        )
        .order_by(MedicationReminder.created_at.desc())
        .limit(200)
    )
    if prescription_id is not None:
        stmt = stmt.where(MedicationReminder.prescription_id == prescription_id)

    res = await db.execute(stmt)
    return {"data": [_serialize(r) for r in res.scalars().all()]}


@router.patch("/{reminder_id}")
async def update_reminder(
    reminder_id: UUID,
    req: MedicationReminderUpdate,
    user: User = Depends(require_patient),
    db: AsyncSession = Depends(get_db),
):
    """Update the schedule and/or enabled flag of the patient's own reminder."""
    reminder = await _get_owned_reminder(db, reminder_id, user)

    if req.times_of_day is not None:
        reminder.times_of_day = req.times_of_day
    if req.enabled is not None:
        reminder.enabled = req.enabled

    await db.flush()
    await db.refresh(reminder)
    return _serialize(reminder)


@router.delete("/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reminder(
    reminder_id: UUID,
    user: User = Depends(require_patient),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete the reminder — the worker stops dispatching immediately."""
    reminder = await _get_owned_reminder(db, reminder_id, user)
    reminder.deleted_at = datetime.now(timezone.utc)
    reminder.enabled = False
    await db.flush()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
