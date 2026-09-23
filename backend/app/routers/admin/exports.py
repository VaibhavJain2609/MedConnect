"""Admin CSV export endpoints.

All endpoints are admin-only and stream a text/csv attachment. Exports are
capped at _EXPORT_MAX_ROWS and each download is recorded in audit_logs with
action="EXPORT" (AuditLog.action is String(10)).
"""

import csv
import io
import json
import uuid as _uuid_mod
from datetime import date, datetime, timezone
from typing import Iterable, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import String, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from app.database import get_db, get_medicine_db
from app.dependencies import require_admin
from app.models.appointment import Appointment
from app.models.audit import AuditLog
from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.medicine import Brand, BrandComposition, BrandPackaging, SaltStrength
from app.models.patient_link import PatientClinicLink
from app.models.user import User

router = APIRouter(
    prefix="/api/v1/admin/export",
    tags=["admin-export"],
    dependencies=[Depends(require_admin)],
)

# Dedicated routers so the list-mirroring exports live at the same prefix
# as the admin list endpoints they back (same convention as
# audit.py's audit_logs_router for /api/v1/admin/audit-logs/export).
patients_export_router = APIRouter(
    prefix="/api/v1/admin/patients",
    tags=["admin-export"],
    dependencies=[Depends(require_admin)],
)
appointments_export_router = APIRouter(
    prefix="/api/v1/admin/appointments",
    tags=["admin-export"],
    dependencies=[Depends(require_admin)],
)

# Safety cap for CSV exports.
_EXPORT_MAX_ROWS = 10_000

# Safety cap for the list-mirroring exports — matches the audit-logs
# export cap in routers/admin/audit.py.
_LIST_EXPORT_MAX_ROWS = 50_000


def _csv_response(filename: str, header: list[str], rows: Iterable[list]) -> StreamingResponse:
    """Render header + rows with the csv module (handles escaping) and stream
    the buffer as a text/csv attachment."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    for row in rows:
        writer.writerow(["" if v is None else v for v in row])
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _json_cell(value) -> str:
    if value is None:
        return ""
    try:
        return json.dumps(value, default=str)
    except (TypeError, ValueError):
        return str(value)


async def _log_export(db: AsyncSession, entity: str, filters: dict, row_count: int) -> None:
    """Audit-trail entry for a collection-level export (NIL record id)."""
    from app.services.audit_service import NIL_ENTITY_ID, log_change

    await log_change(
        db=db,
        table_name=entity,
        record_id=NIL_ENTITY_ID,
        action="EXPORT",
        old_values=None,
        new_values={
            "filters": {k: str(v) for k, v in filters.items() if v is not None},
            "row_count": row_count,
        },
    )
    await db.commit()


def _export_filename(name: str) -> str:
    return f"{name}-export-{date.today().isoformat()}.csv"


@router.get("/users")
async def export_users(
    role: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Export users as CSV. Filters: role, is_active."""
    stmt = select(User).where(User.deleted_at.is_(None))
    if role and role != "all":
        stmt = stmt.where(User.role == role)
    if is_active is not None:
        stmt = stmt.where(User.is_active.is_(is_active))
    stmt = stmt.order_by(User.created_at.desc()).limit(_EXPORT_MAX_ROWS)

    result = await db.execute(stmt)
    users = result.scalars().all()

    rows = [
        [
            str(u.id),
            u.full_name,
            u.email,
            u.phone,
            u.role,
            u.is_active,
            u.created_at.isoformat() if u.created_at else "",
        ]
        for u in users
    ]

    await _log_export(
        db, "users", {"role": role, "is_active": is_active}, len(rows)
    )
    return _csv_response(
        _export_filename("users"),
        ["id", "full_name", "email", "phone", "role", "is_active", "created_at"],
        rows,
    )


