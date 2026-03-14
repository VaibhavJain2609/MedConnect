import math
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_admin
from app.models.audit import AuditLog
from app.models.user import User

router = APIRouter(
    prefix="/api/v1/admin/audit",
    tags=["admin-audit"],
    dependencies=[Depends(require_admin)],
)


@router.get("")
async def list_audit_logs(
    table_name: Optional[str] = Query(None),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    changed_by_name: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(AuditLog, User.full_name.label("changed_by_name"))
        .outerjoin(User, AuditLog.changed_by == User.id)
    )

    if table_name and table_name != "all":
        stmt = stmt.where(AuditLog.table_name == table_name)
    if from_date:
        stmt = stmt.where(AuditLog.changed_at >= from_date)
    if to_date:
        stmt = stmt.where(AuditLog.changed_at <= to_date)
    if changed_by_name:
        stmt = stmt.where(User.full_name.ilike(f"%{changed_by_name}%"))

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
