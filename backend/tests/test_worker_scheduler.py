"""Unit tests for the ARQ reminder scheduler and reminder dispatch.

Two units under test, with arq/Redis fully mocked (no server needed):

* ``app.workers.scheduler`` — ``schedule_appointment_reminders`` enqueues
  ``send_appointment_reminder`` via ``ArqRedis.enqueue_job`` with
  deterministic ``rem:{appointment_id}:{hours}h`` job ids (ARQ dedupes
  re-enqueues of the same id), skips reminders already in the past, and
  ``unschedule_appointment_reminders`` aborts the deferred jobs.
* ``app.workers.tasks.appointment_reminders`` — the dispatched job:
  per-channel ``ReminderLog`` rows, retrying only channels that have not
  sent yet, and the PHI guarantee (log rows never persist rendered
  message bodies).

The worker tasks are invoked directly with the conftest session factory —
they are plain coroutines that only need ``ctx["db_session_factory"]``.
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import app.workers.scheduler as scheduler
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.notification import Notification
from app.models.platform_setting import PlatformSetting
from app.models.reminder_log import ReminderLog
from app.models.user import User
from app.services import notification_channels
from app.workers.tasks.appointment_reminders import send_appointment_reminder
from tests.conftest import test_session


def _worker_ctx() -> dict:
    """ARQ ctx stand-in — the tasks only read ``db_session_factory``."""
    return {"db_session_factory": test_session}


# ---------------------------------------------------------------------------
# scheduler.schedule_appointment_reminders
# ---------------------------------------------------------------------------


@pytest.fixture
def arq_redis(monkeypatch) -> AsyncMock:
    """Replace the shared ARQ pool with a mock ArqRedis."""
    redis = AsyncMock()
    redis.enqueue_job.return_value = MagicMock(name="arq-job")
    monkeypatch.setattr(
        scheduler, "_get_redis_pool", AsyncMock(return_value=redis)
    )
    return redis


def _job_calls(redis: AsyncMock) -> dict[str, object]:
    """enqueue_job await calls keyed by deterministic job id."""
    return {c.kwargs["_job_id"]: c for c in redis.enqueue_job.await_args_list}


async def test_schedule_enqueues_24h_and_2h_jobs(arq_redis: AsyncMock):
    appt_id = str(uuid.uuid4())
    scheduled_at = datetime.now(timezone.utc) + timedelta(hours=48)

    await scheduler.schedule_appointment_reminders(appt_id, scheduled_at)

    assert arq_redis.enqueue_job.await_count == 2
    calls = _job_calls(arq_redis)

    call_24h = calls[f"rem:{appt_id}:24h"]
    assert call_24h.args == ("send_appointment_reminder", appt_id, 24)
    assert call_24h.kwargs["_defer_until"] == scheduled_at - timedelta(hours=24)

    call_2h = calls[f"rem:{appt_id}:2h"]
    assert call_2h.args == ("send_appointment_reminder", appt_id, 2)
    assert call_2h.kwargs["_defer_until"] == scheduled_at - timedelta(hours=2)


async def test_schedule_job_ids_are_deterministic(arq_redis: AsyncMock):
    """Re-scheduling reuses the same job ids so ARQ can dedupe them."""
    appt_id = str(uuid.uuid4())
    scheduled_at = datetime.now(timezone.utc) + timedelta(hours=48)

    await scheduler.schedule_appointment_reminders(appt_id, scheduled_at)
    first_ids = set(_job_calls(arq_redis))

    # ARQ returns None when a job id is already queued — the scheduler must
    # treat that as a no-op, not an error.
    arq_redis.enqueue_job.return_value = None
    await scheduler.schedule_appointment_reminders(appt_id, scheduled_at)
    second_ids = set(_job_calls(arq_redis))

    assert first_ids == second_ids == {
        f"rem:{appt_id}:24h",
        f"rem:{appt_id}:2h",
    }
    assert arq_redis.enqueue_job.await_count == 4


async def test_schedule_skips_jobs_already_in_the_past(arq_redis: AsyncMock):
    """Appointment 3h away: the 24h reminder is past, only the 2h one queues."""
    appt_id = str(uuid.uuid4())
    scheduled_at = datetime.now(timezone.utc) + timedelta(hours=3)

    await scheduler.schedule_appointment_reminders(appt_id, scheduled_at)

    assert arq_redis.enqueue_job.await_count == 1
    call = arq_redis.enqueue_job.await_args_list[0]
    assert call.args == ("send_appointment_reminder", appt_id, 2)
    assert call.kwargs["_job_id"] == f"rem:{appt_id}:2h"


async def test_schedule_no_jobs_when_appointment_imminent(arq_redis: AsyncMock):
    appt_id = str(uuid.uuid4())
    scheduled_at = datetime.now(timezone.utc) + timedelta(hours=1)

    await scheduler.schedule_appointment_reminders(appt_id, scheduled_at)

    arq_redis.enqueue_job.assert_not_awaited()


async def test_schedule_treats_naive_datetime_as_utc(arq_redis: AsyncMock):
    """Naive ``scheduled_at`` is interpreted as UTC, not rejected."""
    appt_id = str(uuid.uuid4())
    scheduled_at = (datetime.now(timezone.utc) + timedelta(hours=48)).replace(
        tzinfo=None
    )

    await scheduler.schedule_appointment_reminders(appt_id, scheduled_at)

    call_24h = _job_calls(arq_redis)[f"rem:{appt_id}:24h"]
    assert call_24h.kwargs["_defer_until"] == (
        scheduled_at - timedelta(hours=24)
    ).replace(tzinfo=timezone.utc)


async def test_schedule_swallows_redis_failure(arq_redis: AsyncMock, monkeypatch):
    """A Redis outage must not propagate — reminder scheduling is best-effort."""
    monkeypatch.setattr(
        scheduler,
        "_get_redis_pool",
        AsyncMock(side_effect=ConnectionError("redis down")),
    )

    await scheduler.schedule_appointment_reminders(
        str(uuid.uuid4()), datetime.now(timezone.utc) + timedelta(hours=48)
    )

    arq_redis.enqueue_job.assert_not_awaited()


async def test_schedule_enqueue_failure_still_attempts_remaining_jobs(
    arq_redis: AsyncMock,
):
    """A failed 24h enqueue should not cost the appointment its 2h reminder."""
    arq_redis.enqueue_job.side_effect = [
        ConnectionError("redis down"),
        MagicMock(name="arq-job"),
    ]
    appt_id = str(uuid.uuid4())

    await scheduler.schedule_appointment_reminders(
        appt_id, datetime.now(timezone.utc) + timedelta(hours=48)
    )

    attempted_ids = set(_job_calls(arq_redis))
    assert f"rem:{appt_id}:2h" in attempted_ids


# ---------------------------------------------------------------------------
# scheduler.unschedule_appointment_reminders
# ---------------------------------------------------------------------------


class _RecordingJob:
    """Stand-in for arq.jobs.Job that records construction + abort()."""

    created: list["_RecordingJob"] = []

    def __init__(self, job_id: str, redis):
        self.job_id = job_id
        self.redis = redis
        self.aborted = False
        _RecordingJob.created.append(self)

    async def abort(self):
        self.aborted = True


@pytest.fixture
def recorded_jobs(monkeypatch) -> list[_RecordingJob]:
    _RecordingJob.created = []
    monkeypatch.setattr("arq.jobs.Job", _RecordingJob)
    return _RecordingJob.created


async def test_unschedule_aborts_both_pending_jobs(
    arq_redis: AsyncMock, recorded_jobs: list[_RecordingJob]
):
    appt_id = str(uuid.uuid4())

    await scheduler.unschedule_appointment_reminders(appt_id)

    # Deterministic ids: an aborted job id can be re-enqueued right away.
    assert [j.job_id for j in recorded_jobs] == [
        f"rem:{appt_id}:24h",
        f"rem:{appt_id}:2h",
    ]
    assert all(j.aborted for j in recorded_jobs)
    assert all(j.redis is arq_redis for j in recorded_jobs)


async def test_unschedule_ignores_missing_jobs(
    arq_redis: AsyncMock, recorded_jobs: list[_RecordingJob], monkeypatch
):
    """A job that already ran/never queued must not block the other abort."""

    class _HalfMissingJob(_RecordingJob):
        async def abort(self):
            if self.job_id.endswith(":24h"):
                raise RuntimeError("job not queued")
            await super().abort()

    monkeypatch.setattr("arq.jobs.Job", _HalfMissingJob)
    appt_id = str(uuid.uuid4())

    await scheduler.unschedule_appointment_reminders(appt_id)

    assert len(recorded_jobs) == 2
    assert recorded_jobs[1].aborted  # the 2h job still aborted


async def test_unschedule_swallows_redis_failure(monkeypatch):
    monkeypatch.setattr(
        scheduler,
        "_get_redis_pool",
        AsyncMock(side_effect=ConnectionError("redis down")),
    )

    await scheduler.unschedule_appointment_reminders(str(uuid.uuid4()))


# ---------------------------------------------------------------------------
# scheduler._arq_redis_settings
# ---------------------------------------------------------------------------


def test_rediss_url_disables_cert_verification(monkeypatch):
    """ElastiCache uses an AWS-internal CA — rediss:// must relax cert checks."""
    monkeypatch.setattr(
        scheduler.settings, "REDIS_URL", "rediss://cache.example:6379/0"
    )
    rs = scheduler._arq_redis_settings()
    assert rs.ssl_cert_reqs == "none"


