"""
Admin clinic endpoints  [MD-198]

POST   /api/v1/admin/clinics              — create a clinic (no owner)
GET    /api/v1/admin/clinics              — list all clinics (paginated)
GET    /api/v1/admin/clinics/{id}         — clinic detail with stats
GET    /api/v1/admin/clinics/{id}/metrics — per-clinic usage metrics
PUT    /api/v1/admin/clinics/{id}         — update any clinic
DELETE /api/v1/admin/clinics/{id}         — soft delete
"""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel as PydanticBaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_admin
from app.models.appointment import Appointment
from app.models.clinic import ClinicBranch, ClinicMembership
from app.models.patient_link import PatientClinicLink
from app.models.queue import QueueEntry
from app.models.user import User
from app.schemas.clinic import AdminClinicDetailResponse, ClinicCreate, ClinicUpdate
from app.services import clinic_service

router = APIRouter(
    prefix="/api/v1/admin/clinics",
    tags=["admin-clinics"],
    dependencies=[Depends(require_admin)],
)


class AdminAddPatientBody(PydanticBaseModel):
    patient_id: str


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


@router.post("/{clinic_id}/patients", status_code=status.HTTP_201_CREATED)
async def admin_add_patient_to_clinic(
    clinic_id: str,
    body: AdminAddPatientBody,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Link a patient to a clinic with pending consent."""
    try:
        cid = uuid.UUID(clinic_id)
        pid = uuid.UUID(body.patient_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "INVALID_ID", "message": "Invalid ID format"}},
        )

    # Validate patient exists
    patient = await db.scalar(
        select(User).where(User.id == pid, User.deleted_at.is_(None), User.role == "patient")
    )
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Patient not found"}},
        )

    # Check for existing link (excluding soft-deleted ones)
    existing = await db.scalar(
        select(PatientClinicLink).where(
            PatientClinicLink.patient_id == pid,
            PatientClinicLink.clinic_id == cid,
            PatientClinicLink.deleted_at.is_(None),
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "DUPLICATE_LINK", "message": "Patient is already linked to this clinic"}},
        )

    link = PatientClinicLink(
        id=uuid.uuid4(),
        patient_id=pid,
        clinic_id=cid,
        linked_by=admin.id,
        consent_status="pending",
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)

    return {
        "link_id": str(link.id),
        "patient_id": str(link.patient_id),
        "clinic_id": str(link.clinic_id),
        "consent_status": link.consent_status,
    }


@router.get("/{clinic_id}/metrics")
async def get_clinic_metrics(
    clinic_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Per-clinic usage metrics for the admin clinic detail page.

    One GROUP BY query per aggregate — no N+1. All counts exclude
    soft-deleted rows. Role counts (doctors/receptionists/owners) cover
    active memberships only; `inactive` counts is_active=False rows and
    `total` counts every live membership.
    """
    try:
        cid = uuid.UUID(clinic_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail={"error": {"code": "INVALID_ID", "message": "Invalid clinic ID"}})
    clinic = await clinic_service.get_clinic(db, cid)
    if not clinic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"error": {"code": "NOT_FOUND", "message": "Clinic not found"}})

    # Members — single GROUP BY over (role, is_active)
    member_rows = (
        await db.execute(
            select(ClinicMembership.role, ClinicMembership.is_active, func.count())
            .where(ClinicMembership.clinic_id == cid, ClinicMembership.deleted_at.is_(None))
            .group_by(ClinicMembership.role, ClinicMembership.is_active)
        )
    ).all()
    members = {"total": 0, "doctors": 0, "receptionists": 0, "owners": 0, "inactive": 0}
    for role, is_active, cnt in member_rows:
        members["total"] += cnt
        if not is_active:
            members["inactive"] += cnt
        elif role == "doctor":
            members["doctors"] += cnt
        elif role == "receptionist":
            members["receptionists"] += cnt
        elif role == "owner":
            members["owners"] += cnt

    # Patient links — single GROUP BY over consent_status
    link_rows = (
        await db.execute(
            select(PatientClinicLink.consent_status, func.count())
            .where(PatientClinicLink.clinic_id == cid, PatientClinicLink.deleted_at.is_(None))
            .group_by(PatientClinicLink.consent_status)
        )
    ).all()
    patients = {"total_linked": 0, "approved": 0, "pending": 0, "revoked": 0}
    for consent_status, cnt in link_rows:
        patients["total_linked"] += cnt
        if consent_status in ("approved", "pending", "revoked"):
            patients[consent_status] += cnt

    # Appointments — single GROUP BY over status, with a FILTER for last-30d
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    appt_rows = (
        await db.execute(
            select(
                Appointment.status,
                func.count(),
                func.count().filter(Appointment.scheduled_at >= cutoff),
            )
            .where(Appointment.clinic_id == cid, Appointment.deleted_at.is_(None))
            .group_by(Appointment.status)
        )
    ).all()
    by_status: dict[str, int] = {}
    appt_total = 0
    appt_last_30d = 0
    for appt_status, cnt, recent in appt_rows:
        by_status[appt_status] = cnt
        appt_total += cnt
        appt_last_30d += recent

    # Queue today — single GROUP BY over status for today's (UTC) queue_date
    today = datetime.now(timezone.utc).date()
    queue_rows = (
        await db.execute(
            select(QueueEntry.status, func.count())
            .where(
                QueueEntry.clinic_id == cid,
                QueueEntry.deleted_at.is_(None),
                QueueEntry.queue_date == today,
            )
            .group_by(QueueEntry.status)
        )
    ).all()
    queue_today = {"waiting": 0, "in_consultation": 0, "completed": 0}
    for queue_status, cnt in queue_rows:
        if queue_status in queue_today:
            queue_today[queue_status] += cnt

    # Branches — plain count
    branch_count = await db.scalar(
        select(func.count())
        .select_from(ClinicBranch)
        .where(ClinicBranch.clinic_id == cid, ClinicBranch.deleted_at.is_(None))
    )

    return {
        "members": members,
        "patients": patients,
        "appointments": {
            "total": appt_total,
            "last_30d": appt_last_30d,
            "by_status": by_status,
        },
        "queue_today": queue_today,
        "branches": branch_count or 0,
    }
