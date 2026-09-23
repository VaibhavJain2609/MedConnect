"""Tests for opt-in medication adherence reminders.

Covers:

* CRUD on /api/v1/medication-reminders — create (upsert), list, patch,
  soft-delete — all patient-scoped: a reminder is only readable/mutable by
  its owner and the target prescription must belong to the caller;
* validation of ``times_of_day`` ("HH:MM" 24h);
* the ``send_medication_reminders`` ARQ task — 15-minute slot matching in
  Asia/Kolkata, Notification.meta dedupe per (reminder, day, timeslot),
  disabled/expired-course skips.

The task is invoked directly with the conftest session factory — it only
needs ``ctx["db_session_factory"]``; ``now`` is injected for determinism.
"""
import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.doctor import Doctor
from app.models.medical_record import MedicalRecord
from app.models.medication_reminder import MedicationReminder
from app.models.notification import Notification
from app.models.prescription import Prescription
from app.models.user import User
from app.workers.tasks.medication_reminders import (
    META_KIND,
    send_medication_reminders,
)
from tests.conftest import create_test_token, test_session

IST = ZoneInfo("Asia/Kolkata")


def _worker_ctx() -> dict:
    """ARQ ctx stand-in — the task only reads ``db_session_factory``."""
    return {"db_session_factory": test_session}


