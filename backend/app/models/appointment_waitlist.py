import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AppointmentWaitlist(Base):
    """A patient's request to be notified when a slot opens for a doctor on a
    fully-booked day.

    Lifecycle: pending → notified | expired | cancelled. When an appointment
    for the same doctor+date is cancelled, the earliest pending entries are
    flipped to ``notified`` and the patients receive an in-app notification
    (notify-only — no auto-booking). The partial unique index guarantees at
    most one pending entry per (patient, doctor, desired_date).
    """

    __tablename__ = "appointment_waitlist"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("doctors.id"), nullable=False
    )
    clinic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=True
    )
    desired_date: Mapped[date] = mapped_column(Date, nullable=False)
    # morning | afternoon | any — coarse preference, no exact-time bookkeeping
    slot_window: Mapped[str] = mapped_column(
        String(20), nullable=False, default="any", server_default="any"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )  # pending | notified | expired | cancelled
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    patient: Mapped["User"] = relationship(foreign_keys=[patient_id])
    doctor: Mapped["Doctor"] = relationship(foreign_keys=[doctor_id])
    clinic: Mapped["Clinic"] = relationship(foreign_keys=[clinic_id])

    __table_args__ = (
        # One pending entry per (patient, doctor, day) — the DB-level guard
        # behind the double-join check in the request endpoint.
        Index(
            "uq_waitlist_pending_per_patient_doctor_date",
            "patient_id",
            "doctor_id",
            "desired_date",
            unique=True,
            postgresql_where=text("status = 'pending' AND deleted_at IS NULL"),
        ),
        # Cancellation fan-out lookup: pending entries for a doctor+date.
        Index(
            "idx_waitlist_doctor_date_status",
            "doctor_id",
            "desired_date",
            "status",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("idx_waitlist_patient", "patient_id", postgresql_where=text("deleted_at IS NULL")),
        Index(
            "idx_waitlist_clinic_status",
            "clinic_id",
            "status",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )
