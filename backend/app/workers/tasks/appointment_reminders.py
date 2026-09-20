"""
Appointment reminder tasks executed by the ARQ worker.

Dispatches the reminder over every notification channel enabled in the
patient's NotificationPreferences (in_app, email, sms, whatsapp) via
app.services.notification_channels, then writes one ReminderLog row per
attempted channel with the real channel value and a sent/failed/skipped
status. The doctor always gets an in-app notification.
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
from app.services import notification_channels, notification_service

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

    # Fetch patient — the full row is needed for channel dispatch (email/phone)
    patient_res = await db.execute(
        select(User).where(User.id == appt.patient_id)
    )
    patient = patient_res.scalar_one_or_none()
    patient_name: str = patient.full_name if patient else "Patient"

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
    doctor_message = (
        f"Reminder: your appointment with {patient_name} "
        f"is in {hours_before} hour(s) — {scheduled_local}."
    )
    if appt.type == "teleconsult" and appt.meeting_url:
        message += f" Join the video call: {appt.meeting_url}"
        doctor_message += f" Join the video call: {appt.meeting_url}"

    notif_meta = {
        "appointment_id": str(appt.id),
        "reminder_type": reminder_type,
    }
    if appt.meeting_url:
        notif_meta["meeting_url"] = appt.meeting_url

    title = f"Appointment in {hours_before} hour(s)"

    # --- Patient: dispatch over every enabled channel -------------------
    channel_results = []
    if patient is None:
        logger.warning(
            "reminder_patient_not_found",
            appointment_id=appointment_id,
            patient_id=str(appt.patient_id),
        )
    else:
        prefs = await notification_channels.get_preferences(patient.id, db=db)

        # Per-type opt-out — not a channel flag, so it gates the whole reminder
        if not prefs.get("appointment_reminders", True):
            logger.info(
                "reminder_skipped_user_opted_out",
                appointment_id=appointment_id,
                patient_id=str(patient.id),
            )
        else:
            channels = [
                c for c in notification_channels.CHANNELS
                if notification_channels.channel_enabled(c, prefs)
            ]
            channel_results = await notification_channels.send_all(
                patient,
                channels,
                title,
                message,
                db=db,
                notif_type=NotificationType.APPOINTMENT.value,
                action_url="/patient/appointments",
                metadata=notif_meta,
                prefs=prefs,
            )

    # In-app notification for the doctor (if resolvable) — doctors always get
    # the in-app copy; patient channel prefs do not apply to them.
    if doctor_user_id is not None:
        await notification_service.create_notification(
            db,
            user_id=doctor_user_id,
            notif_type=NotificationType.APPOINTMENT.value,
            title=title,
            body=doctor_message,
            action_url="/doctor/appointments",
            metadata=notif_meta,
        )

    # One ReminderLog row per attempted channel with the real channel value
    now = datetime.now(tz=timezone.utc)
    for result in channel_results:
        db.add(
            ReminderLog(
                id=uuid.uuid4(),
                appointment_id=appt.id,
                reminder_type=reminder_type,
                channel=result.channel,
                status=result.status,
                message=(
                    f"{result.reason}: {message}" if result.reason else message
                ),
                sent_at=now if result.status == "sent" else None,
            )
        )
    await db.commit()

    # NOTE: do not log patient/doctor names or message bodies — PHI must not
    # reach INFO logs. Identifiers only.
    logger.info(
        "reminder_dispatched",
        appointment_id=appointment_id,
        reminder_type=reminder_type,
        channels={r.channel: r.status for r in channel_results},
    )