async def _make_prescription(
    db: AsyncSession,
    patient_id: uuid.UUID,
    doctor_id: uuid.UUID,
    valid_until: date | None = None,
) -> Prescription:
    """A prescription row + its required parent medical record."""
    record = MedicalRecord(
        id=uuid.uuid4(),
        patient_id=patient_id,
        doctor_id=doctor_id,
        record_type="opd_note",
        title="Reminder test visit",
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


async def _make_reminder(
    db: AsyncSession,
    user_id: uuid.UUID,
    prescription_id: uuid.UUID,
    times: list[str],
    enabled: bool = True,
) -> MedicationReminder:
    reminder = MedicationReminder(
        id=uuid.uuid4(),
        user_id=user_id,
        prescription_id=prescription_id,
        times_of_day=times,
        enabled=enabled,
    )
    db.add(reminder)
    await db.commit()
    return reminder


async def _med_reminder_notifications(
    db: AsyncSession, user_id: uuid.UUID
) -> list[Notification]:
    """med_reminder notifications for a user (soft-deleted included — dedupe
    counts them, so tests must see them too)."""
    res = await db.execute(
        select(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.meta["kind"].astext == META_KIND,
        )
        .execution_options(populate_existing=True)
    )
    return res.scalars().all()


async def _make_other_patient(db: AsyncSession) -> User:
    user = User(
        keycloak_sub=f"other-{uuid.uuid4()}",
        email="other@test.com",
        full_name="Other Patient",
        role="patient",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def _auth(user: User) -> dict[str, str]:
    token = create_test_token(
        sub=user.keycloak_sub, email=user.email, name=user.full_name, roles=[user.role]
    )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# CRUD + ownership scoping
# ---------------------------------------------------------------------------


async def test_create_reminder(
    patient_client: AsyncClient, patient_user: User, doctor_profile: Doctor, db: AsyncSession
):
    rx = await _make_prescription(db, patient_user.id, doctor_profile.id)

    resp = await patient_client.post(
        "/api/v1/medication-reminders",
        json={
            "prescription_id": str(rx.id),
            "times_of_day": ["20:00", "08:00", "08:00"],
            "enabled": True,
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["prescription_id"] == str(rx.id)
    assert body["user_id"] == str(patient_user.id)
    # Deduped + sorted chronologically.
    assert body["times_of_day"] == ["08:00", "20:00"]
    assert body["enabled"] is True


async def test_post_upserts_existing_reminder(
    patient_client: AsyncClient, patient_user: User, doctor_profile: Doctor, db: AsyncSession
):
    rx = await _make_prescription(db, patient_user.id, doctor_profile.id)

    first = await patient_client.post(
        "/api/v1/medication-reminders",
        json={"prescription_id": str(rx.id), "times_of_day": ["08:00"]},
    )
    assert first.status_code == 201

    second = await patient_client.post(
        "/api/v1/medication-reminders",
        json={"prescription_id": str(rx.id), "times_of_day": ["09:00", "21:00"], "enabled": False},
    )
    assert second.status_code == 200, second.text
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["times_of_day"] == ["09:00", "21:00"]
    assert second.json()["enabled"] is False

    listed = await patient_client.get("/api/v1/medication-reminders")
    assert len(listed.json()["data"]) == 1


async def test_list_scoped_to_owner(
    patient_client: AsyncClient, patient_user: User, doctor_profile: Doctor, db: AsyncSession
):
    rx_mine = await _make_prescription(db, patient_user.id, doctor_profile.id)
    other = await _make_other_patient(db)
    rx_other = await _make_prescription(db, other.id, doctor_profile.id)

    await patient_client.post(
        "/api/v1/medication-reminders",
        json={"prescription_id": str(rx_mine.id), "times_of_day": ["08:00"]},
    )
    await _make_reminder(db, other.id, rx_other.id, ["09:00"])

    resp = await patient_client.get("/api/v1/medication-reminders")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["prescription_id"] == str(rx_mine.id)


async def test_create_for_other_patients_prescription_forbidden(
    patient_client: AsyncClient, doctor_profile: Doctor, db: AsyncSession
):
    other = await _make_other_patient(db)
    rx_other = await _make_prescription(db, other.id, doctor_profile.id)

    resp = await patient_client.post(
        "/api/v1/medication-reminders",
        json={"prescription_id": str(rx_other.id), "times_of_day": ["08:00"]},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


async def test_create_for_missing_prescription_404(patient_client: AsyncClient):
    resp = await patient_client.post(
        "/api/v1/medication-reminders",
        json={"prescription_id": str(uuid.uuid4()), "times_of_day": ["08:00"]},
    )
    assert resp.status_code == 404


@pytest.mark.parametrize("bad", ["25:00", "8:00", "08:60", "noon", "0800"])
async def test_invalid_time_rejected(
    patient_client: AsyncClient, patient_user: User, doctor_profile: Doctor, db: AsyncSession, bad: str
):
    rx = await _make_prescription(db, patient_user.id, doctor_profile.id)
    resp = await patient_client.post(
        "/api/v1/medication-reminders",
        json={"prescription_id": str(rx.id), "times_of_day": [bad]},
    )
    assert resp.status_code == 422, resp.text


async def test_patch_reminder(
    patient_client: AsyncClient, patient_user: User, doctor_profile: Doctor, db: AsyncSession
):
    rx = await _make_prescription(db, patient_user.id, doctor_profile.id)
    created = await patient_client.post(
        "/api/v1/medication-reminders",
        json={"prescription_id": str(rx.id), "times_of_day": ["08:00"]},
    )
    rid = created.json()["id"]

    resp = await patient_client.patch(
        f"/api/v1/medication-reminders/{rid}",
        json={"times_of_day": ["07:30", "19:30"], "enabled": False},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["times_of_day"] == ["07:30", "19:30"]
    assert resp.json()["enabled"] is False

    # Partial patch — only enabled.
    resp = await patient_client.patch(
        f"/api/v1/medication-reminders/{rid}", json={"enabled": True}
    )
    assert resp.status_code == 200
    assert resp.json()["enabled"] is True
    assert resp.json()["times_of_day"] == ["07:30", "19:30"]


async def test_patch_and_delete_other_users_reminder_404(
    patient_client: AsyncClient, doctor_profile: Doctor, db: AsyncSession
):
    other = await _make_other_patient(db)
    rx_other = await _make_prescription(db, other.id, doctor_profile.id)
    reminder = await _make_reminder(db, other.id, rx_other.id, ["08:00"])

    resp = await patient_client.patch(
        f"/api/v1/medication-reminders/{reminder.id}", json={"enabled": False}
    )
    assert resp.status_code == 404

    resp = await patient_client.delete(f"/api/v1/medication-reminders/{reminder.id}")
    assert resp.status_code == 404


async def test_delete_reminder(
    patient_client: AsyncClient, patient_user: User, doctor_profile: Doctor, db: AsyncSession
):
    rx = await _make_prescription(db, patient_user.id, doctor_profile.id)
    created = await patient_client.post(
        "/api/v1/medication-reminders",
        json={"prescription_id": str(rx.id), "times_of_day": ["08:00"]},
    )
    rid = created.json()["id"]

    resp = await patient_client.delete(f"/api/v1/medication-reminders/{rid}")
    assert resp.status_code == 204

    listed = await patient_client.get("/api/v1/medication-reminders")
    assert listed.json()["data"] == []

    # Soft-deleted — patching it no longer resolves.
    resp = await patient_client.patch(
        f"/api/v1/medication-reminders/{rid}", json={"enabled": True}
    )
    assert resp.status_code == 404


async def test_unauthenticated_rejected(client: AsyncClient):
    resp = await client.get("/api/v1/medication-reminders")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Worker: slot matching + dedupe
# ---------------------------------------------------------------------------


async def test_worker_notifies_matching_slot(
    patient_user: User, doctor_profile: Doctor, db: AsyncSession
):
    rx = await _make_prescription(db, patient_user.id, doctor_profile.id)
    reminder = await _make_reminder(db, patient_user.id, rx.id, ["08:00", "20:00"])

    await send_medication_reminders(
        _worker_ctx(), now=datetime(2026, 1, 5, 8, 5, tzinfo=IST)
    )
    await db.commit()

    notifs = await _med_reminder_notifications(db, patient_user.id)
    assert len(notifs) == 1
    notif = notifs[0]
    assert notif.title == "Time to take your medication"
    assert notif.type == "prescription"
    assert notif.action_url == "/patient/medications"
    assert notif.meta["reminder_id"] == str(reminder.id)
    assert notif.meta["prescription_id"] == str(rx.id)
    assert notif.meta["timeslot"] == "08:00"
    assert notif.meta["date"] == "2026-01-05"


async def test_worker_dedupes_same_slot_on_rerun(
    patient_user: User, doctor_profile: Doctor, db: AsyncSession
):
    rx = await _make_prescription(db, patient_user.id, doctor_profile.id)
    await _make_reminder(db, patient_user.id, rx.id, ["08:00"])

    now = datetime(2026, 1, 5, 8, 0, tzinfo=IST)
    await send_medication_reminders(_worker_ctx(), now=now)
    # Same slot, later minute — must not double-notify.
    await send_medication_reminders(
        _worker_ctx(), now=datetime(2026, 1, 5, 8, 14, tzinfo=IST)
    )
    await db.commit()

    assert len(await _med_reminder_notifications(db, patient_user.id)) == 1


async def test_worker_fires_per_timeslot_and_per_day(
    patient_user: User, doctor_profile: Doctor, db: AsyncSession
):
    rx = await _make_prescription(db, patient_user.id, doctor_profile.id)
    await _make_reminder(db, patient_user.id, rx.id, ["08:00", "20:00"])

    await send_medication_reminders(
        _worker_ctx(), now=datetime(2026, 1, 5, 8, 0, tzinfo=IST)
    )
    await db.commit()
    assert len(await _med_reminder_notifications(db, patient_user.id)) == 1

    # Evening slot — same day → second notification.
    await send_medication_reminders(
        _worker_ctx(), now=datetime(2026, 1, 5, 20, 3, tzinfo=IST)
    )
    await db.commit()
    notifs = await _med_reminder_notifications(db, patient_user.id)
    assert len(notifs) == 2
    assert {n.meta["timeslot"] for n in notifs} == {"08:00", "20:00"}

    # Next day, morning slot again → a fresh notification for that day.
    await send_medication_reminders(
        _worker_ctx(), now=datetime(2026, 1, 6, 8, 0, tzinfo=IST)
    )
    await db.commit()
    assert len(await _med_reminder_notifications(db, patient_user.id)) == 3


async def test_worker_skips_disabled_and_non_matching(
    patient_user: User, doctor_profile: Doctor, db: AsyncSession
):
    rx = await _make_prescription(db, patient_user.id, doctor_profile.id)
    await _make_reminder(db, patient_user.id, rx.id, ["09:00"], enabled=False)

    rx2 = await _make_prescription(db, patient_user.id, doctor_profile.id)
    await _make_reminder(db, patient_user.id, rx2.id, ["21:00"], enabled=True)

    await send_medication_reminders(
        _worker_ctx(), now=datetime(2026, 1, 5, 8, 0, tzinfo=IST)
    )
    await db.commit()

    assert await _med_reminder_notifications(db, patient_user.id) == []


async def test_worker_skips_expired_prescription(
    patient_user: User, doctor_profile: Doctor, db: AsyncSession
):
    rx = await _make_prescription(
        db,
        patient_user.id,
        doctor_profile.id,
        valid_until=date(2026, 1, 4),  # day before the run
    )
    await _make_reminder(db, patient_user.id, rx.id, ["08:00"])

    await send_medication_reminders(
        _worker_ctx(), now=datetime(2026, 1, 5, 8, 0, tzinfo=IST)
    )
    await db.commit()

    assert await _med_reminder_notifications(db, patient_user.id) == []


async def test_worker_soft_deleted_notification_still_dedupes(
    patient_user: User, doctor_profile: Doctor, db: AsyncSession
):
    """A dismissed (soft-deleted) banner must not trigger a same-slot resend."""
    rx = await _make_prescription(db, patient_user.id, doctor_profile.id)
    await _make_reminder(db, patient_user.id, rx.id, ["08:00"])

    now = datetime(2026, 1, 5, 8, 0, tzinfo=IST)
    await send_medication_reminders(_worker_ctx(), now=now)
    await db.commit()

    notif = (await _med_reminder_notifications(db, patient_user.id))[0]
    notif.deleted_at = datetime.now(tz=IST)
    await db.commit()

    await send_medication_reminders(_worker_ctx(), now=now)
    await db.commit()
    assert len(await _med_reminder_notifications(db, patient_user.id)) == 1


async def test_worker_skips_soft_deleted_reminder(
    patient_user: User, doctor_profile: Doctor, db: AsyncSession
):
    rx = await _make_prescription(db, patient_user.id, doctor_profile.id)
    reminder = await _make_reminder(db, patient_user.id, rx.id, ["08:00"])
    reminder.deleted_at = datetime.now(tz=IST)
    await db.commit()

    await send_medication_reminders(
        _worker_ctx(), now=datetime(2026, 1, 5, 8, 0, tzinfo=IST)
    )
    await db.commit()

    assert await _med_reminder_notifications(db, patient_user.id) == []
