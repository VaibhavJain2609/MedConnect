"""Unit tests for the daily prescription-expiry ARQ cron task.

Covers ``app.workers.tasks.prescription_expiry.check_prescription_expiry``:

* notification window — ``valid_until`` in [today-30d, today+3d], with
  "expiring"/"expired" stages split at ``today``;
* idempotency — dedupe via ``Notification.meta`` markers
  (``{"kind": "rx_expiry", "prescription_id", "stage"}``), including
  soft-deleted rows (a dismissed banner must not resend);
* the ``MAX_PER_RUN`` = 500 safety cap;
* missing-patient handling, per-user ``prescription_alerts`` opt-out, and
  channel filtering (user prefs + platform kill-switch);
* per-item failure isolation (one bad row must not kill the run).

The task is invoked directly with the conftest session factory — it is a
plain coroutine that only needs ``ctx["db_session_factory"]``.
"""
import uuid
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.doctor import Doctor
from app.models.medical_record import MedicalRecord
from app.models.notification import Notification, NotificationPreferences
from app.models.platform_setting import PlatformSetting
from app.models.prescription import Prescription
from app.models.user import User
from app.services import notification_channels
from app.workers.tasks.prescription_expiry import (
    _process_prescription,
    check_prescription_expiry,
)
from tests.conftest import test_session


def _worker_ctx() -> dict:
    """ARQ ctx stand-in — the task only reads ``db_session_factory``."""
    return {"db_session_factory": test_session}


async def _make_prescription(
    db: AsyncSession,
    patient_id: uuid.UUID,
    doctor_id: uuid.UUID,
    valid_until: date | None,
) -> Prescription:
    """A prescription row + its required parent medical record."""
    record = MedicalRecord(
        id=uuid.uuid4(),
        patient_id=patient_id,
        doctor_id=doctor_id,
        record_type="opd_note",
        title="Expiry test visit",
    )
    db.add(record)
    await db.flush()
    rx = Prescription(
        id=uuid.uuid4(),
        record_id=record.id,
        doctor_id=doctor_id,
        patient_id=patient_id,
        medicines=[{"name": "TestDrug", "dosage": "500mg"}],
        valid_until=valid_until,
    )
    db.add(rx)
    await db.commit()
    return rx


async def _rx_notifications(
    db: AsyncSession,
    user_id: uuid.UUID,
    rx_id: uuid.UUID | None = None,
) -> list[Notification]:
    """rx_expiry notifications for a user (soft-deleted rows included —
    dedupe counts them, so tests must see them too)."""
    stmt = (
        select(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.meta["kind"].astext == "rx_expiry",
        )
        # populate_existing: the task writes via its own session — don't
        # serve stale identity-map attributes on re-read.
        .execution_options(populate_existing=True)
    )
    if rx_id is not None:
        stmt = stmt.where(
            Notification.meta["prescription_id"].astext == str(rx_id)
        )
    res = await db.execute(stmt)
    return res.scalars().all()


# ---------------------------------------------------------------------------
# Happy path + dedupe
# ---------------------------------------------------------------------------


async def test_expiring_soon_notifies_patient_and_doctor(
    db: AsyncSession,
    patient_user: User,
    doctor_user: User,
    doctor_profile: Doctor,
):
    rx = await _make_prescription(
        db, patient_user.id, doctor_profile.id, date.today() + timedelta(days=2)
    )

    await check_prescription_expiry(_worker_ctx())
    await db.commit()  # end the read txn — next SELECT sees the task's commits

    patient_notifs = await _rx_notifications(db, patient_user.id, rx.id)
    assert len(patient_notifs) == 1
    notif = patient_notifs[0]
    assert notif.title == "Prescription expiring soon"
    assert notif.type == "prescription"
    assert notif.meta["prescription_id"] == str(rx.id)
    assert notif.meta["stage"] == "expiring"
    assert notif.action_url == "/patient/records"

    doctor_notifs = await _rx_notifications(db, doctor_user.id, rx.id)
    assert len(doctor_notifs) == 1
    assert doctor_notifs[0].meta["stage"] == "expiring"
    assert doctor_notifs[0].action_url == "/doctor/prescriptions"
    assert patient_user.full_name in doctor_notifs[0].message


async def test_second_run_is_deduped_via_meta(
    db: AsyncSession,
    patient_user: User,
    doctor_user: User,
    doctor_profile: Doctor,
):
    rx = await _make_prescription(
        db, patient_user.id, doctor_profile.id, date.today() + timedelta(days=2)
    )

    await check_prescription_expiry(_worker_ctx())
    await check_prescription_expiry(_worker_ctx())
    await db.commit()

    assert len(await _rx_notifications(db, patient_user.id, rx.id)) == 1
    assert len(await _rx_notifications(db, doctor_user.id, rx.id)) == 1


