from contextvars import ContextVar
from typing import Any
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

_current_user_id: ContextVar[uuid.UUID | None] = ContextVar("current_user_id", default=None)


def set_audit_user(user_id: uuid.UUID | None) -> None:
    _current_user_id.set(user_id)


def get_audit_user() -> uuid.UUID | None:
    return _current_user_id.get()


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
