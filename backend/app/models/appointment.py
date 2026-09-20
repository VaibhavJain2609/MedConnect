import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    doctor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("doctors.id"), nullable=False)
    clinic_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=True)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("clinic_branches.id"), nullable=True)
    # NOTE: doctor double-booking is enforced at the DB level by the
    # exclusion constraint `excl_appointments_doctor_no_overlap`
    # (migration 024_db_constraint_races):
    #   EXCLUDE USING gist (doctor_id WITH =,
    #     tstzrange(scheduled_at, scheduled_at + duration_minutes * interval '1 minute', '[)')
    #     WITH &&)
    #   WHERE status IN ('scheduled','arrived','in-progress') AND deleted_at IS NULL
    # It mirrors _check_doctor_conflict in routers/appointments.py. Do not
    # change the type of scheduled_at/duration_minutes without updating it.
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # in-person | teleconsult | follow-up
    status: Mapped[str] = mapped_column(String(20), default="scheduled", nullable=False)
    # scheduled | arrived | in-progress | completed | cancelled | no-show
    chief_complaint: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancelled_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    meeting_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    patient: Mapped["User"] = relationship(foreign_keys=[patient_id])
    doctor: Mapped["Doctor"] = relationship(foreign_keys=[doctor_id])
    clinic: Mapped["Clinic"] = relationship(foreign_keys=[clinic_id])
    creator: Mapped["User"] = relationship(foreign_keys=[created_by])

    __table_args__ = (
        Index(
            "idx_appointments_doctor_scheduled_at",
            "doctor_id",
            "scheduled_at",
            postgresql_where=(deleted_at.is_(None)),
        ),
        Index(
            "idx_appointments_patient_scheduled_at",
            "patient_id",
            "scheduled_at",
            postgresql_where=(deleted_at.is_(None)),
        ),
        Index("idx_appointments_clinic", "clinic_id", postgresql_where=(deleted_at.is_(None))),
        Index("idx_appointments_status", "status", postgresql_where=(deleted_at.is_(None))),
        Index("idx_appointments_branch", "branch_id", postgresql_where=(deleted_at.is_(None))),
    )
