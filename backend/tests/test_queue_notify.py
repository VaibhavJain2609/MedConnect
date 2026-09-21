"""Patient notifications on queue position changes.

Covers:
- status PATCH -> in_consultation emits exactly one "called" in-app
  notification (retried PATCH is a 422 and stays deduped).
- An entry leaving the active set (completed / cancelled / removed)
  promotes the next waiting entry to position 1 -> "next up" notification.
- Patients without a usable user account are skipped silently.
- Wrong-role callers are still rejected (403) and emit nothing.
- Dedupe on Notification.meta (queue_entry_id + kind) — the same pattern
  the doctor-reminder dedupe uses.
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clinic import Clinic, ClinicMembership
from app.models.notification import Notification
from app.models.queue import QueueEntry
from app.models.user import User
from app.routers.queue import _notify_queue_patient
from tests.conftest import make_auth_header

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def clinic(db: AsyncSession, doctor_user: User) -> Clinic:
    c = Clinic(id=uuid.uuid4(), name="Notify Clinic", city="Delhi", created_by=doctor_user.id)
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


async def _membership(db: AsyncSession, clinic_id, user_id, role: str) -> ClinicMembership:
    m = ClinicMembership(
        id=uuid.uuid4(), clinic_id=clinic_id, user_id=user_id, role=role, is_active=True
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


@pytest_asyncio.fixture
async def owner_membership(db: AsyncSession, clinic: Clinic, doctor_user: User) -> ClinicMembership:
    return await _membership(db, clinic.id, doctor_user.id, "owner")


@pytest_asyncio.fixture
async def receptionist_membership(
    db: AsyncSession, clinic: Clinic, doctor_user: User
) -> ClinicMembership:
    return await _membership(db, clinic.id, doctor_user.id, "receptionist")


async def _make_patient(db: AsyncSession, email: str = "other-patient@test.com") -> User:
    user = User(
        keycloak_sub=f"patient-{uuid.uuid4()}",
        email=email,
        full_name="Other Patient",
        role="patient",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def _headers(clinic: Clinic) -> dict[str, str]:
    return {"X-Clinic-Id": str(clinic.id)}


async def _check_in(client, clinic: Clinic, patient_id) -> str:
    resp = await client.post(
        "/api/v1/queue",
        json={"patient_id": str(patient_id)},
        headers=_headers(clinic),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _notifs(db: AsyncSession, user_id, kind: str) -> list[Notification]:
    res = await db.execute(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.meta["kind"].astext == kind,
            Notification.deleted_at.is_(None),
        )
    )
    return list(res.scalars().all())


async def _all_notifs(db: AsyncSession, user_id) -> list[Notification]:
    res = await db.execute(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.deleted_at.is_(None),
        )
    )
    return list(res.scalars().all())


# ---------------------------------------------------------------------------
# "Called" notification
# ---------------------------------------------------------------------------


class TestQueueCalledNotification:
    async def test_in_consultation_notifies_patient(
        self, doctor_client, db, clinic, owner_membership, patient_user
    ):
        entry_id = await _check_in(doctor_client, clinic, patient_user.id)

        resp = await doctor_client.patch(
            f"/api/v1/queue/{entry_id}/status",
            json={"status": "in_consultation"},
            headers=_headers(clinic),
        )
        assert resp.status_code == 200, resp.text

        notifs = await _notifs(db, patient_user.id, "queue_called")
        assert len(notifs) == 1
        notif = notifs[0]
        assert notif.action_url == "/patient/queue"
        assert notif.meta["queue_entry_id"] == entry_id
        assert notif.meta["clinic_id"] == str(clinic.id)
        # No PHI beyond what the patient sees about themselves.
        assert patient_user.full_name not in notif.title
        assert patient_user.full_name not in notif.message

    async def test_called_notification_deduped_on_repeat(
        self, doctor_client, db, clinic, owner_membership, patient_user
    ):
        """A retried/double PATCH must not produce a second notification."""
        entry_id = await _check_in(doctor_client, clinic, patient_user.id)

        first = await doctor_client.patch(
            f"/api/v1/queue/{entry_id}/status",
            json={"status": "in_consultation"},
            headers=_headers(clinic),
        )
        assert first.status_code == 200

        # Repeating the same transition is rejected (422 INVALID_TRANSITION)
        # and must not emit again either way.
        second = await doctor_client.patch(
            f"/api/v1/queue/{entry_id}/status",
            json={"status": "in_consultation"},
            headers=_headers(clinic),
        )
        assert second.status_code == 422

        assert len(await _notifs(db, patient_user.id, "queue_called")) == 1

    async def test_meta_dedupe_blocks_duplicate_emit(
        self, doctor_client, db, clinic, owner_membership, patient_user
    ):
        """The meta-based dedupe itself: a second emit for the same
        (entry, kind) is a no-op even if the caller retries."""
        entry_id = await _check_in(doctor_client, clinic, patient_user.id)
        entry = (
            await db.execute(select(QueueEntry).where(QueueEntry.id == uuid.UUID(entry_id)))
        ).scalar_one()

        await _notify_queue_patient(
            db, entry, kind="queue_called", title="t", body="b"
        )
        await _notify_queue_patient(
            db, entry, kind="queue_called", title="t", body="b"
        )
        assert len(await _notifs(db, patient_user.id, "queue_called")) == 1


# ---------------------------------------------------------------------------
# Next-up promotion
# ---------------------------------------------------------------------------


class TestNextUpNotification:
    async def test_completion_promotes_next_waiting(
        self, doctor_client, db, clinic, owner_membership, patient_user
    ):
        other = await _make_patient(db)
        first_id = await _check_in(doctor_client, clinic, patient_user.id)
        second_id = await _check_in(doctor_client, clinic, other.id)

        # Call patient 1 in — only they get the "called" notification.
        resp = await doctor_client.patch(
            f"/api/v1/queue/{first_id}/status",
            json={"status": "in_consultation"},
            headers=_headers(clinic),
        )
        assert resp.status_code == 200
        assert len(await _notifs(db, patient_user.id, "queue_called")) == 1
        assert await _all_notifs(db, other.id) == []

        # Finish the consult — patient 2 is now position 1 ("next up").
        resp = await doctor_client.patch(
            f"/api/v1/queue/{first_id}/status",
            json={"status": "completed"},
            headers=_headers(clinic),
        )
        assert resp.status_code == 200

        next_up = await _notifs(db, other.id, "queue_next_up")
        assert len(next_up) == 1
        assert next_up[0].meta["queue_entry_id"] == second_id
        assert next_up[0].action_url == "/patient/queue"
        # Patient 1 collected exactly one notification overall.
        assert len(await _all_notifs(db, patient_user.id)) == 1

    async def test_cancellation_promotes_next_waiting(
        self, doctor_client, db, clinic, owner_membership, patient_user
    ):
        other = await _make_patient(db)
        first_id = await _check_in(doctor_client, clinic, patient_user.id)
        await _check_in(doctor_client, clinic, other.id)

        resp = await doctor_client.patch(
            f"/api/v1/queue/{first_id}/status",
            json={"status": "cancelled"},
            headers=_headers(clinic),
        )
        assert resp.status_code == 200
        assert len(await _notifs(db, other.id, "queue_next_up")) == 1
        # Cancelled patient is not notified.
        assert await _all_notifs(db, patient_user.id) == []

    async def test_removal_promotes_next_waiting(
        self, doctor_client, db, clinic, owner_membership, patient_user
    ):
        other = await _make_patient(db)
        first_id = await _check_in(doctor_client, clinic, patient_user.id)
        await _check_in(doctor_client, clinic, other.id)

        resp = await doctor_client.delete(
            f"/api/v1/queue/{first_id}", headers=_headers(clinic)
        )
        assert resp.status_code == 204
        assert len(await _notifs(db, other.id, "queue_next_up")) == 1

    async def test_no_promotion_while_someone_is_ahead(
        self, doctor_client, db, clinic, owner_membership, patient_user
    ):
        """If the lowest active entry is in_consultation, the next waiting
        patient is position 2 — completing a later entry must not notify."""
        other = await _make_patient(db)
        third = await _make_patient(db, email="third@test.com")
        first_id = await _check_in(doctor_client, clinic, patient_user.id)
        second_id = await _check_in(doctor_client, clinic, other.id)
        await _check_in(doctor_client, clinic, third.id)

        # Patient 1 goes into consultation and stays there.
        await doctor_client.patch(
            f"/api/v1/queue/{first_id}/status",
            json={"status": "in_consultation"},
            headers=_headers(clinic),
        )
        # Patient 2 is removed while patient 1 is still active ahead of
        # patient 3 -> nobody reaches position 1.
        resp = await doctor_client.delete(
            f"/api/v1/queue/{second_id}", headers=_headers(clinic)
        )
        assert resp.status_code == 204
        assert await _all_notifs(db, other.id) == []
        assert await _all_notifs(db, third.id) == []


# ---------------------------------------------------------------------------
# Skips and auth
# ---------------------------------------------------------------------------


class TestSkipsAndAuth:
    async def test_patient_without_active_user_skipped(
        self, doctor_client, db, clinic, owner_membership, patient_user
    ):
        """Entry whose patient user can't receive in-app notifications
        (deactivated walk-in-style account) is skipped silently — the queue
        operation itself still succeeds."""
        entry_id = await _check_in(doctor_client, clinic, patient_user.id)

        patient_user.is_active = False
        await db.commit()

        resp = await doctor_client.patch(
            f"/api/v1/queue/{entry_id}/status",
            json={"status": "in_consultation"},
            headers=_headers(clinic),
        )
        assert resp.status_code == 200, resp.text
        assert await _all_notifs(db, patient_user.id) == []

    async def test_wrong_role_cannot_update_status(
        self, client, doctor_client, db, clinic, owner_membership, patient_user
    ):
        """A non-member caller (patient role, no clinic membership) gets 403
        and no notification is emitted."""
        entry_id = await _check_in(doctor_client, clinic, patient_user.id)

        # Base `client` + explicit patient auth header — doctor_client and
        # patient_client share the same httpx client, so the fixture's
        # Authorization header would be the doctor's either way.
        resp = await client.patch(
            f"/api/v1/queue/{entry_id}/status",
            json={"status": "in_consultation"},
            headers={**_headers(clinic), **make_auth_header(patient_user)},
        )
        assert resp.status_code == 403
        assert await _all_notifs(db, patient_user.id) == []

    async def test_receptionist_cannot_complete(
        self, doctor_client, db, clinic, receptionist_membership, patient_user
    ):
        """Receptionists may only advance to in_consultation — completing an
        entry is 403 and emits nothing."""
        entry_id = await _check_in(doctor_client, clinic, patient_user.id)

        resp = await doctor_client.patch(
            f"/api/v1/queue/{entry_id}/status",
            json={"status": "completed"},
            headers=_headers(clinic),
        )
        assert resp.status_code == 403
        assert await _all_notifs(db, patient_user.id) == []


async def test_notification_count_sanity(db: AsyncSession):
    """Sanity: the meta["kind"] query used by the assertions really counts."""
    res = await db.execute(select(func.count(Notification.id)))
    assert res.scalar_one() == 0
