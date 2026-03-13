import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clinic import Clinic, ClinicBranch, ClinicMembership
from app.models.medical_record import MedicalRecord
from app.models.prescription import Prescription
from app.models.user import User
from app.schemas.clinic import (
    AdminClinicDetailResponse,
    AdminClinicListItem,
    ClinicBranchCreate,
    ClinicBranchResponse,
    ClinicCreate,
    ClinicMemberListResponse,
    ClinicMemberResponse,
    ClinicResponse,
    ClinicSettingsUpdate,
    ClinicUpdate,
)


async def create_clinic(db: AsyncSession, data: ClinicCreate, owner_user_id: uuid.UUID) -> Clinic:
    clinic = Clinic(
        id=uuid.uuid4(),
        name=data.name,
        address=data.address,
        city=data.city,
        state=data.state,
        phone=data.phone,
        email=data.email,
        is_active=True,
        record_sharing_mode="per_clinic",
        created_by=owner_user_id,
    )
    db.add(clinic)
    await db.flush()

    membership = ClinicMembership(
        id=uuid.uuid4(),
        clinic_id=clinic.id,
        user_id=owner_user_id,
        role="owner",
        is_active=True,
        joined_at=datetime.utcnow(),
    )
    db.add(membership)
    await db.flush()
    return clinic


