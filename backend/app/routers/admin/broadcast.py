import math
import uuid
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_admin
from app.models.audit import AuditLog
from app.models.notification import NotificationType
from app.models.platform_setting import PlatformSetting
from app.models.user import User
from app.services.notification_service import create_notifications_bulk

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin-broadcast"],
    dependencies=[Depends(require_admin)],
)

# ---------------------------------------------------------------------------
# Announcement broadcasts
# ---------------------------------------------------------------------------

# Marker written into each notification row's `meta` and into the audit log
# entry so past broadcasts can be listed without a dedicated table.
BROADCAST_AUDIT_KIND = "broadcast"


class BroadcastRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1, max_length=5000)
    target_role: Literal["all", "patient", "doctor", "admin"] = "all"
    action_url: Optional[str] = Field(default=None, max_length=512)


@router.post("/notifications/broadcast", status_code=status.HTTP_201_CREATED)
async def send_broadcast(
    payload: BroadcastRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Send an announcement notification to all matching active users."""
    stmt = select(User.id).where(
        User.deleted_at.is_(None),
        User.is_active.is_(True),
    )
    if payload.target_role != "all":
        stmt = stmt.where(User.role == payload.target_role)
    user_ids = (await db.execute(stmt)).scalars().all()

    broadcast_id = uuid.uuid4()
    meta = {
        "broadcast": True,
        "broadcast_id": str(broadcast_id),
        "target_role": payload.target_role,
    }
    recipient_count = await create_notifications_bulk(
        db,
        user_ids,
        NotificationType.SYSTEM.value,
        payload.title,
        payload.body,
        action_url=payload.action_url,
        metadata=meta,
    )

    # Persist the broadcast as an audit_logs entry — the broadcasts list is
    # derived from these rows (new_values carries the full payload).
    db.add(
        AuditLog(
            id=uuid.uuid4(),
            table_name="notifications",
            record_id=broadcast_id,
            action="INSERT",
            changed_by=admin.id,
            new_values={
                "kind": BROADCAST_AUDIT_KIND,
                "broadcast_id": str(broadcast_id),
                "title": payload.title,
                "body": payload.body,
                "target_role": payload.target_role,
                "action_url": payload.action_url,
                "recipient_count": recipient_count,
            },
        )
    )

    return {
        "broadcast_id": str(broadcast_id),
        "title": payload.title,
        "target_role": payload.target_role,
        "recipient_count": recipient_count,
    }


@router.get("/notifications/broadcasts")
async def list_broadcasts(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List past announcement broadcasts (derived from broadcast audit rows)."""
    stmt = (
        select(AuditLog, User.full_name.label("sent_by_name"))
        .outerjoin(User, AuditLog.changed_by == User.id)
        .where(
            AuditLog.table_name == "notifications",
            AuditLog.action == "INSERT",
            AuditLog.new_values["kind"].astext == BROADCAST_AUDIT_KIND,
        )
    )

    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    stmt = stmt.order_by(AuditLog.changed_at.desc()).offset((page - 1) * limit).limit(limit)
    rows = (await db.execute(stmt)).all()

    data = []
    for log, sent_by_name in rows:
        values = log.new_values or {}
        data.append(
            {
                "id": str(log.id),
                "broadcast_id": values.get("broadcast_id") or str(log.record_id),
                "title": values.get("title"),
                "body": values.get("body"),
                "target_role": values.get("target_role"),
                "action_url": values.get("action_url"),
                "recipient_count": values.get("recipient_count"),
                "sent_by": str(log.changed_by) if log.changed_by else None,
                "sent_by_name": sent_by_name,
                "sent_at": log.changed_at.isoformat(),
            }
        )

    return {
        "data": data,
        "total": total,
        "page": page,
        "limit": limit,
        "totalPages": math.ceil(total / limit) if total else 0,
    }


# ---------------------------------------------------------------------------
# Platform settings / feature flags
# ---------------------------------------------------------------------------

# Known keys and their defaults — also seeded by migration
# 024_platform_settings. GET /settings inserts any missing defaults so the
# keys always exist (e.g. in test DBs built from metadata, no migrations).
DEFAULT_SETTINGS: dict[str, dict[str, Any]] = {
    "maintenance_mode": {
        "value": False,
        "description": "When true, the platform is in maintenance mode for non-admin users",
    },
    "registration_enabled": {
        "value": True,
        "description": "When false, new user registration is disabled",
    },
    "reminder_channels_enabled": {
        "value": {"in_app": True, "email": False, "sms": False, "whatsapp": False},
        "description": "Which channels appointment/notification reminders may use",
    },
    "max_upload_mb": {
        "value": 10,
        "description": "Maximum allowed upload size in megabytes",
    },
}


def _validate_setting_value(key: str, value: Any) -> None:
    """Light type validation for known keys; unknown keys accept any JSON."""
    default = DEFAULT_SETTINGS.get(key)
    if default is None:
        return
    expected = default["value"]
    if isinstance(expected, bool):
        ok = isinstance(value, bool)
    elif isinstance(expected, dict):
        ok = isinstance(value, dict)
    elif isinstance(expected, (int, float)):
        ok = isinstance(value, (int, float)) and not isinstance(value, bool)
    else:
        ok = True
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_SETTING_VALUE",
                    "message": f"Invalid value type for setting '{key}'",
                }
            },
        )
    if key == "max_upload_mb" and isinstance(value, (int, float)) and value <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_SETTING_VALUE",
                    "message": "max_upload_mb must be a positive number",
                }
            },
        )


