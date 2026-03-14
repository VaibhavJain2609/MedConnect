"""
Patient vitals time-series endpoints  [MD-253]

POST /api/v1/patients/vitals       — record a vital (patient)
GET  /api/v1/patients/vitals       — list own vitals (patient)
GET  /api/v1/doctors/patients/{patient_id}/vitals — read patient vitals (doctor)
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_active_clinic, get_current_doctor, require_patient
from app.models.doctor import Doctor
from app.models.user import User
from app.models.vital import VITAL_TYPES, PatientVital

router = APIRouter(tags=["vitals"])


# ── Pydantic schemas ───────────────────────────────────────────────────────

class VitalCreate(BaseModel):
    vital_type: str
    value: float
    unit: str
    recorded_at: Optional[datetime] = None
    notes: Optional[str] = None


class VitalResponse(BaseModel):
    id: str
    patient_id: str
    vital_type: str
    value: float
    unit: str
    recorded_at: str
    notes: Optional[str]
    recorded_by: Optional[str]
    created_at: str

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm(cls, v: PatientVital) -> "VitalResponse":
        return cls(
            id=str(v.id),
            patient_id=str(v.patient_id),
            vital_type=v.vital_type,
            value=float(v.value),
            unit=v.unit,
            recorded_at=v.recorded_at.isoformat(),
            notes=v.notes,
            recorded_by=str(v.recorded_by) if v.recorded_by else None,
            created_at=v.created_at.isoformat(),
        )


# ── Patient: record a vital ─────────────────────────────────────────────────

@router.post("/api/v1/patients/vitals", status_code=status.HTTP_201_CREATED)
async def create_vital(
    data: VitalCreate,
    user: User = Depends(require_patient),
    db: AsyncSession = Depends(get_db),
):
    """Record a new vital reading for the authenticated patient."""
    if data.vital_type not in VITAL_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_VITAL_TYPE",
                    "message": f"vital_type must be one of: {', '.join(sorted(VITAL_TYPES))}",
                }
            },
        )

    recorded_at = data.recorded_at or datetime.now(timezone.utc)

    vital = PatientVital(
        id=uuid.uuid4(),
        patient_id=user.id,
        vital_type=data.vital_type,
        value=data.value,
        unit=data.unit,
        recorded_at=recorded_at,
        recorded_by=user.id,
        notes=data.notes,
    )
    db.add(vital)
    await db.flush()
    await db.refresh(vital)
    return VitalResponse.from_orm(vital)


# ── Patient: list own vitals ────────────────────────────────────────────────

@router.get("/api/v1/patients/vitals")
async def list_vitals(
    type: Optional[str] = Query(None, description="Filter by vital_type"),
    days: int = Query(30, ge=1, le=365, description="Number of days of history"),
    limit: int = Query(200, ge=1, le=500),
    user: User = Depends(require_patient),
    db: AsyncSession = Depends(get_db),
):
    """Get patient's own vital readings as a time-series."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    conditions = [
        PatientVital.patient_id == user.id,
        PatientVital.deleted_at.is_(None),
        PatientVital.recorded_at >= since,
    ]

    if type:
        if type not in VITAL_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "INVALID_VITAL_TYPE",
                        "message": f"vital_type must be one of: {', '.join(sorted(VITAL_TYPES))}",
                    }
                },
            )
        conditions.append(PatientVital.vital_type == type)

    stmt = (
        select(PatientVital)
        .where(and_(*conditions))
        .order_by(PatientVital.recorded_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    vitals = result.scalars().all()

    return {
        "data": [VitalResponse.from_orm(v) for v in vitals],
        "total": len(vitals),
    }


# ── Doctor: read patient vitals ─────────────────────────────────────────────

@router.get("/api/v1/doctors/patients/{patient_id}/vitals")
async def get_patient_vitals(
    patient_id: uuid.UUID,
    type: Optional[str] = Query(None, description="Filter by vital_type"),
    days: int = Query(90, ge=1, le=365),
    doctor_info: tuple[User, Doctor] = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
    clinic_context: Optional[tuple] = Depends(get_active_clinic),
):
    """Read a patient's vital readings (doctor view)."""
    from app.models.patient_link import PatientClinicLink
    from app.routers.doctors import _check_patient_consent

    # If there is a clinic context, enforce consent
    if clinic_context:
        clinic_id, _ = clinic_context
        await _check_patient_consent(db, patient_id, clinic_id)

    since = datetime.now(timezone.utc) - timedelta(days=days)

    conditions = [
        PatientVital.patient_id == patient_id,
        PatientVital.deleted_at.is_(None),
        PatientVital.recorded_at >= since,
    ]

    if type:
        if type not in VITAL_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "INVALID_VITAL_TYPE",
                        "message": f"vital_type must be one of: {', '.join(sorted(VITAL_TYPES))}",
                    }
                },
            )
        conditions.append(PatientVital.vital_type == type)

    stmt = (
        select(PatientVital)
        .where(and_(*conditions))
        .order_by(PatientVital.recorded_at.desc())
        .limit(200)
    )
    result = await db.execute(stmt)
    vitals = result.scalars().all()

    return {
        "data": [VitalResponse.from_orm(v) for v in vitals],
        "total": len(vitals),
        "patient_id": str(patient_id),
    }