async def test_soft_deleted_notification_still_dedupes(
    db: AsyncSession,
    patient_user: User,
    doctor_profile: Doctor,
):
    """A dismissed (soft-deleted) banner must not trigger a resend."""
    rx = await _make_prescription(
        db, patient_user.id, doctor_profile.id, date.today() + timedelta(days=2)
    )
    await check_prescription_expiry(_worker_ctx())
    await db.commit()

    notif = (await _rx_notifications(db, patient_user.id, rx.id))[0]
    notif.deleted_at = datetime.now(timezone.utc)
    await db.commit()

    await check_prescription_expiry(_worker_ctx())
    await db.commit()
    assert len(await _rx_notifications(db, patient_user.id, rx.id)) == 1


async def test_expired_stage_title_and_meta(
    db: AsyncSession,
    patient_user: User,
    doctor_profile: Doctor,
):
    rx = await _make_prescription(
        db, patient_user.id, doctor_profile.id, date.today() - timedelta(days=5)
    )

    await check_prescription_expiry(_worker_ctx())
    await db.commit()

    notifs = await _rx_notifications(db, patient_user.id, rx.id)
    assert len(notifs) == 1
    assert notifs[0].title == "Prescription expired"
    assert notifs[0].meta["stage"] == "expired"


# ---------------------------------------------------------------------------
# Window boundaries
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "offset_days,expected_stage",
    [
        (-31, None),       # outside lookback
        (-30, "expired"),  # lookback boundary (inclusive)
        (-1, "expired"),
        (0, "expiring"),   # today is not yet "< today" -> expiring
        (3, "expiring"),   # ahead boundary (inclusive)
        (4, None),         # outside window
    ],
)
async def test_notification_window_boundaries(
    db: AsyncSession,
    patient_user: User,
    doctor_profile: Doctor,
    offset_days: int,
    expected_stage: str | None,
):
    rx = await _make_prescription(
        db,
        patient_user.id,
        doctor_profile.id,
        date.today() + timedelta(days=offset_days),
    )

    await check_prescription_expiry(_worker_ctx())
    await db.commit()

    notifs = await _rx_notifications(db, patient_user.id, rx.id)
    if expected_stage is None:
        assert notifs == []
    else:
        assert len(notifs) == 1
        assert notifs[0].meta["stage"] == expected_stage


async def test_prescription_without_valid_until_is_skipped(
    db: AsyncSession,
    patient_user: User,
    doctor_profile: Doctor,
):
    rx = await _make_prescription(
        db, patient_user.id, doctor_profile.id, valid_until=None
    )

    await check_prescription_expiry(_worker_ctx())
    await db.commit()

    assert await _rx_notifications(db, patient_user.id, rx.id) == []


async def test_soft_deleted_prescription_is_skipped(
    db: AsyncSession,
    patient_user: User,
    doctor_profile: Doctor,
):
    rx = await _make_prescription(
        db, patient_user.id, doctor_profile.id, date.today() + timedelta(days=2)
    )
    rx.deleted_at = datetime.now(timezone.utc)
    await db.commit()

    await check_prescription_expiry(_worker_ctx())
    await db.commit()

    assert await _rx_notifications(db, patient_user.id, rx.id) == []


# ---------------------------------------------------------------------------
# Edge cases: missing patient, opt-out, channel filtering
# ---------------------------------------------------------------------------


async def test_missing_patient_skipped_but_doctor_still_notified(
    db: AsyncSession,
    doctor_user: User,
    doctor_profile: Doctor,
):
    """A prescription whose patient row is gone logs a warning and moves on;
    the doctor copy (without the patient name) is still sent.

    The FK on prescriptions.patient_id makes a dangling reference impossible
    via ORM inserts, so _process_prescription is driven directly with a stub.
    """
    ghost_patient_id = uuid.uuid4()
    rx = SimpleNamespace(
        id=uuid.uuid4(),
        patient_id=ghost_patient_id,
        doctor_id=doctor_profile.id,
        valid_until=date.today() + timedelta(days=1),
    )

    await _process_prescription(db, rx, date.today())

    count = await db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == ghost_patient_id)
    )
    assert count == 0

    doctor_notifs = await _rx_notifications(db, doctor_user.id, rx.id)
    assert len(doctor_notifs) == 1
    # Generic body — no patient name available (and none leaked).
    assert "expires on" in doctor_notifs[0].message


async def test_patient_opted_out_via_preferences(
    db: AsyncSession,
    patient_user: User,
    doctor_user: User,
    doctor_profile: Doctor,
):
    """``prescription_alerts: false`` gates the whole patient notification;
    the doctor copy is unaffected."""
    db.add(
        NotificationPreferences(
            user_id=patient_user.id,
            preferences={"prescription_alerts": False},
        )
    )
    rx = await _make_prescription(
        db, patient_user.id, doctor_profile.id, date.today() + timedelta(days=2)
    )

    await check_prescription_expiry(_worker_ctx())
    await db.commit()

    assert await _rx_notifications(db, patient_user.id, rx.id) == []
    assert len(await _rx_notifications(db, doctor_user.id, rx.id)) == 1