def test_plain_redis_url_keeps_default_ssl_settings(monkeypatch):
    """The cert-verification override only applies to rediss:// URLs."""
    monkeypatch.setattr(
        scheduler.settings, "REDIS_URL", "redis://localhost:6379/0"
    )
    rs = scheduler._arq_redis_settings()
    assert rs.ssl is False
    assert rs.ssl_cert_reqs != "none"


# ---------------------------------------------------------------------------
# appointment_reminders.send_appointment_reminder — dispatch + ReminderLog
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def appointment(
    db: AsyncSession,
    patient_user: User,
    doctor_user: User,
    doctor_profile: Doctor,
) -> Appointment:
    appt = Appointment(
        id=uuid.uuid4(),
        patient_id=patient_user.id,
        doctor_id=doctor_profile.id,
        scheduled_at=datetime.now(timezone.utc) + timedelta(hours=26),
        duration_minutes=30,
        type="in-person",
        status="scheduled",
        created_by=doctor_user.id,
    )
    db.add(appt)
    await db.commit()
    return appt


async def _reminder_logs(db: AsyncSession, appointment_id: uuid.UUID):
    # populate_existing: rows may be updated by the task's own session —
    # without it the identity map would serve stale attributes on re-read.
    res = await db.execute(
        select(ReminderLog)
        .where(ReminderLog.appointment_id == appointment_id)
        .execution_options(populate_existing=True)
    )
    return res.scalars().all()


