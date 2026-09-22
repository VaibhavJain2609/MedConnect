"""
Family member (dependent) profiles  [R12]

POST   /api/v1/family/members              — add a dependent (patient)
GET    /api/v1/family/members              — list own dependents (patient)
GET    /api/v1/family/members/{member_id}  — fetch one dependent (owner only)
PATCH  /api/v1/family/members/{member_id}  — update a dependent (owner only)
DELETE /api/v1/family/members/{member_id}  — soft-delete a dependent (owner only)

Dependents are data profiles owned by the caller — not full user accounts.
Records can be attached to a dependent via ``family_member_id`` on
POST /api/v1/patients/records.
"""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_patient
from app.models.family import FamilyMember
from app.models.user import User
from app.schemas.family import FamilyMemberCreate, FamilyMemberUpdate, serialize_member

router = APIRouter(prefix="/api/v1/family", tags=["family"])


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error": {"code": "NOT_FOUND", "message": "Family member not found"}},
    )


async def _get_owned_member(
    db: AsyncSession, member_id: UUID, owner_id: UUID
) -> FamilyMember:
    """Fetch a live family member owned by ``owner_id``; 404 otherwise."""
    result = await db.execute(
        select(FamilyMember).where(
            FamilyMember.id == member_id,
            FamilyMember.owner_user_id == owner_id,
            FamilyMember.deleted_at.is_(None),
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise _not_found()
    return member


@router.post("/members", status_code=status.HTTP_201_CREATED)
async def create_member(
    body: FamilyMemberCreate,
    user: User = Depends(require_patient),
    db: AsyncSession = Depends(get_db),
):
    member = FamilyMember(
        owner_user_id=user.id,
        full_name=body.full_name,
        dob=body.dob,
        relationship=body.relationship,
        gender=body.gender,
        blood_group=body.blood_group,
        notes=body.notes,
    )
    db.add(member)
    await db.flush()

    from app.services.audit_service import log_change
    await log_change(
        db=db,
        table_name="family_members",
        record_id=member.id,
        action="INSERT",
        old_values=None,
        new_values={
            "owner_user_id": str(user.id),
            "full_name": member.full_name,
            "relationship": member.relationship,
        },
    )

    await db.commit()
    await db.refresh(member)
    return serialize_member(member)


@router.get("/members")
async def list_members(
    user: User = Depends(require_patient),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FamilyMember)
        .where(
            FamilyMember.owner_user_id == user.id,
            FamilyMember.deleted_at.is_(None),
        )
        .order_by(FamilyMember.created_at.asc())
    )
    members = list(result.scalars().all())
    return {"data": [serialize_member(m) for m in members], "total": len(members)}


@router.get("/members/{member_id}")
async def get_member(
    member_id: UUID,
    user: User = Depends(require_patient),
    db: AsyncSession = Depends(get_db),
):
    member = await _get_owned_member(db, member_id, user.id)
    return serialize_member(member)


@router.patch("/members/{member_id}")
async def update_member(
    member_id: UUID,
    body: FamilyMemberUpdate,
    user: User = Depends(require_patient),
    db: AsyncSession = Depends(get_db),
):
    member = await _get_owned_member(db, member_id, user.id)
    data = body.model_dump(exclude_unset=True)

    old_values = {k: getattr(member, k) for k in data}
    for field, value in data.items():
        setattr(member, field, value)

    await db.flush()

    from app.services.audit_service import log_change
    await log_change(
        db=db,
        table_name="family_members",
        record_id=member.id,
        action="UPDATE",
        old_values={k: str(v) if v is not None else None for k, v in old_values.items()},
        new_values={k: str(v) if v is not None else None for k, v in data.items()},
    )

    await db.commit()
    await db.refresh(member)
    return serialize_member(member)


@router.delete("/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_member(
    member_id: UUID,
    user: User = Depends(require_patient),
    db: AsyncSession = Depends(get_db),
):
    member = await _get_owned_member(db, member_id, user.id)
    member.deleted_at = datetime.now(timezone.utc)
    await db.flush()

    from app.services.audit_service import log_change
    await log_change(
        db=db,
        table_name="family_members",
        record_id=member.id,
        action="DELETE",
        old_values={"full_name": member.full_name, "relationship": member.relationship},
        new_values=None,
    )

    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
