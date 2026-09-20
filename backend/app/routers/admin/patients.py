"""Admin patient read endpoints — vitals and appointments for any patient.

GET /api/v1/admin/patients/{id}/vitals          — vital readings (time-series)
GET /api/v1/admin/patients/{id}/vitals/history  — single vital type series
GET /api/v1/admin/patients/{id}/appointments    — appointment list

These back the admin-side patient helpers in frontend/src/lib/api/patients.ts.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_admin
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.user import User
from app.models.vital import VITAL_TYPES, PatientVital
from app.routers.vitals import VitalResponse

router = APIRouter(
    prefix="/api/v1/admin/patients",
    tags=["admin-patients"],
    dependencies=[Depends(require_admin)],
)

# Backend appointment status → frontend PatientAppointment.status union
_APPT_STATUS_MAP = {
    "scheduled": "upcoming",
    "arrived": "upcoming",
    "in-progress": "upcoming",
    "completed": "completed",
    "cancelled": "cancelled",
    "no-show": "cancelled",
}


async def _get_patient_or_404(db: AsyncSession, patient_id: UUID) -> User:
    patient = await db.scalar(
        select(User).where(
            User.id == patient_id,
            User.deleted_at.is_(None),
            User.role == "patient",
        )
    )
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Patient not found"}},
        )
    return patient


def _validate_vital_type(vital_type: str) -> None:
    if vital_type not in VITAL_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_VITAL_TYPE",
                    "message": f"vital_type must be one of: {', '.join(sorted(VITAL_TYPES))}",
                }
            },
        )


@router.get("/{patient_id}/vitals")
async def get_admin_patient_vitals(
    patient_id: UUID,
    type: Optional[str] = Query(None, description="Filter by vital_type"),
    days: int = Query(90, ge=1, le=365),
    limit: int = Query(200, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Read a patient's vital readings (admin view — same shape as the
    doctor-facing vitals endpoint)."""
    await _get_patient_or_404(db, patient_id)

    since = datetime.now(timezone.utc) - timedelta(days=days)
    conditions = [
        PatientVital.patient_id == patient_id,
        PatientVital.deleted_at.is_(None),
        PatientVital.recorded_at >= since,
    ]
    if type:
        _validate_vital_type(type)
        conditions.append(PatientVital.vital_type == type)

    result = await db.execute(
        select(PatientVital)
        .where(and_(*conditions))
        .order_by(PatientVital.recorded_at.desc())
        .limit(limit)
    )
    vitals = result.scalars().all()

    return {
        "data": [VitalResponse.from_orm(v) for v in vitals],
        "total": len(vitals),
        "patient_id": str(patient_id),
        "limit": limit,
    }


@router.get("/{patient_id}/vitals/history")
async def get_admin_patient_vitals_history(
    patient_id: UUID,
    type: str = Query(..., description="Vital type to chart"),
    days: int = Query(365, ge=1, le=1825),
    db: AsyncSession = Depends(get_db),
):
    """Time-series history for a single vital type, oldest → newest.
    Returns [{date, value}] matching the frontend PatientVitalHistory shape."""
    await _get_patient_or_404(db, patient_id)
    _validate_vital_type(type)

    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(PatientVital)
        .where(
            PatientVital.patient_id == patient_id,
            PatientVital.deleted_at.is_(None),
            PatientVital.vital_type == type,
            PatientVital.recorded_at >= since,
        )
        .order_by(PatientVital.recorded_at.asc())
    )
    vitals = result.scalars().all()

    return [
        {"date": v.recorded_at.isoformat(), "value": float(v.value)}
        for v in vitals
    ]


@router.get("/{patient_id}/appointments")
async def get_admin_patient_appointments(
    patient_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List a patient's appointments (newest first) with doctor name and
    specialization — matches the frontend PatientAppointment shape."""
    await _get_patient_or_404(db, patient_id)

    result = await db.execute(
        select(Appointment, User.full_name.label("doctor_name"), Doctor.specialization)
        .join(Doctor, Appointment.doctor_id == Doctor.id)
        .join(User, Doctor.user_id == User.id)
        .where(
            Appointment.patient_id == patient_id,
            Appointment.deleted_at.is_(None),
        )
        .order_by(Appointment.scheduled_at.desc())
        .limit(limit)
    )
    rows = result.all()

    return [
        {
            "id": str(a.id),
            "doctor": doctor_name,
            "doctorPhoto": None,
            "department": specialization or "—",
            "date": a.scheduled_at.date().isoformat(),
            "time": a.scheduled_at.strftime("%H:%M"),
            "status": _APPT_STATUS_MAP.get(a.status, "upcoming"),
            "type": a.type,
            "notes": a.notes,
        }
        for a, doctor_name, specialization in rows
    ]
