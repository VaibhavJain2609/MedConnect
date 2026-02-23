from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.doctor import Doctor
from app.models.user import User
from app.utils.security import decode_keycloak_token

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials:
        print("❌ Authorization header missing")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "UNAUTHORIZED", "message": "Authorization header missing"}},
            headers={"WWW-Authenticate": "Bearer"},
        )
    print(f"✓ Token received: {credentials.credentials[:50]}...")
    payload = decode_keycloak_token(credentials.credentials)
    if payload is None:
        print(f"❌ Token validation failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "UNAUTHORIZED", "message": "Invalid or expired token"}},
            headers={"WWW-Authenticate": "Bearer"},
        )
    print(f"✓ Token valid, issuer: {payload.get('iss')}")

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
    role = "doctor" if "doctor" in roles else "patient"

    if not user:
        # Auto-provision: create local user from Keycloak token claims
        user = User(
            keycloak_sub=sub,
            email=payload.get("email"),
            full_name=payload.get("name", payload.get("preferred_username", "Unknown")),
            role=role,
        )
        db.add(user)
        await db.flush()

        # If doctor role, also create Doctor profile
        if role == "doctor":
            doctor = Doctor(user_id=user.id)
            db.add(doctor)
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
                # Became a doctor, create Doctor profile if missing
                doc_result = await db.execute(
                    select(Doctor).where(Doctor.user_id == user.id, Doctor.deleted_at.is_(None))
                )
                if not doc_result.scalar_one_or_none():
                    db.add(Doctor(user_id=user.id))
            user.role = role
            changed = True
        if changed:
            await db.flush()

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
