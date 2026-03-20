"""
Doctor onboarding endpoints  [MD-208]

GET  /api/v1/onboarding/status      — current step + data
PUT  /api/v1/onboarding/profile     — step 1: name, specialization, phone
PUT  /api/v1/onboarding/license     — step 2: license number, council, year
POST /api/v1/onboarding/clinic      — step 3: create or join clinic
POST /api/v1/onboarding/verify-nhr  — trigger NHR verification (stubbed)
"""
from typing import Optional

import uuid as _uuid_mod
from datetime import timezone as _tz

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.doctor import Doctor
from app.models.user import User
from app.schemas.clinic import ClinicCreate
from app.services import clinic_service
from app.services.nhr_service import verify_license

router = APIRouter(prefix="/api/v1/onboarding", tags=["onboarding"])

ONBOARDING_STEPS = ["pending", "profile", "license", "clinic", "completed"]


async def _get_doctor(db: AsyncSession, user: User) -> Doctor:
    result = await db.execute(
        select(Doctor).where(Doctor.user_id == user.id, Doctor.deleted_at.is_(None))
    )
    doctor = result.scalar_one_or_none()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Doctor profile not found"}},
        )
    return doctor


def _require_doctor_role(user: User):
    if user.role != "doctor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Doctor access required"}},
        )


# ── Status ────────────────────────────────────────────────────────────────

@router.get("/status")
async def get_onboarding_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_doctor_role(user)
    doctor = await _get_doctor(db, user)

    return {
        "onboarding_step": doctor.onboarding_step,
        "verified": doctor.verified,
        "nhr_verification_status": doctor.nhr_verification_status,
        "profile": {
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone,
            "specialization": doctor.specialization,
        },
        "license": {
            "license_number": doctor.license_number,
            "license_council": doctor.license_council,
            "license_year": doctor.license_year,
        },
    }


# ── Step 1: Profile ───────────────────────────────────────────────────────

class ProfileStepRequest(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    specialization: Optional[str] = None


@router.put("/profile")
async def onboarding_profile(
    data: ProfileStepRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_doctor_role(user)
    doctor = await _get_doctor(db, user)

    if data.full_name:
        user.full_name = data.full_name
    if data.phone:
        user.phone = data.phone
    if data.specialization is not None:
        doctor.specialization = data.specialization

    if doctor.onboarding_step in ("pending", "profile"):
        doctor.onboarding_step = "license"

    await db.flush()
    return {"onboarding_step": doctor.onboarding_step, "message": "Profile updated"}


# ── Step 2: License ───────────────────────────────────────────────────────

class LicenseStepRequest(BaseModel):
    license_number: str
    license_council: str
    license_year: int


@router.put("/license")
async def onboarding_license(
    data: LicenseStepRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_doctor_role(user)
    doctor = await _get_doctor(db, user)

    doctor.license_number = data.license_number
    doctor.license_council = data.license_council
    doctor.license_year = data.license_year

    if doctor.onboarding_step in ("pending", "profile", "license"):
        doctor.onboarding_step = "clinic"

    await db.flush()
    return {"onboarding_step": doctor.onboarding_step, "message": "License details saved"}


# ── Step 3: Clinic ────────────────────────────────────────────────────────

class ClinicStepRequest(BaseModel):
    action: str  # "create" | "join_code" | "join_request"
    clinic_data: Optional[ClinicCreate] = None
    invite_code: Optional[str] = None
    clinic_id: Optional[str] = None


@router.post("/clinic")
async def onboarding_clinic(
    data: ClinicStepRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_doctor_role(user)
    doctor = await _get_doctor(db, user)

    if data.action == "create":
        if not data.clinic_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "MISSING_DATA", "message": "clinic_data required for create action"}},
            )
        clinic = await clinic_service.create_clinic(db, data.clinic_data, user.id)
        clinic_id = str(clinic.id)

    elif data.action == "join_code":
        from app.models.clinic_invite import ClinicInvite
        from app.models.clinic import ClinicMembership
        from datetime import datetime as _dt

        if not data.invite_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "MISSING_DATA", "message": "invite_code required"}},
            )
        result = await db.execute(
            select(ClinicInvite).where(
                ClinicInvite.code == data.invite_code.upper(),
                ClinicInvite.deleted_at.is_(None),
            )
        )
        invite = result.scalar_one_or_none()
        if not invite:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "INVALID_CODE", "message": "Invite code not found"}},
            )
        if invite.expires_at and invite.expires_at < _dt.now(_tz.utc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "EXPIRED_CODE", "message": "Invite code expired"}},
            )
        membership = ClinicMembership(
            id=_uuid_mod.uuid4(),
            clinic_id=invite.clinic_id,
            user_id=user.id,
            role=invite.role,
            is_active=True,
            joined_at=_dt.now(_tz.utc),
        )
        db.add(membership)
        invite.use_count += 1
        await db.flush()
        clinic_id = str(invite.clinic_id)

    elif data.action == "join_request":
        from app.models.clinic_invite import ClinicJoinRequest
        from datetime import datetime as _dt

        if not data.clinic_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "MISSING_DATA", "message": "clinic_id required"}},
            )
        req = ClinicJoinRequest(
            id=_uuid_mod.uuid4(),
            clinic_id=_uuid_mod.UUID(data.clinic_id),
            user_id=user.id,
            message="Requesting to join from onboarding",
            status="pending",
        )
        db.add(req)
        await db.flush()
        # Don't advance to completed — wait for approval
        return {
            "onboarding_step": doctor.onboarding_step,
            "message": "Join request submitted. Awaiting clinic admin approval.",
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_ACTION",
                              "message": "action must be one of: create, join_code, join_request"}},
        )

    doctor.onboarding_step = "completed"
    await db.flush()

    return {
        "onboarding_step": doctor.onboarding_step,
        "clinic_id": clinic_id,
        "message": "Clinic step completed. Awaiting platform verification.",
    }


# ── NHR Verification ──────────────────────────────────────────────────────

@router.post("/verify-nhr")
async def trigger_nhr_verification(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_doctor_role(user)
    doctor = await _get_doctor(db, user)

    if not doctor.license_number or not doctor.license_council or not doctor.license_year:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "MISSING_LICENSE",
                              "message": "Complete license details before NHR verification"}},
        )

    result = await verify_license(
        license_number=doctor.license_number,
        license_council=doctor.license_council,
        license_year=doctor.license_year,
        doctor_name=user.full_name,
    )

    doctor.nhr_verification_status = "verified" if result["verified"] else "failed"
    doctor.verification_notes = result["notes"]
    await db.flush()

    return {
        "nhr_verification_status": doctor.nhr_verification_status,
        "notes": result["notes"],
        "nhr_id": result.get("nhr_id"),
    }
