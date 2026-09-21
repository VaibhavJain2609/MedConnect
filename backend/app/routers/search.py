"""Global search endpoints — role-aware.

GET /api/v1/search             — search across entities visible to the caller's role
GET /api/v1/search/suggestions — lightweight autocomplete suggestions

Visibility rules:
  admin   → patients, doctors, clinics, appointments, medicines,
            medical records, lab results, prescriptions
  doctor  → own patients (records they authored or approved clinic links),
            own appointments, medicines, member clinics, plus their
            patients' records / lab results / prescriptions (scoped via
            access_service.accessible_patient_ids_select)
  patient → own medical records, lab results, prescriptions, appointments;
            the active clinic directory (name/city/address only — public
            directory info, used to find a clinic to link to)

PHI discipline: the raw query string is never logged here, and the
read-audit middleware records only the request path (never query params),
so search terms containing PHI cannot leak into logs or audit rows.

Response shape matches frontend/src/lib/api/search.ts:
  {results: [{id, type, title, subtitle?, photo?, url?, metadata?}],
   total, query, took_ms}
"""
import time

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Text, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, get_medicine_db
from app.dependencies import get_current_user
from app.models.appointment import Appointment
from app.models.clinic import Clinic, ClinicMembership
from app.models.doctor import Doctor
from app.models.lab_result import LabResult
from app.models.medical_record import MedicalRecord
from app.models.medicine.commercial import Brand, Manufacturer
from app.models.medicine.salts import Salt
from app.models.prescription import Prescription
from app.models.user import User

router = APIRouter(prefix="/api/v1/search", tags=["search"])

VALID_TYPES = {
    "patient",
    "doctor",
    "clinic",
    "appointment",
    "medicine",
    "record",
    "lab_result",
    "prescription",
}


# ── Per-entity search helpers ────────────────────────────────────────────────
# Each returns (results: list[dict], total: int). `limit`/`offset` apply per
# entity type, so a type="all" search returns up to `limit` rows per category.

async def _search_patients(
    db: AsyncSession, q: str, limit: int, offset: int, doctor: Doctor | None
) -> tuple[list[dict], int]:
    """Patient users matching q. Doctors only see their own patients."""
    term = f"%{q}%"
    match = or_(
        User.full_name.ilike(term),
        User.email.ilike(term),
        User.phone.ilike(term),
    )

    if doctor is not None:
        # Visible patients per the centralized rule: records authored by this
        # doctor OR an approved link to a clinic the doctor belongs to.
        from app.services.access_service import accessible_patient_ids_select
        stmt = (
            select(User)
            .where(
                User.id.in_(
                    accessible_patient_ids_select(
                        doctor.user_id, doctor.id, allow_revoked=False
                    )
                ),
                User.deleted_at.is_(None),
                User.role == "patient",
                match,
            )
        )
        url_prefix = "/doctor/patients"
    else:
        stmt = select(User).where(
            User.deleted_at.is_(None), User.role == "patient", match
        )
        url_prefix = "/admin/users"

    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    result = await db.execute(
        stmt.order_by(User.full_name.asc()).offset(offset).limit(limit)
    )
    users = result.scalars().all()

    results = [
        {
            "id": str(u.id),
            "type": "patient",
            "title": u.full_name,
            "subtitle": u.email or u.phone,
            "photo": None,
            "url": f"{url_prefix}/{u.id}",
            "metadata": {"role": "patient", "phone": u.phone},
        }
        for u in users
    ]
    return results, total


async def _search_doctors(
    db: AsyncSession, q: str, limit: int, offset: int
) -> tuple[list[dict], int]:
    """Doctor profiles matching q (admin view)."""
    term = f"%{q}%"
    stmt = (
        select(Doctor, User)
        .join(User, Doctor.user_id == User.id)
        .where(
            Doctor.deleted_at.is_(None),
            User.deleted_at.is_(None),
            or_(
                User.full_name.ilike(term),
                User.email.ilike(term),
                Doctor.specialization.ilike(term),
                Doctor.license_number.ilike(term),
                Doctor.facility_name.ilike(term),
            ),
        )
    )
    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    result = await db.execute(
        stmt.order_by(User.full_name.asc()).offset(offset).limit(limit)
    )
    rows = result.all()

    results = [
        {
            "id": str(doctor.id),
            "type": "doctor",
            "title": user.full_name,
            "subtitle": doctor.specialization or doctor.facility_name or user.email,
            "photo": None,
            "url": f"/admin/doctors/{doctor.id}",
            "metadata": {
                "user_id": str(user.id),
                "verified": doctor.verified,
                "specialization": doctor.specialization,
            },
        }
        for doctor, user in rows
    ]
    return results, total


