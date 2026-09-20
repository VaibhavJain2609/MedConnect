from contextvars import ContextVar
from typing import Any
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

_current_user_id: ContextVar[uuid.UUID | None] = ContextVar("current_user_id", default=None)


def set_audit_user(user_id: uuid.UUID | None) -> None:
    _current_user_id.set(user_id)


def get_audit_user() -> uuid.UUID | None:
    return _current_user_id.get()


ACTION_READ = "READ"

# audit_logs.record_id is NOT NULL, so collection-level reads (list/search
# endpoints with no single entity id) use this all-zero sentinel.
NIL_ENTITY_ID = uuid.UUID(int=0)


async def log_read(
    db: AsyncSession,
    entity_type: str,
    entity_id: uuid.UUID | None = None,
    *,
    changed_by: uuid.UUID | None = None,
    method: str = "GET",
    path: str,
    status_code: int = 200,
    ip_address: str | None = None,
    request_id: str | None = None,
) -> None:
    """Record a PHI read/access event in audit_logs.

    Reuses the existing schema: entity_type -> table_name, entity_id ->
    record_id (NIL_ENTITY_ID for collection reads), request metadata ->
    new_values JSONB. NEVER pass response bodies or query strings here —
    metadata only.
    """
    from app.models.audit import AuditLog

    entry = AuditLog(
        id=uuid.uuid4(),
        table_name=entity_type,
        record_id=entity_id or NIL_ENTITY_ID,
        action=ACTION_READ,
        changed_by=changed_by if changed_by is not None else get_audit_user(),
        old_values=None,
        new_values={
            "method": method,
            "path": path,
            "status": status_code,
            "ip": ip_address,
            "request_id": request_id,
        },
    )
    db.add(entry)
    # Don't flush here — caller controls the transaction


async def log_change(
    db: AsyncSession,
    table_name: str,
    record_id: uuid.UUID,
    action: str,  # INSERT | UPDATE | DELETE
    old_values: dict | None,
    new_values: dict | None,
) -> None:
    from app.models.audit import AuditLog

    entry = AuditLog(
        id=uuid.uuid4(),
        table_name=table_name,
        record_id=record_id,
        action=action,
        changed_by=get_audit_user(),
        old_values=old_values,
        new_values=new_values,
    )
    db.add(entry)
    # Don't flush here — will be flushed with the transaction
