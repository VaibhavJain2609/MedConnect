import uuid

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.clinic import ClinicMembership
from app.models.doctor import Doctor
from app.models.user import User
from app.utils.security import decode_keycloak_token

security = HTTPBearer(auto_error=False)


import logging

_logger = logging.getLogger(__name__)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "UNAUTHORIZED", "message": "Authorization header missing"}},
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_keycloak_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "UNAUTHORIZED", "message": "Invalid or expired token"}},
            headers={"WWW-Authenticate": "Bearer"},
        )

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "UNAUTHORIZED", "message": "Invalid token payload"}},
        )

    # Lookup by keycloak_sub
    result = await db.execute(
        select(User).where(User.keycloak_sub == sub, User.deleted_at.is_(None), User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()

    # Extract role from token claims
    realm_access = payload.get("realm_access", {})
    roles = realm_access.get("roles", [])
    # Priority: admin > doctor > patient (default)
    if "admin" in roles:
        role = "admin"
    elif "doctor" in roles:
        role = "doctor"
    else:
        role = "patient"

    if not user:
        # Auto-provision: use INSERT ... ON CONFLICT DO NOTHING to avoid race conditions
        # when two concurrent requests arrive for the same new Keycloak user.
        new_id = uuid.uuid4()
        stmt = (
            pg_insert(User)
            .values(
                id=new_id,
                keycloak_sub=sub,
                email=payload.get("email"),
                full_name=payload.get("name", payload.get("preferred_username", "Unknown")),
                role=role,
            )
            .on_conflict_do_nothing(index_elements=["keycloak_sub"])
        )
        await db.execute(stmt)
        # Re-fetch regardless of whether we won or lost the race
        result = await db.execute(
            select(User).where(User.keycloak_sub == sub, User.deleted_at.is_(None), User.is_active.is_(True))
        )
        user = result.scalar_one()

        # Create Doctor profile if needed — INSERT ON CONFLICT to avoid race conditions
        if role == "doctor":
            doc_stmt = (
                pg_insert(Doctor)
                .values(id=uuid.uuid4(), user_id=user.id)
                .on_conflict_do_nothing(
                    index_elements=["user_id"],
                    index_where=Doctor.deleted_at.is_(None),
                )
            )
            await db.execute(doc_stmt)
            await db.flush()
    else:
        # Sync: update local user from token claims on every request
        changed = False
        if payload.get("email") and user.email != payload["email"]:
            user.email = payload["email"]
            changed = True
        name = payload.get("name", payload.get("preferred_username"))
        if name and user.full_name != name:
            user.full_name = name
            changed = True
        if user.role != role:
            # Role changed in Keycloak - update locally
            if role == "doctor" and user.role != "doctor":
                # Became a doctor — insert profile, ignore conflict (race-safe)
                doc_stmt = (
                    pg_insert(Doctor)
                    .values(id=uuid.uuid4(), user_id=user.id)
                    .on_conflict_do_nothing(
                        index_elements=["user_id"],
                        index_where=Doctor.deleted_at.is_(None),
                    )
                )
                await db.execute(doc_stmt)
            user.role = role
            changed = True
        if changed:
            await db.flush()

    from app.services.audit_service import set_audit_user
    set_audit_user(user.id)
    return user


async def get_current_doctor(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> tuple[User, Doctor]:
    if user.role != "doctor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Doctor access required"}},
        )
    result = await db.execute(
        select(Doctor).where(Doctor.user_id == user.id, Doctor.deleted_at.is_(None))
    )
    doctor = result.scalar_one_or_none()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Doctor profile not found"}},
        )
    return user, doctor


async def require_patient(user: User = Depends(get_current_user)) -> User:
    if user.role != "patient":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Patient access required"}},
        )
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """Require admin role for access (MD-32)"""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Admin access required"}},
        )
    return user


async def get_active_clinic(
    x_clinic_id: str | None = Header(None, alias="X-Clinic-Id"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> tuple[uuid.UUID, str] | None:
    """
    Reads X-Clinic-Id header, verifies the user has an active ClinicMembership.
    Returns (clinic_id, membership_role) or None if header is absent.
    Raises 403 if header is present but user is not a member.
    """
    if not x_clinic_id:
        return None
    try:
        clinic_id = uuid.UUID(x_clinic_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "INVALID_CLINIC_ID", "message": "Invalid clinic ID format"}},
        )

    result = await db.execute(
        select(ClinicMembership).where(
            ClinicMembership.clinic_id == clinic_id,
            ClinicMembership.user_id == user.id,
            ClinicMembership.is_active.is_(True),
            ClinicMembership.deleted_at.is_(None),
        )
    )
    membership = result.scalar_one_or_none()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "NOT_CLINIC_MEMBER", "message": "Not a member of this clinic"}},
        )
    return clinic_id, membership.role


async def require_active_clinic(
    x_clinic_id: str | None = Header(None, alias="X-Clinic-Id"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> tuple[uuid.UUID, str]:
    """
    Same as get_active_clinic but raises 400 if header missing (strict version).
    Use for clinic-specific endpoints that always require a clinic context.
    """
    if not x_clinic_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "MISSING_CLINIC", "message": "X-Clinic-Id header required"}},
        )
    result = await get_active_clinic(x_clinic_id, user, db)
    return result  # type: ignore


async def get_verified_doctor(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> tuple[User, Doctor]:
    """Requires doctor role + verified=True + onboarding_step=completed."""
    if user.role != "doctor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Doctor access required"}},
        )
    result = await db.execute(
        select(Doctor).where(Doctor.user_id == user.id, Doctor.deleted_at.is_(None))
    )
    doctor = result.scalar_one_or_none()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Doctor profile not found"}},
        )
    if not doctor.verified or doctor.onboarding_step != "completed":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "ONBOARDING_INCOMPLETE",
                              "message": "Doctor verification not complete"}},
        )
    return user, doctor