async def _search_clinics(
    db: AsyncSession, q: str, limit: int, offset: int, user: User
) -> tuple[list[dict], int]:
    """Clinics matching q.

    - admin   → all clinics → /admin/clinics/{id}
    - doctor  → clinics where the user holds an active membership → /doctor/clinic
    - patient → the active clinic directory (name/city/address only) so a
      patient can find a clinic to link to → /patient/clinics
    """
    term = f"%{q}%"
    match = or_(
        Clinic.name.ilike(term),
        Clinic.city.ilike(term),
        Clinic.address.ilike(term),
    )
    stmt = select(Clinic).where(Clinic.deleted_at.is_(None), match)

    if user.role == "doctor":
        stmt = stmt.where(
            Clinic.id.in_(
                select(ClinicMembership.clinic_id).where(
                    ClinicMembership.user_id == user.id,
                    ClinicMembership.is_active.is_(True),
                    ClinicMembership.deleted_at.is_(None),
                )
            )
        )
        url = "/doctor/clinic"
    elif user.role == "patient":
        stmt = stmt.where(Clinic.is_active.is_(True))
        url = "/patient/clinics"
    else:
        url = None  # per-row /admin/clinics/{id}

    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    result = await db.execute(
        stmt.order_by(Clinic.name.asc()).offset(offset).limit(limit)
    )
    clinics = result.scalars().all()

    results = [
        {
            "id": str(c.id),
            "type": "clinic",
            "title": c.name,
            "subtitle": ", ".join(p for p in (c.city, c.state) if p) or c.address,
            "url": url or f"/admin/clinics/{c.id}",
            "metadata": {"city": c.city, "is_active": c.is_active},
        }
        for c in clinics
    ]
    return results, total


async def _search_appointments(
    db: AsyncSession,
    q: str,
    limit: int,
    offset: int,
    doctor: Doctor | None,
    patient: User | None = None,
) -> tuple[list[dict], int]:
    """Appointments matching q by complaint/notes and the counterpart's name.

    - admin   → all appointments (matched against patient name)
    - doctor  → own appointments (matched against patient name)
    - patient → own appointments (matched against doctor name)
    """
    term = f"%{q}%"

    if patient is not None:
        # Patient view: join through Doctor to the doctor's display name.
        stmt = (
            select(Appointment, User.full_name.label("counterpart_name"))
            .join(Doctor, Appointment.doctor_id == Doctor.id)
            .join(User, Doctor.user_id == User.id)
            .where(
                Appointment.deleted_at.is_(None),
                Appointment.patient_id == patient.id,
                or_(
                    Appointment.chief_complaint.ilike(term),
                    Appointment.notes.ilike(term),
                    User.full_name.ilike(term),
                ),
            )
        )
        url = "/patient/appointments"
        title_prefix = "Dr. "
    else:
        stmt = (
            select(Appointment, User.full_name.label("counterpart_name"))
            .join(User, Appointment.patient_id == User.id)
            .where(
                Appointment.deleted_at.is_(None),
                or_(
                    Appointment.chief_complaint.ilike(term),
                    Appointment.notes.ilike(term),
                    User.full_name.ilike(term),
                ),
            )
        )
        if doctor is not None:
            stmt = stmt.where(Appointment.doctor_id == doctor.id)
        url = "/doctor/appointments" if doctor is not None else "/admin/appointments"
        title_prefix = ""

    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    result = await db.execute(
        stmt.order_by(Appointment.scheduled_at.desc()).offset(offset).limit(limit)
    )
    rows = result.all()

    results = [
        {
            "id": str(a.id),
            "type": "appointment",
            "title": f"{title_prefix}{counterpart_name} — {a.type}",
            "subtitle": (
                f"{a.scheduled_at.isoformat()} · {a.status}"
                + (f" · {a.chief_complaint}" if a.chief_complaint else "")
            ),
            "url": url,
            "metadata": {
                "status": a.status,
                "scheduled_at": a.scheduled_at.isoformat(),
                "counterpart_name": counterpart_name,
            },
        }
        for a, counterpart_name in rows
    ]
    return results, total


