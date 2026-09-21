"""
Clinic invite & join request endpoints  [MD-216, MD-217]

POST   /api/v1/clinics/{id}/invites              — generate invite
GET    /api/v1/clinics/{id}/invites              — list active invites
DELETE /api/v1/clinics/{id}/invites/{invite_id}  — revoke invite
POST   /api/v1/invites/redeem                    — redeem invite code
GET    /api/v1/clinics/search                    — search clinics to join
POST   /api/v1/clinics/{id}/join-request         — request to join
GET    /api/v1/clinics/{id}/join-requests        — list pending requests (clinic admin)
PUT    /api/v1/clinics/{id}/join-requests/{rid}  — approve/reject
"""
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.clinic import Clinic, ClinicMembership
from app.models.clinic_invite import ClinicInvite, ClinicJoinRequest
from app.models.user import User
from app.services import clinic_service
from app.services.notification_service import create_notification

router = APIRouter(prefix="/api/v1", tags=["clinic-invites"])


# ── Helpers ────────────────────────────────────────────────────────────────

async def _require_clinic_admin(db: AsyncSession, user: User, clinic_id: uuid.UUID):
    membership = await clinic_service.get_user_membership(db, user.id, clinic_id)
    if not membership or membership.role not in ("owner", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Clinic admin access required"}},
        )
    return membership


# ── Invite generation ──────────────────────────────────────────────────────

class InviteCreateRequest(BaseModel):
    invite_type: str = "code"  # code | email
    email: Optional[str] = None
    # Whitelisted: clinic invites only ever grant non-privileged staff roles
    # (doctor | receptionist). Accepting arbitrary strings would let an invite
    # mint e.g. "owner"/"admin" members.
    role: Literal["doctor", "receptionist"] = "doctor"
    expires_days: int = 7
    max_uses: Optional[int] = None


