import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ClinicHoliday(Base):
    """A clinic closure day — no bookable slots on that date.

    ``date`` is a naive calendar date in the clinic's local timezone (same
    convention as ``DoctorLeave.date`` / ``DoctorAvailability`` window
    times). ``name`` is an optional label ("Diwali", "Clinic maintenance").
    One row per clinic+date; enforced by the partial unique index below so
    soft-deleted rows don't block re-adding the same date.
    """

    __tablename__ = "clinic_holidays"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    clinic: Mapped["Clinic"] = relationship(foreign_keys=[clinic_id])

    __table_args__ = (
        Index(
            "uq_clinic_holidays_clinic_date",
            "clinic_id",
            "date",
            unique=True,
            postgresql_where=(deleted_at.is_(None)),
        ),
        Index(
            "idx_clinic_holidays_clinic",
            "clinic_id",
            postgresql_where=(deleted_at.is_(None)),
        ),
    )
