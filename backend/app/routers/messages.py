"""Secure patient↔clinic messaging.

Threads live under /api/v1/messages/threads and are strictly
participant-scoped — there is deliberately no admin list endpoint.

- POST   /threads                     — patient starts a thread to a clinic
                                        they have an APPROVED PatientClinicLink
                                        with; the first message body rides in
                                        the same request.
- GET    /threads                     — patient (no X-Clinic-Id): own threads.
                                        clinic staff (X-Clinic-Id + active
                                        membership): that clinic's threads.
- GET    /threads/unread-count        — badge counts for the caller's side.
- GET    /threads/{id}/messages       — participants only; marks the caller's
                                        side seen (clears their unread count).
- POST   /threads/{id}/messages       — participants only; 409 on a closed
                                        thread. Notifies the other side.
- PATCH  /threads/{id}/close          — either participant.
- PATCH  /threads/{id}/reopen         — patient only.

Read state: ``patient_last_seen_at`` / ``clinic_last_seen_at`` per-side
cursors on the thread (clinic cursor is shared by all staff of the clinic).
Unread = messages from the other side created after the caller's cursor.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_active_clinic, get_current_user, require_patient
from app.models.clinic import Clinic, ClinicMembership
from app.models.message import MessageThread, ThreadMessage
from app.models.notification import NotificationType
from app.models.patient_link import PatientClinicLink
from app.models.user import User
from app.services.notification_service import create_notification, create_notifications_bulk

router = APIRouter(prefix="/api/v1/messages", tags=["messages"])

MAX_BODY = 10_000


def _err(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message}},
    )


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ThreadCreate(BaseModel):
    clinic_id: uuid.UUID
    subject: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1, max_length=MAX_BODY)


class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=MAX_BODY)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _serialize_message(m: ThreadMessage, sender_name: str | None = None) -> dict:
    return {
        "id": str(m.id),
        "thread_id": str(m.thread_id),
        "sender_id": str(m.sender_id),
        "sender_name": sender_name,
        "body": m.body,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


def _serialize_thread(
    t: MessageThread,
    *,
    clinic_name: str | None = None,
    patient_name: str | None = None,
    unread: int = 0,
    last: ThreadMessage | None = None,
) -> dict:
    return {
        "id": str(t.id),
        "patient_id": str(t.patient_id),
        "patient_name": patient_name,
        "clinic_id": str(t.clinic_id) if t.clinic_id else None,
        "clinic_name": clinic_name,
        "subject": t.subject,
        "status": t.status,
        "unread_count": unread,
        "last_message_preview": (last.body[:120] if last else None),
        "last_message_at": last.created_at.isoformat() if last and last.created_at else None,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


async def _get_thread(db: AsyncSession, thread_id: uuid.UUID) -> MessageThread:
    res = await db.execute(
        select(MessageThread).where(
            MessageThread.id == thread_id,
            MessageThread.deleted_at.is_(None),
        )
    )
    thread = res.scalar_one_or_none()
    if thread is None:
        raise _err(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Thread not found")
    return thread


async def _participant_thread(
    db: AsyncSession,
    thread_id: uuid.UUID,
    user: User,
    clinic_ctx: tuple[uuid.UUID, str] | None,
) -> tuple[MessageThread, str]:
    """Fetch a thread the caller participates in.

    Returns (thread, side) where side is "patient" or "clinic". Callers with
    an X-Clinic-Id context take the clinic path (membership already verified
    by get_active_clinic); everyone else takes the patient path. Wrong-side
    access is a 404 so thread ids don't leak across patients/clinics.
    """
    thread = await _get_thread(db, thread_id)
    if clinic_ctx is not None:
        clinic_id, _role = clinic_ctx
        if thread.clinic_id != clinic_id:
            raise _err(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Thread not found")
        return thread, "clinic"
    if thread.patient_id != user.id:
        raise _err(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Thread not found")
    return thread, "patient"


async def _clinic_member_ids(db: AsyncSession, clinic_id: uuid.UUID) -> list[uuid.UUID]:
    res = await db.execute(
        select(ClinicMembership.user_id).where(
            ClinicMembership.clinic_id == clinic_id,
            ClinicMembership.is_active.is_(True),
            ClinicMembership.deleted_at.is_(None),
        )
    )
    return list(res.scalars().all())


async def _unread_map(
    db: AsyncSession, thread_ids: list[uuid.UUID], side: str
) -> dict[uuid.UUID, int]:
    """Per-thread count of messages from the OTHER side newer than the
    caller-side read cursor."""
    if not thread_ids:
        return {}
    if side == "patient":
        seen_col = MessageThread.patient_last_seen_at
        # Anything not sent by the patient came from the clinic side.
        other_side = ThreadMessage.sender_id != MessageThread.patient_id
    else:
        seen_col = MessageThread.clinic_last_seen_at
        other_side = ThreadMessage.sender_id == MessageThread.patient_id
    stmt = (
        select(ThreadMessage.thread_id, func.count(ThreadMessage.id))
        .join(MessageThread, MessageThread.id == ThreadMessage.thread_id)
        .where(
            ThreadMessage.thread_id.in_(thread_ids),
            ThreadMessage.deleted_at.is_(None),
            other_side,
            or_(seen_col.is_(None), ThreadMessage.created_at > seen_col),
        )
        .group_by(ThreadMessage.thread_id)
    )
    res = await db.execute(stmt)
    return {row[0]: row[1] for row in res.all()}


async def _last_messages(
    db: AsyncSession, thread_ids: list[uuid.UUID]
) -> dict[uuid.UUID, ThreadMessage]:
    if not thread_ids:
        return {}
    latest = (
        select(
            ThreadMessage.thread_id,
            func.max(ThreadMessage.created_at).label("mx"),
        )
        .where(
            ThreadMessage.thread_id.in_(thread_ids),
            ThreadMessage.deleted_at.is_(None),
        )
        .group_by(ThreadMessage.thread_id)
        .subquery()
    )
    stmt = select(ThreadMessage).join(
        latest,
        (ThreadMessage.thread_id == latest.c.thread_id)
        & (ThreadMessage.created_at == latest.c.mx),
    )
    res = await db.execute(stmt)
    return {m.thread_id: m for m in res.scalars().all()}


async def _thread_list_payload(
    db: AsyncSession, threads: list[MessageThread], side: str
) -> list[dict]:
    """Serialize threads with counterpart names, unread counts and previews."""
    thread_ids = [t.id for t in threads]
    unread = await _unread_map(db, thread_ids, side)
    lasts = await _last_messages(db, thread_ids)

    clinic_ids = {t.clinic_id for t in threads if t.clinic_id}
    patient_ids = {t.patient_id for t in threads}

    clinic_names: dict[uuid.UUID, str] = {}
    if clinic_ids:
        res = await db.execute(select(Clinic.id, Clinic.name).where(Clinic.id.in_(clinic_ids)))
        clinic_names = {row[0]: row[1] for row in res.all()}

    patient_names: dict[uuid.UUID, str] = {}
    if patient_ids:
        res = await db.execute(
            select(User.id, User.full_name).where(User.id.in_(patient_ids))
        )
        patient_names = {row[0]: row[1] for row in res.all()}

    return [
        _serialize_thread(
            t,
            clinic_name=clinic_names.get(t.clinic_id) if t.clinic_id else None,
            patient_name=patient_names.get(t.patient_id),
            unread=unread.get(t.id, 0),
            last=lasts.get(t.id),
        )
        for t in threads
    ]


async def _notify_new_message(
    db: AsyncSession,
    thread: MessageThread,
    sender: User,
    side: str,
    preview: str,
) -> None:
    """Notify the OTHER side of a new message (deep-link into the thread)."""
    sender_name = sender.full_name or "Someone"
    snippet = preview if len(preview) <= 140 else preview[:137] + "..."
    if side == "patient":
        # Patient sent → notify all active staff of the thread's clinic.
        if thread.clinic_id is None:
            return
        member_ids = [uid for uid in await _clinic_member_ids(db, thread.clinic_id) if uid != sender.id]
        if not member_ids:
            return
        await create_notifications_bulk(
            db=db,
            user_ids=member_ids,
            notif_type=NotificationType.MESSAGE.value,
            title=f"New message from {sender_name}",
            body=f"{thread.subject}: {snippet}",
            action_url=f"/doctor/messages?thread={thread.id}",
            metadata={"thread_id": str(thread.id)},
        )
    else:
        # Clinic staff sent → notify the patient.
        await create_notification(
            db=db,
            user_id=thread.patient_id,
            notif_type=NotificationType.MESSAGE.value,
            title=f"New message about “{thread.subject}”",
            body=snippet,
            action_url=f"/patient/messages?thread={thread.id}",
            metadata={"thread_id": str(thread.id)},
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/threads", status_code=status.HTTP_201_CREATED)
async def create_thread(
    req: ThreadCreate,
    user: User = Depends(require_patient),
    db: AsyncSession = Depends(get_db),
):
    """Start a thread with a clinic — requires an APPROVED PatientClinicLink."""
    clinic = await db.get(Clinic, req.clinic_id)
    if clinic is None or clinic.deleted_at is not None:
        raise _err(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Clinic not found")

    link_res = await db.execute(
        select(PatientClinicLink).where(
            PatientClinicLink.patient_id == user.id,
            PatientClinicLink.clinic_id == req.clinic_id,
            PatientClinicLink.consent_status == "approved",
            PatientClinicLink.deleted_at.is_(None),
        )
    )
    if link_res.scalar_one_or_none() is None:
        raise _err(
            status.HTTP_403_FORBIDDEN,
            "NOT_LINKED",
            "You must have an approved link with this clinic to message it",
        )

    now = datetime.now(timezone.utc)
    thread = MessageThread(
        patient_id=user.id,
        clinic_id=req.clinic_id,
        subject=req.subject,
        status="open",
        patient_last_seen_at=now,
    )
    db.add(thread)
    await db.flush()

    message = ThreadMessage(thread_id=thread.id, sender_id=user.id, body=req.body)
    db.add(message)
    await db.flush()
    await db.refresh(thread)

    await _notify_new_message(db, thread, user, "patient", req.body)

    return _serialize_thread(thread, clinic_name=clinic.name, last=message)


# NOTE: /threads/unread-count must be declared BEFORE /threads/{thread_id}
# routes — otherwise the literal "unread-count" is parsed as a UUID path
# param and the badge endpoint is unreachable.


@router.get("/threads/unread-count")
async def unread_count(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    clinic_ctx: tuple[uuid.UUID, str] | None = Depends(get_active_clinic),
):
    """Unread badge counts for the caller's side.

    Patient (no X-Clinic-Id): across their own threads. Clinic staff
    (X-Clinic-Id): across that clinic's threads, using the shared clinic
    read cursor.
    """
    side = "clinic" if clinic_ctx is not None else "patient"
    stmt = select(MessageThread.id).where(MessageThread.deleted_at.is_(None))
    if side == "clinic":
        stmt = stmt.where(MessageThread.clinic_id == clinic_ctx[0])
    else:
        stmt = stmt.where(MessageThread.patient_id == user.id)
    res = await db.execute(stmt)
    thread_ids = list(res.scalars().all())

    unread = await _unread_map(db, thread_ids, side)
    return {
        "unread_threads": len(unread),
        "unread_messages": sum(unread.values()),
    }


@router.get("/threads")
async def list_threads(
    status_filter: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    clinic_ctx: tuple[uuid.UUID, str] | None = Depends(get_active_clinic),
):
    """List threads. With X-Clinic-Id → that clinic's inbox (membership
    enforced by get_active_clinic). Without → the caller's own patient
    threads. No admin/global view — blast radius stays per-participant."""
    side = "clinic" if clinic_ctx is not None else "patient"
    stmt = (
        select(MessageThread)
        .where(MessageThread.deleted_at.is_(None))
        .order_by(MessageThread.updated_at.desc())
        .limit(200)
    )
    if side == "clinic":
        stmt = stmt.where(MessageThread.clinic_id == clinic_ctx[0])
    else:
        stmt = stmt.where(MessageThread.patient_id == user.id)
    if status_filter in ("open", "closed"):
        stmt = stmt.where(MessageThread.status == status_filter)

    res = await db.execute(stmt)
    threads = list(res.scalars().all())
    return {"data": await _thread_list_payload(db, threads, side)}


@router.get("/threads/{thread_id}/messages")
async def list_messages(
    thread_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    clinic_ctx: tuple[uuid.UUID, str] | None = Depends(get_active_clinic),
):
    """Message history for a participant. Reading marks the caller's side
    seen (moves the read cursor past the latest message)."""
    thread, side = await _participant_thread(db, thread_id, user, clinic_ctx)

    res = await db.execute(
        select(ThreadMessage)
        .where(
            ThreadMessage.thread_id == thread.id,
            ThreadMessage.deleted_at.is_(None),
        )
        .order_by(ThreadMessage.created_at.asc())
        .limit(500)
    )
    messages = list(res.scalars().all())

    sender_ids = {m.sender_id for m in messages}
    sender_names: dict[uuid.UUID, str] = {}
    if sender_ids:
        names = await db.execute(
            select(User.id, User.full_name).where(User.id.in_(sender_ids))
        )
        sender_names = {row[0]: row[1] for row in names.all()}

    # Mark the caller's side as seen — clears their unread count.
    now = datetime.now(timezone.utc)
    if side == "patient":
        thread.patient_last_seen_at = now
    else:
        thread.clinic_last_seen_at = now
    await db.flush()
    # refresh: onupdate expires updated_at on flush; serializing an expired
    # attr would trigger lazy IO (MissingGreenlet in async context).
    await db.refresh(thread)

    return {
        "thread": _serialize_thread(thread),
        "data": [
            _serialize_message(m, sender_names.get(m.sender_id)) for m in messages
        ],
    }


@router.post("/threads/{thread_id}/messages", status_code=status.HTTP_201_CREATED)
async def post_message(
    thread_id: uuid.UUID,
    req: MessageCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    clinic_ctx: tuple[uuid.UUID, str] | None = Depends(get_active_clinic),
):
    """Reply in a thread. Participants only; closed threads reject with 409."""
    thread, side = await _participant_thread(db, thread_id, user, clinic_ctx)

    if thread.status == "closed":
        raise _err(
            status.HTTP_409_CONFLICT,
            "THREAD_CLOSED",
            "This conversation is closed",
        )

    now = datetime.now(timezone.utc)
    message = ThreadMessage(thread_id=thread.id, sender_id=user.id, body=req.body)
    db.add(message)

    # Sending implies the sender has seen everything up to now.
    if side == "patient":
        thread.patient_last_seen_at = now
    else:
        thread.clinic_last_seen_at = now

    await db.flush()
    await db.refresh(message)

    await _notify_new_message(db, thread, user, side, req.body)

    return _serialize_message(message, user.full_name)


@router.patch("/threads/{thread_id}/close")
async def close_thread(
    thread_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    clinic_ctx: tuple[uuid.UUID, str] | None = Depends(get_active_clinic),
):
    """Close a thread — allowed by either participant. Idempotent."""
    thread, _side = await _participant_thread(db, thread_id, user, clinic_ctx)
    thread.status = "closed"
    await db.flush()
    await db.refresh(thread)  # onupdate expires updated_at
    return _serialize_thread(thread)


@router.patch("/threads/{thread_id}/reopen")
async def reopen_thread(
    thread_id: uuid.UUID,
    user: User = Depends(require_patient),
    db: AsyncSession = Depends(get_db),
):
    """Reopen a closed thread — patient only (clinic staff get 403 via
    require_patient)."""
    thread = await _get_thread(db, thread_id)
    if thread.patient_id != user.id:
        raise _err(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Thread not found")
    thread.status = "open"
    await db.flush()
    await db.refresh(thread)  # onupdate expires updated_at
    return _serialize_thread(thread)
