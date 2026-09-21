"""Admin CSV export endpoints.

All endpoints are admin-only and stream a text/csv attachment. Exports are
capped at _EXPORT_MAX_ROWS and each download is recorded in audit_logs with
action="EXPORT" (AuditLog.action is String(10)).
"""

import csv
import io
import json
from datetime import date, datetime
from typing import Iterable, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from app.database import get_db, get_medicine_db
from app.dependencies import require_admin
from app.models.appointment import Appointment
from app.models.audit import AuditLog
from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.medicine import Brand, BrandComposition, BrandPackaging, SaltStrength
from app.models.user import User

router = APIRouter(
    prefix="/api/v1/admin/export",
    tags=["admin-export"],
    dependencies=[Depends(require_admin)],
)

# Safety cap for CSV exports.
_EXPORT_MAX_ROWS = 10_000


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
