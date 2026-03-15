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
from app.models.patient_link import PatientClinicLink
from app.models.prescription import Prescription
from app.models.user import User
from app.models.doctor import Doctor
from app.schemas.user import (
    AdminCreatePatientRequest,
    AdminCreatePatientResponse,
    AdminUserDeleteResponse,
    AdminUserDetailResponse,
    AdminUserPrescriptionItem,
    AdminUserPrescriptionsResponse,
    AdminUserRecordItem,
    AdminUserRecordsResponse,
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
    clinic_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    if clinic_id:
        # When filtering by clinic, force role=patient and join PatientClinicLink
        query = (
            select(User, PatientClinicLink.consent_status)
            .join(
                PatientClinicLink,
                (PatientClinicLink.patient_id == User.id)
                & (PatientClinicLink.clinic_id == clinic_id)
                & (PatientClinicLink.deleted_at.is_(None)),
            )
            .where(User.deleted_at.is_(None), User.role == "patient")
        )
        if search:
            query = query.where(
                User.full_name.ilike(f"%{search}%")
                | User.email.ilike(f"%{search}%")
                | User.phone.ilike(f"%{search}%")
            )
        if is_active is not None:
            query = query.where(User.is_active.is_(is_active))

        count_query = select(func.count()).select_from(query.subquery())
        total = await db.scalar(count_query) or 0
        result = await db.execute(
            query.order_by(User.created_at.desc()).offset((page - 1) * limit).limit(limit)
        )
        rows = result.all()

        return AdminUsersListResponse(
            data=[
                {
                    "id": str(row.User.id),
                    "full_name": row.User.full_name,
                    "email": row.User.email,
                    "phone": row.User.phone,
                    "role": row.User.role,
                    "is_active": row.User.is_active,
                    "created_at": row.User.created_at,
                    "consent_status": row.consent_status,
                }
                for row in rows
            ],
            total=total,
            page=page,
            limit=limit,
            totalPages=math.ceil(total / limit) if total else 0,
        )

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
                "consent_status": None,
            }
            for u in users
        ],
        total=total,
        page=page,
        limit=limit,
        totalPages=math.ceil(total / limit) if total else 0,
    )


@router.post("", response_model=AdminCreatePatientResponse, status_code=status.HTTP_201_CREATED)
async def create_patient(
    body: AdminCreatePatientRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a walk-in patient without a Keycloak account."""
    import uuid as uuid_module
    keycloak_sub = f"walkin:{uuid_module.uuid4()}"
    user = User(
        full_name=body.full_name,
        phone=body.phone or None,
        email=body.email or None,
        keycloak_sub=keycloak_sub,
        role="patient",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


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

    last_prescription = await db.scalar(
        select(func.max(Prescription.created_at)).where(
            Prescription.patient_id == user.id,
            Prescription.deleted_at.is_(None),
        )
    )
    last_record = await db.scalar(
        select(func.max(MedicalRecord.created_at)).where(
            MedicalRecord.patient_id == user.id,
            MedicalRecord.deleted_at.is_(None),
        )
    )
    last_visit = max(filter(None, [last_prescription, last_record]), default=None)

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
        allergies=user.allergies,
        chronic_conditions=user.chronic_conditions,
        height_cm=user.height_cm,
        weight_kg=user.weight_kg,
        last_visit=last_visit,
    )


@router.get("/{user_id}/prescriptions", response_model=AdminUserPrescriptionsResponse)
async def get_user_prescriptions(
    user_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    user_exists = await db.scalar(
        select(User.id).where(User.id == user_id, User.deleted_at.is_(None))
    )
    if not user_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "User not found"}},
        )

    total = (
        await db.scalar(
            select(func.count()).where(
                Prescription.patient_id == user_id,
                Prescription.deleted_at.is_(None),
            )
        )
        or 0
    )

    result = await db.execute(
        select(Prescription, User.full_name.label("doctor_name"))
        .join(Doctor, Prescription.doctor_id == Doctor.id)
        .join(User, Doctor.user_id == User.id)
        .where(Prescription.patient_id == user_id, Prescription.deleted_at.is_(None))
        .order_by(Prescription.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    rows = result.all()

    return AdminUserPrescriptionsResponse(
        data=[
            AdminUserPrescriptionItem(
                id=str(rx.Prescription.id),
                doctor_name=rx.doctor_name,
                diagnosis=rx.Prescription.diagnosis,
                notes=rx.Prescription.notes,
                medicines=rx.Prescription.medicines,
                valid_until=rx.Prescription.valid_until,
                created_at=rx.Prescription.created_at,
            )
            for rx in rows
        ],
        total=total,
        page=page,
        limit=limit,
        totalPages=math.ceil(total / limit) if total else 0,
    )


@router.get("/{user_id}/records", response_model=AdminUserRecordsResponse)
async def get_user_records(
    user_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    user_exists = await db.scalar(
        select(User.id).where(User.id == user_id, User.deleted_at.is_(None))
    )
    if not user_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "User not found"}},
        )

    total = (
        await db.scalar(
            select(func.count()).where(
                MedicalRecord.patient_id == user_id,
                MedicalRecord.deleted_at.is_(None),
            )
        )
        or 0
    )

    result = await db.execute(
        select(MedicalRecord, User.full_name.label("doctor_name"))
        .outerjoin(Doctor, MedicalRecord.doctor_id == Doctor.id)
        .outerjoin(User, Doctor.user_id == User.id)
        .where(MedicalRecord.patient_id == user_id, MedicalRecord.deleted_at.is_(None))
        .order_by(MedicalRecord.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    rows = result.all()

    return AdminUserRecordsResponse(
        data=[
            AdminUserRecordItem(
                id=str(r.MedicalRecord.id),
                record_type=r.MedicalRecord.record_type,
                title=r.MedicalRecord.title,
                description=r.MedicalRecord.description,
                source=r.MedicalRecord.source,
                doctor_name=r.doctor_name,
                created_at=r.MedicalRecord.created_at,
            )
            for r in rows
        ],
        total=total,
        page=page,
        limit=limit,
        totalPages=math.ceil(total / limit) if total else 0,
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


@router.get("/{user_id}/related-patients")
async def get_related_patients(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Find other patients sharing the same email or phone (family group)."""
    from sqlalchemy import or_

    result = await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "User not found"}},
        )

    conditions = []
    if target.email:
        conditions.append(User.email == target.email)
    if target.phone:
        conditions.append(User.phone == target.phone)

    if not conditions:
        return {"data": []}

    result = await db.execute(
        select(User)
        .where(
            User.id != target.id,
            User.deleted_at.is_(None),
            User.role == "patient",
            or_(*conditions),
        )
    )
    related = result.scalars().all()

    return {
        "data": [
            {"id": str(u.id), "full_name": u.full_name, "phone": u.phone, "email": u.email}
            for u in related
        ]
    }