@router.post("/clinics/{clinic_id}/invites", status_code=status.HTTP_201_CREATED)
async def create_invite(
    clinic_id: str,
    data: InviteCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        cid = uuid.UUID(clinic_id)
    except ValueError:
        raise HTTPException(status_code=422, detail={"error": {"code": "INVALID_ID"}})

    await _require_clinic_admin(db, user, cid)

    code = secrets.token_urlsafe(12)[:16].upper()
    invite = ClinicInvite(
        id=uuid.uuid4(),
        clinic_id=cid,
        invite_type=data.invite_type,
        code=code,
        email=data.email,
        role=data.role,
        expires_at=datetime.now(timezone.utc) + timedelta(days=data.expires_days),
        max_uses=data.max_uses,
        use_count=0,
        created_by=user.id,
    )
    db.add(invite)
    await db.flush()
    return {"id": str(invite.id), "code": code, "expires_at": invite.expires_at.isoformat(),
            "role": invite.role, "invite_type": invite.invite_type}


@router.get("/clinics/{clinic_id}/invites")
async def list_invites(
    clinic_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        cid = uuid.UUID(clinic_id)
    except ValueError:
        raise HTTPException(status_code=422, detail={"error": {"code": "INVALID_ID"}})

    await _require_clinic_admin(db, user, cid)

    result = await db.execute(
        select(ClinicInvite).where(
            ClinicInvite.clinic_id == cid,
            ClinicInvite.deleted_at.is_(None),
        ).order_by(ClinicInvite.created_at.desc())
    )
    invites = result.scalars().all()

    return {
        "data": [
            {
                "id": str(i.id),
                "code": i.code,
                "invite_type": i.invite_type,
                "email": i.email,
                "role": i.role,
                "expires_at": i.expires_at.isoformat() if i.expires_at else None,
                "max_uses": i.max_uses,
                "use_count": i.use_count,
            }
            for i in invites
        ]
    }


@router.delete("/clinics/{clinic_id}/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invite(
    clinic_id: str,
    invite_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        cid, iid = uuid.UUID(clinic_id), uuid.UUID(invite_id)
    except ValueError:
        raise HTTPException(status_code=422, detail={"error": {"code": "INVALID_ID"}})

    await _require_clinic_admin(db, user, cid)

    result = await db.execute(
        select(ClinicInvite).where(
            ClinicInvite.id == iid,
            ClinicInvite.clinic_id == cid,
            ClinicInvite.deleted_at.is_(None),
        )
    )
    invite = result.scalar_one_or_none()
    if not invite:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND"}})
    invite.deleted_at = datetime.now(timezone.utc)
    await db.flush()


# ── Redeem invite ──────────────────────────────────────────────────────────

class RedeemRequest(BaseModel):
    code: str


@router.post("/invites/redeem")
async def redeem_invite(
    data: RedeemRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ClinicInvite).where(
            ClinicInvite.code == data.code.upper(),
            ClinicInvite.deleted_at.is_(None),
        )
    )
    invite = result.scalar_one_or_none()

    # Doctor invites may only be redeemed by users with the doctor role (role
    # elevation itself goes through the gated POST /auth/set-role path).
    # Receptionist invites grant a non-clinical staff membership, so any
    # authenticated user may redeem them — the membership role, not the
    # account role, scopes their access. Non-doctors get a uniform 403 for
    # missing/doctor invites so they cannot probe code validity.
    if user.role != "doctor" and (invite is None or invite.role != "receptionist"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Doctor access required to redeem a clinic invite"}},
        )

    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "INVALID_CODE", "message": "Invite code not found or expired"}},
        )
    if invite.expires_at and invite.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "EXPIRED_CODE", "message": "Invite code has expired"}},
        )
    if invite.max_uses and invite.use_count >= invite.max_uses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "CODE_EXHAUSTED", "message": "Invite code has reached max uses"}},
        )

    # Check if already a member — include deactivated rows: the unique index
    # covers them, so a deactivated member must be reactivated, not re-inserted.
    existing = (
        await db.execute(
            select(ClinicMembership).where(
                ClinicMembership.clinic_id == invite.clinic_id,
                ClinicMembership.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None and existing.is_active and existing.deleted_at is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "ALREADY_MEMBER", "message": "Already a member of this clinic"}},
        )
    if existing is not None:
        existing.is_active = True
        existing.role = invite.role
        existing.deleted_at = None
    else:
        db.add(
            ClinicMembership(
                id=uuid.uuid4(),
                clinic_id=invite.clinic_id,
                user_id=user.id,
                role=invite.role,
                is_active=True,
                joined_at=datetime.now(timezone.utc),
            )
        )
    invite.use_count += 1
    await db.flush()

    return {
        "message": "Successfully joined clinic",
        "clinic_id": str(invite.clinic_id),
        "role": invite.role,
    }


# ── Clinic search ──────────────────────────────────────────────────────────

@router.get("/clinics/search")
async def search_clinics(
    q: str = Query(..., min_length=2),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Clinic)
        .where(
            Clinic.name.ilike(f"%{q}%"),
            Clinic.is_active.is_(True),
            Clinic.deleted_at.is_(None),
        )
        .limit(20)
    )
    clinics = result.scalars().all()
    return {
        "data": [{"id": str(c.id), "name": c.name, "city": c.city, "state": c.state} for c in clinics]
    }


# ── Join requests ──────────────────────────────────────────────────────────

class JoinRequestCreate(BaseModel):
    message: Optional[str] = None


@router.post("/clinics/{clinic_id}/join-request", status_code=status.HTTP_201_CREATED)
async def create_join_request(
    clinic_id: str,
    data: JoinRequestCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        cid = uuid.UUID(clinic_id)
    except ValueError:
        raise HTTPException(status_code=422, detail={"error": {"code": "INVALID_ID"}})

    clinic = await db.get(Clinic, cid)
    if clinic is None or clinic.deleted_at is not None:
        raise HTTPException(
            status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Clinic not found"}}
        )

    # Check already a member
    existing = await clinic_service.get_user_membership(db, user.id, cid)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "ALREADY_MEMBER", "message": "Already a member of this clinic"}},
        )

    # Check pending request already exists
    existing_req = await db.execute(
        select(ClinicJoinRequest).where(
            ClinicJoinRequest.clinic_id == cid,
            ClinicJoinRequest.user_id == user.id,
            ClinicJoinRequest.status == "pending",
            ClinicJoinRequest.deleted_at.is_(None),
        )
    )
    if existing_req.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "REQUEST_EXISTS", "message": "Pending request already exists"}},
        )

    req = ClinicJoinRequest(
        id=uuid.uuid4(),
        clinic_id=cid,
        user_id=user.id,
        message=data.message,
        status="pending",
    )
    db.add(req)
    await db.flush()
    return {"id": str(req.id), "status": "pending", "message": "Join request submitted"}


