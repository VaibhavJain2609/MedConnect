import csv
import io
import json
import math
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import String, cast, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_admin
from app.models.audit import AuditLog
from app.models.user import User
from app.services.audit_service import NIL_ENTITY_ID, log_change

router = APIRouter(
    prefix="/api/v1/admin/audit",
    tags=["admin-audit"],
    dependencies=[Depends(require_admin)],
)

# Separate router so the export lives at /api/v1/admin/reports/export —
# the path the frontend's exportReport() helper already calls.
reports_router = APIRouter(
    prefix="/api/v1/admin/reports",
    tags=["admin-reports"],
    dependencies=[Depends(require_admin)],
)

# Dedicated router for GET /api/v1/admin/audit-logs/export — the download
# endpoint the audit-logs page's "Export CSV" button calls.
audit_logs_router = APIRouter(
    prefix="/api/v1/admin/audit-logs",
    tags=["admin-audit"],
    dependencies=[Depends(require_admin)],
)

# Safety cap for CSV exports.
_EXPORT_MAX_ROWS = 50_000

# Max length of a serialized old_values/new_values CSV cell.
_JSON_CELL_MAX = 500


def _audit_filters(
    stmt,
    table_name: Optional[str],
    record_id: Optional[str],
    from_date: Optional[datetime],
    to_date: Optional[datetime],
    changed_by_name: Optional[str],
    user_id: Optional[uuid.UUID] = None,
):
    """Apply the shared audit-log filters to a select(AuditLog, changed_by_name) stmt."""
    if table_name and table_name != "all":
        stmt = stmt.where(AuditLog.table_name == table_name)
    if record_id:
        # record_id is a UUID column — cast to text for substring matching.
        stmt = stmt.where(
            cast(AuditLog.record_id, String).ilike(f"%{record_id}%")
        )
    if from_date:
        stmt = stmt.where(AuditLog.changed_at >= from_date)
    if to_date:
        stmt = stmt.where(AuditLog.changed_at <= to_date)
    if changed_by_name:
        stmt = stmt.where(User.full_name.ilike(f"%{changed_by_name}%"))
    if user_id:
        # Actor filter — rows where this user made the change.
        stmt = stmt.where(AuditLog.changed_by == user_id)
    return stmt


def _audit_base_query():
    return (
        select(AuditLog, User.full_name.label("changed_by_name"))
        .outerjoin(User, AuditLog.changed_by == User.id)
    )