@router.get("/patients")
async def export_patients(
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Export patient users as CSV (users export restricted to role=patient)."""
    stmt = (
        select(User)
        .where(User.deleted_at.is_(None), User.role == "patient")
    )
    if is_active is not None:
        stmt = stmt.where(User.is_active.is_(is_active))
    stmt = stmt.order_by(User.created_at.desc()).limit(_EXPORT_MAX_ROWS)

    result = await db.execute(stmt)
    patients = result.scalars().all()

    rows = [
        [
            str(u.id),
            u.full_name,
            u.email,
            u.phone,
            u.role,
            u.is_active,
            u.created_at.isoformat() if u.created_at else "",
        ]
        for u in patients
    ]

    await _log_export(db, "users", {"role": "patient", "is_active": is_active}, len(rows))
    return _csv_response(
        _export_filename("patients"),
        ["id", "full_name", "email", "phone", "role", "is_active", "created_at"],
        rows,
    )


@router.get("/audit-logs")
async def export_audit_logs(
    table_name: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Export audit logs as CSV. Filters: table_name, action, date_from, date_to."""
    stmt = select(AuditLog)
    if table_name and table_name != "all":
        stmt = stmt.where(AuditLog.table_name == table_name)
    if action and action != "all":
        stmt = stmt.where(AuditLog.action == action)
    if date_from:
        stmt = stmt.where(AuditLog.changed_at >= date_from)
    if date_to:
        stmt = stmt.where(AuditLog.changed_at <= date_to)
    stmt = stmt.order_by(AuditLog.changed_at.desc()).limit(_EXPORT_MAX_ROWS)

    result = await db.execute(stmt)
    logs = result.scalars().all()

    rows = [
        [
            str(log.id),
            log.table_name,
            str(log.record_id),
            log.action,
            str(log.changed_by) if log.changed_by else "",
            log.changed_at.isoformat() if log.changed_at else "",
            _json_cell(log.old_values),
            _json_cell(log.new_values),
        ]
        for log in logs
    ]

    await _log_export(
        db,
        "audit_logs",
        {"table_name": table_name, "action": action, "date_from": date_from, "date_to": date_to},
        len(rows),
    )
    return _csv_response(
        _export_filename("audit-logs"),
        [
            "id",
            "table_name",
            "record_id",
            "action",
            "changed_by",
            "created_at",
            "old_values",
            "new_values",
        ],
        rows,
    )


@router.get("/appointments")
async def export_appointments(
    status: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Export appointments as CSV. Filters: status, date_from, date_to."""
    PatientUser = aliased(User)
    DoctorUser = aliased(User)

    stmt = (
        select(
            Appointment.id,
            PatientUser.full_name.label("patient_name"),
            DoctorUser.full_name.label("doctor_name"),
            Clinic.name.label("clinic"),
            Appointment.scheduled_at,
            Appointment.status,
            Appointment.type,
        )
        .outerjoin(PatientUser, Appointment.patient_id == PatientUser.id)
        .outerjoin(Doctor, Appointment.doctor_id == Doctor.id)
        .outerjoin(DoctorUser, Doctor.user_id == DoctorUser.id)
        .outerjoin(Clinic, Appointment.clinic_id == Clinic.id)
        .where(Appointment.deleted_at.is_(None))
    )
    if status and status != "all":
        stmt = stmt.where(Appointment.status == status)
    if date_from:
        stmt = stmt.where(Appointment.scheduled_at >= date_from)
    if date_to:
        stmt = stmt.where(Appointment.scheduled_at <= date_to)
    stmt = stmt.order_by(Appointment.scheduled_at.desc()).limit(_EXPORT_MAX_ROWS)

    result = await db.execute(stmt)
    appts = result.all()

    rows = [
        [
            str(r.id),
            r.patient_name,
            r.doctor_name,
            r.clinic,
            r.scheduled_at.isoformat() if r.scheduled_at else "",
            r.status,
            r.type,
        ]
        for r in appts
    ]

    await _log_export(
        db,
        "appointments",
        {"status": status, "date_from": date_from, "date_to": date_to},
        len(rows),
    )
    return _csv_response(
        _export_filename("appointments"),
        ["id", "patient_name", "doctor_name", "clinic", "scheduled_at", "status", "type"],
        rows,
    )


@router.get("/medicines")
async def export_medicines(
    db: AsyncSession = Depends(get_db),
    medicine_db: AsyncSession = Depends(get_medicine_db),
):
    """Export the medicine catalog (brands) as CSV from the medicine DB."""
    stmt = (
        select(Brand)
        .options(
            selectinload(Brand.manufacturer),
            selectinload(Brand.compositions)
            .selectinload(BrandComposition.salt_strength)
            .selectinload(SaltStrength.salt),
            selectinload(Brand.packaging).selectinload(BrandPackaging.pack_form),
        )
        .order_by(Brand.brand_name)
        .limit(_EXPORT_MAX_ROWS)
    )

    result = await medicine_db.execute(stmt)
    brands = result.scalars().all()

    rows = []
    for brand in brands:
        schedules = {
            bc.salt_strength.salt.schedule
            for bc in brand.compositions
            if bc.salt_strength and bc.salt_strength.salt and bc.salt_strength.salt.schedule
        }
        dosage_forms = {
            pack.pack_form.form_name
            for pack in brand.packaging
            if pack.pack_form
        }
        rows.append([
            brand.brand_name,
            brand.manufacturer.manufacturer_name if brand.manufacturer else "",
            brand.salt_composition,
            "; ".join(sorted(schedules)),
            "; ".join(sorted(dosage_forms)),
        ])

    # Audit entry lives in the main DB (audit_logs table), not the medicine DB.
    await _log_export(db, "brands", {}, len(rows))
    return _csv_response(
        _export_filename("medicines"),
        ["brand_name", "manufacturer", "salt_composition", "schedule", "dosage_form"],
        rows,
    )


# ---------------------------------------------------------------------------
# List-mirroring exports — same path prefix + filters as the admin list
# endpoints they back, so the portal "Export CSV" buttons export exactly
# what the admin sees. Capped at _LIST_EXPORT_MAX_ROWS (50k, same as the
# audit-logs export) and each download writes an EXPORT audit row.
# ---------------------------------------------------------------------------

# The /admin/patients page renders Patient.status as is_active→"completed"
# (Active) / !is_active→"pending" (Inactive). Its status dropdown sends
# those frontend status values, so the export maps them back onto
# is_active; anything else is ignored (same as the list endpoint, which
# does not declare a `status` param).
_PATIENT_STATUS_TO_IS_ACTIVE = {"completed": True, "pending": False}


@patients_export_router.get("/export")
async def export_admin_patients(
    search: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    is_active: Optional[bool] = Query(None),
    clinic_id: Optional[str] = Query(None),
    consent_status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Export the admin patient list as CSV.

    Mirrors the filters of GET /api/v1/admin/users?role=patient (the list
    backing the /admin/patients page): ``search`` matches full_name /
    email / phone, ``is_active`` filters account state, and ``clinic_id``
    scopes to patients linked to that clinic via patient_clinic_links
    (optionally narrowed by ``consent_status``). ``status`` accepts the
    page's frontend status values (completed→active, pending→inactive).
    Columns match what the admin list shows — no PHI.
    """
    stmt = select(User).where(User.deleted_at.is_(None), User.role == "patient")

    if clinic_id:
        try:
            _uuid_mod.UUID(clinic_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "INVALID_CLINIC_ID",
                        "message": "clinic_id must be a valid UUID",
                    }
                },
            )
        stmt = stmt.join(
            PatientClinicLink,
            (PatientClinicLink.patient_id == User.id)
            & (PatientClinicLink.clinic_id == clinic_id)
            & (PatientClinicLink.deleted_at.is_(None)),
        )
        if consent_status:
            stmt = stmt.where(PatientClinicLink.consent_status == consent_status)

    if search:
        stmt = stmt.where(
            User.full_name.ilike(f"%{search}%")
            | User.email.ilike(f"%{search}%")
            | User.phone.ilike(f"%{search}%")
        )

    effective_is_active = is_active
    if effective_is_active is None and status_filter:
        effective_is_active = _PATIENT_STATUS_TO_IS_ACTIVE.get(status_filter)
    if effective_is_active is not None:
        stmt = stmt.where(User.is_active.is_(effective_is_active))

    stmt = stmt.order_by(User.created_at.desc()).limit(_LIST_EXPORT_MAX_ROWS)
    result = await db.execute(stmt)
    patients = result.scalars().all()

    # Clinic-link counts in one grouped query (avoids N+1).
    patient_ids = [u.id for u in patients]
    link_counts: dict = {}
    if patient_ids:
        count_rows = await db.execute(
            select(PatientClinicLink.patient_id, func.count())
            .where(
                PatientClinicLink.deleted_at.is_(None),
                PatientClinicLink.patient_id.in_(patient_ids),
            )
            .group_by(PatientClinicLink.patient_id)
        )
        link_counts = {row[0]: row[1] for row in count_rows.all()}

    rows = [
        [
            str(u.id),
            u.full_name,
            u.email,
            u.phone,
            u.created_at.date().isoformat() if u.created_at else "",
            link_counts.get(u.id, 0),
        ]
        for u in patients
    ]

    await _log_export(
        db,
        "users",
        {
            "role": "patient",
            "search": search,
            "status": status_filter,
            "is_active": effective_is_active,
            "clinic_id": clinic_id,
            "consent_status": consent_status,
        },
        len(rows),
    )
    return _csv_response(
        _export_filename("patients"),
        ["id", "name", "email", "phone", "joined_date", "clinic_links_count"],
        rows,
    )


