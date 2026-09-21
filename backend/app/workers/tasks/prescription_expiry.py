"""
Prescription expiry notifications — daily ARQ cron task.

Finds prescriptions whose ``valid_until`` falls inside the notification
window (expiring within 3 days, or expired up to 30 days ago) and notifies:

- the PATIENT over every enabled channel (in_app baseline + email/sms/
  whatsapp/push per NotificationPreferences and the platform channel
  kill-switch);
- the prescribing DOCTOR in-app only.

Dedupe / idempotency
--------------------
``ReminderLog`` is NOT reused here: its ``appointment_id`` column is a
non-nullable FK to ``appointments.id``, so it cannot log prescription events.
Instead, idempotency is enforced via the ``meta`` JSONB column on the
notifications table — every notification this task creates carries
``{"kind": "rx_expiry", "prescription_id": ..., "stage": ...}`` and the task
checks for an existing row per (recipient, prescription, stage) before
sending. Two stages exist ("expiring" / "expired"), so a recipient gets at
most one expiring-soon and one expired notification per prescription. Soft-
deleted notifications still count — a user dismissing the banner must not
trigger a resend.

PHI note: never log names, bodies, or other PHI — identifiers only.
"""
import uuid
from datetime import date, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.doctor import Doctor
from app.models.notification import Notification, NotificationType
from app.models.prescription import Prescription
from app.models.user import User
from app.services import notification_channels, notification_service, platform_settings

logger = structlog.get_logger()

# Notify when valid_until is within this many days ahead...
EXPIRING_SOON_DAYS = 3
# ...or already past by at most this many days.
EXPIRED_LOOKBACK_DAYS = 30
# Safety cap — one run never processes more than this many prescriptions.
MAX_PER_RUN = 500

# Notification.meta["kind"] value marking rows created by this task.
META_KIND = "rx_expiry"


async def check_prescription_expiry(ctx: dict) -> None:
    """
    ARQ cron task: notify patients/doctors about expiring/expired prescriptions.

    Args:
        ctx: ARQ worker context dict; must contain 'db_session_factory'.
    """
    session_factory = ctx["db_session_factory"]
    today = date.today()
    window_start = today - timedelta(days=EXPIRED_LOOKBACK_DAYS)
    window_end = today + timedelta(days=EXPIRING_SOON_DAYS)

    processed = 0
    failed = 0
    async with session_factory() as db:
        res = await db.execute(
            select(Prescription)
            .where(
                Prescription.deleted_at.is_(None),
                Prescription.valid_until.isnot(None),
                Prescription.valid_until >= window_start,
                Prescription.valid_until <= window_end,
            )
            .order_by(Prescription.valid_until)
            .limit(MAX_PER_RUN)
        )
        prescriptions = res.scalars().all()

        for rx in prescriptions:
            try:
                await _process_prescription(db, rx, today)
                processed += 1
            except Exception as exc:
                # One bad row must not kill the run — roll back its partial
                # work and continue with the next prescription.
                await db.rollback()
                failed += 1
                logger.error(
                    "rx_expiry_item_failed",
                    prescription_id=str(rx.id),
                    error=str(exc),
                    exc_info=True,
                )

    # Ids/counts only — no PHI in logs.
    logger.info(
        "rx_expiry_run_complete",
        scanned=len(prescriptions),
        processed=processed,
        failed=failed,
        window_start=window_start.isoformat(),
        window_end=window_end.isoformat(),
    )