@router.get("/clinics/{clinic_id}/join-requests")
async def list_join_requests(
    clinic_id: str,
    status_filter: str = Query("pending", alias="status"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        cid = uuid.UUID(clinic_id)
    except ValueError:
        raise HTTPException(status_code=422, detail={"error": {"code": "INVALID_ID"}})

    await _require_clinic_admin(db, user, cid)

    stmt = (
        select(ClinicJoinRequest, User.full_name, User.email)
        .join(User, User.id == ClinicJoinRequest.user_id)
        .where(
            ClinicJoinRequest.clinic_id == cid,
            ClinicJoinRequest.deleted_at.is_(None),
        )
    )
    if status_filter != "all":
        stmt = stmt.where(ClinicJoinRequest.status == status_filter)

    result = await db.execute(stmt.order_by(ClinicJoinRequest.created_at.desc()))
    rows = result.all()

    return {
        "data": [
            {
                "id": str(r.id),
                "user_id": str(r.user_id),
                "full_name": name,
                "email": email,
                "message": r.message,
                "status": r.status,
                "created_at": r.created_at.isoformat(),
            }
            for r, name, email in rows
        ]
    }


class ReviewRequestBody(BaseModel):
    action: str  # approved | rejected
    # Whitelisted staff roles only — approving a join request must never mint
    # owner/admin memberships.
    role: Literal["doctor", "receptionist"] = "doctor"


@router.put("/clinics/{clinic_id}/join-requests/{request_id}")
async def review_join_request(
    clinic_id: str,
    request_id: str,
    data: ReviewRequestBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        cid, rid = uuid.UUID(clinic_id), uuid.UUID(request_id)
    except ValueError:
        raise HTTPException(status_code=422, detail={"error": {"code": "INVALID_ID"}})

    await _require_clinic_admin(db, user, cid)

    result = await db.execute(
        select(ClinicJoinRequest).where(
            ClinicJoinRequest.id == rid,
            ClinicJoinRequest.clinic_id == cid,
            ClinicJoinRequest.status == "pending",
            ClinicJoinRequest.deleted_at.is_(None),
        )
    )
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND"}})

    if data.action not in ("approved", "rejected"):
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "INVALID_ACTION", "message": "action must be approved or rejected"}},
        )

    req.status = data.action
    req.reviewed_by = user.id
    req.reviewed_at = datetime.now(timezone.utc)

    if data.action == "approved":
        # Reactivate an existing (incl. deactivated) membership rather than
        # inserting — the unique index covers inactive rows too.
        existing_mem = (
            await db.execute(
                select(ClinicMembership).where(
                    ClinicMembership.clinic_id == cid,
                    ClinicMembership.user_id == req.user_id,
                )
            )
        ).scalar_one_or_none()
        if existing_mem is not None:
            existing_mem.is_active = True
            existing_mem.role = data.role
            existing_mem.deleted_at = None
        else:
            db.add(
                ClinicMembership(
                    id=uuid.uuid4(),
                    clinic_id=cid,
                    user_id=req.user_id,
                    role=data.role,
                    is_active=True,
                    joined_at=datetime.now(timezone.utc),
                )
            )

    await db.flush()

    # Notify the user who submitted the join request
    clinic_result = await db.execute(
        select(Clinic).where(Clinic.id == cid, Clinic.deleted_at.is_(None))
    )
    clinic = clinic_result.scalar_one_or_none()
    clinic_name = clinic.name if clinic else "the clinic"

    action_label = "approved" if data.action == "approved" else "rejected"
    await create_notification(
        db=db,
        user_id=req.user_id,
        notif_type="system",
        title=f"Your join request to {clinic_name} was {action_label}",
        body=f"Your request to join {clinic_name} has been {action_label}.",
        action_url="/doctor/clinic",
    )

    return {"status": data.action, "request_id": str(rid)}