@router.get("")
async def list_audit_logs(
    table_name: Optional[str] = Query(None),
    record_id: Optional[str] = Query(None),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    changed_by_name: Optional[str] = Query(None),
    user_id: Optional[uuid.UUID] = Query(
        None, description="Filter to changes made by this user (audit_logs.changed_by)"
    ),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = _audit_filters(
        _audit_base_query(), table_name, record_id, from_date, to_date,
        changed_by_name, user_id,
    )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = await db.scalar(count_stmt) or 0

    stmt = stmt.order_by(AuditLog.changed_at.desc()).offset((page - 1) * limit).limit(limit)
    result = await db.execute(stmt)
    rows = result.all()

    data = []
    for row in rows:
        log: AuditLog = row[0]
        changer_name: str | None = row[1]

        # Extract a short summary from new_values or old_values
        changes_summary = None
        if log.new_values:
            skip_keys = {"id", "created_at", "updated_at", "deleted_at"}
            preview = {k: v for k, v in log.new_values.items() if k not in skip_keys}
            # Take the first 2 items for display
            preview_items = list(preview.items())[:2]
            changes_summary = ", ".join(f"{k}: {v}" for k, v in preview_items)

        data.append({
            "id": str(log.id),
            "table_name": log.table_name,
            "record_id": str(log.record_id),
            "record_id_short": str(log.record_id)[:8],
            "action": log.action,
            "changed_by": str(log.changed_by) if log.changed_by else None,
            "changed_by_name": changer_name,
            "changed_at": log.changed_at.isoformat(),
            "old_values": log.old_values,
            "new_values": log.new_values,
            "changes_summary": changes_summary,
        })

    return {
        "data": data,
        "total": total,
        "page": page,
        "limit": limit,
        "totalPages": math.ceil(total / limit) if total else 0,
    }


@reports_router.get("/export")
async def export_report(
    type: str = Query("audit", description="Report type (only 'audit' supported)"),
    format: str = Query("csv", description="Export format (only 'csv' supported)"),
    table_name: Optional[str] = Query(None),
    record_id: Optional[str] = Query(None),
    changed_by_name: Optional[str] = Query(None),
    user_id: Optional[uuid.UUID] = Query(None),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Export audit logs as CSV (StreamingResponse, text/csv).

    Called by the frontend exportReport() helper which sends
    format=csv&start_date=...&end_date=... .
    """
    if type != "audit":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "UNSUPPORTED_REPORT_TYPE",
                              "message": "Only type=audit is supported"}},
        )
    if format != "csv":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "UNSUPPORTED_FORMAT",
                              "message": "Only format=csv is supported"}},
        )

    effective_from = from_date or start_date
    effective_to = to_date or end_date

    stmt = _audit_filters(
        _audit_base_query(),
        table_name,
        record_id,
        effective_from,
        effective_to,
        changed_by_name,
        user_id,
    ).order_by(AuditLog.changed_at.desc()).limit(_EXPORT_MAX_ROWS)

    result = await db.execute(stmt)
    rows = result.all()

    header = [
        "changed_at",
        "action",
        "table_name",
        "record_id",
        "changed_by_name",
        "old_values",
        "new_values",
    ]

    def _generate():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(header)
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)
        for row in rows:
            log: AuditLog = row[0]
            changer_name: str | None = row[1]
            writer.writerow([
                log.changed_at.isoformat() if log.changed_at else "",
                log.action,
                log.table_name,
                str(log.record_id),
                changer_name or "System",
                _json_cell(log.old_values),
                _json_cell(log.new_values),
            ])
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)

    filename = f"audit-export-{datetime.now(timezone.utc).date().isoformat()}.csv"
    return StreamingResponse(
        _generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _json_cell(value) -> str:
    """Serialize old/new values to a compact JSON cell, truncated at ~500 chars."""
    if value is None:
        return ""
    try:
        s = json.dumps(value, separators=(",", ":"), default=str)
    except (TypeError, ValueError):
        s = str(value)
    if len(s) > _JSON_CELL_MAX:
        return s[:_JSON_CELL_MAX] + "…"
    return s


_AUDIT_EXPORT_HEADER = [
    "timestamp",
    "actor_id",
    "actor_name",
    "action",
    "table_name",
    "record_id",
    "old_values",
    "new_values",
]


@audit_logs_router.get("/export")
async def export_audit_logs(
    table_name: Optional[str] = Query(None),
    record_id: Optional[str] = Query(None),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    changed_by_name: Optional[str] = Query(None),
    user_id: Optional[uuid.UUID] = Query(
        None, description="Filter to changes made by this user (audit_logs.changed_by)"
    ),
    db: AsyncSession = Depends(get_db),
):
    """Export audit logs as CSV (text/csv attachment).

    Honors the same filters as GET /api/v1/admin/audit — table_name,
    record_id, from_date, to_date, changed_by_name, user_id — via the
    shared _audit_filters query builder. Newest first, capped at
    _EXPORT_MAX_ROWS (50k). The AuditLog model stores no ip/request_id
    columns, so they are not exported (request metadata lives inside
    new_values for READ/EXPORT rows and is exported with it).
    """
    stmt = _audit_filters(
        _audit_base_query(),
        table_name,
        record_id,
        from_date,
        to_date,
        changed_by_name,
        user_id,
    ).order_by(AuditLog.changed_at.desc()).limit(_EXPORT_MAX_ROWS)

    result = await db.execute(stmt)
    rows = result.all()

    # 50k rows buffered is fine — no need to stream per-row.
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(_AUDIT_EXPORT_HEADER)
    for row in rows:
        log: AuditLog = row[0]
        changer_name: str | None = row[1]
        writer.writerow([
            log.changed_at.isoformat() if log.changed_at else "",
            str(log.changed_by) if log.changed_by else "",
            changer_name or "System",
            log.action,
            log.table_name,
            str(log.record_id),
            _json_cell(log.old_values),
            _json_cell(log.new_values),
        ])

    # Record the download itself (same convention as routers/admin/exports.py).
    await log_change(
        db=db,
        table_name="audit_logs",
        record_id=NIL_ENTITY_ID,
        action="EXPORT",
        old_values=None,
        new_values={
            "filters": {
                k: str(v)
                for k, v in {
                    "table_name": table_name,
                    "record_id": record_id,
                    "from_date": from_date,
                    "to_date": to_date,
                    "changed_by_name": changed_by_name,
                    "user_id": user_id,
                }.items()
                if v is not None
            },
            "row_count": len(rows),
        },
    )
    await db.commit()

    filename = f"audit-logs-{datetime.now(timezone.utc).date().isoformat()}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
