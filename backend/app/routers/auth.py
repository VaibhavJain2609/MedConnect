from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.clinic_invite import ClinicInvite
from app.models.doctor import Doctor
from app.models.user import User
from app.schemas.auth import UserResponse
from app.utils.keycloak_admin import assign_realm_role

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    return UserResponse(
        id=str(user.id),
        email=user.email,
        phone=user.phone,
        full_name=user.full_name,
        role=user.role,
        language_pref=user.language_pref,
    )


class SetRoleRequest(BaseModel):
    role: str
    invite_code: Optional[str] = None


async def _get_valid_doctor_invite(db: AsyncSession, code: str) -> ClinicInvite | None:
    """Return a usable doctor invite for the code, or None if invalid/expired/exhausted."""
    result = await db.execute(
        select(ClinicInvite).where(
            ClinicInvite.code == code.upper(),
            ClinicInvite.deleted_at.is_(None),
        )
    )
    invite = result.scalar_one_or_none()
    if invite is None or invite.role != "doctor":
        return None
    now = datetime.now(timezone.utc)
    if invite.expires_at and invite.expires_at < now:
        return None
    if invite.max_uses and invite.use_count >= invite.max_uses:
        return None
    return invite


@router.post("/set-role", status_code=200)
async def set_role(
    body: SetRoleRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.role not in ("patient", "doctor"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_ROLE", "message": "Role must be 'patient' or 'doctor'"}},
        )

    if body.role == "patient":
        # Open self-assignment. Note: roles granted in Keycloak still take
        # precedence — the token-claim sync re-applies them on each request,
        # so this cannot strip an existing doctor/admin role.
        await assign_realm_role(user.keycloak_sub, "patient")
        if user.role != "patient":
            user.role = "patient"
            await db.commit()
        return {"message": "Role updated to patient"}

    # body.role == "doctor" — privileged. Only allowed for admins or with a
    # valid, unexpired, non-exhausted clinic invite code for the doctor role.
    if user.role != "admin":
        if not body.invite_code:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "INVITE_REQUIRED",
                                  "message": "A valid clinic invite code is required to become a doctor"}},
            )
        invite = await _get_valid_doctor_invite(db, body.invite_code)
        if invite is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "INVALID_INVITE",
                                  "message": "Invite code is invalid, expired, or exhausted"}},
            )
        # The invite is validated here but NOT consumed — use_count is
        # incremented when the invite is actually redeemed for clinic
        # membership (redeem_invite / onboarding join_code).

    # Assign role in Keycloak so subsequent tokens carry the claim
    await assign_realm_role(user.keycloak_sub, "doctor")

    # Sync locally
    if user.role != "doctor":
        user.role = "doctor"

        # Create Doctor profile if missing
        result = await db.execute(select(Doctor).where(Doctor.user_id == user.id, Doctor.deleted_at.is_(None)))
        existing_doctor = result.scalar_one_or_none()
        if not existing_doctor:
            doctor = Doctor(user_id=user.id)
            db.add(doctor)

        await db.commit()

    return {"message": "Role updated to doctor"}
