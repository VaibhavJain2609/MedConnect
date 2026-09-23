"""Medication adherence reminders — 15-minute ARQ cron task.

Patients opt in per prescription via ``/api/v1/medication-reminders``; this
task sweeps enabled ``medication_reminders`` rows and drops an in-app
notification ("Time to take your medication") for every ``times_of_day``
entry that falls inside the current 15-minute slot.

Timezone
--------
``times_of_day`` is interpreted in Asia/Kolkata — the same default the
appointment-reminder task uses (``CLINIC_TZ`` there). ``User`` has no
timezone column and reminders are user- rather than clinic-scoped, so the
platform default applies consistently.

Dedupe / idempotency
--------------------
Follows the Notification.meta dedupe pattern used by ``prescription_expiry``
and the queue-notification emitters: every notification this task creates
carries
``{"kind": "med_reminder", "reminder_id", "prescription_id", "date",
"timeslot"}`` and the task checks for an existing row per
(reminder, day, timeslot) before creating one. Soft-deleted rows still
count — dismissing the banner must not trigger a resend of the same slot.

PHI note: never log names, bodies, or other PHI — identifiers only.
"""
import uuid
from datetime import date, datetime
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.medication_reminder import MedicationReminder
from app.models.notification import Notification, NotificationType
from app.models.prescription import Prescription
from app.services import notification_service

logger = structlog.get_logger()

# Same platform default as CLINIC_TZ in appointment_reminders.py — the
# User model exposes no timezone of its own.
PATIENT_TZ = ZoneInfo("Asia/Kolkata")

# Matches the cron registration (minute={0,15,30,45}) — a "HH:MM" entry
# fires if it falls inside the current 15-minute slot.
SLOT_MINUTES = 15

# Safety cap — one run never processes more than this many reminders.
MAX_PER_RUN = 1000

# Notification.meta["kind"] value marking rows created by this task.
META_KIND = "med_reminder"


def _slot_bounds(now_local: datetime) -> tuple[int, int]:
    """Return [start, end) minutes-of-day for the slot containing ``now_local``."""
    start = (now_local.hour * 60 + now_local.minute) // SLOT_MINUTES * SLOT_MINUTES
    return start, start + SLOT_MINUTES


def _matching_times(times_of_day: list, slot_start: int, slot_end: int) -> list[str]:
    """times_of_day entries ("HH:MM") inside the current slot window."""
    matched = []
    for t in times_of_day or []:
        try:
            hour, minute = int(t[:2]), int(t[3:5])
        except (TypeError, ValueError, IndexError):
            logger.warning("med_reminder_bad_time", time_value=str(t))
            continue
        if slot_start <= hour * 60 + minute < slot_end:
            matched.append(t)
    return matched


async def send_medication_reminders(ctx: dict, *, now: datetime | None = None) -> None:
    """
    ARQ cron task: notify patients whose enabled reminder schedule lands in
    the current 15-minute slot.

    Args:
        ctx: ARQ worker context dict; must contain 'db_session_factory'.
        now: Optional override for "current time" (testing). Naive values are
             interpreted as PATIENT_TZ local time; aware values are converted.
    """
    session_factory = ctx["db_session_factory"]

    if now is None:
        now_local = datetime.now(tz=PATIENT_TZ)
    elif now.tzinfo is None:
        now_local = now.replace(tzinfo=PATIENT_TZ)
    else:
        now_local = now.astimezone(PATIENT_TZ)

    today = now_local.date()
    slot_start, slot_end = _slot_bounds(now_local)

    processed = 0
    sent = 0
    failed = 0
    async with session_factory() as db:
        # Ids only — same reason as check_prescription_expiry: rollback()
        # expires ORM state, so rows are re-loaded inside the per-item try.
        res = await db.execute(
            select(MedicationReminder.id)
            .join(
                Prescription,
                Prescription.id == MedicationReminder.prescription_id,
            )
            .where(
                MedicationReminder.enabled.is_(True),
                MedicationReminder.deleted_at.is_(None),
                Prescription.deleted_at.is_(None),
                # Only "active" prescriptions remind — an expired course
                # (valid_until in the past) stops firing automatically.
                (Prescription.valid_until.is_(None))
                | (Prescription.valid_until >= today),
            )
            .order_by(MedicationReminder.created_at)
            .limit(MAX_PER_RUN)
        )
        reminder_ids = res.scalars().all()

        for rid in reminder_ids:
            try:
                reminder = await db.get(MedicationReminder, rid)
                if reminder is None:
                    continue
                sent += await _process_reminder(
                    db, reminder, today, slot_start, slot_end
                )
                processed += 1
            except Exception as exc:
                # One bad row must not kill the run — roll back its partial
                # work and continue with the next reminder.
                await db.rollback()
                failed += 1
                logger.error(
                    "med_reminder_item_failed",
                    reminder_id=str(rid),
                    error=str(exc),
                    exc_info=True,
                )

    # Ids/counts only — no PHI in logs.
    logger.info(
        "med_reminder_run_complete",
        scanned=len(reminder_ids),
        processed=processed,
        sent=sent,
        failed=failed,
        date=today.isoformat(),
        slot_start=slot_start,
    )


async def _process_reminder(
    db: AsyncSession,
    reminder: MedicationReminder,
    today: date,
    slot_start: int,
    slot_end: int,
) -> int:
    """Emit one deduped in-app notification per matching timeslot; commit."""
    matched = _matching_times(reminder.times_of_day, slot_start, slot_end)
    if not matched:
        return 0

    created = 0
    for timeslot in matched:
        meta = {
            "kind": META_KIND,
            "reminder_id": str(reminder.id),
            "prescription_id": str(reminder.prescription_id),
            "date": today.isoformat(),
            "timeslot": timeslot,
        }
        if await _already_notified(db, reminder, today, timeslot):
            logger.info(
                "med_reminder_skipped_already_sent",
                reminder_id=str(reminder.id),
                timeslot=timeslot,
            )
            continue

        await notification_service.create_notification(
            db,
            user_id=reminder.user_id,
            notif_type=NotificationType.PRESCRIPTION.value,
            title="Time to take your medication",
            body=f"Your scheduled {timeslot} dose is due — check your medications.",
            action_url="/patient/medications",
            metadata=meta,
        )
        created += 1

    await db.commit()

    if created:
        logger.info(
            "med_reminder_dispatched",
            reminder_id=str(reminder.id),
            prescription_id=str(reminder.prescription_id),
            user_id=str(reminder.user_id),
            timeslots=matched,
        )
    return created


async def _already_notified(
    db: AsyncSession,
    reminder: MedicationReminder,
    today: date,
    timeslot: str,
) -> bool:
    """
    True if this task already created a notification for
    (reminder, day, timeslot). Matches on the ``meta`` JSONB markers —
    soft-deleted rows still count so a dismissed banner is not resent.
    """
    res = await db.execute(
        select(Notification.id)
        .where(
            Notification.user_id == reminder.user_id,
            Notification.meta["kind"].astext == META_KIND,
            Notification.meta["reminder_id"].astext == str(reminder.id),
            Notification.meta["date"].astext == today.isoformat(),
            Notification.meta["timeslot"].astext == timeslot,
        )
        .limit(1)
    )
    return res.scalar_one_or_none() is not None
