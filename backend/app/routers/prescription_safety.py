"""
Prescription Safety Check Endpoint (R13)

GET /api/v1/prescriptions/{prescription_id}/safety-check

Returns the latest persisted clinical-safety snapshot written when the
prescription was created — which items were checked, which alerts were
computed, and the override reason when a "major" alert was overridden.

Access rules:
- Doctors can see checks for prescriptions they authored, or for
  prescriptions issued under a clinic they belong to (active membership).
- Patients can see checks on their own prescriptions (it is their data).
- Admins can see any prescription's checks.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.clinic import ClinicMembership
from app.models.doctor import Doctor
from app.models.prescription import Prescription
from app.models.prescription_safety_check import PrescriptionSafetyCheck
from app.models.user import User
from app.schemas.prescription import PrescriptionSafetyCheckResponse

router = APIRouter(prefix="/api/v1/prescriptions", tags=["prescription-safety"])


@router.get("/{prescription_id}/safety-check", response_model=PrescriptionSafetyCheckResponse)
async def get_prescription_safety_check(
    prescription_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    prescription = (
        await db.execute(
            select(Prescription).where(
                Prescription.id == prescription_id,
                Prescription.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()

    if prescription is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Prescription not found"}},
        )

    # Authorization — same spirit as the prescription PDF endpoint, extended
    # with clinic membership (a clinic's doctors can review each other's
    # issued prescriptions).
    if current_user.role == "patient":
        if prescription.patient_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "FORBIDDEN", "message": "Access denied"}},
            )
    elif current_user.role == "doctor":
        doctor = (
            await db.execute(
                select(Doctor).where(
                    Doctor.user_id == current_user.id,
                    Doctor.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        authorized = doctor is not None and prescription.doctor_id == doctor.id
        if not authorized and prescription.clinic_id is not None:
            authorized = (
                await db.execute(
                    select(ClinicMembership.id).where(
                        ClinicMembership.clinic_id == prescription.clinic_id,
                        ClinicMembership.user_id == current_user.id,
                        ClinicMembership.is_active.is_(True),
                        ClinicMembership.deleted_at.is_(None),
                    )
                )
            ).scalar_one_or_none() is not None
        if not authorized:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "FORBIDDEN", "message": "Access denied"}},
            )
    elif current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Access denied"}},
        )
    # admin role: no additional check required

    check = (
        await db.execute(
            select(PrescriptionSafetyCheck)
            .where(PrescriptionSafetyCheck.prescription_id == prescription_id)
            .order_by(PrescriptionSafetyCheck.checked_at.desc(), PrescriptionSafetyCheck.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if check is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": "No safety check recorded for this prescription",
                }
            },
        )

    return PrescriptionSafetyCheckResponse(
        id=check.id,
        prescription_id=check.prescription_id,
        checked_at=check.checked_at,
        items=check.items_json,
        alerts=check.alerts_json,
        override_reason=check.override_reason,
        created_at=check.created_at,
    )
