"""
Appointment reminder tasks executed by the ARQ worker.

Writes a ReminderLog row and creates an in-app Notification for the
patient (and the doctor) so reminders are actually visible in the app.
WhatsApp / SMS delivery can be wired in later by updating the
`_dispatch` function and setting `channel` accordingly.
"""
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.notification import NotificationType
from app.models.reminder_log import ReminderLog
from app.models.user import User
from app.services import notification_service

logger = structlog.get_logger()

# TODO: render times in the clinic's own timezone once the Clinic model
# exposes one; until then all reminder times use Asia/Kolkata (IST).
CLINIC_TZ = ZoneInfo("Asia/Kolkata")


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
    """Fetch appointment details, build message, persist ReminderLog + notifications."""
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

    # Skip if this reminder was already sent (e.g. retried/duplicated job)
    already_sent_res = await db.execute(
        select(ReminderLog.id).where(
            ReminderLog.appointment_id == appt.id,
            ReminderLog.reminder_type == reminder_type,
            ReminderLog.status == "sent",
        )
    )
    if already_sent_res.scalar_one_or_none() is not None:
        logger.info(
            "reminder_skipped_already_sent",
            appointment_id=appointment_id,
            reminder_type=reminder_type,
        )
        return

    # Fetch patient
    patient_res = await db.execute(
        select(User.full_name).where(User.id == appt.patient_id)
    )
    patient_name: str = patient_res.scalar_one_or_none() or "Patient"

    # Fetch doctor user id + name via User → Doctor join
    doctor_res = await db.execute(
        select(User.id, User.full_name)
        .join(Doctor, Doctor.user_id == User.id)
        .where(Doctor.id == appt.doctor_id)
    )
    doctor_row = doctor_res.one_or_none()
    doctor_user_id = doctor_row[0] if doctor_row else None
    doctor_name: str = doctor_row[1] if doctor_row else "Doctor"

    # scheduled_at is stored in UTC — render in the clinic timezone
    scheduled_utc = appt.scheduled_at
    if scheduled_utc.tzinfo is None:
        scheduled_utc = scheduled_utc.replace(tzinfo=timezone.utc)
    scheduled_local = scheduled_utc.astimezone(CLINIC_TZ).strftime("%d %b %Y at %I:%M %p %Z")

    message = (
        f"Reminder: {patient_name}, your appointment with {doctor_name} "
        f"is in {hours_before} hour(s) — {scheduled_local}."
    )

    notif_meta = {
        "appointment_id": str(appt.id),
        "reminder_type": reminder_type,
    }

    # In-app notification for the patient
    await notification_service.create_notification(
        db,
        user_id=appt.patient_id,
        notif_type=NotificationType.APPOINTMENT.value,
        title=f"Appointment in {hours_before} hour(s)",
        body=message,
        action_url="/patient/appointments",
        metadata=notif_meta,
    )

    # In-app notification for the doctor (if resolvable)
    if doctor_user_id is not None:
        await notification_service.create_notification(
            db,
            user_id=doctor_user_id,
            notif_type=NotificationType.APPOINTMENT.value,
            title=f"Appointment in {hours_before} hour(s)",
            body=(
                f"Reminder: your appointment with {patient_name} "
                f"is in {hours_before} hour(s) — {scheduled_local}."
            ),
            action_url="/doctor/appointments",
            metadata=notif_meta,
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

    # NOTE: do not log patient/doctor names or message bodies — PHI must not
    # reach INFO logs. Identifiers only.
    logger.info(
        "reminder_logged",
        appointment_id=appointment_id,
        reminder_type=reminder_type,
    )
