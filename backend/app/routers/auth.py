from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
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


@router.post("/set-role", status_code=200)
async def set_role(
    body: SetRoleRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.role != "doctor":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_ROLE", "message": "Only 'doctor' role can be self-assigned"}},
        )

    # Assign role in Keycloak
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
