"""
Encounter (visit) endpoints — SOAP clinical notes.

POST   /api/v1/encounters        — create encounter (verified doctor)
GET    /api/v1/encounters        — list (doctor: own, patient: own, admin: all)
GET    /api/v1/encounters/{id}   — read (author, patient owner, clinic admin, admin)
PATCH  /api/v1/encounters/{id}   — update (authoring doctor only)
DELETE /api/v1/encounters/{id}   — soft delete (author or admin)
"""
import uuid
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_verified_doctor
from app.models.appointment import Appointment
from app.models.clinic import Clinic, ClinicMembership
from app.models.doctor import Doctor
from app.models.encounter import Encounter
from app.models.medical_record import MedicalRecord
from app.models.patient_link import PatientClinicLink
from app.models.user import User
from app.schemas.encounter import EncounterCreate, EncounterResponse, EncounterUpdate

router = APIRouter(prefix="/api/v1/encounters", tags=["encounters"])


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _serialize_encounter(
    enc: Encounter,
    patient_name: str | None = None,
    doctor_name: str | None = None,
    clinic_name: str | None = None,
) -> dict:
    return {
        "id": str(enc.id),
        "patient_id": str(enc.patient_id),
        "patient_name": patient_name,
        "doctor_id": str(enc.doctor_id),
        "doctor_name": doctor_name,
        "appointment_id": str(enc.appointment_id) if enc.appointment_id else None,
        "clinic_id": str(enc.clinic_id) if enc.clinic_id else None,
        "clinic_name": clinic_name,
        "subjective": enc.subjective,
        "objective": enc.objective,
        "assessment": enc.assessment,
        "plan": enc.plan,
        "vitals_snapshot": enc.vitals_snapshot,
        "created_at": enc.created_at.isoformat(),
        "updated_at": enc.updated_at.isoformat(),
    }


async def _load_encounter_with_names(db: AsyncSession, enc: Encounter) -> dict:
    """Eagerly load related display names for a single encounter."""
    patient_name: str | None = None
    doctor_name: str | None = None
    clinic_name: str | None = None

    patient_res = await db.execute(
        select(User.full_name).where(User.id == enc.patient_id)
    )
    patient_name = patient_res.scalar_one_or_none()

    doctor_res = await db.execute(
        select(User.full_name)
        .join(Doctor, Doctor.user_id == User.id)
        .where(Doctor.id == enc.doctor_id)
    )
    doctor_name = doctor_res.scalar_one_or_none()

    if enc.clinic_id:
        clinic_res = await db.execute(
            select(Clinic.name).where(Clinic.id == enc.clinic_id)
        )
        clinic_name = clinic_res.scalar_one_or_none()

    return _serialize_encounter(enc, patient_name, doctor_name, clinic_name)


async def _doctor_patient_relationship_exists(
    db: AsyncSession,
    doctor: Doctor,
    patient_id: UUID,
    appointment: Appointment | None = None,
) -> bool:
    """
    Mirrors doctors.py::_check_doctor_patient_relationship (module-private there)
    and appointments.py::_doctor_patient_relationship_exists.

    True if:
    - the doctor has authored at least one medical record for the patient, OR
    - the doctor's user shares a clinic that has an APPROVED
      PatientClinicLink for the patient (revoked consent must never authorize
      new writes — it only preserves reads of pre-revocation data), OR
    - a non-terminal appointment between this doctor and the patient was
      supplied (the appointment was already authorized when it was created).
    """
    if appointment is not None:
        # A cancelled/no-show appointment is not an active relationship —
        # otherwise a stale appointment grants indefinite write access.
        return appointment.status in {"scheduled", "arrived", "in-progress", "completed"}

    record_exists = await db.execute(
        select(MedicalRecord.id)
        .where(
            MedicalRecord.doctor_id == doctor.id,
            MedicalRecord.patient_id == patient_id,
            MedicalRecord.deleted_at.is_(None),
        )
        .limit(1)
    )
    if record_exists.scalar_one_or_none() is not None:
        return True

    shared_clinic = await db.execute(
        select(ClinicMembership.id)
        .join(PatientClinicLink, PatientClinicLink.clinic_id == ClinicMembership.clinic_id)
        .where(
            ClinicMembership.user_id == doctor.user_id,
            ClinicMembership.is_active.is_(True),
            ClinicMembership.deleted_at.is_(None),
            PatientClinicLink.patient_id == patient_id,
            PatientClinicLink.consent_status == "approved",
            PatientClinicLink.deleted_at.is_(None),
        )
        .limit(1)
    )
    return shared_clinic.scalar_one_or_none() is not None