async def _ensure_default_settings(db: AsyncSession) -> None:
    """Insert any missing default settings keys (idempotent)."""
    for key, spec in DEFAULT_SETTINGS.items():
        stmt = (
            pg_insert(PlatformSetting)
            .values(
                id=uuid.uuid4(),
                key=key,
                value=spec["value"],
                description=spec["description"],
            )
            .on_conflict_do_nothing(index_elements=["key"])
        )
        await db.execute(stmt)
    await db.flush()


class PlatformSettingsUpdate(BaseModel):
    """Accepts either a single {key, value, description?} update or a bulk
    {settings: {key: value, ...}} payload."""

    key: Optional[str] = Field(default=None, max_length=100)
    value: Any = None
    description: Optional[str] = Field(default=None, max_length=500)
    settings: Optional[dict[str, Any]] = None

    @model_validator(mode="after")
    def _check_payload(self):
        if not self.settings and self.key is None:
            raise ValueError("Provide either {key, value} or {settings: {...}}")
        return self


def _serialize_setting(row: PlatformSetting) -> dict:
    return {
        "key": row.key,
        "value": row.value,
        "description": row.description,
        "updated_by": str(row.updated_by) if row.updated_by else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.get("/settings")
async def get_settings(db: AsyncSession = Depends(get_db)):
    """Return all platform settings, seeding any missing defaults first."""
    await _ensure_default_settings(db)
    rows = (
        (await db.execute(select(PlatformSetting).order_by(PlatformSetting.key)))
        .scalars()
        .all()
    )
    return {"data": [_serialize_setting(r) for r in rows]}


@router.put("/settings")
async def update_settings(
    payload: PlatformSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Upsert platform settings — single {key, value} or bulk {settings}."""
    updates: dict[str, Any] = dict(payload.settings or {})
    if payload.key is not None:
        updates[payload.key] = payload.value

    for key, value in updates.items():
        if not key or len(key) > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "INVALID_SETTING_KEY",
                        "message": "Setting keys must be 1-100 characters",
                    }
                },
            )
        if value is None:
            # JSONB column is NOT NULL and a bound None would be SQL NULL,
            # not JSON 'null' — reject it outright.
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "INVALID_SETTING_VALUE",
                        "message": f"Setting '{key}' cannot be null",
                    }
                },
            )
        _validate_setting_value(key, value)
        existing = (
            await db.execute(
                select(PlatformSetting).where(PlatformSetting.key == key)
            )
        ).scalar_one_or_none()
        stmt = (
            pg_insert(PlatformSetting)
            .values(
                id=uuid.uuid4(),
                key=key,
                value=value,
                updated_by=admin.id,
            )
            .on_conflict_do_update(
                index_elements=["key"],
                set_={
                    "value": value,
                    "updated_by": admin.id,
                    "updated_at": func.now(),
                },
            )
        )
        await db.execute(stmt)
        from app.services.audit_service import log_change
        await log_change(
            db=db,
            table_name="platform_settings",
            record_id=(existing.id if existing else uuid.uuid5(uuid.NAMESPACE_URL, f"platform-setting:{key}")),
            action="UPDATE" if existing else "INSERT",
            old_values={"value": existing.value} if existing else None,
            new_values={"value": value, "updated_by": str(admin.id)},
        )

    # Optional description update applies to the single-key form only.
    if payload.key is not None and payload.description is not None:
        row = (
            await db.execute(
                select(PlatformSetting).where(PlatformSetting.key == payload.key)
            )
        ).scalar_one_or_none()
        if row is not None:
            row.description = payload.description

    await db.flush()

    rows = (
        (await db.execute(select(PlatformSetting).order_by(PlatformSetting.key)))
        .scalars()
        .all()
    )
    return {"data": [_serialize_setting(r) for r in rows]}
