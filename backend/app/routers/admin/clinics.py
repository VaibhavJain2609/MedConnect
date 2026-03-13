"""
Admin clinic endpoints  [MD-198]

POST   /api/v1/admin/clinics        — create a clinic (no owner)
GET    /api/v1/admin/clinics        — list all clinics (paginated)
GET    /api/v1/admin/clinics/{id}   — clinic detail with stats
PUT    /api/v1/admin/clinics/{id}   — update any clinic
DELETE /api/v1/admin/clinics/{id}   — soft delete
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_admin
from app.schemas.clinic import AdminClinicDetailResponse, ClinicCreate, ClinicUpdate
from app.services import clinic_service

router = APIRouter(
    prefix="/api/v1/admin/clinics",
    tags=["admin-clinics"],
    dependencies=[Depends(require_admin)],
)


@router.post("", response_model=AdminClinicDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_clinic(
    data: ClinicCreate,
    db: AsyncSession = Depends(get_db),
):
    clinic = await clinic_service.create_clinic(db, data, owner_user_id=None)
    detail = await clinic_service.admin_get_clinic_detail(db, clinic.id)
    return detail


@router.get("")
async def list_clinics(
    search: str | None = Query(None),
    is_active: bool | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    items, total = await clinic_service.admin_list_clinics(
        db, search=search, is_active=is_active, page=page, limit=limit
    )
    return {
        "data": [i.model_dump() for i in items],
        "total": total,
        "page": page,
        "limit": limit,
        "totalPages": max(1, -(-total // limit)),
    }


@router.get("/{clinic_id}", response_model=AdminClinicDetailResponse)
async def get_clinic_detail(
    clinic_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        cid = uuid.UUID(clinic_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail={"error": {"code": "INVALID_ID", "message": "Invalid clinic ID"}})
    detail = await clinic_service.admin_get_clinic_detail(db, cid)
    if not detail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"error": {"code": "NOT_FOUND", "message": "Clinic not found"}})
    return detail


@router.put("/{clinic_id}", response_model=AdminClinicDetailResponse)
async def update_clinic(
    clinic_id: str,
    data: ClinicUpdate,
    db: AsyncSession = Depends(get_db),
):
    try:
        cid = uuid.UUID(clinic_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail={"error": {"code": "INVALID_ID", "message": "Invalid clinic ID"}})
    clinic = await clinic_service.get_clinic(db, cid)
    if not clinic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"error": {"code": "NOT_FOUND", "message": "Clinic not found"}})
    await clinic_service.update_clinic(db, clinic, data)
    detail = await clinic_service.admin_get_clinic_detail(db, cid)
    return detail


@router.delete("/{clinic_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_clinic(
    clinic_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        cid = uuid.UUID(clinic_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail={"error": {"code": "INVALID_ID", "message": "Invalid clinic ID"}})
    clinic = await clinic_service.get_clinic(db, cid)
    if not clinic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"error": {"code": "NOT_FOUND", "message": "Clinic not found"}})
    await clinic_service.delete_clinic(db, clinic)