async def test_channel_filtering_honours_prefs_and_platform_switch(
    db: AsyncSession,
    patient_user: User,
    doctor_profile: Doctor,
    monkeypatch,
):
    """Channels attempted = user prefs ANDed with the platform kill-switch."""
    db.add(
        PlatformSetting(
            key="reminder_channels_enabled",
            value={"in_app": True, "email": True, "sms": True, "whatsapp": False},
        )
    )
    db.add(
        NotificationPreferences(
            user_id=patient_user.id,
            preferences={
                "email_notifications": False,
                "sms_notifications": True,
                "whatsapp_notifications": True,
            },
        )
    )
    rx = await _make_prescription(
        db, patient_user.id, doctor_profile.id, date.today() + timedelta(days=2)
    )

    attempted: list[str] = []
    real_send_all = notification_channels.send_all

    async def _spy(user, channels, *args, **kwargs):
        attempted.extend(channels)
        return await real_send_all(user, channels, *args, **kwargs)

    monkeypatch.setattr(notification_channels, "send_all", _spy)

    await check_prescription_expiry(_worker_ctx())

    # email disabled by user pref; whatsapp disabled by platform switch.
    assert attempted == ["in_app", "sms"]


# ---------------------------------------------------------------------------
# Safety cap + failure isolation
# ---------------------------------------------------------------------------


async def test_max_per_run_cap(
    db: AsyncSession,
    patient_user: User,
    doctor_profile: Doctor,
):
    """A run processes at most MAX_PER_RUN (500) prescriptions; the 501st —
    ordered last by valid_until — is left for the next run."""
    records = [
        MedicalRecord(
            id=uuid.uuid4(),
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            record_type="opd_note",
            title="cap test",
        )
        for _ in range(501)
    ]
    db.add_all(records)
    await db.flush()

    overflow_rx_id = uuid.uuid4()
    rxs = []
    for i, record in enumerate(records):
        rxs.append(
            Prescription(
                # The last prescription expires latest so valid_until
                # ordering pushes it past the 500-row limit.
                id=overflow_rx_id if i == 500 else uuid.uuid4(),
                record_id=record.id,
                doctor_id=doctor_profile.id,
                patient_id=patient_user.id,
                medicines=[],
                valid_until=date.today() + timedelta(days=2 if i == 500 else 1),
            )
        )
    db.add_all(rxs)
    await db.commit()

    await check_prescription_expiry(_worker_ctx())
    await db.commit()

    patient_notifs = await _rx_notifications(db, patient_user.id)
    assert len(patient_notifs) == 500
    notified_rx_ids = {n.meta["prescription_id"] for n in patient_notifs}
    assert str(overflow_rx_id) not in notified_rx_ids


@pytest.mark.xfail(
    reason=(
        "BUG (report-only): check_prescription_expiry's error handler "
        "crashes the whole run. The except block does db.rollback() — which "
        "expires every ORM object in the session — then logger.error reads "
        "str(rx.id), a lazy expired-attribute load that raises "
        "MissingGreenlet outside the greenlet context "
        "(prescription_expiry.py:87-94). The exception propagates out of the "
        "task, so every remaining prescription is skipped — 'one bad row "
        "must not kill the run' does not hold."
    ),
    strict=True,
)
async def test_one_bad_prescription_does_not_abort_run(
    db: AsyncSession,
    patient_user: User,
    doctor_user: User,
    doctor_profile: Doctor,
    monkeypatch,
):
    """An exception mid-item should roll back that item's work and let the
    run continue with the next prescription."""
    rx_fail = await _make_prescription(
        db, patient_user.id, doctor_profile.id, date.today() + timedelta(days=1)
    )
    rx_ok = await _make_prescription(
        db, patient_user.id, doctor_profile.id, date.today() + timedelta(days=2)
    )

    calls = 0
    real_send_all = notification_channels.send_all

    async def _flaky(user, channels, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("channel dispatch exploded")
        return await real_send_all(user, channels, *args, **kwargs)

    monkeypatch.setattr(notification_channels, "send_all", _flaky)

    await check_prescription_expiry(_worker_ctx())
    await db.commit()

    # rx_fail sorted first by valid_until: its send_all blew up, its partial
    # work rolled back — no patient OR doctor notification for it.
    assert await _rx_notifications(db, patient_user.id, rx_fail.id) == []
    assert await _rx_notifications(db, doctor_user.id, rx_fail.id) == []

    # rx_ok still fully processed.
    assert len(await _rx_notifications(db, patient_user.id, rx_ok.id)) == 1
    assert len(await _rx_notifications(db, doctor_user.id, rx_ok.id)) == 1