async def _validate_clinic_membership(
    db: AsyncSession,
    user: User,
    clinic_id: UUID | None,
) -> None:
    """Raise 403 if clinic_id is supplied but the caller is not an active member."""
    if clinic_id is None:
        return
    membership_res = await db.execute(
        select(ClinicMembership.id).where(
            ClinicMembership.clinic_id == clinic_id,
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


async def _is_clinic_admin_for_encounter(
    db: AsyncSession,
    user: User,
    enc: Encounter,
) -> bool:
    """True if the user holds an owner/admin membership on the encounter's clinic."""
    if enc.clinic_id is None:
        return False
    res = await db.execute(
        select(ClinicMembership.id).where(
            ClinicMembership.clinic_id == enc.clinic_id,
            ClinicMembership.user_id == user.id,
            ClinicMembership.role.in_(["owner", "admin"]),
            ClinicMembership.is_active.is_(True),
            ClinicMembership.deleted_at.is_(None),
        )
    )
    return res.scalar_one_or_none() is not None


async def _get_doctor_for_user(db: AsyncSession, user: User) -> Doctor | None:
    res = await db.execute(
        select(Doctor).where(Doctor.user_id == user.id, Doctor.deleted_at.is_(None))
    )
    return res.scalar_one_or_none()


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_encounter(
    req: EncounterCreate,
    doctor_info: tuple[User, Doctor] = Depends(get_verified_doctor),
    db: AsyncSession = Depends(get_db),
):
    """Create a SOAP encounter note. Doctor must have an existing relationship
    with the patient (authored record, shared clinic link, or a valid
    appointment supplied in the request)."""
    user, doctor = doctor_info

    # Verify patient exists
    patient_res = await db.execute(
        select(User).where(
            User.id == req.patient_id,
            User.deleted_at.is_(None),
            User.is_active.is_(True),
            User.role == "patient",
        )
    )
    if not patient_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Patient not found"}},
        )

    # If an appointment is supplied, it must belong to this doctor + patient
    appointment: Appointment | None = None
    if req.appointment_id is not None:
        appt_res = await db.execute(
            select(Appointment).where(
                Appointment.id == req.appointment_id,
                Appointment.deleted_at.is_(None),
            )
        )
        appointment = appt_res.scalar_one_or_none()
        if appointment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "NOT_FOUND", "message": "Appointment not found"}},
            )
        if appointment.doctor_id != doctor.id or appointment.patient_id != req.patient_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "APPOINTMENT_MISMATCH",
                        "message": "Appointment does not match this doctor and patient",
                    }
                },
            )

    # Relationship check (mirrors the doctor↔patient check used elsewhere)
    if not await _doctor_patient_relationship_exists(db, doctor, req.patient_id, appointment):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "PATIENT_ACCESS_DENIED", "message": "No relationship with this patient"}},
        )

    # Tenant validation: explicit clinic_id requires membership; otherwise
    # inherit the appointment's clinic when linked.
    effective_clinic_id = req.clinic_id
    if effective_clinic_id is None and appointment is not None:
        effective_clinic_id = appointment.clinic_id
    await _validate_clinic_membership(db, user, effective_clinic_id)

    enc = Encounter(
        id=uuid.uuid4(),
        patient_id=req.patient_id,
        doctor_id=doctor.id,
        appointment_id=appointment.id if appointment else None,
        clinic_id=effective_clinic_id,
        subjective=req.subjective,
        objective=req.objective,
        assessment=req.assessment,
        plan=req.plan,
        vitals_snapshot=req.vitals_snapshot,
    )
    db.add(enc)
    await db.flush()
    await db.refresh(enc)

    return await _load_encounter_with_names(db, enc)


