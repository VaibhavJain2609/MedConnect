import math
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import require_admin
from app.models.medical_record import MedicalRecord
from app.models.prescription import Prescription
from app.models.user import User
from app.schemas.user import (
    AdminUserDeleteResponse,
    AdminUserDetailResponse,
    AdminUserUpdateRequest,
    AdminUserUpdateResponse,
    AdminUsersListResponse,
)

router = APIRouter(
    prefix="/api/v1/admin/users",
    tags=["admin-users"],
    dependencies=[Depends(require_admin)],
)


@router.get("", response_model=AdminUsersListResponse)
async def list_users(
    search: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(User).where(User.deleted_at.is_(None))

    if search:
        query = query.where(
            User.full_name.ilike(f"%{search}%")
            | User.email.ilike(f"%{search}%")
            | User.phone.ilike(f"%{search}%")
        )
    if role and role != "all":
        query = query.where(User.role == role)
    if is_active is not None:
        query = query.where(User.is_active.is_(is_active))

    total = await db.scalar(select(func.count()).select_from(query.subquery())) or 0
    result = await db.execute(
        query.order_by(User.created_at.desc()).offset((page - 1) * limit).limit(limit)
    )
    users = result.scalars().all()

    return AdminUsersListResponse(
        data=[
            {
                "id": str(u.id),
                "full_name": u.full_name,
                "email": u.email,
                "phone": u.phone,
                "role": u.role,
                "is_active": u.is_active,
                "created_at": u.created_at,
            }
            for u in users
        ],
        total=total,
        page=page,
        limit=limit,
        totalPages=math.ceil(total / limit) if total else 0,
    )


@router.get("/{user_id}", response_model=AdminUserDetailResponse)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User)
        .options(selectinload(User.doctor_profile))
        .where(User.id == user_id, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "User not found"}},
        )

    records_count = (
        await db.scalar(
            select(func.count()).where(
                MedicalRecord.patient_id == user.id,
                MedicalRecord.deleted_at.is_(None),
            )
        )
        or 0
    )
    prescriptions_count = (
        await db.scalar(
            select(func.count()).where(
                Prescription.patient_id == user.id,
                Prescription.deleted_at.is_(None),
            )
        )
        or 0
    )

    return AdminUserDetailResponse(
        id=str(user.id),
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        role=user.role,
        is_active=user.is_active,
        language_pref=user.language_pref,
        blood_group=user.blood_group,
        emergency_contact_name=user.emergency_contact_name,
        emergency_contact_phone=user.emergency_contact_phone,
        created_at=user.created_at,
        updated_at=user.updated_at,
        doctor_profile=user.doctor_profile,
        records_count=records_count,
        prescriptions_count=prescriptions_count,
    )


VALID_ROLES = {"patient", "doctor", "admin"}


@router.put("/{user_id}", response_model=AdminUserUpdateResponse)
async def update_user(
    user_id: str,
    body: AdminUserUpdateRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if str(admin.id) == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "SELF_MODIFY", "message": "Cannot modify your own account"}},
        )

    result = await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "User not found"}},
        )

    if body.role is not None and body.role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_ROLE", "message": f"Role must be one of: {', '.join(VALID_ROLES)}"}},
        )

    updated = False
    if body.full_name is not None:
        user.full_name = body.full_name
        updated = True
    if body.email is not None:
        user.email = body.email
        updated = True
    if body.phone is not None:
        user.phone = body.phone
        updated = True
    if body.role is not None:
        user.role = body.role
        updated = True
    if body.is_active is not None:
        user.is_active = body.is_active
        updated = True
    if body.language_pref is not None:
        user.language_pref = body.language_pref
        updated = True

    if updated:
        user.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(user)

    return AdminUserUpdateResponse(
        id=str(user.id),
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        role=user.role,
        is_active=user.is_active,
        language_pref=user.language_pref,
        message="User updated successfully",
    )


@router.delete("/{user_id}", response_model=AdminUserDeleteResponse)
async def delete_user(
    user_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if str(admin.id) == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "SELF_DELETE", "message": "Cannot delete your own account"}},
        )

    result = await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "User not found"}},
        )

    user.deleted_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)

    await db.commit()

    return AdminUserDeleteResponse(
        id=str(user.id),
        message="User deleted successfully",
    )
