"""
Appointment reminder tasks executed by the ARQ worker.

Currently logs reminders to the database only.
WhatsApp / SMS delivery can be wired in later by updating the
`_dispatch` function and setting `channel` accordingly.
"""
import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.reminder_log import ReminderLog
from app.models.user import User

logger = structlog.get_logger()


async def send_appointment_reminder(ctx: dict, appointment_id: str, hours_before: int) -> None:
    """
    ARQ task: send (or log) a reminder for a single appointment.

    Args:
        ctx: ARQ worker context dict; must contain 'db_session_factory'.
        appointment_id: UUID string of the appointment.
        hours_before: 24 or 2 — used to populate reminder_type and log message.
    """
    session_factory = ctx["db_session_factory"]

    reminder_type = "24h" if hours_before == 24 else "2h"

    async with session_factory() as db:
        try:
            await _process_reminder(db, appointment_id, hours_before, reminder_type)
        except Exception as exc:
            logger.error(
                "reminder_task_failed",
                appointment_id=appointment_id,
                hours_before=hours_before,
                error=str(exc),
                exc_info=True,
            )
            raise


async def _process_reminder(
    db: AsyncSession,
    appointment_id: str,
    hours_before: int,
    reminder_type: str,
) -> None:
    """Fetch appointment details, build message, and persist the ReminderLog row."""
    appt_res = await db.execute(
        select(Appointment).where(
            Appointment.id == uuid.UUID(appointment_id),
            Appointment.deleted_at.is_(None),
        )
    )
    appt = appt_res.scalar_one_or_none()

    if appt is None:
        logger.warning(
            "reminder_skipped_appointment_not_found",
            appointment_id=appointment_id,
        )
        return

    # Skip reminders for cancelled / completed / no-show appointments
    if appt.status in {"cancelled", "completed", "no-show"}:
        logger.info(
            "reminder_skipped_terminal_status",
            appointment_id=appointment_id,
            status=appt.status,
        )
        return

    # Fetch patient
    patient_res = await db.execute(
        select(User.full_name, User.phone).where(User.id == appt.patient_id)
    )
    patient_row = patient_res.one_or_none()
    patient_name: str = patient_row.full_name if patient_row else "Patient"

    # Fetch doctor name via User → Doctor join
    doctor_res = await db.execute(
        select(User.full_name)
        .join(Doctor, Doctor.user_id == User.id)
        .where(Doctor.id == appt.doctor_id)
    )
    doctor_name: str = doctor_res.scalar_one_or_none() or "Doctor"

    scheduled_local = appt.scheduled_at.strftime("%d %b %Y at %I:%M %p")
    message = (
        f"Reminder: {patient_name}, your appointment with {doctor_name} "
        f"is in {hours_before} hour(s) — {scheduled_local}."
    )

    log_entry = ReminderLog(
        id=uuid.uuid4(),
        appointment_id=appt.id,
        reminder_type=reminder_type,
        channel="log",
        status="sent",
        message=message,
        sent_at=datetime.now(tz=timezone.utc),
    )
    db.add(log_entry)
    await db.commit()

    logger.info(
        "reminder_logged",
        appointment_id=appointment_id,
        reminder_type=reminder_type,
        patient=patient_name,
        doctor=doctor_name,
        message=message,
    )
