from datetime import datetime, timedelta, date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, get_medicine_db
from app.dependencies import require_admin
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

    # Compute trends vs previous period
    end = _parse_date(end_date) or datetime.now().date()
    start = _parse_date(start_date) or (end - timedelta(days=30))
    period_days = (end - start).days or 30
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=period_days)

    def pct_change(current: int, previous: int) -> float:
        if previous == 0:
            return 0.0
        return round((current - previous) / previous * 100, 1)

    # Patients trend
    cur_patients = await db.scalar(
        select(func.count()).select_from(User).where(
            User.role == "patient",
            User.deleted_at.is_(None),
            func.date(User.created_at) >= start,
            func.date(User.created_at) <= end,
        )
    ) or 0
    prev_patients = await db.scalar(
        select(func.count()).select_from(User).where(
            User.role == "patient",
            User.deleted_at.is_(None),
            func.date(User.created_at) >= prev_start,
            func.date(User.created_at) <= prev_end,
        )
    ) or 0

    # Records trend
    cur_records = await db.scalar(
        select(func.count()).select_from(MedicalRecord).where(
            MedicalRecord.deleted_at.is_(None),
            func.date(MedicalRecord.created_at) >= start,
            func.date(MedicalRecord.created_at) <= end,
        )
    ) or 0
    prev_records = await db.scalar(
        select(func.count()).select_from(MedicalRecord).where(
            MedicalRecord.deleted_at.is_(None),
            func.date(MedicalRecord.created_at) >= prev_start,
            func.date(MedicalRecord.created_at) <= prev_end,
        )
    ) or 0

    # Prescriptions trend
    cur_rx = await db.scalar(
        select(func.count()).select_from(Prescription).where(
            Prescription.deleted_at.is_(None),
            func.date(Prescription.created_at) >= start,
            func.date(Prescription.created_at) <= end,
        )
    ) or 0
    prev_rx = await db.scalar(
        select(func.count()).select_from(Prescription).where(
            Prescription.deleted_at.is_(None),
            func.date(Prescription.created_at) >= prev_start,
            func.date(Prescription.created_at) <= prev_end,
        )
    ) or 0

    # Doctors trend
    cur_doctors = await db.scalar(
        select(func.count()).select_from(Doctor).where(
            Doctor.deleted_at.is_(None),
            func.date(Doctor.created_at) >= start,
            func.date(Doctor.created_at) <= end,
        )
    ) or 0
    prev_doctors = await db.scalar(
        select(func.count()).select_from(Doctor).where(
            Doctor.deleted_at.is_(None),
            func.date(Doctor.created_at) >= prev_start,
            func.date(Doctor.created_at) <= prev_end,
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

    # Get cumulative patient count up to start date as baseline
    baseline = await db.scalar(
        select(func.count()).select_from(User).where(
            User.role == "patient",
            User.deleted_at.is_(None),
            func.date(User.created_at) < start,
        )
    ) or 0

    trend = []
    running_total = baseline
    current = start
    while current <= end:
        day_new = await db.scalar(
            select(func.count()).select_from(User).where(
                User.role == "patient",
                User.deleted_at.is_(None),
                func.date(User.created_at) == current,
            )
        ) or 0
        running_total += day_new
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

    baseline = await db.scalar(
        select(func.count()).select_from(MedicalRecord).where(
            MedicalRecord.deleted_at.is_(None),
            func.date(MedicalRecord.created_at) < start,
        )
    ) or 0

    trend = []
    running_total = baseline
    current = start
    while current <= end:
        day_new = await db.scalar(
            select(func.count()).select_from(MedicalRecord).where(
                MedicalRecord.deleted_at.is_(None),
                func.date(MedicalRecord.created_at) == current,
            )
        ) or 0
        running_total += day_new
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

    baseline = await db.scalar(
        select(func.count()).select_from(Prescription).where(
            Prescription.deleted_at.is_(None),
            func.date(Prescription.created_at) < start,
        )
    ) or 0

    trend = []
    running_total = baseline
    current = start
    while current <= end:
        day_new = await db.scalar(
            select(func.count()).select_from(Prescription).where(
                Prescription.deleted_at.is_(None),
                func.date(Prescription.created_at) == current,
            )
        ) or 0
        running_total += day_new
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

    baseline = await db.scalar(
        select(func.count()).select_from(Doctor).where(
            Doctor.deleted_at.is_(None),
            func.date(Doctor.created_at) < start,
        )
    ) or 0

    trend = []
    running_total = baseline
    current = start
    while current <= end:
        day_new = await db.scalar(
            select(func.count()).select_from(Doctor).where(
                Doctor.deleted_at.is_(None),
                func.date(Doctor.created_at) == current,
            )
        ) or 0
        running_total += day_new
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

    statistics = []
    current = start
    while current <= end:
        new_patients = await db.scalar(
            select(func.count()).select_from(User).where(
                User.role == "patient",
                User.deleted_at.is_(None),
                func.date(User.created_at) == current,
            )
        ) or 0
        returning_patients = await db.scalar(
            select(func.count(MedicalRecord.patient_id.distinct())).select_from(MedicalRecord).where(
                MedicalRecord.deleted_at.is_(None),
                func.date(MedicalRecord.created_at) == current,
            )
        ) or 0
        statistics.append({
            "date": current.strftime("%Y-%m-%d"),
            "new_patients": new_patients,
            "returning_patients": returning_patients,
        })
        current += timedelta(days=1)

    return {"statistics": statistics}


@router.get("/appointment-requests")
async def get_appointment_requests(
    limit: int = Query(5, ge=1, le=50),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get recent medical records as activity feed."""
    result = await db.execute(
        select(MedicalRecord)
        .where(MedicalRecord.deleted_at.is_(None))
        .order_by(MedicalRecord.created_at.desc())
        .limit(limit)
    )
    records = result.scalars().all()

    # Fetch patient names
    requests = []
    for rec in records:
        patient = await db.get(User, rec.patient_id)
        requests.append({
            "id": str(rec.id),
            "patient_id": str(rec.patient_id),
            "patient_name": patient.full_name if patient else "Unknown",
            "patient_photo": None,
            "doctor_id": str(rec.doctor_id) if rec.doctor_id else None,
            "doctor_name": None,
            "department": rec.record_type,
            "requested_date": rec.created_at.strftime("%Y-%m-%d"),
            "requested_time": rec.created_at.strftime("%I:%M %p"),
            "status": "pending",
            "created_at": rec.created_at.isoformat(),
        })

    return {"requests": requests}


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

    import math
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


@router.get("/doctors")
async def get_admin_doctors(
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=100),
    search: Optional[str] = Query(None),
    specialty: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get paginated list of doctors."""
    query = (
        select(Doctor, User)
        .join(User, Doctor.user_id == User.id)
        .where(Doctor.deleted_at.is_(None), User.deleted_at.is_(None))
    )
    if search:
        query = query.where(
            User.full_name.ilike(f"%{search}%")
            | User.email.ilike(f"%{search}%")
            | Doctor.specialization.ilike(f"%{search}%")
        )
    if specialty:
        query = query.where(Doctor.specialization == specialty)

    total = await db.scalar(select(func.count()).select_from(query.subquery())) or 0
    result = await db.execute(
        query.order_by(Doctor.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    rows = result.all()

    import math
    return {
        "doctors": [
            {
                "id": str(doc.id),
                "name": user.full_name,
                "email": user.email,
                "photo": None,
                "specialty": doc.specialization,
                "license_number": doc.license_number,
                "facility": doc.facility_name,
                "verified": doc.verified,
                "created_at": doc.created_at.isoformat(),
            }
            for doc, user in rows
        ],
        "total": total,
        "page": page,
        "limit": limit,
        "totalPages": math.ceil(total / limit) if total else 0,
    }


@router.get("/doctors/specialties")
async def get_doctor_specialties(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get distinct doctor specializations."""
    result = await db.execute(
        select(Doctor.specialization)
        .where(Doctor.deleted_at.is_(None), Doctor.specialization.isnot(None))
        .distinct()
        .order_by(Doctor.specialization)
    )
    return [row[0] for row in result.all()]


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
    """Get paginated list of medical records (as appointments)."""
    query = (
        select(MedicalRecord, User)
        .join(User, MedicalRecord.patient_id == User.id)
        .where(MedicalRecord.deleted_at.is_(None), User.deleted_at.is_(None))
    )
    if search:
        query = query.where(User.full_name.ilike(f"%{search}%"))
    if department:
        query = query.where(MedicalRecord.record_type == department)

    total = await db.scalar(select(func.count()).select_from(query.subquery())) or 0
    result = await db.execute(
        query.order_by(MedicalRecord.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    rows = result.all()

    import math
    return {
        "appointments": [
            {
                "id": str(rec.id),
                "patient_name": user.full_name,
                "patient_photo": None,
                "doctor_name": None,
                "department": rec.record_type,
                "appointment_date": rec.created_at.strftime("%Y-%m-%d"),
                "appointment_time": rec.created_at.strftime("%I:%M %p"),
                "status": "completed",
                "type": rec.record_type,
                "notes": rec.description,
                "created_at": rec.created_at.isoformat(),
            }
            for rec, user in rows
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
    """Get distinct record types (used as departments)."""
    result = await db.execute(
        select(MedicalRecord.record_type)
        .where(MedicalRecord.deleted_at.is_(None))
        .distinct()
        .order_by(MedicalRecord.record_type)
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

    import math
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


@router.get("/lab-results")
async def get_admin_lab_results(
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=100),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    test_category: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get paginated list of lab result records."""
    query = (
        select(MedicalRecord, User)
        .join(User, MedicalRecord.patient_id == User.id)
        .where(
            MedicalRecord.deleted_at.is_(None),
            MedicalRecord.record_type == "lab_result",
            User.deleted_at.is_(None),
        )
    )
    if search:
        query = query.where(
            User.full_name.ilike(f"%{search}%")
            | MedicalRecord.title.ilike(f"%{search}%")
        )

    total = await db.scalar(select(func.count()).select_from(query.subquery())) or 0
    result = await db.execute(
        query.order_by(MedicalRecord.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    rows = result.all()

    import math
    return {
        "results": [
            {
                "id": str(rec.id),
                "test_id": f"LAB-{str(rec.id)[:8].upper()}",
                "patient_name": user.full_name,
                "patient_photo": None,
                "test_name": rec.title,
                "test_category": "General",
                "status": "completed",
                "notes": rec.description,
                "created_at": rec.created_at.isoformat(),
                "appointment_date": rec.created_at.strftime("%Y-%m-%d"),
            }
            for rec, user in rows
        ],
        "total": total,
        "page": page,
        "limit": limit,
        "totalPages": math.ceil(total / limit) if total else 0,
    }


@router.get("/lab-results/categories")
async def get_lab_test_categories(admin: User = Depends(require_admin)):
    return ["General", "Hematology", "Biochemistry", "Radiology", "Microbiology"]