async def get_clinic(db: AsyncSession, clinic_id: uuid.UUID) -> Clinic | None:
    result = await db.execute(
        select(Clinic).where(Clinic.id == clinic_id, Clinic.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


async def get_user_membership(
    db: AsyncSession, user_id: uuid.UUID, clinic_id: uuid.UUID
) -> ClinicMembership | None:
    result = await db.execute(
        select(ClinicMembership).where(
            ClinicMembership.user_id == user_id,
            ClinicMembership.clinic_id == clinic_id,
            ClinicMembership.is_active.is_(True),
            ClinicMembership.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def list_user_clinics(db: AsyncSession, user_id: uuid.UUID) -> list[ClinicResponse]:
    result = await db.execute(
        select(Clinic)
        .join(ClinicMembership, ClinicMembership.clinic_id == Clinic.id)
        .where(
            ClinicMembership.user_id == user_id,
            ClinicMembership.is_active.is_(True),
            ClinicMembership.deleted_at.is_(None),
            Clinic.deleted_at.is_(None),
        )
        .order_by(Clinic.name)
    )
    clinics = result.scalars().all()
    return [ClinicResponse.model_validate(c) for c in clinics]


async def update_clinic(
    db: AsyncSession, clinic: Clinic, data: ClinicUpdate
) -> Clinic:
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(clinic, field, value)
    await db.flush()
    return clinic


async def update_clinic_settings(
    db: AsyncSession, clinic: Clinic, data: ClinicSettingsUpdate
) -> Clinic:
    clinic.record_sharing_mode = data.record_sharing_mode
    await db.flush()
    return clinic


async def delete_clinic(db: AsyncSession, clinic: Clinic) -> None:
    clinic.deleted_at = datetime.utcnow()
    await db.flush()


async def list_clinic_members(
    db: AsyncSession, clinic_id: uuid.UUID
) -> ClinicMemberListResponse:
    result = await db.execute(
        select(ClinicMembership, User)
        .join(User, User.id == ClinicMembership.user_id)
        .where(
            ClinicMembership.clinic_id == clinic_id,
            ClinicMembership.is_active.is_(True),
            ClinicMembership.deleted_at.is_(None),
            User.deleted_at.is_(None),
        )
        .order_by(ClinicMembership.joined_at)
    )
    rows = result.all()
    members = [
        ClinicMemberResponse(
            id=str(m.id),
            user_id=str(m.user_id),
            full_name=u.full_name,
            email=u.email,
            role=m.role,
            branch_id=str(m.branch_id) if m.branch_id else None,
            is_active=m.is_active,
            joined_at=m.joined_at,
        )
        for m, u in rows
    ]
    return ClinicMemberListResponse(data=members, total=len(members))


async def create_branch(
    db: AsyncSession, clinic_id: uuid.UUID, data: ClinicBranchCreate
) -> ClinicBranch:
    branch = ClinicBranch(
        id=uuid.uuid4(),
        clinic_id=clinic_id,
        name=data.name,
        address=data.address,
        city=data.city,
        state=data.state,
        phone=data.phone,
        is_active=True,
    )
    db.add(branch)
    await db.flush()
    return branch


# ── Admin operations ────────────────────────────────────────────────────────

async def admin_list_clinics(
    db: AsyncSession,
    search: str | None = None,
    is_active: bool | None = None,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[AdminClinicListItem], int]:
    # Member count subquery
    member_count_sq = (
        select(ClinicMembership.clinic_id, func.count().label("cnt"))
        .where(
            ClinicMembership.is_active.is_(True),
            ClinicMembership.deleted_at.is_(None),
        )
        .group_by(ClinicMembership.clinic_id)
        .subquery()
    )

    stmt = (
        select(Clinic, func.coalesce(member_count_sq.c.cnt, 0).label("member_count"))
        .outerjoin(member_count_sq, member_count_sq.c.clinic_id == Clinic.id)
        .where(Clinic.deleted_at.is_(None))
    )
    if search:
        stmt = stmt.where(Clinic.name.ilike(f"%{search}%"))
    if is_active is not None:
        stmt = stmt.where(Clinic.is_active == is_active)

    total_result = await db.execute(select(func.count()).select_from(stmt.subquery()))
    total = total_result.scalar_one()

    stmt = stmt.order_by(Clinic.created_at.desc()).offset((page - 1) * limit).limit(limit)
    rows = (await db.execute(stmt)).all()

    items = [
        AdminClinicListItem(
            id=str(c.id),
            name=c.name,
            city=c.city,
            state=c.state,
            is_active=c.is_active,
            record_sharing_mode=c.record_sharing_mode,
            member_count=int(mc),
            created_at=c.created_at,
        )
        for c, mc in rows
    ]
    return items, total


async def admin_get_clinic_detail(
    db: AsyncSession, clinic_id: uuid.UUID
) -> AdminClinicDetailResponse | None:
    clinic = await get_clinic(db, clinic_id)
    if not clinic:
        return None

    member_count = (
        await db.execute(
            select(func.count()).where(
                ClinicMembership.clinic_id == clinic_id,
                ClinicMembership.is_active.is_(True),
                ClinicMembership.deleted_at.is_(None),
            )
        )
    ).scalar_one()

    record_count = (
        await db.execute(
            select(func.count()).where(
                MedicalRecord.clinic_id == clinic_id,
                MedicalRecord.deleted_at.is_(None),
            )
        )
    ).scalar_one()

    prescription_count = (
        await db.execute(
            select(func.count()).where(
                Prescription.clinic_id == clinic_id,
                Prescription.deleted_at.is_(None),
            )
        )
    ).scalar_one()

    branches_result = await db.execute(
        select(ClinicBranch).where(
            ClinicBranch.clinic_id == clinic_id,
            ClinicBranch.deleted_at.is_(None),
        )
    )
    branches = [ClinicBranchResponse.model_validate(b) for b in branches_result.scalars().all()]

    return AdminClinicDetailResponse(
        id=str(clinic.id),
        name=clinic.name,
        address=clinic.address,
        city=clinic.city,
        state=clinic.state,
        phone=clinic.phone,
        email=clinic.email,
        logo_url=clinic.logo_url,
        is_active=clinic.is_active,
        record_sharing_mode=clinic.record_sharing_mode,
        created_by=str(clinic.created_by) if clinic.created_by else None,
        created_at=clinic.created_at,
        updated_at=clinic.updated_at,
        member_count=member_count,
        record_count=record_count,
        prescription_count=prescription_count,
        branches=branches,
    )
