"""
Record access consent endpoints  [MD-RecordAccess]

POST /api/v1/doctors/patients/{patient_id}/record-access   — doctor requests consent
GET  /api/v1/doctors/patients/{patient_id}/record-access   — doctor checks consent status
GET  /api/v1/patients/record-access-requests               — patient lists requests
PUT  /api/v1/patients/record-access-requests/{consent_id}  — patient acts on request
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_active_clinic, get_current_doctor, require_active_clinic, require_patient
from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.patient_link import PatientClinicLink
from app.models.record_access import RecordAccessConsent
from app.models.user import User
from app.services.notification_service import create_notification

router = APIRouter(prefix="/api/v1", tags=["record-access"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class RecordAccessRequest(BaseModel):
    purpose: Optional[str] = None
    access_duration_days: int = Field(default=30, ge=1, le=365)


class RecordAccessAction(BaseModel):
    action: Literal["approved", "rejected", "revoked"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize_consent(consent: RecordAccessConsent, **extras) -> dict:
    return {
        "id": str(consent.id),
        "status": consent.status,
        "purpose": consent.purpose,
        "access_duration_days": consent.access_duration_days,
        "expires_at": consent.expires_at.isoformat() if consent.expires_at else None,
        "consented_at": consent.consented_at.isoformat() if consent.consented_at else None,
        "created_at": consent.created_at.isoformat(),
        **extras,
    }


# ---------------------------------------------------------------------------
# Doctor: request consent
# ---------------------------------------------------------------------------

@router.post(
    "/doctors/patients/{patient_id}/record-access",
    status_code=status.HTTP_201_CREATED,
)
async def request_record_access(
    patient_id: uuid.UUID,
    body: RecordAccessRequest,
    doctor_info: tuple[User, Doctor] = Depends(get_current_doctor),
    clinic_ctx: tuple = Depends(require_active_clinic),
    db: AsyncSession = Depends(get_db),
):
    """Doctor requests full record access for a patient (Tier 2 consent)."""
    _, doctor = doctor_info
    clinic_id, _ = clinic_ctx

    # Verify patient has an approved clinic link
    link_result = await db.execute(
        select(PatientClinicLink).where(
            PatientClinicLink.patient_id == patient_id,
            PatientClinicLink.clinic_id == clinic_id,
            PatientClinicLink.consent_status == "approved",
            PatientClinicLink.deleted_at.is_(None),
        )
    )
    if not link_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "NOT_LINKED", "message": "Patient has no approved clinic link"}},
        )

    # Check for existing pending request
    pending_result = await db.execute(
        select(RecordAccessConsent).where(
            RecordAccessConsent.doctor_id == doctor.id,
            RecordAccessConsent.patient_id == patient_id,
            RecordAccessConsent.status == "pending",
            RecordAccessConsent.deleted_at.is_(None),
        ).limit(1)
    )
    if pending_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "PENDING_REQUEST_EXISTS", "message": "A pending request already exists"}},
        )

    consent = RecordAccessConsent(
        id=uuid.uuid4(),
        doctor_id=doctor.id,
        patient_id=patient_id,
        clinic_id=clinic_id,
        status="pending",
        purpose=body.purpose,
        access_duration_days=body.access_duration_days,
    )
    db.add(consent)
    await db.flush()

    # Notify patient
    doctor_user = await db.get(User, doctor.user_id)
    doctor_name = doctor_user.full_name if doctor_user else "Your doctor"
    await create_notification(
        db=db,
        user_id=patient_id,
        notif_type="system",
        title=f"Record access request from Dr. {doctor_name}",
        body=f"Dr. {doctor_name} has requested access to your full medical records.",
        action_url="/patient/clinics",
        metadata={"consent_id": str(consent.id)},
    )

    return _serialize_consent(consent)


# ---------------------------------------------------------------------------
# Doctor: check consent status
# ---------------------------------------------------------------------------

@router.get("/doctors/patients/{patient_id}/record-access")
async def get_record_access_consent(
    patient_id: uuid.UUID,
    doctor_info: tuple[User, Doctor] = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    """Doctor checks their current consent status for a patient."""
    _, doctor = doctor_info

    result = await db.execute(
        select(RecordAccessConsent)
        .where(
            RecordAccessConsent.doctor_id == doctor.id,
            RecordAccessConsent.patient_id == patient_id,
            RecordAccessConsent.deleted_at.is_(None),
        )
        .order_by(RecordAccessConsent.created_at.desc())
        .limit(1)
    )
    consent = result.scalar_one_or_none()
    if not consent:
        return None

    return _serialize_consent(consent)


# ---------------------------------------------------------------------------
# Patient: list all requests
# ---------------------------------------------------------------------------

@router.get("/patients/record-access-requests")
async def list_record_access_requests(
    status_filter: Optional[str] = Query(None, alias="status"),
    user: User = Depends(require_patient),
    db: AsyncSession = Depends(get_db),
):
    """Patient lists all record access requests directed to them."""
    stmt = (
        select(RecordAccessConsent, User.full_name.label("doctor_name"), Doctor.specialization, Clinic.name.label("clinic_name"))
        .join(Doctor, Doctor.id == RecordAccessConsent.doctor_id)
        .join(User, User.id == Doctor.user_id)
        .join(Clinic, Clinic.id == RecordAccessConsent.clinic_id)
        .where(
            RecordAccessConsent.patient_id == user.id,
            RecordAccessConsent.deleted_at.is_(None),
        )
        .order_by(RecordAccessConsent.created_at.desc())
    )
    if status_filter:
        stmt = stmt.where(RecordAccessConsent.status == status_filter)

    result = await db.execute(stmt)
    rows = result.all()

    data = [
        {
            **_serialize_consent(consent),
            "doctor_name": doctor_name,
            "doctor_specialization": specialization,
            "clinic_name": clinic_name,
        }
        for consent, doctor_name, specialization, clinic_name in rows
    ]

    return {"data": data}


# ---------------------------------------------------------------------------
# Patient: act on request
# ---------------------------------------------------------------------------

@router.put("/patients/record-access-requests/{consent_id}")
async def act_on_record_access_request(
    consent_id: uuid.UUID,
    body: RecordAccessAction,
    user: User = Depends(require_patient),
    db: AsyncSession = Depends(get_db),
):
    """Patient approves, rejects, or revokes a record access request."""
    result = await db.execute(
        select(RecordAccessConsent).where(
            RecordAccessConsent.id == consent_id,
            RecordAccessConsent.patient_id == user.id,
            RecordAccessConsent.deleted_at.is_(None),
        )
    )
    consent = result.scalar_one_or_none()
    if not consent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Consent request not found"}},
        )

    now = datetime.now(timezone.utc)

    if body.action == "approved":
        consent.status = "approved"
        consent.consented_at = now
        consent.expires_at = now + timedelta(days=consent.access_duration_days)
    elif body.action == "rejected":
        consent.status = "rejected"
    elif body.action == "revoked":
        if consent.status != "approved":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "INVALID_ACTION", "message": "Can only revoke an approved consent"}},
            )
        consent.status = "revoked"

    await db.flush()

    # Notify doctor
    doctor = await db.get(Doctor, consent.doctor_id)
    if doctor:
        patient_name = user.full_name or "A patient"
        action_label = body.action
        await create_notification(
            db=db,
            user_id=doctor.user_id,
            notif_type="system",
            title=f"Patient {patient_name} {action_label} record access",
            body=f"{patient_name} has {action_label} your request for full record access.",
            action_url=f"/doctor/patients/{user.id}",
        )

    return _serialize_consent(consent)