async def _notifications_for(db: AsyncSession, user_id: uuid.UUID, appointment_id: uuid.UUID):
    res = await db.execute(
        select(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.meta["appointment_id"].astext == str(appointment_id),
        )
        .execution_options(populate_existing=True)
    )
    return res.scalars().all()


async def test_reminder_success_logs_sent_and_notifies_both_sides(
    db: AsyncSession,
    patient_user: User,
    doctor_user: User,
    appointment: Appointment,
):
    # Default platform settings enable in_app only — one log row expected.
    await send_appointment_reminder(_worker_ctx(), str(appointment.id), 24)

    logs = await _reminder_logs(db, appointment.id)
    assert len(logs) == 1
    log = logs[0]
    assert log.reminder_type == "24h"
    assert log.channel == "in_app"
    assert log.status == "sent"
    assert log.sent_at is not None

    patient_notifs = await _notifications_for(db, patient_user.id, appointment.id)
    assert len(patient_notifs) == 1
    assert patient_notifs[0].title == "Appointment in 24 hour(s)"
    assert patient_notifs[0].meta["reminder_type"] == "24h"

    doctor_notifs = await _notifications_for(db, doctor_user.id, appointment.id)
    assert len(doctor_notifs) == 1


async def test_reminder_two_hour_type(
    db: AsyncSession, appointment: Appointment
):
    await send_appointment_reminder(_worker_ctx(), str(appointment.id), 2)

    logs = await _reminder_logs(db, appointment.id)
    assert [log.reminder_type for log in logs] == ["2h"]


