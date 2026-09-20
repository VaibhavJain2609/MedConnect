import uuid
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import invalidate_user_cache, require_admin
from app.models.doctor import Doctor
from app.models.medical_record import MedicalRecord
from app.models.notification import Notification, NotificationType
from app.models.prescription import Prescription
from app.models.user import User

router = APIRouter(prefix="/api/v1/admin", tags=["admin", "doctors"])


class DoctorVerifyRequest(BaseModel):
    action: Literal["approve", "reject"]
    reason: str = ""


class AdminDoctorDetailResponse(BaseModel):
    id: str
    user_id: str
    name: str
    email: str | None
    phone: str | None
    specialization: str | None
    license_number: str | None
    facility_name: str | None
    facility_city: str | None
    verified: bool
    created_at: datetime
    updated_at: datetime
    is_active: bool
    prescriptions_count: int
    records_count: int


@router.get("/doctors")
async def list_admin_doctors(
    search: str | None = Query(None),
    specialty: str | None = Query(None),
    verified: str | None = Query(None),  # "true", "false", or None for all
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=100),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all doctors for admin with optional filters (MD-33)."""
    stmt = (
        select(Doctor, User)
        .join(User, Doctor.user_id == User.id)
        .where(Doctor.deleted_at.is_(None), User.deleted_at.is_(None))
    )

    if search:
        stmt = stmt.where(
            User.full_name.ilike(f"%{search}%")
            | User.email.ilike(f"%{search}%")
            | Doctor.license_number.ilike(f"%{search}%")
        )

    if specialty:
        stmt = stmt.where(Doctor.specialization.ilike(f"%{specialty}%"))

    if verified == "true":
        stmt = stmt.where(Doctor.verified.is_(True))
    elif verified == "false":
        stmt = stmt.where(Doctor.verified.is_(False))

    # Total count
    count_result = await db.scalar(
        select(func.count()).select_from(stmt.subquery())
    )
    total = count_result or 0

    # Paginated results
    offset = (page - 1) * limit
    stmt = stmt.offset(offset).limit(limit).order_by(Doctor.created_at.desc())
    result = await db.execute(stmt)
    rows = result.all()

    doctors = [
        {
            "id": str(doctor.id),
            "user_id": str(doctor.user_id),
            "name": user.full_name,
            "email": user.email,
            "specialization": doctor.specialization,
            "license_number": doctor.license_number,
            "facility_name": doctor.facility_name,
            "facility_city": doctor.facility_city,
            "verified": doctor.verified,
            "created_at": doctor.created_at.isoformat(),
        }
        for doctor, user in rows
    ]

    return {
        "doctors": doctors,
        "total": total,
        "page": page,
        "limit": limit,
        "totalPages": max(1, (total + limit - 1) // limit),
    }


@router.get("/doctors/specialties")
async def list_doctor_specialties(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List distinct doctor specializations for filter dropdown (MD-33)."""
    result = await db.execute(
        select(Doctor.specialization)
        .where(Doctor.deleted_at.is_(None), Doctor.specialization.isnot(None))
        .distinct()
        .order_by(Doctor.specialization)
    )
    return [row[0] for row in result.all()]


