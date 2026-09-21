"""
Doctor-facing clinic endpoints  [MD-197]

POST   /api/v1/clinics          — create clinic (becomes owner)
GET    /api/v1/clinics/my       — list my clinics
GET    /api/v1/clinics/{id}     — clinic detail (member only)
PUT    /api/v1/clinics/{id}     — update (owner/admin)
GET    /api/v1/clinics/{id}/members  — list members
PUT    /api/v1/clinics/{id}/settings — update record_sharing_mode
POST   /api/v1/clinics/{id}/branches — create branch
GET    /api/v1/clinics/{id}/branches — list branches [MD-274]
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_doctor, get_current_user
from app.models.doctor import Doctor
from app.models.user import User
from app.schemas.clinic import (
    ClinicBranchCreate,
    ClinicBranchListResponse,
    ClinicBranchResponse,
    ClinicCreate,
    ClinicListResponse,
    ClinicMemberListResponse,
    ClinicResponse,
    ClinicSettingsUpdate,
    ClinicUpdate,
)
from app.services import clinic_service

router = APIRouter(prefix="/api/v1/clinics", tags=["clinics"])


async def _get_clinic_or_404(db: AsyncSession, clinic_id: str):
    try:
        cid = uuid.UUID(clinic_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail={"error": {"code": "INVALID_ID", "message": "Invalid clinic ID"}})
    clinic = await clinic_service.get_clinic(db, cid)
    if not clinic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"error": {"code": "NOT_FOUND", "message": "Clinic not found"}})
    return clinic


async def _require_membership(db: AsyncSession, user: User, clinic_id: str, roles: list[str] | None = None):
    """Verify user is an active member; optionally restrict to given roles."""
    try:
        cid = uuid.UUID(clinic_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail={"error": {"code": "INVALID_ID", "message": "Invalid clinic ID"}})
    membership = await clinic_service.get_user_membership(db, user.id, cid)
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail={"error": {"code": "FORBIDDEN", "message": "Not a member of this clinic"}})
    if roles and membership.role not in roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail={"error": {"code": "FORBIDDEN",
                                              "message": f"Role must be one of: {', '.join(roles)}"}})
    return membership


@router.post("", response_model=ClinicResponse, status_code=status.HTTP_201_CREATED)
async def create_clinic(
    data: ClinicCreate,
    doctor_info: tuple[User, Doctor] = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    # Only doctors may create clinics (they become the owner member).
    user, _doctor = doctor_info
    clinic = await clinic_service.create_clinic(db, data, user.id)

    # Audit clinic creation + the owner membership row the service created.
    from app.services.audit_service import log_change
    await log_change(
        db=db,
        table_name="clinics",
        record_id=clinic.id,
        action="INSERT",
        old_values=None,
        new_values={
            "created_by": str(user.id),
            "record_sharing_mode": clinic.record_sharing_mode,
            "is_active": clinic.is_active,
        },
    )
    owner_membership = await clinic_service.get_user_membership(db, user.id, clinic.id)
    if owner_membership:
        await log_change(
            db=db,
            table_name="clinic_memberships",
            record_id=owner_membership.id,
            action="INSERT",
            old_values=None,
            new_values={
                "clinic_id": str(clinic.id),
                "user_id": str(user.id),
                "role": "owner",
            },
        )

    return ClinicResponse.model_validate(clinic)


@router.get("/my", response_model=ClinicListResponse)
async def list_my_clinics(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    clinics = await clinic_service.list_user_clinics(db, user.id)
    return ClinicListResponse(data=clinics, total=len(clinics))


@router.get("/{clinic_id}", response_model=ClinicResponse)
async def get_clinic(
    clinic_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_membership(db, user, clinic_id)
    clinic = await _get_clinic_or_404(db, clinic_id)
    return ClinicResponse.model_validate(clinic)


@router.put("/{clinic_id}", response_model=ClinicResponse)
async def update_clinic(
    clinic_id: str,
    data: ClinicUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_membership(db, user, clinic_id, roles=["owner", "admin"])
    clinic = await _get_clinic_or_404(db, clinic_id)
    fields_changed = sorted(data.model_dump(exclude_none=True).keys())
    clinic = await clinic_service.update_clinic(db, clinic, data)

    # Audit clinic update — field names only, never values.
    from app.services.audit_service import log_change
    await log_change(
        db=db,
        table_name="clinics",
        record_id=clinic.id,
        action="UPDATE",
        old_values=None,
        new_values={"fields_changed": fields_changed},
    )

    return ClinicResponse.model_validate(clinic)


@router.get("/{clinic_id}/members", response_model=ClinicMemberListResponse)
async def list_members(
    clinic_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_membership(db, user, clinic_id)
    return await clinic_service.list_clinic_members(db, uuid.UUID(clinic_id))


@router.put("/{clinic_id}/settings", response_model=ClinicResponse)
async def update_settings(
    clinic_id: str,
    data: ClinicSettingsUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_membership(db, user, clinic_id, roles=["owner", "admin"])
    clinic = await _get_clinic_or_404(db, clinic_id)
    old_sharing_mode = clinic.record_sharing_mode
    clinic = await clinic_service.update_clinic_settings(db, clinic, data)

    # Audit the settings change (old -> new record_sharing_mode).
    from app.services.audit_service import log_change
    await log_change(
        db=db,
        table_name="clinics",
        record_id=clinic.id,
        action="UPDATE",
        old_values={"record_sharing_mode": old_sharing_mode},
        new_values={"record_sharing_mode": clinic.record_sharing_mode},
    )

    return ClinicResponse.model_validate(clinic)


@router.post("/{clinic_id}/branches", response_model=ClinicBranchResponse,
             status_code=status.HTTP_201_CREATED)
async def create_branch(
    clinic_id: str,
    data: ClinicBranchCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_membership(db, user, clinic_id, roles=["owner", "admin"])
    branch = await clinic_service.create_branch(db, uuid.UUID(clinic_id), data)

    # Audit branch creation — ids + name only.
    from app.services.audit_service import log_change
    await log_change(
        db=db,
        table_name="clinic_branches",
        record_id=branch.id,
        action="INSERT",
        old_values=None,
        new_values={
            "clinic_id": str(branch.clinic_id),
            "name": branch.name,
        },
    )

    return ClinicBranchResponse.model_validate(branch)


@router.get("/{clinic_id}/branches", response_model=ClinicBranchListResponse)
async def list_branches(
    clinic_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all active branches for a clinic. Requires clinic membership. [MD-274]"""
    await _require_membership(db, user, clinic_id)
    branches = await clinic_service.list_clinic_branches(db, uuid.UUID(clinic_id))
    return ClinicBranchListResponse(data=branches, total=len(branches))
