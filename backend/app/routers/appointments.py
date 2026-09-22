import logging
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import cast, func, select, update
from sqlalchemy.dialects.postgresql import INTERVAL
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.config import settings
from app.database import get_db
from app.dependencies import get_active_clinic, get_current_doctor, get_current_user, require_active_clinic, require_admin
from app.models.appointment import Appointment
from app.models.clinic import Clinic, ClinicBranch, ClinicMembership
from app.models.doctor import Doctor
from app.models.medical_record import MedicalRecord
from app.models.patient_link import PatientClinicLink, PatientLinkCode
from app.models.prescription import Prescription
from app.models.user import User
from app.schemas.appointments_response import (
    AppointmentResponse,
    AppointmentsListResponse,
    LinkProvisionalResponse,
)
from app.services import access_service
from app.services.notification_service import create_notification

router = APIRouter(prefix="/api/v1/appointments", tags=["appointments"])

logger = logging.getLogger(__name__)

# Max waitlist entries notified per freed slot — first-come by created_at.
WAITLIST_NOTIFY_LIMIT = 5

VALID_TYPES = {"in-person", "teleconsult", "follow-up"}
VALID_STATUSES = {"scheduled", "arrived", "in-progress", "completed", "cancelled", "no-show"}

# Status transition map: current_status -> allowed_next_statuses
STATUS_TRANSITIONS: dict[str, set[str]] = {
    "scheduled": {"arrived", "cancelled", "no-show"},
    "arrived": {"in-progress", "cancelled"},
    "in-progress": {"completed", "cancelled"},
    "completed": set(),
    "cancelled": set(),
    "no-show": set(),
}


# ─── Pydantic schemas ─────────────────────────────────────────────────────────

class AppointmentCreate(BaseModel):
    patient_id: UUID
    doctor_id: UUID | None = None   # inferred from auth token when omitted
    clinic_id: UUID | None = None
    branch_id: UUID | None = None
    scheduled_at: datetime
    duration_minutes: int = Field(default=30, ge=5, le=480)
    type: str
    chief_complaint: str | None = None
    notes: str | None = None

    @field_validator("scheduled_at")
    @classmethod
    def _scheduled_at_utc(cls, v: datetime) -> datetime:
        return v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v


class AppointmentStatusUpdate(BaseModel):
    status: str
    cancelled_reason: str | None = None


class AppointmentUpdate(BaseModel):
    doctor_id: UUID | None = None
    clinic_id: UUID | None = None
    branch_id: UUID | None = None
    scheduled_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=5, le=480)

    @field_validator("scheduled_at")
    @classmethod
    def _scheduled_at_utc(cls, v):
        if v is not None and v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v
    type: str | None = None
    chief_complaint: str | None = None
    notes: str | None = None


class GuestAppointmentCreate(BaseModel):
    patient_name: str
    patient_phone: str
    doctor_id: UUID | None = None
    scheduled_at: datetime
    duration_minutes: int = Field(default=30, ge=5, le=480)
    type: str
    chief_complaint: str | None = None
    notes: str | None = None
    branch_id: UUID | None = None

    @field_validator("scheduled_at")
    @classmethod
    def _scheduled_at_utc(cls, v: datetime) -> datetime:
        return v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v


class LinkProvisionalRequest(BaseModel):
    provisional_patient_id: UUID
    link_code: str


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _serialize_appointment(
    appt: Appointment,
    patient_name: str | None = None,
    doctor_name: str | None = None,
    clinic_name: str | None = None,
    branch_name: str | None = None,
    is_provisional: bool = False,
    patient_phone: str | None = None,
) -> dict:
    return {
        "id": str(appt.id),
        "patient_id": str(appt.patient_id),
        "patient_name": patient_name,
        "doctor_id": str(appt.doctor_id),
        "doctor_name": doctor_name,
        "clinic_id": str(appt.clinic_id) if appt.clinic_id else None,
        "clinic_name": clinic_name,
        "branch_id": str(appt.branch_id) if appt.branch_id else None,
        "branch_name": branch_name,
        "scheduled_at": appt.scheduled_at.isoformat(),
        "duration_minutes": appt.duration_minutes,
        "type": appt.type,
        "status": appt.status,
        "chief_complaint": appt.chief_complaint,
        "notes": appt.notes,
        "cancelled_reason": appt.cancelled_reason,
        "meeting_url": appt.meeting_url,
        "is_provisional": is_provisional,
        "patient_phone": patient_phone,
        "created_by": str(appt.created_by),
        "created_at": appt.created_at.isoformat(),
        "updated_at": appt.updated_at.isoformat(),
    }


async def _load_appointment_with_names(db: AsyncSession, appt: Appointment) -> dict:
    """Eagerly load related names for a single appointment."""
    patient_name: str | None = None
    doctor_name: str | None = None
    clinic_name: str | None = None
    branch_name: str | None = None
    is_provisional: bool = False
    patient_phone: str | None = None

    patient_res = await db.execute(
        select(User.full_name, User.is_provisional, User.phone).where(User.id == appt.patient_id)
    )
    patient_row = patient_res.one_or_none()
    if patient_row:
        patient_name = patient_row.full_name
        is_provisional = patient_row.is_provisional
        patient_phone = patient_row.phone if patient_row.is_provisional else None

    doctor_res = await db.execute(
        select(User.full_name)
        .join(Doctor, Doctor.user_id == User.id)
        .where(Doctor.id == appt.doctor_id)
    )
    doctor_name = doctor_res.scalar_one_or_none()

    if appt.clinic_id:
        clinic_res = await db.execute(
            select(Clinic.name).where(Clinic.id == appt.clinic_id)
        )
        clinic_name = clinic_res.scalar_one_or_none()

    if appt.branch_id:
        branch_res = await db.execute(
            select(ClinicBranch.name).where(ClinicBranch.id == appt.branch_id)
        )
        branch_name = branch_res.scalar_one_or_none()

    return _serialize_appointment(
        appt, patient_name, doctor_name, clinic_name, branch_name,
        is_provisional=is_provisional, patient_phone=patient_phone,
    )


