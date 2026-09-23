"""Opt-in per-prescription medication reminder schedule.

A patient enables reminders on one of their own prescriptions and picks the
times of day (``["08:00", "20:00"]``, 24h ``HH:MM``) at which the
``send_medication_reminders`` ARQ cron task should drop an in-app
notification. One live row per (user, prescription) — enforced by the
partial unique index in ``__table_args__``; re-enabling after a soft delete
creates a fresh row.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MedicationReminder(Base):
    __tablename__ = "medication_reminders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    prescription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prescriptions.id"), nullable=False, index=True
    )
    # JSON list of "HH:MM" strings (24h, interpreted in the reminder timezone
    # — Asia/Kolkata, same default as appointment reminders).
    times_of_day: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        # At most one live reminder per (user, prescription). Partial so
        # re-enabling after a soft delete is allowed.
        Index(
            "uq_medication_reminders_user_rx",
            "user_id",
            "prescription_id",
            unique=True,
            postgresql_where=(deleted_at.is_(None)),
        ),
        Index(
            "idx_medication_reminders_enabled",
            "enabled",
            postgresql_where=(deleted_at.is_(None)),
        ),
    )
