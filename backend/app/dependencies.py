import asyncio
import logging
import time
import uuid
from typing import NamedTuple

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.clinic import ClinicMembership
from app.models.doctor import Doctor
from app.models.user import User
from app.services.audit_service import set_audit_user
from app.utils.security import decode_keycloak_token

security = HTTPBearer(auto_error=False)

_logger = logging.getLogger(__name__)

# MD-383: Short-lived in-process user cache keyed by Keycloak sub.
# Stores a minimal immutable snapshot (NOT the ORM instance) so that the
# object returned to callers is always attached to the request's session —
# mutations made by endpoints (e.g. role changes) actually persist.
# A role/is_active mismatch forces a cache miss so changes propagate
# within TTL, and the cached user_id is re-loaded via db.get() so a
# deactivated/deleted account is rejected instead of served stale.
class _CachedUser(NamedTuple):
    expires_at: float  # time.monotonic() deadline
    user_id: uuid.UUID
    role: str
    is_active: bool
    email: str | None
    full_name: str | None


_user_cache: dict[str, _CachedUser] = {}
_USER_CACHE_TTL = 30.0  # seconds
_USER_CACHE_MAX = 2048  # bound the dict so it can't grow without limit


def _user_cache_put(sub: str, entry: _CachedUser) -> None:
    """Insert a cache entry, evicting expired entries (then the oldest) when full."""
    if len(_user_cache) >= _USER_CACHE_MAX:
        now = time.monotonic()
        for key in [k for k, v in _user_cache.items() if v.expires_at <= now]:
            _user_cache.pop(key, None)
        if len(_user_cache) >= _USER_CACHE_MAX:
            oldest = min(_user_cache, key=lambda k: _user_cache[k].expires_at)
            _user_cache.pop(oldest, None)
    _user_cache[sub] = entry


def invalidate_user_cache(sub: str | None) -> None:
    """Drop a cached user entry (e.g. after an admin role/deactivation change)."""
    if sub:
        _user_cache.pop(sub, None)


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
    # JWKS fetch + JWT verification is synchronous/blocking — run off the event loop.
    payload = await asyncio.to_thread(decode_keycloak_token, credentials.credentials)
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

    # MD-383: Fast path — a cached snapshot lets us skip the claim-sync write
    # path. The user row is re-loaded via db.get() so the returned ORM object
    # is bound to this request's session (mutations persist) and stale
    # deactivated/deleted accounts are not served from cache.
    _now = time.monotonic()
    _cached = _user_cache.get(sub)
    # A claim mismatch (name/email changed in Keycloak) forces a cache miss so
    # the sync path below still propagates updated claims to the local row.
    if (
        _cached is not None
        and _cached.expires_at > _now
        and _cached.role == role
        and _cached.is_active
        and _cached.email == payload.get("email")
        and _cached.full_name == payload.get("name", payload.get("preferred_username"))
    ):
        user = await db.get(User, _cached.user_id)
        if (
            user is not None
            and user.deleted_at is None
            and user.is_active
            and user.role == role
        ):
            set_audit_user(user.id)
            return user
        _user_cache.pop(sub, None)

    # Lookup by keycloak_sub (any state, so we can distinguish a disabled or
    # deleted account from a genuinely new user instead of auto-provisioning
    # over an existing row).
    result = await db.execute(
        select(User).where(User.keycloak_sub == sub)
    )
    user = result.scalar_one_or_none()

    if user is not None and (user.deleted_at is not None or not user.is_active):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "ACCOUNT_DISABLED", "message": "Account is deactivated"}},
        )

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
        user = result.scalar_one_or_none()
        if user is None:
            # A concurrent insert landed a deactivated/deleted row, or the row
            # was removed between the conflict check and this read.
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "ACCOUNT_DISABLED", "message": "Account is deactivated"}},
            )

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
    elif getattr(user, "erased_at", None) is not None:
        # Erased (DPDP) user — do NOT resurrect name/email from token claims.
        # Only the role is kept in sync; PII fields stay anonymized.
        if user.role != role:
            user.role = role
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

    set_audit_user(user.id)
    # Populate cache for subsequent requests from the same token subject.
    # Only an immutable snapshot is stored — never the ORM instance.
    _user_cache_put(
        sub,
        _CachedUser(
            expires_at=time.monotonic() + _USER_CACHE_TTL,
            user_id=user.id,
            role=user.role,
            is_active=user.is_active,
            email=user.email,
            full_name=user.full_name,
        ),
    )
    return user


async def get_current_doctor(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> tuple[User, Doctor]:
    """Doctor role + Doctor profile. Does NOT require admin verification —
    use `get_verified_doctor` for endpoints that expose patient data.
    This unverified variant must remain available for onboarding flows."""
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
