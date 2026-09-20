"""Global search endpoints — role-aware.

GET /api/v1/search             — search across entities visible to the caller's role
GET /api/v1/search/suggestions — lightweight autocomplete suggestions

Visibility rules:
  admin   → patients, doctors, clinics, appointments, medicines
  doctor  → own patients (records they authored or approved clinic links),
            own appointments, medicines
  patient → own medical records

Response shape matches frontend/src/lib/api/search.ts:
  {results: [{id, type, title, subtitle?, photo?, url?, metadata?}],
   total, query, took_ms}
"""
import time

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select, union
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, get_medicine_db
from app.dependencies import get_current_user
from app.models.appointment import Appointment
from app.models.clinic import Clinic, ClinicMembership
from app.models.doctor import Doctor
from app.models.medical_record import MedicalRecord
from app.models.medicine.commercial import Brand, Manufacturer
from app.models.medicine.salts import Salt
from app.models.patient_link import PatientClinicLink
from app.models.user import User

router = APIRouter(prefix="/api/v1/search", tags=["search"])

VALID_TYPES = {"patient", "doctor", "clinic", "appointment", "medicine", "record"}


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
        # Visible patients = patients with records authored by this doctor OR
        # patients with an approved link to a clinic the doctor belongs to.
        records_subq = (
            select(User.id.label("id"))
            .join(MedicalRecord, MedicalRecord.patient_id == User.id)
            .where(
                MedicalRecord.doctor_id == doctor.id,
                MedicalRecord.deleted_at.is_(None),
            )
        )
        clinic_subq = (
            select(User.id.label("id"))
            .join(PatientClinicLink, PatientClinicLink.patient_id == User.id)
            .join(
                ClinicMembership,
                ClinicMembership.clinic_id == PatientClinicLink.clinic_id,
            )
            .where(
                ClinicMembership.user_id == doctor.user_id,
                ClinicMembership.is_active.is_(True),
                ClinicMembership.deleted_at.is_(None),
                PatientClinicLink.consent_status == "approved",
                PatientClinicLink.deleted_at.is_(None),
            )
        )
        visible = union(records_subq, clinic_subq).subquery()
        stmt = (
            select(User)
            .join(visible, visible.c.id == User.id)
            .where(User.deleted_at.is_(None), User.role == "patient", match)
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
    db: AsyncSession, q: str, limit: int, offset: int
) -> tuple[list[dict], int]:
    """Clinics matching q (admin view)."""
    term = f"%{q}%"
    stmt = select(Clinic).where(
        Clinic.deleted_at.is_(None),
        or_(
            Clinic.name.ilike(term),
            Clinic.city.ilike(term),
            Clinic.address.ilike(term),
        ),
    )
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
            "url": f"/admin/clinics/{c.id}",
            "metadata": {"city": c.city, "is_active": c.is_active},
        }
        for c in clinics
    ]
    return results, total


async def _search_appointments(
    db: AsyncSession, q: str, limit: int, offset: int, doctor: Doctor | None
) -> tuple[list[dict], int]:
    """Appointments matching q by complaint/notes/patient name.
    Doctors are restricted to their own appointments."""
    term = f"%{q}%"
    stmt = (
        select(Appointment, User.full_name.label("patient_name"))
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

    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    result = await db.execute(
        stmt.order_by(Appointment.scheduled_at.desc()).offset(offset).limit(limit)
    )
    rows = result.all()

    url = "/doctor/appointments" if doctor is not None else "/admin/appointments"
    results = [
        {
            "id": str(a.id),
            "type": "appointment",
            "title": f"{patient_name} — {a.type}",
            "subtitle": (
                f"{a.scheduled_at.isoformat()} · {a.status}"
                + (f" · {a.chief_complaint}" if a.chief_complaint else "")
            ),
            "url": url,
            "metadata": {
                "status": a.status,
                "scheduled_at": a.scheduled_at.isoformat(),
                "patient_name": patient_name,
            },
        }
        for a, patient_name in rows
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


async def _search_records(
    db: AsyncSession, q: str, limit: int, offset: int, user: User
) -> tuple[list[dict], int]:
    """A patient's own medical records matching q."""
    term = f"%{q}%"
    stmt = select(MedicalRecord).where(
        MedicalRecord.patient_id == user.id,
        MedicalRecord.deleted_at.is_(None),
        or_(
            MedicalRecord.title.ilike(term),
            MedicalRecord.description.ilike(term),
            MedicalRecord.record_type.ilike(term),
        ),
    )
    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    result = await db.execute(
        stmt.order_by(MedicalRecord.created_at.desc()).offset(offset).limit(limit)
    )
    records = result.scalars().all()

    results = [
        {
            "id": str(r.id),
            "type": "record",
            "title": r.title,
            "subtitle": f"{r.record_type} · {r.created_at.date().isoformat()}",
            "url": f"/patient/records/{r.id}",
            "metadata": {"record_type": r.record_type, "source": r.source},
        }
        for r in records
    ]
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
        description="Entity filter: patient|doctor|clinic|appointment|medicine|record",
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
            await _collect(_search_clinics(db, q, limit, offset))
        if wanted in (None, "appointment"):
            await _collect(_search_appointments(db, q, limit, offset, doctor=None))
        if wanted in (None, "medicine"):
            await _collect(_search_medicines(medicine_db, q, limit, offset, user.role))
    elif user.role == "doctor":
        doctor = await _get_doctor_profile(db, user)
        if wanted in (None, "patient") and doctor is not None:
            await _collect(_search_patients(db, q, limit, offset, doctor=doctor))
        if wanted in (None, "appointment") and doctor is not None:
            await _collect(_search_appointments(db, q, limit, offset, doctor=doctor))
        if wanted in (None, "medicine"):
            await _collect(_search_medicines(medicine_db, q, limit, offset, user.role))
    else:
        # patient — own records only
        if wanted in (None, "record"):
            await _collect(_search_records(db, q, limit, offset, user))

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
        await _collect(_search_clinics(db, q, limit, 0))
        await _collect(_search_medicines(medicine_db, q, limit, 0, user.role))
    elif user.role == "doctor":
        doctor = await _get_doctor_profile(db, user)
        if doctor is not None:
            await _collect(_search_patients(db, q, limit, 0, doctor=doctor))
        await _collect(_search_medicines(medicine_db, q, limit, 0, user.role))
    else:
        await _collect(_search_records(db, q, limit, 0, user))

    return {"suggestions": suggestions[:limit]}
