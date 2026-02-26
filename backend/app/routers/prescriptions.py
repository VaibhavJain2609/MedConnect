"""Prescription-related endpoints (accessible by both doctors and patients)."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.doctor import Doctor
from app.models.prescription import Prescription
from app.models.user import User
from app.services.pdf_service import generate_prescription_pdf

router = APIRouter(prefix="/api/v1/prescriptions", tags=["prescriptions"])


@router.get("/{prescription_id}/pdf")
async def download_prescription_pdf(
    prescription_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Download prescription as PDF.

    Authorization: Patient who owns the prescription or doctor who created it.
    """
    # Fetch prescription
    stmt = (
        select(Prescription)
        .where(Prescription.id == prescription_id, Prescription.deleted_at.is_(None))
    )
    result = await db.execute(stmt)
    prescription = result.scalar_one_or_none()

    if not prescription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Prescription not found"}},
        )

    # Authorization check
    is_patient = current_user.role == "patient" and prescription.patient_id == current_user.id

    # For doctor authorization, check if doctor_profile exists and matches
    is_doctor = False
    if current_user.role == "doctor" and current_user.doctor_profile:
        is_doctor = prescription.doctor_id == current_user.doctor_profile.id

    if not (is_patient or is_doctor):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Not authorized"}},
        )

    # Fetch doctor and patient
    doctor_stmt = select(Doctor).where(Doctor.id == prescription.doctor_id)
    doctor_result = await db.execute(doctor_stmt)
    doctor = doctor_result.scalar_one()

    doctor_user_stmt = select(User).where(User.id == doctor.user_id)
    doctor_user_result = await db.execute(doctor_user_stmt)
    doctor_user = doctor_user_result.scalar_one()

    patient_stmt = select(User).where(User.id == prescription.patient_id)
    patient_result = await db.execute(patient_stmt)
    patient = patient_result.scalar_one()

    # Generate PDF
    pdf_buffer = generate_prescription_pdf(
        prescription=prescription,
        doctor=doctor,
        doctor_user=doctor_user,
        patient=patient,
    )

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=prescription_{prescription_id}.pdf"
        }
    )