async def test_failed_channel_is_retried_without_resending_sent(
    db: AsyncSession,
    patient_user: User,
    appointment: Appointment,
    monkeypatch,
):
    """in_app succeeds + email fails on run 1; run 2 retries email only."""
    db.add(
        PlatformSetting(
            key="reminder_channels_enabled",
            value={"in_app": True, "email": True, "sms": False, "whatsapp": False},
        )
    )
    await db.commit()
    monkeypatch.setattr(notification_channels.settings, "SMTP_HOST", "smtp.test")
    monkeypatch.setattr(notification_channels.settings, "SMTP_FROM", "noreply@test")

    def _smtp_down(msg):
        raise ConnectionError("smtp down")

    monkeypatch.setattr(notification_channels, "_smtp_send", _smtp_down)
    await send_appointment_reminder(_worker_ctx(), str(appointment.id), 24)

    logs = {log.channel: log for log in await _reminder_logs(db, appointment.id)}
    assert logs["in_app"].status == "sent"
    assert logs["email"].status == "failed"
    assert logs["email"].sent_at is None

    # Retry with SMTP healthy — only the failed channel is re-dispatched.
    monkeypatch.setattr(notification_channels, "_smtp_send", lambda msg: None)
    await send_appointment_reminder(_worker_ctx(), str(appointment.id), 24)

    await db.commit()  # end the read txn — next SELECT sees the task's commits
    logs = {log.channel: log for log in await _reminder_logs(db, appointment.id)}
    assert logs["email"].status == "sent"
    assert logs["email"].sent_at is not None
    # One log row per channel — updated in place, not duplicated.
    assert len(logs) == 2
    # in_app was already sent: no second in-app notification for the patient.
    patient_notifs = await _notifications_for(db, patient_user.id, appointment.id)
    assert len(patient_notifs) == 1


async def test_reminder_log_stores_no_phi(
    db: AsyncSession,
    patient_user: User,
    doctor_user: User,
    appointment: Appointment,
):
    """ReminderLog.message holds the outcome code, never the rendered body
    (patient/doctor names are PHI at rest)."""
    await send_appointment_reminder(_worker_ctx(), str(appointment.id), 24)

    logs = await _reminder_logs(db, appointment.id)
    assert len(logs) == 1
    message = logs[0].message or ""
    assert message == "delivered"
    assert patient_user.full_name not in message
    assert doctor_user.full_name not in message


async def test_reminder_skips_terminal_appointment(
    db: AsyncSession, appointment: Appointment
):
    appointment.status = "cancelled"
    await db.commit()

    await send_appointment_reminder(_worker_ctx(), str(appointment.id), 24)

    assert await _reminder_logs(db, appointment.id) == []
    count = await db.scalar(select(func.count()).select_from(Notification))
    assert count == 0


async def test_reminder_skips_unknown_appointment(db: AsyncSession):
    await send_appointment_reminder(_worker_ctx(), str(uuid.uuid4()), 24)
    count = await db.scalar(select(func.count()).select_from(ReminderLog))
    assert count == 0


async def test_retry_does_not_duplicate_doctor_notification(
    db: AsyncSession,
    doctor_user: User,
    appointment: Appointment,
    monkeypatch,
):
    """A partial retry must re-dispatch only unsent channels — including not
    re-creating the doctor's in-app copy."""
    db.add(
        PlatformSetting(
            key="reminder_channels_enabled",
            value={"in_app": True, "email": True, "sms": False, "whatsapp": False},
        )
    )
    await db.commit()
    monkeypatch.setattr(notification_channels.settings, "SMTP_HOST", "smtp.test")
    monkeypatch.setattr(notification_channels.settings, "SMTP_FROM", "noreply@test")

    def _smtp_down(msg):
        raise ConnectionError("smtp down")

    monkeypatch.setattr(notification_channels, "_smtp_send", _smtp_down)
    await send_appointment_reminder(_worker_ctx(), str(appointment.id), 24)
    monkeypatch.setattr(notification_channels, "_smtp_send", lambda msg: None)
    await send_appointment_reminder(_worker_ctx(), str(appointment.id), 24)

    await db.commit()
    doctor_notifs = await _notifications_for(db, doctor_user.id, appointment.id)
    assert len(doctor_notifs) == 1