async def _process_prescription(db: AsyncSession, rx: Prescription, today: date) -> None:
    """Dispatch expiry notifications for one prescription, then commit."""
    stage = "expired" if rx.valid_until < today else "expiring"
    date_str = rx.valid_until.strftime("%d %b %Y")

    if stage == "expired":
        title = "Prescription expired"
        patient_body = f"Your prescription expired on {date_str}."
    else:
        title = "Prescription expiring soon"
        patient_body = f"Your prescription expires on {date_str}."

    notif_meta = {
        "kind": META_KIND,
        "prescription_id": str(rx.id),
        "stage": stage,
        "valid_until": rx.valid_until.isoformat(),
    }

    # --- Patient: in_app + enabled external channels ---------------------
    patient_res = await db.execute(select(User).where(User.id == rx.patient_id))
    patient = patient_res.scalar_one_or_none()

    if patient is None:
        logger.warning(
            "rx_expiry_patient_not_found",
            prescription_id=str(rx.id),
            patient_id=str(rx.patient_id),
        )
    elif await _already_notified(db, rx.patient_id, rx.id, stage):
        logger.info(
            "rx_expiry_skipped_already_sent",
            prescription_id=str(rx.id),
            user_id=str(rx.patient_id),
            stage=stage,
        )
    else:
        prefs = await notification_channels.get_preferences(patient.id, db=db)

        # Per-type opt-out — gates the whole patient notification.
        if not prefs.get("prescription_alerts", True):
            logger.info(
                "rx_expiry_skipped_user_opted_out",
                prescription_id=str(rx.id),
                user_id=str(patient.id),
            )
        else:
            channels = [
                c
                for c in notification_channels.CHANNELS
                if notification_channels.channel_enabled(c, prefs)
            ]
            # Platform-level kill-switch (admin → reminder_channels_enabled)
            channels = [
                c
                for c in channels
                if await platform_settings.platform_channel_enabled(db, c)
            ]
            results = await notification_channels.send_all(
                patient,
                channels,
                title,
                patient_body,
                db=db,
                notif_type=NotificationType.PRESCRIPTION.value,
                action_url="/patient/records",
                metadata=notif_meta,
                prefs=prefs,
            )
            logger.info(
                "rx_expiry_patient_dispatched",
                prescription_id=str(rx.id),
                user_id=str(patient.id),
                stage=stage,
                channels={r.channel: r.status for r in results},
            )

    # --- Doctor: in-app only ---------------------------------------------
    doctor_res = await db.execute(
        select(Doctor.user_id).where(
            Doctor.id == rx.doctor_id,
            Doctor.deleted_at.is_(None),
        )
    )
    doctor_user_id = doctor_res.scalar_one_or_none()

    if doctor_user_id is None:
        logger.warning(
            "rx_expiry_doctor_not_found",
            prescription_id=str(rx.id),
            doctor_id=str(rx.doctor_id),
        )
    elif await _already_notified(db, doctor_user_id, rx.id, stage):
        logger.info(
            "rx_expiry_skipped_already_sent",
            prescription_id=str(rx.id),
            user_id=str(doctor_user_id),
            stage=stage,
        )
    else:
        doctor_body = (
            f"A prescription you wrote for {patient.full_name} "
            f"{'expired' if stage == 'expired' else 'expires'} on {date_str}."
            if patient is not None
            else (
                f"A prescription you wrote "
                f"{'expired' if stage == 'expired' else 'expires'} on {date_str}."
            )
        )
        await notification_service.create_notification(
            db,
            user_id=doctor_user_id,
            notif_type=NotificationType.PRESCRIPTION.value,
            title=title,
            body=doctor_body,
            action_url="/doctor/prescriptions",
            metadata=notif_meta,
        )
        logger.info(
            "rx_expiry_doctor_notified",
            prescription_id=str(rx.id),
            user_id=str(doctor_user_id),
            stage=stage,
        )

    await db.commit()


async def _already_notified(
    db: AsyncSession,
    user_id: uuid.UUID,
    prescription_id: uuid.UUID,
    stage: str,
) -> bool:
    """
    True if this task already created an expiry notification for
    (user, prescription, stage). Matches on the ``meta`` JSONB markers —
    ReminderLog cannot be used (its appointment_id FK is non-nullable).
    Soft-deleted rows still count so dismissed banners are not resent.
    """
    res = await db.execute(
        select(Notification.id)
        .where(
            Notification.user_id == user_id,
            Notification.meta["kind"].astext == META_KIND,
            Notification.meta["prescription_id"].astext == str(prescription_id),
            Notification.meta["stage"].astext == stage,
        )
        .limit(1)
    )
    return res.scalar_one_or_none() is not None
