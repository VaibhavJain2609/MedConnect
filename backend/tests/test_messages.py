"""Coverage for the secure patient↔clinic messaging router.

Covers:
- POST   /api/v1/messages/threads            — approved-link gate, first message
- GET    /api/v1/messages/threads            — patient list + clinic-scoped list
- GET    /api/v1/messages/threads/unread-count — per-side badge counts
- GET    /api/v1/messages/threads/{id}/messages — participant reads + seen cursor
- POST   /api/v1/messages/threads/{id}/messages — replies, closed-thread 409
- PATCH  /api/v1/messages/threads/{id}/close    — either participant
- PATCH  /api/v1/messages/threads/{id}/reopen   — patient only
- Participant enforcement: other patient 404, non-member doctor 403, member
  of a different clinic 404.
- Notification emitted to the other side on new messages.

NOTE: ``patient_client``/``doctor_client`` share the same ``AsyncClient`` as
``client`` — tests exercising both roles pass explicit ``headers=`` on every
request via ``_hdr()`` so the Authorization/X-Clinic-Id values are always
deterministic.
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clinic import Clinic, ClinicMembership
from app.models.doctor import Doctor
from app.models.notification import Notification
from app.models.patient_link import PatientClinicLink
from app.models.user import User
from tests.conftest import make_auth_header

pytestmark = pytest.mark.asyncio

API = "/api/v1/messages"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def clinic(db: AsyncSession, doctor_user: User) -> Clinic:
    c = Clinic(id=uuid.uuid4(), name="Msg Clinic", city="Delhi", created_by=doctor_user.id)
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


@pytest_asyncio.fixture
async def clinic_membership(db: AsyncSession, clinic: Clinic, doctor_user: User):
    m = ClinicMembership(
        id=uuid.uuid4(),
        clinic_id=clinic.id,
        user_id=doctor_user.id,
        role="owner",
        is_active=True,
    )
    db.add(m)
    await db.commit()
    return m


@pytest_asyncio.fixture
async def approved_link(
    db: AsyncSession, patient_user: User, clinic: Clinic, doctor_user: User
) -> PatientClinicLink:
    link = PatientClinicLink(
        id=uuid.uuid4(),
        patient_id=patient_user.id,
        clinic_id=clinic.id,
        linked_by=doctor_user.id,
        consent_status="approved",
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return link


@pytest_asyncio.fixture
async def other_patient(db: AsyncSession) -> User:
    u = User(
        keycloak_sub=f"patient-{uuid.uuid4()}",
        email=f"{uuid.uuid4().hex[:8]}@test.com",
        full_name="Other Patient",
        role="patient",
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


def _hdr(user: User, clinic_id=None, roles=None) -> dict:
    """Explicit per-request headers (Authorization + optional X-Clinic-Id)."""
    h = make_auth_header(user, roles=roles)
    if clinic_id is not None:
        h["X-Clinic-Id"] = str(clinic_id)
    return h


async def _create_thread(client, user: User, clinic_id, subject="Help", body="Hello clinic"):
    res = await client.post(
        f"{API}/threads",
        json={"clinic_id": str(clinic_id), "subject": subject, "body": body},
        headers=_hdr(user),
    )
    assert res.status_code == 201, res.text
    return res.json()


# ---------------------------------------------------------------------------
# Thread creation
# ---------------------------------------------------------------------------


async def test_patient_creates_thread_with_first_message(
    client, patient_user, clinic, approved_link, clinic_membership, db
):
    thread = await _create_thread(client, patient_user, clinic.id, "Fever", "I have a fever")
    assert thread["subject"] == "Fever"
    assert thread["status"] == "open"
    assert thread["clinic_id"] == str(clinic.id)
    assert thread["clinic_name"] == "Msg Clinic"
    assert thread["last_message_preview"] == "I have a fever"

    res = await client.get(
        f"{API}/threads/{thread['id']}/messages", headers=_hdr(patient_user)
    )
    assert res.status_code == 200
    msgs = res.json()["data"]
    assert len(msgs) == 1
    assert msgs[0]["body"] == "I have a fever"
    assert msgs[0]["sender_id"] == str(patient_user.id)
    assert msgs[0]["sender_name"] == "Patient User"


async def test_create_thread_requires_approved_link(client, clinic, db, patient_user, doctor_user):
    # No link at all → 403
    res = await client.post(
        f"{API}/threads",
        json={"clinic_id": str(clinic.id), "subject": "Hi", "body": "msg"},
        headers=_hdr(patient_user),
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "NOT_LINKED"

    # Pending link → still 403
    link = PatientClinicLink(
        id=uuid.uuid4(),
        patient_id=patient_user.id,
        clinic_id=clinic.id,
        linked_by=doctor_user.id,
        consent_status="pending",
    )
    db.add(link)
    await db.commit()
    res = await client.post(
        f"{API}/threads",
        json={"clinic_id": str(clinic.id), "subject": "Hi", "body": "msg"},
        headers=_hdr(patient_user),
    )
    assert res.status_code == 403


async def test_create_thread_unknown_clinic_404(client, patient_user):
    res = await client.post(
        f"{API}/threads",
        json={"clinic_id": str(uuid.uuid4()), "subject": "Hi", "body": "msg"},
        headers=_hdr(patient_user),
    )
    assert res.status_code == 404


async def test_doctor_cannot_create_thread(client, doctor_user, clinic):
    res = await client.post(
        f"{API}/threads",
        json={"clinic_id": str(clinic.id), "subject": "Hi", "body": "msg"},
        headers=_hdr(doctor_user, clinic.id),
    )
    assert res.status_code == 403


# ---------------------------------------------------------------------------
# Listing + participation
# ---------------------------------------------------------------------------


async def test_patient_lists_only_own_threads(
    client, patient_user, other_patient, clinic, approved_link, clinic_membership, db, doctor_user
):
    await _create_thread(client, patient_user, clinic.id, "Mine", "mine")

    # Another patient's thread on the same clinic must not appear.
    link2 = PatientClinicLink(
        id=uuid.uuid4(),
        patient_id=other_patient.id,
        clinic_id=clinic.id,
        linked_by=doctor_user.id,
        consent_status="approved",
    )
    db.add(link2)
    await db.commit()
    await _create_thread(client, other_patient, clinic.id, "Theirs", "theirs")

    res = await client.get(f"{API}/threads", headers=_hdr(patient_user))
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data) == 1
    assert data[0]["subject"] == "Mine"
    assert data[0]["clinic_name"] == "Msg Clinic"


async def test_clinic_scoped_listing(
    client, patient_user, doctor_user, clinic, approved_link, clinic_membership, db
):
    await _create_thread(client, patient_user, clinic.id, "InScope", "hello")

    # A second clinic the doctor also belongs to has no threads.
    clinic2 = Clinic(id=uuid.uuid4(), name="Other Clinic", created_by=doctor_user.id)
    db.add(clinic2)
    await db.flush()
    db.add(
        ClinicMembership(
            id=uuid.uuid4(),
            clinic_id=clinic2.id,
            user_id=doctor_user.id,
            role="owner",
            is_active=True,
        )
    )
    await db.commit()

    res = await client.get(f"{API}/threads", headers=_hdr(doctor_user, clinic.id))
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data) == 1
    assert data[0]["subject"] == "InScope"
    assert data[0]["patient_name"] == "Patient User"

    res2 = await client.get(f"{API}/threads", headers=_hdr(doctor_user, clinic2.id))
    assert res2.status_code == 200
    assert res2.json()["data"] == []


async def test_other_patient_cannot_read_or_reply(
    client, patient_user, other_patient, clinic, approved_link, clinic_membership
):
    thread = await _create_thread(client, patient_user, clinic.id)

    res = await client.get(
        f"{API}/threads/{thread['id']}/messages", headers=_hdr(other_patient)
    )
    assert res.status_code == 404
    res = await client.post(
        f"{API}/threads/{thread['id']}/messages",
        json={"body": "sneaky"},
        headers=_hdr(other_patient),
    )
    assert res.status_code == 404
    res = await client.patch(
        f"{API}/threads/{thread['id']}/close", headers=_hdr(other_patient)
    )
    assert res.status_code == 404


async def test_doctor_not_in_clinic_forbidden(
    client, patient_user, clinic, approved_link, db
):
    """A doctor with no membership in the thread's clinic gets 403 from the
    clinic-context dependency, and 404 on the patient path (no header)."""
    thread = await _create_thread(client, patient_user, clinic.id)

    outsider = User(
        keycloak_sub=f"doctor-{uuid.uuid4()}",
        email=f"{uuid.uuid4().hex[:8]}@test.com",
        full_name="Outsider Doctor",
        role="doctor",
    )
    db.add(outsider)
    await db.flush()
    db.add(Doctor(id=uuid.uuid4(), user_id=outsider.id, verified=True, onboarding_step="completed"))
    await db.commit()

    # X-Clinic-Id naming a clinic they don't belong to → 403.
    res = await client.get(
        f"{API}/threads/{thread['id']}/messages", headers=_hdr(outsider, clinic.id)
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "NOT_CLINIC_MEMBER"

    # Clinic-scoped list also 403.
    res = await client.get(f"{API}/threads", headers=_hdr(outsider, clinic.id))
    assert res.status_code == 403

    # Without clinic context they take the patient path → 404.
    res = await client.get(
        f"{API}/threads/{thread['id']}/messages", headers=_hdr(outsider)
    )
    assert res.status_code == 404


async def test_member_of_other_clinic_gets_404(
    client, patient_user, doctor_user, clinic, approved_link, clinic_membership, db
):
    """A doctor who IS a clinic member — but of a DIFFERENT clinic — gets
    404 on the thread (valid membership, wrong clinic → no existence leak)."""
    thread = await _create_thread(client, patient_user, clinic.id)

    other_clinic = Clinic(id=uuid.uuid4(), name="Elsewhere", created_by=doctor_user.id)
    db.add(other_clinic)
    await db.flush()
    db.add(
        ClinicMembership(
            id=uuid.uuid4(),
            clinic_id=other_clinic.id,
            user_id=doctor_user.id,
            role="doctor",
            is_active=True,
        )
    )
    await db.commit()

    res = await client.get(
        f"{API}/threads/{thread['id']}/messages",
        headers=_hdr(doctor_user, other_clinic.id),
    )
    assert res.status_code == 404
    res = await client.post(
        f"{API}/threads/{thread['id']}/messages",
        json={"body": "wrong clinic"},
        headers=_hdr(doctor_user, other_clinic.id),
    )
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Replies, close, reopen
# ---------------------------------------------------------------------------


async def test_staff_reply_and_patient_reads(
    client, patient_user, doctor_user, clinic, approved_link, clinic_membership
):
    thread = await _create_thread(client, patient_user, clinic.id)

    res = await client.post(
        f"{API}/threads/{thread['id']}/messages",
        json={"body": "Take rest and fluids"},
        headers=_hdr(doctor_user, clinic.id),
    )
    assert res.status_code == 201, res.text
    assert res.json()["sender_id"] == str(doctor_user.id)

    res = await client.get(
        f"{API}/threads/{thread['id']}/messages", headers=_hdr(patient_user)
    )
    assert res.status_code == 200
    msgs = res.json()["data"]
    assert [m["body"] for m in msgs] == ["Hello clinic", "Take rest and fluids"]


async def test_close_blocks_replies_and_patient_reopens(
    client, patient_user, doctor_user, clinic, approved_link, clinic_membership
):
    thread = await _create_thread(client, patient_user, clinic.id)
    tid = thread["id"]

    # Clinic staff closes.
    res = await client.patch(
        f"{API}/threads/{tid}/close", headers=_hdr(doctor_user, clinic.id)
    )
    assert res.status_code == 200
    assert res.json()["status"] == "closed"

    # Replies rejected with 409 on both sides.
    res = await client.post(
        f"{API}/threads/{tid}/messages", json={"body": "still here"}, headers=_hdr(patient_user)
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "THREAD_CLOSED"
    res = await client.post(
        f"{API}/threads/{tid}/messages",
        json={"body": "staff too"},
        headers=_hdr(doctor_user, clinic.id),
    )
    assert res.status_code == 409

    # Staff cannot reopen (patient-only endpoint → 403).
    res = await client.patch(
        f"{API}/threads/{tid}/reopen", headers=_hdr(doctor_user, clinic.id)
    )
    assert res.status_code == 403

    # Patient reopens → replies work again.
    res = await client.patch(f"{API}/threads/{tid}/reopen", headers=_hdr(patient_user))
    assert res.status_code == 200
    assert res.json()["status"] == "open"
    res = await client.post(
        f"{API}/threads/{tid}/messages", json={"body": "thanks"}, headers=_hdr(patient_user)
    )
    assert res.status_code == 201


async def test_patient_can_close_own_thread(
    client, patient_user, clinic, approved_link, clinic_membership
):
    thread = await _create_thread(client, patient_user, clinic.id)
    res = await client.patch(
        f"{API}/threads/{thread['id']}/close", headers=_hdr(patient_user)
    )
    assert res.status_code == 200
    assert res.json()["status"] == "closed"


async def test_status_filter(
    client, patient_user, clinic, approved_link, clinic_membership
):
    t1 = await _create_thread(client, patient_user, clinic.id, "Open one")
    t2 = await _create_thread(client, patient_user, clinic.id, "Closed one")
    await client.patch(f"{API}/threads/{t2['id']}/close", headers=_hdr(patient_user))

    res = await client.get(
        f"{API}/threads", params={"status_filter": "open"}, headers=_hdr(patient_user)
    )
    assert {t["subject"] for t in res.json()["data"]} == {"Open one"}
    res = await client.get(
        f"{API}/threads", params={"status_filter": "closed"}, headers=_hdr(patient_user)
    )
    assert {t["subject"] for t in res.json()["data"]} == {"Closed one"}


# ---------------------------------------------------------------------------
# Unread counts + notifications
# ---------------------------------------------------------------------------


async def test_unread_counts_both_sides(
    client, patient_user, doctor_user, clinic, approved_link, clinic_membership, db
):
    thread = await _create_thread(client, patient_user, clinic.id)
    tid = thread["id"]

    # NOTE: ``await db.commit()`` between requests mirrors production
    # transaction boundaries. The test session keeps ONE transaction open,
    # so every ``server_default=func.now()`` (CURRENT_TIMESTAMP = tx start)
    # would otherwise be identical across requests and created_at would
    # never be strictly greater than a last_seen cursor set later.

    # Patient just created it → their unread is 0; clinic sees 1 unread msg.
    res = await client.get(f"{API}/threads/unread-count", headers=_hdr(patient_user))
    assert res.json() == {"unread_threads": 0, "unread_messages": 0}

    res = await client.get(f"{API}/threads/unread-count", headers=_hdr(doctor_user, clinic.id))
    assert res.json() == {"unread_threads": 1, "unread_messages": 1}

    # Staff reads the thread → clinic unread clears.
    res = await client.get(f"{API}/threads/{tid}/messages", headers=_hdr(doctor_user, clinic.id))
    assert res.status_code == 200
    await db.commit()
    res = await client.get(f"{API}/threads/unread-count", headers=_hdr(doctor_user, clinic.id))
    assert res.json() == {"unread_threads": 0, "unread_messages": 0}

    # Staff replies → patient unread grows to 1.
    await client.post(
        f"{API}/threads/{tid}/messages",
        json={"body": "reply one"},
        headers=_hdr(doctor_user, clinic.id),
    )
    await db.commit()
    res = await client.get(f"{API}/threads/unread-count", headers=_hdr(patient_user))
    assert res.json() == {"unread_threads": 1, "unread_messages": 1}

    # Patient replies → their own cursor moves past the staff reply, and the
    # new patient message bumps the clinic-side unread.
    await client.post(
        f"{API}/threads/{tid}/messages",
        json={"body": "thanks!"},
        headers=_hdr(patient_user),
    )
    await db.commit()
    res = await client.get(f"{API}/threads/unread-count", headers=_hdr(patient_user))
    assert res.json() == {"unread_threads": 0, "unread_messages": 0}
    res = await client.get(f"{API}/threads/unread-count", headers=_hdr(doctor_user, clinic.id))
    assert res.json() == {"unread_threads": 1, "unread_messages": 1}


async def test_thread_list_includes_unread_count(
    client, patient_user, doctor_user, clinic, approved_link, clinic_membership
):
    await _create_thread(client, patient_user, clinic.id)
    res = await client.get(f"{API}/threads", headers=_hdr(doctor_user, clinic.id))
    assert res.json()["data"][0]["unread_count"] == 1
    res = await client.get(f"{API}/threads", headers=_hdr(patient_user))
    assert res.json()["data"][0]["unread_count"] == 0


async def test_notification_emitted_to_other_side(
    client, patient_user, doctor_user, clinic, approved_link, clinic_membership, db
):
    # Patient creates thread → clinic staff notified with doctor deep link.
    thread = await _create_thread(client, patient_user, clinic.id, "Rx question", "Is this safe?")
    tid = thread["id"]

    res = await db.execute(
        select(Notification).where(
            Notification.user_id == doctor_user.id,
            Notification.type == "message",
        )
    )
    notifs = res.scalars().all()
    assert len(notifs) == 1
    assert notifs[0].action_url == f"/doctor/messages?thread={tid}"
    assert notifs[0].meta["thread_id"] == tid
    assert "Rx question" in notifs[0].message

    # Staff replies → patient notified with patient-portal deep link.
    await client.post(
        f"{API}/threads/{tid}/messages",
        json={"body": "Yes, with food"},
        headers=_hdr(doctor_user, clinic.id),
    )
    res = await db.execute(
        select(Notification).where(
            Notification.user_id == patient_user.id,
            Notification.type == "message",
        )
    )
    pnotifs = res.scalars().all()
    assert len(pnotifs) == 1
    assert pnotifs[0].action_url == f"/patient/messages?thread={tid}"
    assert pnotifs[0].meta["thread_id"] == tid


async def test_unauthenticated_rejected(client):
    res = await client.get(f"{API}/threads")
    assert res.status_code == 401
    res = await client.get(f"{API}/threads/unread-count")
    assert res.status_code == 401
    res = await client.post(
        f"{API}/threads",
        json={"clinic_id": str(uuid.uuid4()), "subject": "s", "body": "b"},
    )
    assert res.status_code == 401


async def test_messages_immutable_no_edit_route(
    client, patient_user, clinic, approved_link, clinic_membership
):
    """No PATCH/PUT on individual messages — method not allowed."""
    thread = await _create_thread(client, patient_user, clinic.id)
    res = await client.get(
        f"{API}/threads/{thread['id']}/messages", headers=_hdr(patient_user)
    )
    msg_id = res.json()["data"][0]["id"]
    res = await client.patch(
        f"{API}/threads/{thread['id']}/messages/{msg_id}",
        json={"body": "edited"},
        headers=_hdr(patient_user),
    )
    assert res.status_code in (404, 405)