async def _search_medicines(
    medicine_db: AsyncSession, q: str, limit: int, offset: int, role: str
) -> tuple[list[dict], int]:
    """Brands and salts matching q in the medicine catalog DB."""
    term = f"%{q}%"
    url = "/admin/medicines" if role == "admin" else "/doctor/prescriptions/new"

    brand_stmt = (
        select(Brand, Manufacturer.manufacturer_name)
        .join(Manufacturer, Brand.manufacturer_id == Manufacturer.manufacturer_id)
        .where(Brand.is_discontinued.is_(False), Brand.brand_name.ilike(term))
    )
    salt_stmt = select(Salt).where(Salt.salt_name.ilike(term))

    brand_total = await medicine_db.scalar(
        select(func.count()).select_from(brand_stmt.subquery())
    ) or 0
    salt_total = await medicine_db.scalar(
        select(func.count()).select_from(salt_stmt.subquery())
    ) or 0

    brand_rows = (
        await medicine_db.execute(
            brand_stmt.order_by(Brand.brand_name.asc()).offset(offset).limit(limit)
        )
    ).all()
    salt_rows = (
        await medicine_db.execute(
            salt_stmt.order_by(Salt.salt_name.asc()).offset(offset).limit(limit)
        )
    ).scalars().all()

    results = [
        {
            "id": str(brand.brand_id),
            "type": "medicine",
            "title": brand.brand_name,
            "subtitle": manufacturer_name,
            "url": url,
            "metadata": {"kind": "brand", "drug_type": brand.drug_type},
        }
        for brand, manufacturer_name in brand_rows
    ]
    results += [
        {
            "id": str(salt.salt_id),
            "type": "medicine",
            "title": salt.salt_name,
            "subtitle": "Salt / generic",
            "url": url,
            "metadata": {"kind": "salt"},
        }
        for salt in salt_rows
    ]
    return results, brand_total + salt_total


def _record_url(role: str, record: MedicalRecord) -> str:
    if role == "patient":
        return f"/patient/records/{record.id}"
    if role == "doctor":
        return f"/doctor/patients/{record.patient_id}"
    return f"/admin/users/{record.patient_id}"


async def _search_records(
    db: AsyncSession,
    q: str,
    limit: int,
    offset: int,
    user: User,
    doctor: Doctor | None = None,
) -> tuple[list[dict], int]:
    """Medical records matching q by title/description/type.

    - patient → own records only
    - doctor  → records of patients they may access (access_service rule:
      authored records or an approved clinic link)
    - admin   → all records
    """
    term = f"%{q}%"
    stmt = (
        select(MedicalRecord, User.full_name.label("patient_name"))
        .join(User, MedicalRecord.patient_id == User.id)
        .where(
            MedicalRecord.deleted_at.is_(None),
            or_(
                MedicalRecord.title.ilike(term),
                MedicalRecord.description.ilike(term),
                MedicalRecord.record_type.ilike(term),
            ),
        )
    )
    if user.role == "patient":
        stmt = stmt.where(MedicalRecord.patient_id == user.id)
    elif user.role == "doctor":
        from app.services.access_service import accessible_patient_ids_select
        stmt = stmt.where(
            MedicalRecord.patient_id.in_(
                accessible_patient_ids_select(
                    user.id, doctor.id if doctor else None, allow_revoked=False
                )
            )
        )

    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    result = await db.execute(
        stmt.order_by(MedicalRecord.created_at.desc()).offset(offset).limit(limit)
    )
    rows = result.all()

    results = [
        {
            "id": str(r.id),
            "type": "record",
            "title": r.title,
            "subtitle": (
                f"{r.record_type} · {r.created_at.date().isoformat()}"
                + (f" · {patient_name}" if user.role != "patient" else "")
            ),
            "url": _record_url(user.role, r),
            "metadata": {
                "record_type": r.record_type,
                "source": r.source,
                "patient_id": str(r.patient_id),
            },
        }
        for r, patient_name in rows
    ]
    return results, total


def _lab_result_url(role: str, lab: LabResult) -> str:
    if role == "patient":
        return "/patient/lab-results"
    if role == "doctor":
        return f"/doctor/patients/{lab.patient_id}"
    return "/admin/lab-results"


