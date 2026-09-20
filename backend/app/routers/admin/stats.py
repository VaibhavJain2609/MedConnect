import math
from datetime import datetime, timedelta, date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.database import get_db, get_medicine_db
from app.dependencies import require_admin
from app.models.notification import NotificationType
from app.services import notification_service
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.medical_record import MedicalRecord
from app.models.prescription import Prescription
from app.models.user import User
from app.models.medicine.commercial import Brand

router = APIRouter(prefix="/api/v1/admin", tags=["admin", "stats"])


def _parse_date(date_str: Optional[str]) -> Optional[date]:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None


def _day_start(d: date) -> datetime:
    """Start-of-day datetime for index-friendly half-open range predicates
    on timestamptz columns: ``col >= _day_start(start) AND col < _day_start(end+1)``."""
    return datetime.combine(d, datetime.min.time())


def _as_date(value) -> date:
    """Normalize a func.date() aggregate key to datetime.date."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


async def _daily_counts(
    db: AsyncSession,
    date_column,
    *filters,
    count_column=None,
) -> dict[date, int]:
    """One GROUP BY func.date() query returning {day: count}.

    Replaces the old per-day loop of func.count() queries. Filters must use
    index-friendly range predicates (>= start_dt, < end_dt) — never
    func.date(col) comparisons, which defeat indexes."""
    day_expr = func.date(date_column)
    count_expr = (
        func.count(count_column.distinct()) if count_column is not None else func.count()
    )
    rows = (
        await db.execute(
            select(day_expr.label("day"), count_expr.label("n"))
            .where(*filters)
            .group_by(day_expr)
        )
    ).all()
    return {_as_date(row.day): row.n for row in rows}


@router.get("/stats")
async def get_dashboard_stats(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    medicine_db: AsyncSession = Depends(get_medicine_db),
):
    """Get dashboard statistics from real database."""
    # Count patients
    total_patients = await db.scalar(
        select(func.count()).select_from(User).where(
            User.role == "patient",
            User.deleted_at.is_(None),
            User.is_active.is_(True),
        )
    ) or 0

    # Count doctors
    total_doctors = await db.scalar(
        select(func.count()).select_from(Doctor).where(
            Doctor.deleted_at.is_(None)
        )
    ) or 0

    verified_doctors = await db.scalar(
        select(func.count()).select_from(Doctor).where(
            Doctor.deleted_at.is_(None),
            Doctor.verified.is_(True),
        )
    ) or 0

    # Count medical records
    total_records = await db.scalar(
        select(func.count()).select_from(MedicalRecord).where(
            MedicalRecord.deleted_at.is_(None)
        )
    ) or 0

    # Count prescriptions
    total_prescriptions = await db.scalar(
        select(func.count()).select_from(Prescription).where(
            Prescription.deleted_at.is_(None)
        )
    ) or 0

    # Count medicines (brands) from medicine DB
    total_medicines = await medicine_db.scalar(
        select(func.count()).select_from(Brand)
    ) or 0

    # Compute trends vs previous period.
    # Half-open [start_dt, end_dt) ranges keep created_at indexes usable;
    # func.date(col) predicates would force a sequential scan.
    end = _parse_date(end_date) or datetime.now().date()
    start = _parse_date(start_date) or (end - timedelta(days=30))
    period_days = (end - start).days or 30
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=period_days)

    start_dt = _day_start(start)
    end_dt = _day_start(end + timedelta(days=1))
    prev_start_dt = _day_start(prev_start)
    prev_end_dt = _day_start(prev_end + timedelta(days=1))  # == start_dt

    def pct_change(current: int, previous: int) -> float:
        if previous == 0:
            return 0.0
        return round((current - previous) / previous * 100, 1)

    # Patients trend
    cur_patients = await db.scalar(
        select(func.count()).select_from(User).where(
            User.role == "patient",
            User.deleted_at.is_(None),
            User.created_at >= start_dt,
            User.created_at < end_dt,
        )
    ) or 0
    prev_patients = await db.scalar(
        select(func.count()).select_from(User).where(
            User.role == "patient",
            User.deleted_at.is_(None),
            User.created_at >= prev_start_dt,
            User.created_at < prev_end_dt,
        )
    ) or 0

    # Records trend
    cur_records = await db.scalar(
        select(func.count()).select_from(MedicalRecord).where(
            MedicalRecord.deleted_at.is_(None),
            MedicalRecord.created_at >= start_dt,
            MedicalRecord.created_at < end_dt,
        )
    ) or 0
    prev_records = await db.scalar(
        select(func.count()).select_from(MedicalRecord).where(
            MedicalRecord.deleted_at.is_(None),
            MedicalRecord.created_at >= prev_start_dt,
            MedicalRecord.created_at < prev_end_dt,
        )
    ) or 0

    # Prescriptions trend
    cur_rx = await db.scalar(
        select(func.count()).select_from(Prescription).where(
            Prescription.deleted_at.is_(None),
            Prescription.created_at >= start_dt,
            Prescription.created_at < end_dt,
        )
    ) or 0
    prev_rx = await db.scalar(
        select(func.count()).select_from(Prescription).where(
            Prescription.deleted_at.is_(None),
            Prescription.created_at >= prev_start_dt,
            Prescription.created_at < prev_end_dt,
        )
    ) or 0

    # Doctors trend
    cur_doctors = await db.scalar(
        select(func.count()).select_from(Doctor).where(
            Doctor.deleted_at.is_(None),
            Doctor.created_at >= start_dt,
            Doctor.created_at < end_dt,
        )
    ) or 0
    prev_doctors = await db.scalar(
        select(func.count()).select_from(Doctor).where(
            Doctor.deleted_at.is_(None),
            Doctor.created_at >= prev_start_dt,
            Doctor.created_at < prev_end_dt,
        )
    ) or 0

    return {
        "total_patients": total_patients,
        "total_doctors": total_doctors,
        "verified_doctors": verified_doctors,
        "unverified_doctors": total_doctors - verified_doctors,
        "total_records": total_records,
        "total_prescriptions": total_prescriptions,
        "total_medicines": total_medicines,
        "patient_trend": pct_change(cur_patients, prev_patients),
        "record_trend": pct_change(cur_records, prev_records),
        "prescription_trend": pct_change(cur_rx, prev_rx),
        "doctor_trend": pct_change(cur_doctors, prev_doctors),
    }


@router.get("/stats/patient-trend")
async def get_patient_trend(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get daily new patient counts for sparkline (last 30 days)."""
    end = _parse_date(end_date) or datetime.now().date()
    start = _parse_date(start_date) or (end - timedelta(days=29))
    start_dt = _day_start(start)
    end_dt = _day_start(end + timedelta(days=1))

    # Get cumulative patient count up to start date as baseline
    baseline = await db.scalar(
        select(func.count()).select_from(User).where(
            User.role == "patient",
            User.deleted_at.is_(None),
            User.created_at < start_dt,
        )
    ) or 0

    # One grouped query instead of one query per day
    daily = await _daily_counts(
        db,
        User.created_at,
        User.role == "patient",
        User.deleted_at.is_(None),
        User.created_at >= start_dt,
        User.created_at < end_dt,
    )

    trend = []
    running_total = baseline
    current = start
    while current <= end:
        running_total += daily.get(current, 0)
        trend.append({"date": current.strftime("%Y-%m-%d"), "value": running_total})
        current += timedelta(days=1)

    return {"trend": trend}


