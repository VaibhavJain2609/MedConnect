"""
Patient-clinic linking endpoints  [MD-222]

GET  /api/v1/patients/link-code              — get/generate weekly link code (patient)
POST /api/v1/clinics/{id}/link-patient       — link patient by code (doctor)
GET  /api/v1/patients/clinic-links           — list linked clinics (patient)
PUT  /api/v1/patients/clinic-links/{id}/consent — approve/revoke consent (patient)
GET  /api/v1/clinics/{id}/patients           — list linked patients (clinic member)
"""
import random
import string
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_active_clinic, get_current_user, require_patient
from app.models.clinic import Clinic, ClinicMembership
from app.models.patient_link import PatientClinicLink, PatientLinkCode
from app.models.user import User
from app.services.notification_service import create_notification

router = APIRouter(prefix="/api/v1", tags=["patient-links"])


def _generate_code() -> str:
    """Generate a 10-digit alphanumeric link code."""
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=10))


def _next_sunday() -> datetime:
    """Return the next Sunday midnight UTC (weekly rotation)."""
    now = datetime.now(timezone.utc)
    days_until_sunday = (6 - now.weekday()) % 7 or 7
    return (now + timedelta(days=days_until_sunday)).replace(hour=0, minute=0, second=0, microsecond=0)


# ── Patient: get / generate link code ─────────────────────────────────────

@router.get("/patients/link-code")
async def get_link_code(
    user: User = Depends(require_patient),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PatientLinkCode).where(
            PatientLinkCode.patient_id == user.id,
            PatientLinkCode.deleted_at.is_(None),
        )
    )
    link_code = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)

    # Create or rotate if missing/expired
    if not link_code or link_code.expires_at < now:
        if link_code:
            link_code.deleted_at = now
        link_code = PatientLinkCode(
            id=uuid.uuid4(),
            patient_id=user.id,
            code=_generate_code(),
            expires_at=_next_sunday(),
        )
        db.add(link_code)
        await db.flush()

    return {
        "code": link_code.code,
        "expires_at": link_code.expires_at.isoformat(),
    }


# ── Doctor: link patient by code ──────────────────────────────────────────

class LinkPatientRequest(BaseModel):
    code: str


@router.post("/clinics/{clinic_id}/link-patient", status_code=status.HTTP_201_CREATED)
async def link_patient(
    clinic_id: str,
    data: LinkPatientRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role != "doctor":
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN"}})

    try:
        cid = uuid.UUID(clinic_id)
    except ValueError:
        raise HTTPException(status_code=422, detail={"error": {"code": "INVALID_ID"}})

    # Verify doctor is a member of this clinic
    membership = await db.execute(
        select(ClinicMembership).where(
            ClinicMembership.clinic_id == cid,
            ClinicMembership.user_id == user.id,
            ClinicMembership.is_active.is_(True),
            ClinicMembership.deleted_at.is_(None),
        )
    )
    if not membership.scalar_one_or_none():
        raise HTTPException(status_code=403, detail={"error": {"code": "NOT_CLINIC_MEMBER"}})

    # Look up the code
    code_result = await db.execute(
        select(PatientLinkCode).where(
            PatientLinkCode.code == data.code.upper(),
            PatientLinkCode.deleted_at.is_(None),
        )
    )
    link_code = code_result.scalar_one_or_none()
    if not link_code:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "INVALID_CODE", "message": "Patient link code not found"}},
        )
    if link_code.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "EXPIRED_CODE", "message": "Patient link code has expired"}},
        )

    # Check not already linked
    existing = await db.execute(
        select(PatientClinicLink).where(
            PatientClinicLink.patient_id == link_code.patient_id,
            PatientClinicLink.clinic_id == cid,
            PatientClinicLink.deleted_at.is_(None),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": "ALREADY_LINKED", "message": "Patient already linked to this clinic"}},
        )

    link = PatientClinicLink(
        id=uuid.uuid4(),
        patient_id=link_code.patient_id,
        clinic_id=cid,
        linked_by=user.id,
        consent_status="pending",
    )
    db.add(link)
    await db.flush()

    # Fetch patient name for response
    patient = await db.get(User, link_code.patient_id)

    return {
        "link_id": str(link.id),
        "patient_id": str(link_code.patient_id),
        "patient_name": patient.full_name if patient else None,
        "consent_status": "pending",
        "message": "Patient linked. Awaiting patient consent.",
    }


# ── Patient: list linked clinics ──────────────────────────────────────────

@router.get("/patients/clinic-links")
async def list_clinic_links(
    user: User = Depends(require_patient),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PatientClinicLink, Clinic)
        .join(Clinic, Clinic.id == PatientClinicLink.clinic_id)
        .where(
            PatientClinicLink.patient_id == user.id,
            PatientClinicLink.deleted_at.is_(None),
            Clinic.deleted_at.is_(None),
        )
        .order_by(PatientClinicLink.created_at.desc())
    )
    rows = result.all()
    return {
        "data": [
            {
                "id": str(link.id),
                "clinic_id": str(link.clinic_id),
                "clinic_name": clinic.name,
                "clinic_city": clinic.city,
                "consent_status": link.consent_status,
                "consented_at": link.consented_at.isoformat() if link.consented_at else None,
                "created_at": link.created_at.isoformat(),
            }
            for link, clinic in rows
        ]
    }