@router.get("/doctors/{doctor_id}", response_model=AdminDoctorDetailResponse)
async def get_doctor_detail(
    doctor_id: UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get full doctor detail for admin review (MD-65)."""
    result = await db.execute(
        select(Doctor)
        .options(selectinload(Doctor.user))
        .where(Doctor.id == doctor_id, Doctor.deleted_at.is_(None))
    )
    doctor = result.scalar_one_or_none()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Doctor not found"}},
        )

    user = doctor.user

    prescriptions_count = (
        await db.scalar(
            select(func.count()).where(
                Prescription.doctor_id == doctor.id,
                Prescription.deleted_at.is_(None),
            )
        )
        or 0
    )
    records_count = (
        await db.scalar(
            select(func.count()).where(
                MedicalRecord.doctor_id == doctor.id,
                MedicalRecord.deleted_at.is_(None),
            )
        )
        or 0
    )

    return AdminDoctorDetailResponse(
        id=str(doctor.id),
        user_id=str(doctor.user_id),
        name=user.full_name,
        email=user.email,
        phone=user.phone,
        specialization=doctor.specialization,
        license_number=doctor.license_number,
        facility_name=doctor.facility_name,
        facility_city=doctor.facility_city,
        verified=doctor.verified,
        created_at=doctor.created_at,
        updated_at=doctor.updated_at,
        is_active=user.is_active,
        prescriptions_count=prescriptions_count,
        records_count=records_count,
    )


@router.put("/doctors/{doctor_id}/verify")
async def verify_doctor(
    doctor_id: UUID,
    body: DoctorVerifyRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Approve or reject doctor verification (MD-66)."""
    result = await db.execute(
        select(Doctor).where(Doctor.id == doctor_id, Doctor.deleted_at.is_(None))
    )
    doctor = result.scalar_one_or_none()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Doctor not found"}},
        )

    old_verified = doctor.verified
    doctor.verified = body.action == "approve"

    if body.action == "approve":
        notif_title = "Verification Approved"
        notif_msg = (
            f"Your doctor profile has been approved. {body.reason}".strip()
            if body.reason
            else "Your doctor profile has been approved."
        )
    else:
        notif_title = "Verification Rejected"
        notif_msg = (
            f"Your doctor profile verification was rejected. Reason: {body.reason}"
            if body.reason
            else "Your doctor profile verification was rejected."
        )

    db.add(
        Notification(
            user_id=doctor.user_id,
            type=NotificationType.SYSTEM,
            title=notif_title,
            message=notif_msg,
            action_url="/doctor/dashboard",
        )
    )

    from app.services.audit_service import log_change
    await log_change(
        db=db,
        table_name="doctors",
        record_id=doctor.id,
        action="UPDATE",
        old_values={"verified": old_verified},
        new_values={"verified": doctor.verified, "action": body.action, "reason": body.reason},
    )
    await db.commit()
    await db.refresh(doctor)

    return {
        "id": str(doctor.id),
        "verified": doctor.verified,
        "message": f"Doctor {'approved' if body.action == 'approve' else 'rejected'} successfully",
    }


class AdminDoctorCreateRequest(BaseModel):
    # Frontend sends Partial<Doctor> which uses `name`; accept full_name too.
    name: str | None = None
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    specialization: str | None = None
    license_number: str | None = None
    facility_name: str | None = None
    facility_city: str | None = None
    verified: bool = False


class AdminDoctorUpdateRequest(BaseModel):
    name: str | None = None
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    is_active: bool | None = None
    specialization: str | None = None
    license_number: str | None = None
    facility_name: str | None = None
    facility_city: str | None = None
    verified: bool | None = None


def _doctor_payload(doctor: Doctor, user: User) -> dict:
    """Same shape as list_admin_doctors items / frontend Doctor interface."""
    return {
        "id": str(doctor.id),
        "user_id": str(doctor.user_id),
        "name": user.full_name,
        "email": user.email,
        "specialization": doctor.specialization,
        "license_number": doctor.license_number,
        "facility_name": doctor.facility_name,
        "facility_city": doctor.facility_city,
        "verified": doctor.verified,
        "created_at": doctor.created_at.isoformat(),
    }