# Allow a small clock-skew margin so "right now" bookings are not rejected
PAST_SCHEDULE_SKEW = timedelta(minutes=5)


def _as_aware_utc(dt: datetime) -> datetime:
    """Coerce naive datetimes to UTC — timestamptz binds reject naive values."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _ensure_not_in_past(scheduled_at: datetime) -> None:
    """Raise 400 if scheduled_at is in the past (beyond a small skew allowance)."""
    now = datetime.now(tz=timezone.utc)
    candidate = _as_aware_utc(scheduled_at)
    if candidate < now - PAST_SCHEDULE_SKEW:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_SCHEDULED_AT",
                    "message": "scheduled_at cannot be in the past",
                }
            },
        )


async def _doctor_patient_relationship_exists(
    db: AsyncSession,
    doctor_user_id: UUID,
    doctor_id: UUID | None,
    patient_id: UUID,
    allow_revoked: bool = True,
) -> bool:
    """Delegates to access_service.doctor_patient_relationship_exists —
    the single source of truth for the doctor↔patient access rule.

    ``allow_revoked=False`` restricts the clinic-link path to ``approved`` —
    revoked consent must never authorize NEW writes (appointments, encounters,
    prescriptions), only reads of pre-revocation data.
    """
    return await access_service.doctor_patient_relationship_exists(
        db, doctor_user_id, doctor_id, patient_id, allow_revoked=allow_revoked
    )


async def _staff_clinic_context(
    db: AsyncSession,
    user: User,
    x_clinic_id: str | None,
) -> UUID | None:
    """Front-desk clinic context for write endpoints that also serve staff.

    Returns the X-Clinic-Id clinic when the header is present AND the caller
    holds an active ClinicMembership there (any role — owner | admin | doctor |
    receptionist). Returns None when the header is absent, malformed, or the
    caller is not a member — callers then fall back to their normal role gate.
    """
    if not x_clinic_id:
        return None
    try:
        clinic_id = uuid.UUID(x_clinic_id)
    except ValueError:
        return None
    if await access_service.get_membership_role(db, user.id, clinic_id) is None:
        return None
    return clinic_id


async def _validate_clinic_and_branch(
    db: AsyncSession,
    user: User,
    clinic_id: UUID | None,
    branch_id: UUID | None,
) -> UUID | None:
    """
    Tenant validation for client-supplied clinic_id / branch_id.

    - branch_id must reference an existing branch; if clinic_id is also given,
      the branch must belong to it; if clinic_id is omitted, the clinic is
      derived from the branch.
    - whenever a clinic is supplied (directly or via branch), the caller must
      hold an active ClinicMembership for it (same check as doctors.py).
    Returns the effective clinic_id.
    """
    effective_clinic_id = clinic_id

    if branch_id is not None:
        branch_res = await db.execute(
            select(ClinicBranch).where(
                ClinicBranch.id == branch_id,
                ClinicBranch.deleted_at.is_(None),
            )
        )
        branch = branch_res.scalar_one_or_none()
        if branch is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "NOT_FOUND", "message": "Branch not found"}},
            )
        if effective_clinic_id is None:
            effective_clinic_id = branch.clinic_id
        elif branch.clinic_id != effective_clinic_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "INVALID_BRANCH",
                        "message": "branch_id does not belong to the specified clinic",
                    }
                },
            )

    if effective_clinic_id is not None:
        membership_res = await db.execute(
            select(ClinicMembership.id).where(
                ClinicMembership.clinic_id == effective_clinic_id,
                ClinicMembership.user_id == user.id,
                ClinicMembership.is_active.is_(True),
                ClinicMembership.deleted_at.is_(None),
            )
        )
        if membership_res.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "NOT_CLINIC_MEMBER", "message": "Not a member of this clinic"}},
            )

    return effective_clinic_id


def _generate_meeting_url() -> str:
    """Random unguessable Jitsi room URL for a teleconsult appointment.

    The appointment UUID must NOT be used: it is exposed on queue, admin,
    search, and audit surfaces — a deterministic room name would let anyone
    holding the UUID join a live consult on public Jitsi.
    """
    return f"{settings.JITSI_BASE_URL.rstrip('/')}/medconnect-{secrets.token_urlsafe(24)}"


async def _enqueue_appointment_reminders(appt: Appointment) -> None:
    """Enqueue reminder jobs for an appointment. Never raises (non-critical)."""
    try:
        from app.workers.scheduler import schedule_appointment_reminders
        await schedule_appointment_reminders(str(appt.id), appt.scheduled_at)
    except Exception:
        pass  # reminder scheduling is non-critical


async def _emit_appointment_webhook(
    db: AsyncSession, appt: Appointment, event_type: str, extra: dict | None = None
) -> None:
    """Emit a clinic webhook for an appointment. Never raises (non-critical).

    PHI minimization: payload carries IDs + status + timestamps only — no
    names, chief complaints or notes.
    """
    from app.services import webhook_service

    await webhook_service.emit_event_safe(
        db,
        appt.clinic_id,
        event_type,
        {
            "appointment_id": str(appt.id),
            "patient_id": str(appt.patient_id),
            "doctor_id": str(appt.doctor_id),
            "branch_id": str(appt.branch_id) if appt.branch_id else None,
            "status": appt.status,
            "scheduled_at": appt.scheduled_at.isoformat() if appt.scheduled_at else None,
            **(extra or {}),
        },
    )


async def _unschedule_appointment_reminders(appt: Appointment) -> None:
    """Abort existing deferred reminder jobs. Never raises (non-critical)."""
    try:
        from app.workers.scheduler import unschedule_appointment_reminders
        await unschedule_appointment_reminders(str(appt.id))
    except Exception:
        pass  # reminder scheduling is non-critical


async def _notify_waitlist_on_cancellation(db: AsyncSession, appt: Appointment) -> None:
    """Notify waitlisted patients that a slot freed for this doctor+date.

    Notify-only — nothing is auto-booked. Runs inside a SAVEPOINT so a
    waitlist failure can never abort the cancellation itself, and commits
    atomically with it via the request-scoped session.
    """
    from app.models.appointment_waitlist import AppointmentWaitlist

    try:
        async with db.begin_nested():
            res = await db.execute(
                select(AppointmentWaitlist)
                .where(
                    AppointmentWaitlist.doctor_id == appt.doctor_id,
                    AppointmentWaitlist.desired_date == appt.scheduled_at.date(),
                    AppointmentWaitlist.status == "pending",
                    AppointmentWaitlist.deleted_at.is_(None),
                )
                .order_by(AppointmentWaitlist.created_at.asc())
                .limit(WAITLIST_NOTIFY_LIMIT)
            )
            entries = res.scalars().all()
            if not entries:
                return

            now = datetime.now(tz=timezone.utc)
            date_label = appt.scheduled_at.date().isoformat()
            for entry in entries:
                entry.status = "notified"
                entry.notified_at = now
                await create_notification(
                    db=db,
                    user_id=entry.patient_id,
                    notif_type="appointment",
                    title="A slot opened up",
                    body=(
                        f"An appointment slot opened on {date_label} — "
                        "book now before it's taken."
                    ),
                    action_url="/patient/appointments",
                    metadata={
                        "waitlist_id": str(entry.id),
                        "doctor_id": str(appt.doctor_id),
                        "desired_date": date_label,
                    },
                )
    except Exception:
        # Waitlist fan-out is best-effort — cancellation must never fail
        # because of it. The SAVEPOINT rollback keeps the outer txn usable.
        logger.exception("waitlist notify failed for appointment %s", appt.id)


# ─── Conflict helpers ─────────────────────────────────────────────────────────

ACTIVE_STATUSES = ["scheduled", "arrived", "in-progress"]


def _existing_end_expr():
    """SQL expression: scheduled_at + duration_minutes as a PostgreSQL interval."""
    return Appointment.scheduled_at + cast(
        func.concat(Appointment.duration_minutes, " minutes"),
        INTERVAL,
    )


async def _check_doctor_conflict(
    db: AsyncSession,
    doctor_id: UUID,
    scheduled_at: datetime,
    duration_minutes: int,
    exclude_id: UUID | None = None,
) -> None:
    """Raise 409 if the doctor already has an active overlapping appointment."""
    new_end = scheduled_at + timedelta(minutes=duration_minutes)
    stmt = select(Appointment).where(
        Appointment.doctor_id == doctor_id,
        Appointment.deleted_at.is_(None),
        Appointment.status.in_(ACTIVE_STATUSES),
        Appointment.scheduled_at < new_end,
        scheduled_at < _existing_end_expr(),
    )
    if exclude_id:
        stmt = stmt.where(Appointment.id != exclude_id)
    conflict = (await db.execute(stmt)).scalar_one_or_none()
    if conflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "DOCTOR_UNAVAILABLE",
                    "message": "The doctor already has an appointment during this time slot",
                }
            },
        )


async def _check_patient_clinic_conflict(
    db: AsyncSession,
    patient_id: UUID,
    clinic_id: UUID,
    scheduled_at: datetime,
    duration_minutes: int,
    exclude_id: UUID | None = None,
) -> None:
    """Raise 409 if the patient already has an appointment at this clinic with overlapping time."""
    new_end = scheduled_at + timedelta(minutes=duration_minutes)
    stmt = select(Appointment).where(
        Appointment.patient_id == patient_id,
        Appointment.clinic_id == clinic_id,
        Appointment.deleted_at.is_(None),
        Appointment.status.in_(ACTIVE_STATUSES),
        Appointment.scheduled_at < new_end,
        scheduled_at < _existing_end_expr(),
    )
    if exclude_id:
        stmt = stmt.where(Appointment.id != exclude_id)
    conflict = (await db.execute(stmt)).scalar_one_or_none()
    if conflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "PATIENT_CLINIC_CONFLICT",
                    "message": "Patient already has an appointment at this clinic during this time",
                }
            },
        )


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
async def create_appointment(
    req: AppointmentCreate,
    current_user: User = Depends(get_current_user),
    x_clinic_id: str | None = Header(None, alias="X-Clinic-Id"),
    db: AsyncSession = Depends(get_db),
):
    """Create a new appointment. Patient books for themselves; doctor books for
    a patient; front-desk clinic staff (any active membership under the
    X-Clinic-Id context, incl. receptionist) book linked patients."""
    if req.type not in VALID_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_TYPE", "message": f"type must be one of: {', '.join(sorted(VALID_TYPES))}"}},
        )

    _ensure_not_in_past(req.scheduled_at)

    # Resolve doctor_id: use request value or fall back to the authenticated user's doctor record
    doctor_id = req.doctor_id
    if doctor_id is None:
        doc_res = await db.execute(
            select(Doctor.id).where(Doctor.user_id == current_user.id, Doctor.deleted_at.is_(None))
        )
        doctor_id = doc_res.scalar_one_or_none()
        if doctor_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "MISSING_DOCTOR", "message": "doctor_id is required"}},
            )

    # Verify doctor exists
    doctor_res = await db.execute(
        select(Doctor).where(Doctor.id == doctor_id, Doctor.deleted_at.is_(None))
    )
    if not doctor_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Doctor not found"}},
        )

    # Verify patient exists
    patient_res = await db.execute(
        select(User).where(User.id == req.patient_id, User.deleted_at.is_(None), User.is_active.is_(True))
    )
    if not patient_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Patient not found"}},
        )

    # Authorization: patients can only book for themselves — unless they act as
    # front-desk staff: an active clinic membership (any role, incl.
    # receptionist) under the X-Clinic-Id context lets them book for a patient
    # who has an approved link with that clinic, with a doctor-member of it.
    staff_clinic_id: UUID | None = None
    if current_user.role == "patient" and req.patient_id != current_user.id:
        staff_clinic_id = await _staff_clinic_context(db, current_user, x_clinic_id)
        if staff_clinic_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "FORBIDDEN", "message": "Patients can only book appointments for themselves"}},
            )
        if req.clinic_id is not None and req.clinic_id != staff_clinic_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "INVALID_CLINIC", "message": "clinic_id must match the X-Clinic-Id clinic context"}},
            )
        # The booked doctor must be an active member of this clinic
        doctor_user_id = (
            await db.execute(
                select(Doctor.user_id).where(Doctor.id == doctor_id, Doctor.deleted_at.is_(None))
            )
        ).scalar_one_or_none()
        if doctor_user_id is None or await access_service.get_membership_role(
            db, doctor_user_id, staff_clinic_id
        ) is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "DOCTOR_NOT_IN_CLINIC", "message": "Doctor is not a member of this clinic"}},
            )
        # Approved PatientClinicLink required — missing/pending/revoked → 403
        await access_service.check_patient_consent(db, req.patient_id, staff_clinic_id)

    # Authorization: doctors can only schedule under their own profile, and only
    # for patients they have an existing relationship with (a record they authored
    # or a shared clinic link) — prevents booking for arbitrary patient_ids.
    if current_user.role == "doctor":
        own_doc_res = await db.execute(
            select(Doctor.id).where(Doctor.user_id == current_user.id, Doctor.deleted_at.is_(None))
        )
        own_doctor_id = own_doc_res.scalar_one_or_none()
        if own_doctor_id and doctor_id != own_doctor_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "FORBIDDEN", "message": "Doctors can only create appointments under their own schedule"}},
            )
        if req.patient_id != current_user.id and not await _doctor_patient_relationship_exists(
            db, current_user.id, own_doctor_id, req.patient_id, allow_revoked=False
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "PATIENT_ACCESS_DENIED", "message": "No relationship with this patient"}},
            )

    # Tenant validation: clinic_id/branch_id from the body require membership.
    # A staff booking that omits clinic_id lands on the X-Clinic-Id clinic.
    effective_clinic_id = await _validate_clinic_and_branch(
        db,
        current_user,
        req.clinic_id if req.clinic_id is not None else staff_clinic_id,
        req.branch_id,
    )

    # Check doctor availability
    await _check_doctor_conflict(db, doctor_id, req.scheduled_at, req.duration_minutes)

    # Check patient-clinic conflict (only when a clinic is specified)
    if effective_clinic_id:
        await _check_patient_clinic_conflict(db, req.patient_id, effective_clinic_id, req.scheduled_at, req.duration_minutes)

    appt = Appointment(
        id=uuid.uuid4(),
        patient_id=req.patient_id,
        doctor_id=doctor_id,
        clinic_id=effective_clinic_id,
        branch_id=req.branch_id,
        scheduled_at=req.scheduled_at,
        duration_minutes=req.duration_minutes,
        type=req.type,
        status="scheduled",
        chief_complaint=req.chief_complaint,
        notes=req.notes,
        created_by=current_user.id,
    )
    if appt.type == "teleconsult":
        appt.meeting_url = _generate_meeting_url()
    db.add(appt)
    try:
        await db.flush()
    except IntegrityError:
        # Exclusion constraint caught a concurrent double-booking race
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "DOCTOR_UNAVAILABLE", "message": "Doctor has a conflicting appointment at this time"}},
        )
    await db.refresh(appt)

    # Schedule reminders — awaited so enqueue failures are surfaced to logs
    # before the response is returned (the helper never raises).
    await _enqueue_appointment_reminders(appt)

    # Outbound webhook — PHI-minimal payload (IDs/status/timestamps only),
    # fire-and-forget; emit failures never break booking.
    await _emit_appointment_webhook(db, appt, "appointment.booked")

    return await _load_appointment_with_names(db, appt)


@router.get("", response_model=AppointmentsListResponse)
async def list_appointments(
    date_param: str | None = Query(None, alias="date"),
    status_filter: str | None = Query(None, alias="status"),
    upcoming: bool | None = Query(None),
    all_appointments: bool | None = Query(None, alias="all"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    clinic_ctx: tuple | None = Depends(get_active_clinic),
    db: AsyncSession = Depends(get_db),
):
    """
    List appointments.
    - doctor role: returns their own appointments; default today unless date/upcoming param provided
    - clinic staff (any active membership incl. receptionist) with X-Clinic-Id:
      the clinic's full schedule, same date/upcoming filtering as doctors
    - patient role: returns their own appointments
    - admin with all=true: returns all appointments
    """
    now = datetime.now(tz=timezone.utc)

    stmt = select(Appointment).where(Appointment.deleted_at.is_(None))

    # Front-desk staff (e.g. a receptionist membership) view the clinic-wide
    # schedule. Global-role doctors keep their own-appointments view even when
    # X-Clinic-Id is present, so the doctor list is unchanged.
    clinic_id_ctx: UUID | None = clinic_ctx[0] if (clinic_ctx is not None and current_user.role != "doctor") else None

    admin_sees_all = bool(all_appointments and current_user.role == "admin")

    if admin_sees_all:
        # Admin sees everything
        pass
    elif current_user.role == "doctor":
        # Get doctor profile
        doc_res = await db.execute(
            select(Doctor).where(Doctor.user_id == current_user.id, Doctor.deleted_at.is_(None))
        )
        doctor = doc_res.scalar_one_or_none()
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "NOT_FOUND", "message": "Doctor profile not found"}},
            )
        stmt = stmt.where(Appointment.doctor_id == doctor.id)
    elif clinic_id_ctx is not None:
        stmt = stmt.where(Appointment.clinic_id == clinic_id_ctx)
    else:
        # Patient sees their own
        stmt = stmt.where(Appointment.patient_id == current_user.id)

    if not admin_sees_all and (current_user.role == "doctor" or clinic_id_ctx is not None):
        if upcoming:
            stmt = stmt.where(Appointment.scheduled_at >= now)
        elif date_param:
            try:
                target_date = date.fromisoformat(date_param)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": {"code": "INVALID_DATE", "message": "date must be YYYY-MM-DD"}},
                )
            day_start = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=timezone.utc)
            day_end = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59, tzinfo=timezone.utc)
            stmt = stmt.where(Appointment.scheduled_at >= day_start, Appointment.scheduled_at <= day_end)
        else:
            # Default: today
            today = now.date()
            day_start = datetime(today.year, today.month, today.day, 0, 0, 0, tzinfo=timezone.utc)
            day_end = datetime(today.year, today.month, today.day, 23, 59, 59, tzinfo=timezone.utc)
            stmt = stmt.where(Appointment.scheduled_at >= day_start, Appointment.scheduled_at <= day_end)

    if status_filter:
        stmt = stmt.where(Appointment.status == status_filter)

    # Total count for the filtered query (before pagination)
    total = (
        await db.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()

    stmt = stmt.order_by(Appointment.scheduled_at.asc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    appointments = result.scalars().all()

    # Batch load names
    patient_ids = list({a.patient_id for a in appointments})
    doctor_ids = list({a.doctor_id for a in appointments})
    clinic_ids = list({a.clinic_id for a in appointments if a.clinic_id})
    branch_ids = list({a.branch_id for a in appointments if a.branch_id})

    patient_names: dict[uuid.UUID, str] = {}
    patient_provisional: dict[uuid.UUID, bool] = {}
    patient_phones: dict[uuid.UUID, str | None] = {}
    if patient_ids:
        pr = await db.execute(
            select(User.id, User.full_name, User.is_provisional, User.phone).where(User.id.in_(patient_ids))
        )
        for row in pr.all():
            patient_names[row.id] = row.full_name
            patient_provisional[row.id] = row.is_provisional
            patient_phones[row.id] = row.phone if row.is_provisional else None

    doctor_names: dict[uuid.UUID, str] = {}
    if doctor_ids:
        dr = await db.execute(
            select(Doctor.id, User.full_name)
            .join(User, User.id == Doctor.user_id)
            .where(Doctor.id.in_(doctor_ids))
        )
        doctor_names = {row.id: row.full_name for row in dr.all()}

    clinic_names: dict[uuid.UUID, str] = {}
    if clinic_ids:
        cr = await db.execute(select(Clinic.id, Clinic.name).where(Clinic.id.in_(clinic_ids)))
        clinic_names = {row.id: row.name for row in cr.all()}

    branch_names: dict[uuid.UUID, str] = {}
    if branch_ids:
        br = await db.execute(select(ClinicBranch.id, ClinicBranch.name).where(ClinicBranch.id.in_(branch_ids)))
        branch_names = {row.id: row.name for row in br.all()}

    data = [
        _serialize_appointment(
            a,
            patient_name=patient_names.get(a.patient_id),
            doctor_name=doctor_names.get(a.doctor_id),
            clinic_name=clinic_names.get(a.clinic_id) if a.clinic_id else None,
            branch_name=branch_names.get(a.branch_id) if a.branch_id else None,
            is_provisional=patient_provisional.get(a.patient_id, False),
            patient_phone=patient_phones.get(a.patient_id),
        )
        for a in appointments
    ]
    return {"data": data, "total": total, "limit": limit, "offset": offset}


@router.get("/{appointment_id}", response_model=AppointmentResponse)
async def get_appointment(
    appointment_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.deleted_at.is_(None),
        )
    )
    appt = result.scalar_one_or_none()
    if not appt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Appointment not found"}},
        )

    # Access control: patient can only see their own; doctor can see theirs; admin sees all
    if current_user.role == "patient" and appt.patient_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Access denied"}},
        )
    if current_user.role == "doctor":
        doc_res = await db.execute(
            select(Doctor).where(Doctor.user_id == current_user.id, Doctor.deleted_at.is_(None))
        )
        doctor = doc_res.scalar_one_or_none()
        if not doctor or appt.doctor_id != doctor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "FORBIDDEN", "message": "Access denied"}},
            )

    return await _load_appointment_with_names(db, appt)


@router.put("/{appointment_id}", response_model=AppointmentResponse)
async def update_appointment(
    appointment_id: UUID,
    req: AppointmentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update appointment details (doctor, time, type, etc.). Only allowed when status is 'scheduled'."""
    result = await db.execute(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.deleted_at.is_(None),
        )
    )
    appt = result.scalar_one_or_none()
    if not appt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Appointment not found"}},
        )

    if appt.status != "scheduled":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"error": {"code": "INVALID_STATUS", "message": "Only scheduled appointments can be modified"}},
        )

    # Access control.
    # Clinic staff: any active membership (incl. receptionist) at the
    # appointment's clinic grants front-desk management of that appointment —
    # same membership gate as the X-Clinic-Id endpoints, keyed off the
    # appointment's clinic. Admin keeps the unrestricted path.
    staff_role: str | None = None
    if current_user.role != "admin" and appt.clinic_id is not None:
        staff_role = await access_service.get_membership_role(
            db, current_user.id, appt.clinic_id
        )

    if current_user.role == "patient" and staff_role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Patients cannot modify appointments; use cancel instead"}},
        )

    if current_user.role == "doctor":
        doc_res = await db.execute(
            select(Doctor).where(Doctor.user_id == current_user.id, Doctor.deleted_at.is_(None))
        )
        doctor = doc_res.scalar_one_or_none()
        is_owning_doctor = doctor is not None and appt.doctor_id == doctor.id
        if not is_owning_doctor and staff_role is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "FORBIDDEN", "message": "Access denied"}},
            )
        if is_owning_doctor and req.doctor_id is not None and req.doctor_id != doctor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "FORBIDDEN", "message": "Doctors cannot reassign appointments to other doctors"}},
            )

    # Front-desk staff may reassign the appointment only to a doctor who is
    # an active member of the same clinic (a missing doctor still 404s below).
    if (
        staff_role is not None
        and req.doctor_id is not None
        and req.doctor_id != appt.doctor_id
    ):
        new_doc_user_id = (
            await db.execute(
                select(Doctor.user_id).where(
                    Doctor.id == req.doctor_id, Doctor.deleted_at.is_(None)
                )
            )
        ).scalar_one_or_none()
        if new_doc_user_id is not None and await access_service.get_membership_role(
            db, new_doc_user_id, appt.clinic_id
        ) is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "DOCTOR_NOT_IN_CLINIC", "message": "Doctor is not a member of this clinic"}},
            )

    # Resolve effective values for conflict checking
    new_doctor_id = req.doctor_id if req.doctor_id is not None else appt.doctor_id
    new_scheduled_at = req.scheduled_at if req.scheduled_at is not None else appt.scheduled_at
    new_duration = req.duration_minutes if req.duration_minutes is not None else appt.duration_minutes
    new_clinic_id = req.clinic_id if req.clinic_id is not None else appt.clinic_id

    # Verify new doctor exists if changing
    if new_doctor_id != appt.doctor_id:
        doctor_res = await db.execute(
            select(Doctor).where(Doctor.id == new_doctor_id, Doctor.deleted_at.is_(None))
        )
        if not doctor_res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "NOT_FOUND", "message": "Doctor not found"}},
            )

    # Validate type if changing
    if req.type is not None and req.type not in VALID_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_TYPE", "message": f"type must be one of: {', '.join(sorted(VALID_TYPES))}"}},
        )

    # Cannot reschedule into the past
    if req.scheduled_at is not None:
        _ensure_not_in_past(req.scheduled_at)

    # Check doctor availability (exclude self to allow updating non-conflicting fields)
    await _check_doctor_conflict(db, new_doctor_id, new_scheduled_at, new_duration, exclude_id=appointment_id)

    # Check patient-clinic conflict
    if new_clinic_id:
        await _check_patient_clinic_conflict(
            db, appt.patient_id, new_clinic_id, new_scheduled_at, new_duration, exclude_id=appointment_id
        )

    # Tenant validation on retag — same membership + branch↔clinic rules as create
    if req.clinic_id is not None or req.branch_id is not None:
        new_branch_id = req.branch_id if req.branch_id is not None else appt.branch_id
        await _validate_clinic_and_branch(db, current_user, new_clinic_id, new_branch_id)

    # Apply updates
    if req.doctor_id is not None:
        appt.doctor_id = req.doctor_id
    if req.clinic_id is not None:
        appt.clinic_id = req.clinic_id
    if req.branch_id is not None:
        appt.branch_id = req.branch_id
    if req.scheduled_at is not None:
        appt.scheduled_at = req.scheduled_at
    if req.duration_minutes is not None:
        appt.duration_minutes = req.duration_minutes
    if req.type is not None:
        appt.type = req.type
    if req.chief_complaint is not None:
        appt.chief_complaint = req.chief_complaint
    if req.notes is not None:
        appt.notes = req.notes

    # Keep meeting_url in sync with the (possibly updated) appointment type
    if appt.type == "teleconsult" and not appt.meeting_url:
        appt.meeting_url = _generate_meeting_url()
    elif appt.type != "teleconsult":
        appt.meeting_url = None

    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "DOCTOR_UNAVAILABLE", "message": "Doctor has a conflicting appointment at this time"}},
        )
    await db.refresh(appt)

    # Rescheduled — cancel stale reminder jobs, then enqueue for the new time
    if req.scheduled_at is not None:
        await _unschedule_appointment_reminders(appt)
        await _enqueue_appointment_reminders(appt)

    return await _load_appointment_with_names(db, appt)


