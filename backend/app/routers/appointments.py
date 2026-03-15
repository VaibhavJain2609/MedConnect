import uuid
from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database import get_db
from app.dependencies import get_current_doctor, get_current_user, require_admin
from app.models.appointment import Appointment
from app.models.clinic import Clinic, ClinicBranch
from app.models.doctor import Doctor
from app.models.user import User

router = APIRouter(prefix="/api/v1/appointments", tags=["appointments"])

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
    doctor_id: UUID
    clinic_id: UUID | None = None
    branch_id: UUID | None = None
    scheduled_at: datetime
    duration_minutes: int = 30
    type: str
    chief_complaint: str | None = None
    notes: str | None = None


class AppointmentStatusUpdate(BaseModel):
    status: str
    cancelled_reason: str | None = None


class AppointmentResponse(BaseModel):
    id: UUID
    patient_id: UUID
    patient_name: str | None = None
    doctor_id: UUID
    doctor_name: str | None = None
    clinic_id: UUID | None = None
    clinic_name: str | None = None
    branch_id: UUID | None = None
    branch_name: str | None = None
    scheduled_at: datetime
    duration_minutes: int
    type: str
    status: str
    chief_complaint: str | None = None
    notes: str | None = None
    cancelled_reason: str | None = None
    created_by: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _serialize_appointment(
    appt: Appointment,
    patient_name: str | None = None,
    doctor_name: str | None = None,
    clinic_name: str | None = None,
    branch_name: str | None = None,
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

    patient_res = await db.execute(
        select(User.full_name).where(User.id == appt.patient_id)
    )
    patient_name = patient_res.scalar_one_or_none()

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

    return _serialize_appointment(appt, patient_name, doctor_name, clinic_name, branch_name)


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_appointment(
    req: AppointmentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new appointment. Patient books for themselves; doctor books for a patient."""
    if req.type not in VALID_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_TYPE", "message": f"type must be one of: {', '.join(sorted(VALID_TYPES))}"}},
        )

    # Verify doctor exists
    doctor_res = await db.execute(
        select(Doctor).where(Doctor.id == req.doctor_id, Doctor.deleted_at.is_(None))
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

    appt = Appointment(
        id=uuid.uuid4(),
        patient_id=req.patient_id,
        doctor_id=req.doctor_id,
        clinic_id=req.clinic_id,
        branch_id=req.branch_id,
        scheduled_at=req.scheduled_at,
        duration_minutes=req.duration_minutes,
        type=req.type,
        status="scheduled",
        chief_complaint=req.chief_complaint,
        notes=req.notes,
        created_by=current_user.id,
    )
    db.add(appt)
    await db.flush()
    await db.refresh(appt)
    return await _load_appointment_with_names(db, appt)


@router.get("")
async def list_appointments(
    date_param: str | None = Query(None, alias="date"),
    status_filter: str | None = Query(None, alias="status"),
    upcoming: bool | None = Query(None),
    all_appointments: bool | None = Query(None, alias="all"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List appointments.
    - doctor role: returns their own appointments; default today unless date/upcoming param provided
    - patient role: returns their own appointments
    - admin with all=true: returns all appointments
    """
    now = datetime.now(tz=timezone.utc)

    stmt = select(Appointment).where(Appointment.deleted_at.is_(None))

    if all_appointments and current_user.role == "admin":
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
    else:
        # Patient sees their own
        stmt = stmt.where(Appointment.patient_id == current_user.id)

    if status_filter:
        stmt = stmt.where(Appointment.status == status_filter)

    stmt = stmt.order_by(Appointment.scheduled_at.asc())
    result = await db.execute(stmt)
    appointments = result.scalars().all()

    # Batch load names
    patient_ids = list({a.patient_id for a in appointments})
    doctor_ids = list({a.doctor_id for a in appointments})
    clinic_ids = list({a.clinic_id for a in appointments if a.clinic_id})
    branch_ids = list({a.branch_id for a in appointments if a.branch_id})

    patient_names: dict[uuid.UUID, str] = {}
    if patient_ids:
        pr = await db.execute(select(User.id, User.full_name).where(User.id.in_(patient_ids)))
        patient_names = {row.id: row.full_name for row in pr.all()}

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
        )
        for a in appointments
    ]
    return {"data": data, "total": len(data)}


@router.get("/{appointment_id}")
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


@router.put("/{appointment_id}/status")
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

    # Access control: doctor must own the appointment; patient can only cancel their own
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
    elif current_user.role == "patient":
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

    # Validate transition
    allowed = STATUS_TRANSITIONS.get(appt.status, set())
    if req.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "INVALID_TRANSITION",
                    "message": f"Cannot transition from '{appt.status}' to '{req.status}'",
                }
            },
        )

    appt.status = req.status
    if req.cancelled_reason is not None:
        appt.cancelled_reason = req.cancelled_reason
    await db.flush()
    await db.refresh(appt)
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

    now = datetime.now(tz=timezone.utc)
    appt.deleted_at = now
    appt.status = "cancelled"
    await db.flush()
