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

# ── Critical vital thresholds [MD-270] ──────────────────────────────────────
# Maps vital_type (DB names) to threshold config.
# min/max are the DANGER thresholds — crossing either triggers a notification.
VITAL_THRESHOLDS: dict[str, dict] = {
    "bp_systolic":      {"min": None, "max": 180, "label": "Systolic BP",      "unit": "mmHg"},
    "bp_diastolic":     {"min": None, "max": 120, "label": "Diastolic BP",     "unit": "mmHg"},
    "glucose_fasting":  {"min": 70,   "max": 300, "label": "Blood Glucose (Fasting)", "unit": "mg/dL"},
    "glucose_pp":       {"min": 70,   "max": 300, "label": "Blood Glucose (PP)", "unit": "mg/dL"},
    "spo2":             {"min": 92,   "max": None, "label": "SpO2",             "unit": "%"},
    "pulse":            {"min": 40,   "max": 150, "label": "Heart Rate",        "unit": "bpm"},
}


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
    abnormal_flag: bool = False

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm(cls, v: PatientVital) -> "VitalResponse":
        abnormal = _is_abnormal(v.vital_type, float(v.value))
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
            abnormal_flag=abnormal,
        )


def _is_abnormal(vital_type: str, value: float) -> bool:
    """Return True if the value crosses a critical threshold."""
    thresholds = VITAL_THRESHOLDS.get(vital_type)
    if not thresholds:
        return False
    if thresholds["min"] is not None and value < thresholds["min"]:
        return True
    if thresholds["max"] is not None and value > thresholds["max"]:
        return True
    return False


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

    # MD-270: critical vitals alerting — fire notifications if threshold crossed
    if _is_abnormal(data.vital_type, float(data.value)):
        await _fire_critical_vital_notifications(
            db=db,
            patient_user=user,
            vital_type=data.vital_type,
            value=float(data.value),
        )

    return VitalResponse.from_orm(vital)


async def _fire_critical_vital_notifications(
    db: AsyncSession,
    patient_user: User,
    vital_type: str,
    value: float,
) -> None:
    """Create Notification records for patient and linked doctors when a vital is critical."""
    from app.models.notification import Notification, NotificationType
    from app.models.patient_link import PatientClinicLink
    from app.models.clinic import ClinicMembership
    from app.models.doctor import Doctor

    thresholds = VITAL_THRESHOLDS[vital_type]
    label = thresholds["label"]
    unit = thresholds["unit"]

    # Build a human-readable direction string
    if thresholds["max"] is not None and value > thresholds["max"]:
        direction = f"critically high ({value} {unit}, threshold: {thresholds['max']} {unit})"
    else:
        direction = f"critically low ({value} {unit}, threshold: {thresholds['min']} {unit})"

    title = "Critical Vital Alert"
    message = (
        f"Your {label} reading is {direction}. "
        "Please consult your doctor immediately."
    )

    # Notification for the patient
    patient_notification = Notification(
        id=uuid.uuid4(),
        user_id=patient_user.id,
        type=NotificationType.SYSTEM,
        title=title,
        message=message,
        meta={"vital_type": vital_type, "value": value, "abnormal_flag": True},
    )
    db.add(patient_notification)

    # Find all doctors linked to the patient via approved clinic links
    # PatientClinicLink gives us the clinic_id → ClinicMembership gives doctor user_ids
    linked_clinics_stmt = select(PatientClinicLink.clinic_id).where(
        PatientClinicLink.patient_id == patient_user.id,
        PatientClinicLink.consent_status == "approved",
        PatientClinicLink.deleted_at.is_(None),
    )
    linked_clinics_result = await db.execute(linked_clinics_stmt)
    clinic_ids = [row[0] for row in linked_clinics_result]

    if clinic_ids:
        doctor_users_stmt = (
            select(Doctor.user_id)
            .join(ClinicMembership, ClinicMembership.user_id == Doctor.user_id)
            .where(
                ClinicMembership.clinic_id.in_(clinic_ids),
                ClinicMembership.is_active.is_(True),
                ClinicMembership.deleted_at.is_(None),
                Doctor.deleted_at.is_(None),
            )
            .distinct()
        )
        doctor_users_result = await db.execute(doctor_users_stmt)
        doctor_user_ids = [row[0] for row in doctor_users_result]

        doctor_message = (
            f"Patient {patient_user.full_name}'s {label} reading is {direction}. "
            "Immediate attention may be required."
        )
        for doctor_user_id in doctor_user_ids:
            doctor_notification = Notification(
                id=uuid.uuid4(),
                user_id=doctor_user_id,
                type=NotificationType.SYSTEM,
                title=title,
                message=doctor_message,
                meta={
                    "vital_type": vital_type,
                    "value": value,
                    "patient_id": str(patient_user.id),
                    "patient_name": patient_user.full_name,
                    "abnormal_flag": True,
                },
            )
            db.add(doctor_notification)

    await db.flush()


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