@router.get("/stats/record-trend")
async def get_record_trend(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get daily new medical record counts for sparkline."""
    end = _parse_date(end_date) or datetime.now().date()
    start = _parse_date(start_date) or (end - timedelta(days=29))
    start_dt = _day_start(start)
    end_dt = _day_start(end + timedelta(days=1))

    baseline = await db.scalar(
        select(func.count()).select_from(MedicalRecord).where(
            MedicalRecord.deleted_at.is_(None),
            MedicalRecord.created_at < start_dt,
        )
    ) or 0

    daily = await _daily_counts(
        db,
        MedicalRecord.created_at,
        MedicalRecord.deleted_at.is_(None),
        MedicalRecord.created_at >= start_dt,
        MedicalRecord.created_at < end_dt,
    )

    trend = []
    running_total = baseline
    current = start
    while current <= end:
        running_total += daily.get(current, 0)
        trend.append({"date": current.strftime("%Y-%m-%d"), "value": running_total})
        current += timedelta(days=1)

    return {"trend": trend}


@router.get("/stats/prescription-trend")
async def get_prescription_trend(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get daily new prescription counts for sparkline."""
    end = _parse_date(end_date) or datetime.now().date()
    start = _parse_date(start_date) or (end - timedelta(days=29))
    start_dt = _day_start(start)
    end_dt = _day_start(end + timedelta(days=1))

    baseline = await db.scalar(
        select(func.count()).select_from(Prescription).where(
            Prescription.deleted_at.is_(None),
            Prescription.created_at < start_dt,
        )
    ) or 0

    daily = await _daily_counts(
        db,
        Prescription.created_at,
        Prescription.deleted_at.is_(None),
        Prescription.created_at >= start_dt,
        Prescription.created_at < end_dt,
    )

    trend = []
    running_total = baseline
    current = start
    while current <= end:
        running_total += daily.get(current, 0)
        trend.append({"date": current.strftime("%Y-%m-%d"), "value": running_total})
        current += timedelta(days=1)

    return {"trend": trend}


@router.get("/stats/doctor-trend")
async def get_doctor_trend(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get daily doctor count for sparkline."""
    end = _parse_date(end_date) or datetime.now().date()
    start = _parse_date(start_date) or (end - timedelta(days=29))
    start_dt = _day_start(start)
    end_dt = _day_start(end + timedelta(days=1))

    baseline = await db.scalar(
        select(func.count()).select_from(Doctor).where(
            Doctor.deleted_at.is_(None),
            Doctor.created_at < start_dt,
        )
    ) or 0

    daily = await _daily_counts(
        db,
        Doctor.created_at,
        Doctor.deleted_at.is_(None),
        Doctor.created_at >= start_dt,
        Doctor.created_at < end_dt,
    )

    trend = []
    running_total = baseline
    current = start
    while current <= end:
        running_total += daily.get(current, 0)
        trend.append({"date": current.strftime("%Y-%m-%d"), "value": running_total})
        current += timedelta(days=1)

    return {"trend": trend}


@router.get("/stats/record-types")
async def get_record_type_stats(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get medical record counts grouped by type."""
    result = await db.execute(
        select(MedicalRecord.record_type, func.count().label("count"))
        .where(MedicalRecord.deleted_at.is_(None))
        .group_by(MedicalRecord.record_type)
        .order_by(func.count().desc())
    )
    rows = result.all()
    return {"record_types": [{"type": row[0], "count": row[1]} for row in rows]}


@router.get("/stats/patient-statistics")
async def get_patient_statistics(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get new vs returning patient activity per day (last 7 days)."""
    end = _parse_date(end_date) or datetime.now().date()
    start = _parse_date(start_date) or (end - timedelta(days=6))
    start_dt = _day_start(start)
    end_dt = _day_start(end + timedelta(days=1))

    # Two grouped queries instead of two queries per day
    new_daily = await _daily_counts(
        db,
        User.created_at,
        User.role == "patient",
        User.deleted_at.is_(None),
        User.created_at >= start_dt,
        User.created_at < end_dt,
    )
    returning_daily = await _daily_counts(
        db,
        MedicalRecord.created_at,
        MedicalRecord.deleted_at.is_(None),
        MedicalRecord.created_at >= start_dt,
        MedicalRecord.created_at < end_dt,
        count_column=MedicalRecord.patient_id,
    )

    statistics = []
    current = start
    while current <= end:
        statistics.append({
            "date": current.strftime("%Y-%m-%d"),
            "new_patients": new_daily.get(current, 0),
            "returning_patients": returning_daily.get(current, 0),
        })
        current += timedelta(days=1)

    return {"statistics": statistics}


@router.get("/appointment-requests")
async def get_appointment_requests(
    limit: int = Query(5, ge=1, le=50),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get recent appointment requests as activity feed.

    Single joined query over the real Appointment model — patient and
    doctor names come from JOINs, not a per-row db.get() (N+1)."""
    PatientUser = aliased(User)
    DoctorUser = aliased(User)

    result = await db.execute(
        select(Appointment, PatientUser, Doctor, DoctorUser)
        .join(PatientUser, Appointment.patient_id == PatientUser.id)
        .join(Doctor, Appointment.doctor_id == Doctor.id)
        .outerjoin(DoctorUser, Doctor.user_id == DoctorUser.id)
        .where(
            Appointment.deleted_at.is_(None),
            PatientUser.deleted_at.is_(None),
            Doctor.deleted_at.is_(None),
        )
        .order_by(Appointment.created_at.desc())
        .limit(limit)
    )
    rows = result.all()

    return {
        "requests": [
            {
                "id": str(appt.id),
                "patient_id": str(appt.patient_id),
                "patient_name": patient.full_name,
                "patient_photo": None,
                "doctor_id": str(appt.doctor_id),
                "doctor_name": doc_user.full_name if doc_user else None,
                "department": doctor.specialization,
                "requested_date": appt.scheduled_at.strftime("%Y-%m-%d"),
                "requested_time": appt.scheduled_at.strftime("%I:%M %p"),
                "status": appt.status,
                "created_at": appt.created_at.isoformat(),
            }
            for appt, patient, doctor, doc_user in rows
        ]
    }


@router.get("/patients")
async def get_admin_patients(
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=100),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get paginated list of patients."""
    query = select(User).where(
        User.role == "patient",
        User.deleted_at.is_(None),
    )
    if search:
        query = query.where(
            User.full_name.ilike(f"%{search}%")
            | User.email.ilike(f"%{search}%")
            | User.phone.ilike(f"%{search}%")
        )
    if status == "active":
        query = query.where(User.is_active.is_(True))
    elif status == "inactive":
        query = query.where(User.is_active.is_(False))

    total = await db.scalar(select(func.count()).select_from(query.subquery())) or 0
    result = await db.execute(
        query.order_by(User.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    users = result.scalars().all()

    return {
        "patients": [
            {
                "id": str(u.id),
                "name": u.full_name,
                "email": u.email,
                "phone": u.phone,
                "photo": None,
                "status": "active" if u.is_active else "inactive",
                "statusLabel": "Active" if u.is_active else "Inactive",
                "created_at": u.created_at.isoformat(),
            }
            for u in users
        ],
        "total": total,
        "page": page,
        "limit": limit,
        "totalPages": math.ceil(total / limit) if total else 0,
    }


@router.get("/appointments")
async def get_admin_appointments(
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=100),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get paginated list of appointments (real Appointment model)."""
    PatientUser = aliased(User)
    DoctorUser = aliased(User)

    query = (
        select(Appointment, PatientUser, Doctor, DoctorUser)
        .join(PatientUser, Appointment.patient_id == PatientUser.id)
        .join(Doctor, Appointment.doctor_id == Doctor.id)
        .outerjoin(DoctorUser, Doctor.user_id == DoctorUser.id)
        .where(
            Appointment.deleted_at.is_(None),
            PatientUser.deleted_at.is_(None),
            Doctor.deleted_at.is_(None),
        )
    )
    if search:
        query = query.where(PatientUser.full_name.ilike(f"%{search}%"))
    if status:
        query = query.where(Appointment.status == status)
    if department:
        query = query.where(Doctor.specialization == department)
    if date:
        day = _parse_date(date)
        if day:
            # Half-open day range — keeps the scheduled_at indexes usable
            query = query.where(
                Appointment.scheduled_at >= _day_start(day),
                Appointment.scheduled_at < _day_start(day + timedelta(days=1)),
            )

    total = await db.scalar(select(func.count()).select_from(query.subquery())) or 0
    result = await db.execute(
        query.order_by(Appointment.scheduled_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    rows = result.all()

    return {
        "appointments": [
            {
                "id": str(appt.id),
                "patient_name": patient.full_name,
                "patient_photo": None,
                "doctor_name": doc_user.full_name if doc_user else None,
                "department": doctor.specialization,
                "appointment_date": appt.scheduled_at.strftime("%Y-%m-%d"),
                "appointment_time": appt.scheduled_at.strftime("%I:%M %p"),
                "status": appt.status,
                "type": appt.type,
                "notes": appt.notes,
                "created_at": appt.created_at.isoformat(),
            }
            for appt, patient, doctor, doc_user in rows
        ],
        "total": total,
        "page": page,
        "limit": limit,
        "totalPages": math.ceil(total / limit) if total else 0,
    }


@router.get("/appointments/departments")
async def get_appointment_departments(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get distinct doctor specializations (used as appointment departments)."""
    result = await db.execute(
        select(Doctor.specialization)
        .where(Doctor.deleted_at.is_(None), Doctor.specialization.isnot(None))
        .distinct()
        .order_by(Doctor.specialization)
    )
    return [row[0] for row in result.all()]


@router.get("/visits")
async def get_admin_visits(
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=100),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get paginated list of visits (prescriptions with patient info)."""
    query = (
        select(Prescription, User)
        .join(User, Prescription.patient_id == User.id)
        .where(Prescription.deleted_at.is_(None), User.deleted_at.is_(None))
    )
    if search:
        query = query.where(User.full_name.ilike(f"%{search}%"))

    total = await db.scalar(select(func.count()).select_from(query.subquery())) or 0
    result = await db.execute(
        query.order_by(Prescription.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    rows = result.all()

    return {
        "visits": [
            {
                "id": str(rx.id),
                "visit_id": f"VIS-{str(rx.id)[:8].upper()}",
                "patient_name": user.full_name,
                "patient_photo": None,
                "doctor_name": None,
                "visit_date": rx.created_at.strftime("%Y-%m-%d"),
                "visit_time": rx.created_at.strftime("%I:%M %p"),
                "status": "completed",
                "diagnosis": rx.diagnosis,
                "notes": rx.notes,
                "created_at": rx.created_at.isoformat(),
            }
            for rx, user in rows
        ],
        "total": total,
        "page": page,
        "limit": limit,
        "totalPages": math.ceil(total / limit) if total else 0,
    }


@router.get("/visits/departments")
async def get_visit_departments(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get distinct record types from prescriptions (used as visit departments)."""
    result = await db.execute(
        select(MedicalRecord.record_type)
        .where(MedicalRecord.deleted_at.is_(None))
        .distinct()
        .order_by(MedicalRecord.record_type)
    )
    return [row[0] for row in result.all() if row[0]]


class AppointmentRejectBody(BaseModel):
    reason: Optional[str] = None


async def _get_appointment_or_404(db: AsyncSession, appointment_id) -> Appointment:
    from uuid import UUID
    try:
        appt_id = appointment_id if not isinstance(appointment_id, str) else UUID(appointment_id)
    except ValueError:
        raise HTTPException(status_code=422, detail={"error": {"code": "INVALID_ID", "message": "Invalid appointment ID"}})
    res = await db.execute(
        select(Appointment).where(Appointment.id == appt_id, Appointment.deleted_at.is_(None))
    )
    appt = res.scalar_one_or_none()
    if appt is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Appointment not found"}})
    return appt


@router.post("/appointment-requests/{appointment_id}/approve")
async def approve_appointment_request(
    appointment_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Approve a pending appointment request — keeps it 'scheduled' and
    notifies the patient that the booking was confirmed."""
    appt = await _get_appointment_or_404(db, appointment_id)
    if appt.status != "scheduled":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "INVALID_STATE", "message": f"Cannot approve an appointment in '{appt.status}' state"}},
        )

    await notification_service.create_notification(
        db,
        user_id=appt.patient_id,
        notif_type=NotificationType.APPOINTMENT.value,
        title="Appointment confirmed",
        body="Your appointment request has been approved.",
        action_url="/patient/appointments",
        metadata={"appointment_id": str(appt.id)},
    )

    from app.services.audit_service import log_change
    await log_change(
        db=db,
        table_name="appointments",
        record_id=appt.id,
        action="UPDATE",
        old_values={"status": appt.status},
        new_values={"approved_by_admin": True},
    )
    await db.commit()
    return {"id": str(appt.id), "status": appt.status}


@router.post("/appointment-requests/{appointment_id}/reject")
async def reject_appointment_request(
    appointment_id: str,
    body: AppointmentRejectBody | None = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Reject a pending appointment request — cancels it and notifies the patient."""
    appt = await _get_appointment_or_404(db, appointment_id)
    if appt.status not in {"scheduled"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "INVALID_STATE", "message": f"Cannot reject an appointment in '{appt.status}' state"}},
        )

    reason = (body.reason if body else None) or "Rejected by clinic administration"
    appt.status = "cancelled"
    appt.cancelled_reason = reason

    await notification_service.create_notification(
        db,
        user_id=appt.patient_id,
        notif_type=NotificationType.APPOINTMENT.value,
        title="Appointment request declined",
        body=f"Your appointment request was declined. {reason}",
        action_url="/patient/appointments",
        metadata={"appointment_id": str(appt.id)},
    )

    from app.services.audit_service import log_change
    await log_change(
        db=db,
        table_name="appointments",
        record_id=appt.id,
        action="UPDATE",
        old_values={"status": "scheduled"},
        new_values={"status": "cancelled", "cancelled_reason": reason},
    )
    await db.commit()
    return {"id": str(appt.id), "status": appt.status}
