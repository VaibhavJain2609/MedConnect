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
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # in-person | teleconsult | follow-up
    status: Mapped[str] = mapped_column(String(20), default="scheduled", nullable=False)
    # scheduled | arrived | in-progress | completed | cancelled | no-show
    chief_complaint: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancelled_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    )