async def _search_lab_results(
    db: AsyncSession,
    q: str,
    limit: int,
    offset: int,
    user: User,
    doctor: Doctor | None = None,
) -> tuple[list[dict], int]:
    """Lab results matching q by test name/category/test id.

    - patient → own results only
    - doctor  → results of accessible patients only
    - admin   → all results
    """
    term = f"%{q}%"
    stmt = (
        select(LabResult, User.full_name.label("patient_name"))
        .join(User, LabResult.patient_id == User.id)
        .where(
            LabResult.deleted_at.is_(None),
            or_(
                LabResult.test_name.ilike(term),
                LabResult.test_category.ilike(term),
                LabResult.test_id.ilike(term),
            ),
        )
    )
    if user.role == "patient":
        stmt = stmt.where(LabResult.patient_id == user.id)
    elif user.role == "doctor":
        from app.services.access_service import accessible_patient_ids_select
        stmt = stmt.where(
            LabResult.patient_id.in_(
                accessible_patient_ids_select(
                    user.id, doctor.id if doctor else None, allow_revoked=False
                )
            )
        )

    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    result = await db.execute(
        stmt.order_by(LabResult.appointment_date.desc()).offset(offset).limit(limit)
    )
    rows = result.all()

    results = [
        {
            "id": str(lr.id),
            "type": "lab_result",
            "title": lr.test_name,
            "subtitle": (
                " · ".join(
                    p
                    for p in (
                        lr.test_category,
                        lr.status,
                        lr.appointment_date.date().isoformat(),
                        patient_name if user.role != "patient" else None,
                    )
                    if p
                )
            ),
            "url": _lab_result_url(user.role, lr),
            "metadata": {
                "test_id": lr.test_id,
                "status": lr.status,
                "abnormal_flag": lr.abnormal_flag,
                "patient_id": str(lr.patient_id),
            },
        }
        for lr, patient_name in rows
    ]
    return results, total


def _prescription_url(role: str, rx: Prescription) -> str:
    if role == "patient":
        # Patient-facing prescriptions are viewed through their backing record.
        return f"/patient/records/{rx.record_id}"
    if role == "doctor":
        return f"/doctor/prescriptions/{rx.id}"
    return f"/admin/users/{rx.patient_id}"


def _medicine_names(medicines) -> list[str]:
    """Extract display names from the JSONB medicine list."""
    if not isinstance(medicines, list):
        return []
    return [
        m["brand_name"]
        for m in medicines
        if isinstance(m, dict) and m.get("brand_name")
    ]


async def _search_prescriptions(
    db: AsyncSession,
    q: str,
    limit: int,
    offset: int,
    user: User,
    doctor: Doctor | None = None,
) -> tuple[list[dict], int]:
    """Prescriptions matching q by diagnosis, notes, or medicine brand name
    (the JSONB ``medicines`` column is cast to text for the name match).

    - patient → own prescriptions only
    - doctor  → prescriptions of accessible patients only
    - admin   → all prescriptions
    """
    term = f"%{q}%"
    stmt = (
        select(Prescription, User.full_name.label("patient_name"))
        .join(User, Prescription.patient_id == User.id)
        .where(
            Prescription.deleted_at.is_(None),
            or_(
                Prescription.diagnosis.ilike(term),
                Prescription.notes.ilike(term),
                cast(Prescription.medicines, Text).ilike(term),
            ),
        )
    )
    if user.role == "patient":
        stmt = stmt.where(Prescription.patient_id == user.id)
    elif user.role == "doctor":
        from app.services.access_service import accessible_patient_ids_select
        stmt = stmt.where(
            Prescription.patient_id.in_(
                accessible_patient_ids_select(
                    user.id, doctor.id if doctor else None, allow_revoked=False
                )
            )
        )

    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    result = await db.execute(
        stmt.order_by(Prescription.created_at.desc()).offset(offset).limit(limit)
    )
    rows = result.all()

    results = []
    for rx, patient_name in rows:
        med_names = _medicine_names(rx.medicines)
        subtitle_parts = [
            ", ".join(med_names[:3]) if med_names else None,
            rx.created_at.date().isoformat(),
            patient_name if user.role != "patient" else None,
        ]
        results.append(
            {
                "id": str(rx.id),
                "type": "prescription",
                "title": f"Rx — {rx.diagnosis or 'General'}",
                "subtitle": " · ".join(p for p in subtitle_parts if p),
                "url": _prescription_url(user.role, rx),
                "metadata": {
                    "patient_id": str(rx.patient_id),
                    "record_id": str(rx.record_id),
                    "medicines": med_names,
                },
            }
        )
    return results, total