# ── Patient: update consent ────────────────────────────────────────────────

class ConsentUpdate(BaseModel):
    action: str  # approved | revoked


@router.put("/patients/clinic-links/{link_id}/consent")
async def update_consent(
    link_id: str,
    data: ConsentUpdate,
    user: User = Depends(require_patient),
    db: AsyncSession = Depends(get_db),
):
    try:
        lid = uuid.UUID(link_id)
    except ValueError:
        raise HTTPException(status_code=422, detail={"error": {"code": "INVALID_ID"}})

    if data.action not in ("approved", "revoked"):
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "INVALID_ACTION", "message": "action must be approved or revoked"}},
        )

    result = await db.execute(
        select(PatientClinicLink).where(
            PatientClinicLink.id == lid,
            PatientClinicLink.patient_id == user.id,
            PatientClinicLink.deleted_at.is_(None),
        )
    )
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND"}})

    link.consent_status = data.action
    if data.action == "approved":
        link.consented_at = datetime.now(timezone.utc)
    await db.flush()

    # Notify the doctor who created the link
    doctor_user = await db.get(User, link.linked_by)
    if doctor_user:
        patient_name = user.full_name or "A patient"
        action_label = "approved" if data.action == "approved" else "revoked"
        await create_notification(
            db=db,
            user_id=doctor_user.id,
            notif_type="system",
            title=f"Patient {patient_name} {action_label} clinic access",
            body=f"{patient_name} has {action_label} their consent for clinic access.",
            action_url="/doctor/patients/link",
        )

    return {"consent_status": link.consent_status}


# ── Clinic member: list linked patients ────────────────────────────────────

@router.get("/clinics/{clinic_id}/patients")
async def list_clinic_patients(
    clinic_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    consent_only: bool = True,
):
    try:
        cid = uuid.UUID(clinic_id)
    except ValueError:
        raise HTTPException(status_code=422, detail={"error": {"code": "INVALID_ID"}})

    # Verify clinic membership
    m = await db.execute(
        select(ClinicMembership).where(
            ClinicMembership.clinic_id == cid,
            ClinicMembership.user_id == user.id,
            ClinicMembership.is_active.is_(True),
            ClinicMembership.deleted_at.is_(None),
        )
    )
    if not m.scalar_one_or_none():
        raise HTTPException(status_code=403, detail={"error": {"code": "NOT_CLINIC_MEMBER"}})

    stmt = (
        select(PatientClinicLink, User)
        .join(User, User.id == PatientClinicLink.patient_id)
        .where(
            PatientClinicLink.clinic_id == cid,
            PatientClinicLink.deleted_at.is_(None),
            User.deleted_at.is_(None),
        )
        .order_by(PatientClinicLink.created_at.desc())
    )
    if consent_only:
        stmt = stmt.where(PatientClinicLink.consent_status == "approved")

    result = await db.execute(stmt)
    rows = result.all()

    return {
        "data": [
            {
                "link_id": str(link.id),
                "patient_id": str(patient.id),
                "full_name": patient.full_name,
                "email": patient.email,
                "phone": patient.phone,
                "consent_status": link.consent_status,
                "linked_at": link.created_at.isoformat(),
            }
            for link, patient in rows
        ],
        "total": len(rows),
    }