@router.post("/doctors", status_code=status.HTTP_201_CREATED)
async def create_doctor(
    body: AdminDoctorCreateRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a doctor: local User (role=doctor) + Doctor profile.

    The account is local-only (walkin: keycloak_sub) — the doctor cannot log in
    until a Keycloak account is linked, same convention as walk-in patients."""
    full_name = (body.full_name or body.name or "").strip()
    if not full_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "VALIDATION_ERROR", "message": "name is required"}},
        )

    user = User(
        id=uuid.uuid4(),
        keycloak_sub=f"walkin:{uuid.uuid4()}",
        full_name=full_name,
        email=body.email or None,
        phone=body.phone or None,
        role="doctor",
    )
    db.add(user)
    await db.flush()

    doctor = Doctor(
        id=uuid.uuid4(),
        user_id=user.id,
        specialization=body.specialization,
        license_number=body.license_number,
        facility_name=body.facility_name,
        facility_city=body.facility_city,
        verified=body.verified,
    )
    db.add(doctor)
    await db.flush()

    from app.services.audit_service import log_change
    await log_change(
        db=db,
        table_name="doctors",
        record_id=doctor.id,
        action="INSERT",
        old_values=None,
        new_values={k: v for k, v in body.model_dump(exclude_none=True).items()},
    )
    await db.commit()
    await db.refresh(doctor)
    await db.refresh(user)

    return _doctor_payload(doctor, user)


@router.put("/doctors/{doctor_id}")
async def update_doctor(
    doctor_id: UUID,
    body: AdminDoctorUpdateRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update a doctor's profile and linked user fields."""
    result = await db.execute(
        select(Doctor)
        .options(selectinload(Doctor.user))
        .where(Doctor.id == doctor_id, Doctor.deleted_at.is_(None))
    )
    doctor = result.scalar_one_or_none()
    if not doctor or doctor.user is None or doctor.user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Doctor not found"}},
        )

    user = doctor.user
    now = datetime.now(timezone.utc)
    user_touched = False
    doctor_touched = False

    full_name = body.full_name if body.full_name is not None else body.name
    if full_name is not None:
        user.full_name = full_name
        user_touched = True
    if body.email is not None:
        user.email = body.email
        user_touched = True
    if body.phone is not None:
        user.phone = body.phone
        user_touched = True
    if body.is_active is not None:
        user.is_active = body.is_active
        user_touched = True

    if body.specialization is not None:
        doctor.specialization = body.specialization
        doctor_touched = True
    if body.license_number is not None:
        doctor.license_number = body.license_number
        doctor_touched = True
    if body.facility_name is not None:
        doctor.facility_name = body.facility_name
        doctor_touched = True
    if body.facility_city is not None:
        doctor.facility_city = body.facility_city
        doctor_touched = True
    if body.verified is not None:
        doctor.verified = body.verified
        doctor_touched = True

    if user_touched:
        user.updated_at = now
        invalidate_user_cache(user.keycloak_sub)
    if doctor_touched:
        doctor.updated_at = now

    from app.services.audit_service import log_change
    await log_change(
        db=db,
        table_name="doctors",
        record_id=doctor.id,
        action="UPDATE",
        old_values=None,
        new_values={k: v for k, v in body.model_dump(exclude_none=True).items()},
    )
    await db.commit()
    await db.refresh(doctor)
    await db.refresh(user)

    return _doctor_payload(doctor, user)


@router.delete("/doctors/{doctor_id}")
async def delete_doctor(
    doctor_id: UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a doctor profile and deactivate the linked user."""
    result = await db.execute(
        select(Doctor)
        .options(selectinload(Doctor.user))
        .where(Doctor.id == doctor_id, Doctor.deleted_at.is_(None))
    )
    doctor = result.scalar_one_or_none()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Doctor not found"}},
        )

    # Self-sabotage guard — mirrors admin/users.py: deleting the profile also
    # deactivates the linked user, which would lock an admin out of their own
    # account when the two are the same person.
    if doctor.user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "SELF_DELETE", "message": "Cannot delete your own doctor profile"}},
        )

    now = datetime.now(timezone.utc)
    doctor.deleted_at = now
    doctor.updated_at = now

    user = doctor.user
    if user is not None and user.deleted_at is None:
        user.deleted_at = now
        user.updated_at = now
        user.is_active = False
        invalidate_user_cache(user.keycloak_sub)

    from app.services.audit_service import log_change
    await log_change(
        db=db,
        table_name="doctors",
        record_id=doctor.id,
        action="DELETE",
        old_values={"verified": doctor.verified, "specialization": doctor.specialization},
        new_values={"deleted": True},
    )
    await db.commit()

    return {"id": str(doctor.id), "message": "Doctor deleted successfully"}