async def _get_doctor_profile(db: AsyncSession, user: User) -> Doctor | None:
    return await db.scalar(
        select(Doctor).where(
            Doctor.user_id == user.id, Doctor.deleted_at.is_(None)
        )
    )


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("")
async def global_search(
    q: str = Query(..., min_length=1, description="Search query"),
    type: str | None = Query(
        None,
        description=(
            "Entity filter: patient|doctor|clinic|appointment|medicine|"
            "record|lab_result|prescription"
        ),
    ),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    medicine_db: AsyncSession = Depends(get_medicine_db),
):
    """Role-aware global search. `limit`/`offset` apply per entity type."""
    started = time.perf_counter()
    wanted = type if type in VALID_TYPES else None

    results: list[dict] = []
    total = 0

    async def _collect(coro) -> None:
        nonlocal total
        items, count = await coro
        results.extend(items)
        total += count

    if user.role == "admin":
        if wanted in (None, "patient"):
            await _collect(_search_patients(db, q, limit, offset, doctor=None))
        if wanted in (None, "doctor"):
            await _collect(_search_doctors(db, q, limit, offset))
        if wanted in (None, "clinic"):
            await _collect(_search_clinics(db, q, limit, offset, user))
        if wanted in (None, "appointment"):
            await _collect(_search_appointments(db, q, limit, offset, doctor=None))
        if wanted in (None, "medicine"):
            await _collect(_search_medicines(medicine_db, q, limit, offset, user.role))
        if wanted in (None, "record"):
            await _collect(_search_records(db, q, limit, offset, user))
        if wanted in (None, "lab_result"):
            await _collect(_search_lab_results(db, q, limit, offset, user))
        if wanted in (None, "prescription"):
            await _collect(_search_prescriptions(db, q, limit, offset, user))
    elif user.role == "doctor":
        doctor = await _get_doctor_profile(db, user)
        if wanted in (None, "patient") and doctor is not None:
            await _collect(_search_patients(db, q, limit, offset, doctor=doctor))
        if wanted in (None, "appointment") and doctor is not None:
            await _collect(_search_appointments(db, q, limit, offset, doctor=doctor))
        if wanted in (None, "medicine"):
            await _collect(_search_medicines(medicine_db, q, limit, offset, user.role))
        if wanted in (None, "clinic"):
            await _collect(_search_clinics(db, q, limit, offset, user))
        if doctor is not None:
            if wanted in (None, "record"):
                await _collect(_search_records(db, q, limit, offset, user, doctor))
            if wanted in (None, "lab_result"):
                await _collect(_search_lab_results(db, q, limit, offset, user, doctor))
            if wanted in (None, "prescription"):
                await _collect(_search_prescriptions(db, q, limit, offset, user, doctor))
    elif user.role == "patient":
        # own data + the clinic directory
        if wanted in (None, "record"):
            await _collect(_search_records(db, q, limit, offset, user))
        if wanted in (None, "lab_result"):
            await _collect(_search_lab_results(db, q, limit, offset, user))
        if wanted in (None, "prescription"):
            await _collect(_search_prescriptions(db, q, limit, offset, user))
        if wanted in (None, "appointment"):
            await _collect(
                _search_appointments(db, q, limit, offset, doctor=None, patient=user)
            )
        if wanted in (None, "clinic"):
            await _collect(_search_clinics(db, q, limit, offset, user))
    # Unknown/other roles get an empty result set — never fall through to a
    # broader scope.

    took_ms = round((time.perf_counter() - started) * 1000, 2)
    return {
        "results": results,
        "total": total,
        "query": q,
        "took_ms": took_ms,
    }


@router.get("/suggestions")
async def search_suggestions(
    q: str = Query(..., min_length=1, description="Autocomplete query"),
    limit: int = Query(10, ge=1, le=25),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    medicine_db: AsyncSession = Depends(get_medicine_db),
):
    """Autocomplete suggestions — reuses the role-aware search helpers and
    returns deduplicated result titles."""
    suggestions: list[str] = []
    seen: set[str] = set()

    async def _collect(coro) -> None:
        items, _ = await coro
        for item in items:
            title = item.get("title")
            if title and title not in seen:
                seen.add(title)
                suggestions.append(title)

    if user.role == "admin":
        await _collect(_search_patients(db, q, limit, 0, doctor=None))
        await _collect(_search_doctors(db, q, limit, 0))
        await _collect(_search_clinics(db, q, limit, 0, user))
        await _collect(_search_medicines(medicine_db, q, limit, 0, user.role))
        await _collect(_search_lab_results(db, q, limit, 0, user))
        await _collect(_search_prescriptions(db, q, limit, 0, user))
    elif user.role == "doctor":
        doctor = await _get_doctor_profile(db, user)
        if doctor is not None:
            await _collect(_search_patients(db, q, limit, 0, doctor=doctor))
            await _collect(_search_lab_results(db, q, limit, 0, user, doctor))
            await _collect(_search_prescriptions(db, q, limit, 0, user, doctor))
        await _collect(_search_medicines(medicine_db, q, limit, 0, user.role))
        await _collect(_search_clinics(db, q, limit, 0, user))
    elif user.role == "patient":
        await _collect(_search_records(db, q, limit, 0, user))
        await _collect(_search_lab_results(db, q, limit, 0, user))
        await _collect(_search_prescriptions(db, q, limit, 0, user))
        await _collect(_search_clinics(db, q, limit, 0, user))

    return {"suggestions": suggestions[:limit]}