@router.put("/{appointment_id}/status", response_model=AppointmentResponse)
async def update_appointment_status(
    appointment_id: UUID,
    req: AppointmentStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update appointment status with transition validation."""
    if req.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_STATUS", "message": f"status must be one of: {', '.join(sorted(VALID_STATUSES))}"}},
        )

    result = await db.execute(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.deleted_at.is_(None),
        )
    )
    appt = result.scalar_one_or_none()
    if not appt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Appointment not found"}},
        )

    # Access control: doctor must own the appointment; patient can only cancel
    # their own; clinic staff (any active membership at the appointment's
    # clinic — incl. receptionist) run the front-desk transitions; admin any.
    is_owning_doctor = False
    if current_user.role == "doctor":
        doc_res = await db.execute(
            select(Doctor).where(Doctor.user_id == current_user.id, Doctor.deleted_at.is_(None))
        )
        doctor = doc_res.scalar_one_or_none()
        is_owning_doctor = doctor is not None and appt.doctor_id == doctor.id

    is_clinic_staff = (
        current_user.role != "admin"
        and appt.clinic_id is not None
        and await access_service.get_membership_role(
            db, current_user.id, appt.clinic_id
        )
        is not None
    )

    if current_user.role == "doctor":
        if not is_owning_doctor and not is_clinic_staff:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "FORBIDDEN", "message": "Access denied"}},
            )
    elif current_user.role == "patient" and not is_clinic_staff:
        if appt.patient_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "FORBIDDEN", "message": "Access denied"}},
            )
        # Patients may only cancel
        if req.status != "cancelled":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "FORBIDDEN", "message": "Patients may only cancel appointments"}},
            )
    # Admin can update any status

    # Validate transition. Front-desk staff use the doctor transition table
    # minus 'completed' — finishing a consult stays a clinical action for the
    # owning doctor or an admin.
    allowed = STATUS_TRANSITIONS.get(appt.status, set())
    if is_clinic_staff and not is_owning_doctor:
        allowed = allowed - {"completed"}
    if req.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "error": {
                    "code": "INVALID_TRANSITION",
                    "message": f"Cannot transition from '{appt.status}' to '{req.status}'",
                }
            },
        )

    if req.status == "cancelled":
        await _unschedule_appointment_reminders(appt)

    previous_status = appt.status
    appt.status = req.status
    if req.cancelled_reason is not None:
        appt.cancelled_reason = req.cancelled_reason
    await db.flush()
    await db.refresh(appt)

    # A freed slot may have patients waiting — notify-only, never raises.
    if req.status == "cancelled":
        await _notify_waitlist_on_cancellation(db, appt)

    # Outbound webhook — IDs + statuses only, fire-and-forget.
    await _emit_appointment_webhook(
        db, appt, "appointment.status_changed", {"previous_status": previous_status}
    )

    return await _load_appointment_with_names(db, appt)


@router.delete("/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_appointment(
    appointment_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete (cancel) an appointment."""
    result = await db.execute(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.deleted_at.is_(None),
        )
    )
    appt = result.scalar_one_or_none()
    if not appt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Appointment not found"}},
        )

    # Access control
    if current_user.role == "patient" and appt.patient_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Access denied"}},
        )
    if current_user.role == "doctor":
        doc_res = await db.execute(
            select(Doctor).where(Doctor.user_id == current_user.id, Doctor.deleted_at.is_(None))
        )
        doctor = doc_res.scalar_one_or_none()
        if not doctor or appt.doctor_id != doctor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "FORBIDDEN", "message": "Access denied"}},
            )

    # Enforce status transitions — cannot cancel terminal appointments
    if appt.status in {"completed", "cancelled", "no-show"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "error": {
                    "code": "INVALID_TRANSITION",
                    "message": f"Cannot cancel an appointment with status '{appt.status}'",
                }
            },
        )

    now = datetime.now(tz=timezone.utc)
    appt.deleted_at = now
    appt.status = "cancelled"
    await _unschedule_appointment_reminders(appt)
    await db.flush()

    # A freed slot may have patients waiting — notify-only, never raises.
    await _notify_waitlist_on_cancellation(db, appt)