@router.get("")
async def list_encounters(
    patient_id: UUID | None = Query(None),
    appointment_id: UUID | None = Query(None),
    date_param: str | None = Query(None, alias="date"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List encounters.
    - doctor: own encounters (patient_id filter still scoped to own)
    - patient: own encounters
    - admin: all encounters
    """
    stmt = select(Encounter).where(Encounter.deleted_at.is_(None))

    if current_user.role == "doctor":
        doctor = await _get_doctor_for_user(db, current_user)
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "NOT_FOUND", "message": "Doctor profile not found"}},
            )
        stmt = stmt.where(Encounter.doctor_id == doctor.id)
        if patient_id is not None:
            stmt = stmt.where(Encounter.patient_id == patient_id)
    elif current_user.role == "patient":
        stmt = stmt.where(Encounter.patient_id == current_user.id)
    elif current_user.role == "admin":
        if patient_id is not None:
            stmt = stmt.where(Encounter.patient_id == patient_id)
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Access denied"}},
        )

    if appointment_id is not None:
        stmt = stmt.where(Encounter.appointment_id == appointment_id)

    if date_param:
        try:
            filter_date = datetime.strptime(date_param, "%Y-%m-%d").date()
            # UTC day boundary — consistent with appointments/queue convention
            day_start = datetime.combine(filter_date, datetime.min.time(), tzinfo=timezone.utc)
            stmt = stmt.where(
                Encounter.created_at >= day_start,
                Encounter.created_at < day_start + timedelta(days=1),
            )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "INVALID_DATE", "message": "Invalid date format. Use YYYY-MM-DD"}},
            )

    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    result = await db.execute(
        stmt.order_by(Encounter.created_at.desc()).offset(offset).limit(limit)
    )
    encounters = result.scalars().all()

    data = await _load_encounters_with_names(db, encounters)
    return {"data": data, "total": total, "limit": limit, "offset": offset}


@router.get("/{encounter_id}")
async def get_encounter(
    encounter_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Read a single encounter. Allowed: the authoring doctor, the patient it
    belongs to, an owner/admin member of the encounter's clinic, or an admin."""
    result = await db.execute(
        select(Encounter).where(Encounter.id == encounter_id, Encounter.deleted_at.is_(None))
    )
    enc = result.scalar_one_or_none()
    if enc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Encounter not found"}},
        )

    allowed = False
    if current_user.role == "admin":
        allowed = True
    elif current_user.role == "patient":
        allowed = enc.patient_id == current_user.id
    elif current_user.role == "doctor":
        doctor = await _get_doctor_for_user(db, current_user)
        if doctor is not None and enc.doctor_id == doctor.id:
            allowed = True
        elif await _is_clinic_admin_for_encounter(db, current_user, enc):
            allowed = True

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Access denied"}},
        )

    return await _load_encounter_with_names(db, enc)


@router.patch("/{encounter_id}")
async def update_encounter(
    encounter_id: UUID,
    req: EncounterUpdate,
    doctor_info: tuple[User, Doctor] = Depends(get_verified_doctor),
    db: AsyncSession = Depends(get_db),
):
    """Update a SOAP encounter. Only the authoring doctor may edit."""
    user, doctor = doctor_info

    result = await db.execute(
        select(Encounter).where(Encounter.id == encounter_id, Encounter.deleted_at.is_(None))
    )
    enc = result.scalar_one_or_none()
    if enc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Encounter not found"}},
        )
    if enc.doctor_id != doctor.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Only the authoring doctor can edit this encounter"}},
        )

    update_fields = req.model_dump(exclude_unset=True)

    if "appointment_id" in update_fields:
        new_appt_id = update_fields["appointment_id"]
        if new_appt_id is None:
            enc.appointment_id = None
        else:
            appt_res = await db.execute(
                select(Appointment).where(
                    Appointment.id == new_appt_id,
                    Appointment.deleted_at.is_(None),
                )
            )
            appointment = appt_res.scalar_one_or_none()
            if appointment is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": {"code": "NOT_FOUND", "message": "Appointment not found"}},
                )
            if appointment.doctor_id != doctor.id or appointment.patient_id != enc.patient_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": {
                            "code": "APPOINTMENT_MISMATCH",
                            "message": "Appointment does not match this doctor and patient",
                        }
                    },
                )
            enc.appointment_id = appointment.id
            if enc.clinic_id is None and appointment.clinic_id is not None:
                await _validate_clinic_membership(db, user, appointment.clinic_id)
                enc.clinic_id = appointment.clinic_id

    if "clinic_id" in update_fields:
        new_clinic_id = update_fields["clinic_id"]
        if new_clinic_id is None and enc.clinic_id is not None:
            # Clearing clinic_id would hide the encounter from clinic admins —
            # disallow; move to another clinic instead.
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "VALIDATION_ERROR", "message": "clinic_id cannot be cleared once set"}},
            )
        await _validate_clinic_membership(db, user, new_clinic_id)
        enc.clinic_id = new_clinic_id

    for field in ("subjective", "objective", "assessment", "plan", "vitals_snapshot"):
        if field in update_fields:
            setattr(enc, field, update_fields[field])

    enc.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(enc)

    return await _load_encounter_with_names(db, enc)


@router.delete("/{encounter_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_encounter(
    encounter_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete an encounter. Allowed: the authoring doctor or an admin."""
    result = await db.execute(
        select(Encounter).where(Encounter.id == encounter_id, Encounter.deleted_at.is_(None))
    )
    enc = result.scalar_one_or_none()
    if enc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Encounter not found"}},
        )

    if current_user.role == "admin":
        pass
    elif current_user.role == "doctor":
        doctor = await _get_doctor_for_user(db, current_user)
        if doctor is None or enc.doctor_id != doctor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "FORBIDDEN", "message": "Only the authoring doctor or an admin can delete this encounter"}},
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Only the authoring doctor or an admin can delete this encounter"}},
        )

    enc.deleted_at = datetime.now(timezone.utc)
    enc.updated_at = datetime.now(timezone.utc)
    await db.flush()
