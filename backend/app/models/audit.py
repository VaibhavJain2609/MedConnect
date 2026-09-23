import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    table_name: Mapped[str] = mapped_column(String(50), nullable=False)
    record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(10), nullable=False)  # INSERT | UPDATE | DELETE | READ
    changed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    old_values: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_values: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # NO soft delete — audit logs are immutable
    changer: Mapped["User"] = relationship("User", foreign_keys=[changed_by])

    __table_args__ = (
        Index("idx_audit_table_record", "table_name", "record_id"),
        Index("idx_audit_changed_by", "changed_by"),
        Index("idx_audit_changed_at", "changed_at"),
    )


class AuditLogArchive(Base):
    """Cold-storage copy of ``audit_logs`` rows past the retention window.

    Written by the daily ``audit_retention`` worker task
    (``app/workers/tasks/audit_retention.py``): same columns as the live table
    plus ``archived_at``. Rows here are never updated or deleted by the app.

    ``changed_by`` deliberately carries no FK to ``users.id`` — the archive
    must stay writable/readable even if a user row is ever hard-deleted
    (e.g. a future erasure flow). The admin endpoint still joins ``users``
    explicitly for the actor name.
    """

    __tablename__ = "audit_log_archive"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    table_name: Mapped[str] = mapped_column(String(50), nullable=False)
    record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(10), nullable=False)  # INSERT | UPDATE | DELETE | READ
    changed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    old_values: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_values: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    archived_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # NO soft delete, NO changer relationship — archive rows are immutable and
    # self-contained; join users explicitly where a name is needed.
    __table_args__ = (
        Index("idx_audit_archive_table_record", "table_name", "record_id"),
        Index("idx_audit_archive_changed_by", "changed_by"),
        Index("idx_audit_archive_changed_at", "changed_at"),
    )