@router.post("/guest", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
async def create_guest_appointment(
    body: GuestAppointmentCreate,
    current_user: User = Depends(get_current_user),
    clinic_ctx: tuple = Depends(require_active_clinic),
    db: AsyncSession = Depends(get_db),
):
    """Book an appointment for a walk-in / call-in patient (creates a provisional user)."""
    clinic_id, _clinic_role = clinic_ctx

    if body.type not in VALID_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_TYPE", "message": f"type must be one of: {', '.join(sorted(VALID_TYPES))}"}},
        )

    # Resolve doctor_id
    doctor_id = body.doctor_id
    if doctor_id is None:
        doc_res = await db.execute(
            select(Doctor.id).where(Doctor.user_id == current_user.id, Doctor.deleted_at.is_(None))
        )
        doctor_id = doc_res.scalar_one_or_none()
        if doctor_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "MISSING_DOCTOR", "message": "doctor_id is required"}},
            )
    else:
        doc_check = await db.execute(
            select(Doctor).where(Doctor.id == doctor_id, Doctor.deleted_at.is_(None))
        )
        if not doc_check.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "NOT_FOUND", "message": "Doctor not found"}},
            )

    # Verify the doctor is an active member of this clinic
    doctor_user_res = await db.execute(
        select(Doctor.user_id).where(Doctor.id == doctor_id, Doctor.deleted_at.is_(None))
    )
    doctor_user_id = doctor_user_res.scalar_one_or_none()
    doctor_membership = await db.execute(
        select(ClinicMembership.id).where(
            ClinicMembership.clinic_id == clinic_id,
            ClinicMembership.user_id == doctor_user_id,
            ClinicMembership.is_active.is_(True),
            ClinicMembership.deleted_at.is_(None),
        )
    )
    if doctor_membership.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "DOCTOR_NOT_IN_CLINIC", "message": "Doctor is not a member of this clinic"}},
        )

    # Verify branch_id belongs to this clinic
    if body.branch_id is not None:
        branch_res = await db.execute(
            select(ClinicBranch.id).where(
                ClinicBranch.id == body.branch_id,
                ClinicBranch.clinic_id == clinic_id,
                ClinicBranch.deleted_at.is_(None),
            )
        )
        if branch_res.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "INVALID_BRANCH", "message": "branch_id does not belong to this clinic"}},
            )

    _ensure_not_in_past(body.scheduled_at)
    await _check_doctor_conflict(db, doctor_id, body.scheduled_at, body.duration_minutes)

    # Create provisional patient user
    provisional_user = User(
        id=uuid.uuid4(),
        full_name=body.patient_name,
        phone=body.patient_phone,
        role="patient",
        is_provisional=True,
        keycloak_sub=None,
        is_active=True,
    )
    db.add(provisional_user)
    await db.flush()

    # Auto-approve clinic link (clinic created the patient)
    link = PatientClinicLink(
        id=uuid.uuid4(),
        patient_id=provisional_user.id,
        clinic_id=clinic_id,
        linked_by=current_user.id,
        consent_status="approved",
        consented_at=datetime.now(tz=timezone.utc),
    )
    db.add(link)

    appt = Appointment(
        id=uuid.uuid4(),
        patient_id=provisional_user.id,
        doctor_id=doctor_id,
        clinic_id=clinic_id,
        branch_id=body.branch_id,
        scheduled_at=body.scheduled_at,
        duration_minutes=body.duration_minutes,
        type=body.type,
        status="scheduled",
        chief_complaint=body.chief_complaint,
        notes=body.notes,
        created_by=current_user.id,
    )
    if appt.type == "teleconsult":
        appt.meeting_url = _generate_meeting_url()
    db.add(appt)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "DOCTOR_UNAVAILABLE", "message": "Doctor has a conflicting appointment at this time"}},
        )
    await db.refresh(appt)

    # Outbound webhook — guest bookings are always clinic-scoped.
    await _emit_appointment_webhook(db, appt, "appointment.booked")

    return await _load_appointment_with_names(db, appt)