def _parse_export_day(value: str, param: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_DATE",
                    "message": f"{param} must be YYYY-MM-DD",
                }
            },
        )


@appointments_export_router.get("/export")
async def export_admin_appointments(
    status_filter: Optional[str] = Query(None, alias="status"),
    date_param: Optional[str] = Query(None, alias="date"),
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    clinic_id: Optional[str] = Query(None),
    clinic: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Export the admin appointments list as CSV.

    Backs the /admin/appointments page, which lists every appointment
    (GET /api/v1/appointments?all=true). Honors that page's filters:
    ``status``; ``date`` (single day) or ``from``/``to`` (inclusive
    YYYY-MM-DD bounds on scheduled_at, applied independently); ``clinic``
    (clinic name, exact match — the page's dropdown) or ``clinic_id``;
    and ``search`` matching patient name, doctor name, or appointment id.
    """
    PatientUser = aliased(User)
    DoctorUser = aliased(User)

    stmt = (
        select(
            Appointment.id,
            PatientUser.full_name.label("patient_name"),
            DoctorUser.full_name.label("doctor_name"),
            Clinic.name.label("clinic"),
            Appointment.scheduled_at,
            Appointment.status,
        )
        .outerjoin(PatientUser, Appointment.patient_id == PatientUser.id)
        .outerjoin(Doctor, Appointment.doctor_id == Doctor.id)
        .outerjoin(DoctorUser, Doctor.user_id == DoctorUser.id)
        .outerjoin(Clinic, Appointment.clinic_id == Clinic.id)
        .where(Appointment.deleted_at.is_(None))
    )

    if status_filter and status_filter != "all":
        stmt = stmt.where(Appointment.status == status_filter)

    if date_param:
        target = _parse_export_day(date_param, "date")
        day_start = datetime(target.year, target.month, target.day, tzinfo=timezone.utc)
        day_end = day_start.replace(hour=23, minute=59, second=59, microsecond=999999)
        stmt = stmt.where(
            Appointment.scheduled_at >= day_start,
            Appointment.scheduled_at <= day_end,
        )
    else:
        range_start = _parse_export_day(date_from, "from") if date_from else None
        range_end = _parse_export_day(date_to, "to") if date_to else None
        if range_start and range_end and range_start > range_end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "INVALID_DATE_RANGE",
                        "message": "from must be on or before to",
                    }
                },
            )
        if range_start:
            stmt = stmt.where(
                Appointment.scheduled_at
                >= datetime(range_start.year, range_start.month, range_start.day, tzinfo=timezone.utc)
            )
        if range_end:
            stmt = stmt.where(
                Appointment.scheduled_at
                <= datetime(
                    range_end.year, range_end.month, range_end.day,
                    23, 59, 59, 999999, tzinfo=timezone.utc,
                )
            )

    if clinic_id:
        try:
            _uuid_mod.UUID(clinic_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "INVALID_CLINIC_ID",
                        "message": "clinic_id must be a valid UUID",
                    }
                },
            )
        stmt = stmt.where(Appointment.clinic_id == clinic_id)
    if clinic:
        stmt = stmt.where(Clinic.name == clinic)

    if search:
        stmt = stmt.where(
            PatientUser.full_name.ilike(f"%{search}%")
            | DoctorUser.full_name.ilike(f"%{search}%")
            | cast(Appointment.id, String).ilike(f"%{search}%")
        )

    stmt = stmt.order_by(Appointment.scheduled_at.desc()).limit(_LIST_EXPORT_MAX_ROWS)
    result = await db.execute(stmt)
    appts = result.all()

    rows = [
        [
            str(r.id),
            r.patient_name,
            r.doctor_name,
            r.clinic,
            r.scheduled_at.isoformat() if r.scheduled_at else "",
            r.status,
        ]
        for r in appts
    ]

    await _log_export(
        db,
        "appointments",
        {
            "status": status_filter,
            "date": date_param,
            "from": date_from,
            "to": date_to,
            "clinic_id": clinic_id,
            "clinic": clinic,
            "search": search,
        },
        len(rows),
    )
    return _csv_response(
        _export_filename("appointments"),
        ["id", "patient_name", "doctor_name", "clinic", "scheduled_at", "status"],
        rows,
    )