@router.post("/{appointment_id}/meeting-link", response_model=AppointmentResponse)
async def generate_meeting_link(
    appointment_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """(Re)generate the teleconsult meeting link. Only the appointment's
    patient participant or doctor participant may call this."""
    result = await db.execute(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.deleted_at.is_(None),
        )
    )
    appt = result.scalar_one_or_none()
    if not appt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Appointment not found"}},
        )

    if current_user.role == "patient":
        if appt.patient_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "FORBIDDEN", "message": "Access denied"}},
            )
    elif current_user.role == "doctor":
        doc_res = await db.execute(
            select(Doctor).where(Doctor.user_id == current_user.id, Doctor.deleted_at.is_(None))
        )
        doctor = doc_res.scalar_one_or_none()
        if not doctor or appt.doctor_id != doctor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "FORBIDDEN", "message": "Access denied"}},
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Only appointment participants can generate a meeting link"}},
        )

    if appt.type != "teleconsult":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"error": {"code": "NOT_TELECONSULT", "message": "Meeting links are only available for teleconsult appointments"}},
        )

    appt.meeting_url = _generate_meeting_url()
    await db.flush()
    await db.refresh(appt)
    return await _load_appointment_with_names(db, appt)


@router.post("/link-provisional", response_model=LinkProvisionalResponse, status_code=status.HTTP_200_OK)
async def link_provisional_patient(
    body: LinkProvisionalRequest,
    current_user: User = Depends(get_current_user),
    clinic_ctx: tuple = Depends(require_active_clinic),
    db: AsyncSession = Depends(get_db),
):
    """Link a provisional (walk-in) patient to a real patient account using a link code."""
    clinic_id, clinic_role = clinic_ctx
    now = datetime.now(tz=timezone.utc)

    # Merging patient records is a privileged operation — owner/admin only
    if clinic_role not in {"owner", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Only clinic owners and admins can link patient records"}},
        )

    # Fetch provisional user
    prov_res = await db.execute(
        select(User).where(User.id == body.provisional_patient_id, User.deleted_at.is_(None))
    )
    provisional_user = prov_res.scalar_one_or_none()
    if not provisional_user or not provisional_user.is_provisional:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Provisional patient not found"}},
        )

    # The provisional patient must actually belong to this clinic — either via a
    # PatientClinicLink or an appointment at this clinic — before merging.
    prov_link_res = await db.execute(
        select(PatientClinicLink.id)
        .where(
            PatientClinicLink.patient_id == provisional_user.id,
            PatientClinicLink.clinic_id == clinic_id,
            PatientClinicLink.deleted_at.is_(None),
        )
        .limit(1)
    )
    prov_appt_res = await db.execute(
        select(Appointment.id)
        .where(
            Appointment.patient_id == provisional_user.id,
            Appointment.clinic_id == clinic_id,
            Appointment.deleted_at.is_(None),
        )
        .limit(1)
    )
    if (
        prov_link_res.scalar_one_or_none() is None
        and prov_appt_res.scalar_one_or_none() is None
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Provisional patient has no link or appointments at this clinic"}},
        )

    # Look up link code
    code_res = await db.execute(
        select(PatientLinkCode).where(
            PatientLinkCode.code == body.link_code.upper(),
            PatientLinkCode.deleted_at.is_(None),
        )
    )
    link_code = code_res.scalar_one_or_none()
    if not link_code:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "INVALID_CODE", "message": "Link code not found or already used"}},
        )
    if link_code.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "CODE_EXPIRED", "message": "Link code has expired"}},
        )

    # Fetch real patient
    real_res = await db.execute(
        select(User).where(User.id == link_code.patient_id, User.deleted_at.is_(None), User.is_active.is_(True))
    )
    real_patient = real_res.scalar_one_or_none()
    if not real_patient or real_patient.is_provisional:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_PATIENT", "message": "Real patient account not found"}},
        )

    provisional_id = provisional_user.id
    real_id = real_patient.id

    if provisional_id == real_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "SAME_PATIENT", "message": "Provisional and real patient cannot be the same"}},
        )

    # Bulk-transfer ownership
    appt_update = await db.execute(
        update(Appointment)
        .where(Appointment.patient_id == provisional_id, Appointment.deleted_at.is_(None))
        .values(patient_id=real_id)
    )
    await db.execute(
        update(MedicalRecord)
        .where(MedicalRecord.patient_id == provisional_id, MedicalRecord.deleted_at.is_(None))
        .values(patient_id=real_id)
    )
    await db.execute(
        update(Prescription)
        .where(Prescription.patient_id == provisional_id, Prescription.deleted_at.is_(None))
        .values(patient_id=real_id)
    )
    linked_count = appt_update.rowcount

    # Upsert PatientClinicLink for real patient + this clinic
    existing_link_res = await db.execute(
        select(PatientClinicLink).where(
            PatientClinicLink.patient_id == real_id,
            PatientClinicLink.clinic_id == clinic_id,
        )
    )
    existing_link = existing_link_res.scalar_one_or_none()
    if existing_link is None:
        db.add(PatientClinicLink(
            id=uuid.uuid4(),
            patient_id=real_id,
            clinic_id=clinic_id,
            linked_by=current_user.id,
            consent_status="approved",
            consented_at=now,
        ))
    elif existing_link.consent_status == "revoked":
        # Reset to pending so the patient re-consents instead of silently
        # regaining clinic access through the merge.
        existing_link.consent_status = "pending"
        existing_link.consented_at = None
        existing_link.deleted_at = None

    # Soft-delete provisional user
    provisional_user.deleted_at = now

    # Fetch clinic name for notification
    clinic_res = await db.execute(select(Clinic.name).where(Clinic.id == clinic_id))
    clinic_name = clinic_res.scalar_one_or_none() or "the clinic"

    await db.flush()

    # Notify real patient
    await create_notification(
        db=db,
        user_id=real_id,
        notif_type="system",
        title="Appointments linked to your account",
        body=f"Appointments booked under your name at {clinic_name} have been linked to your account.",
        action_url="/patient/appointments",
    )

    return {
        "real_patient_id": str(real_id),
        "full_name": real_patient.full_name,
        "phone": real_patient.phone,
        "linked_count": linked_count,
    }
