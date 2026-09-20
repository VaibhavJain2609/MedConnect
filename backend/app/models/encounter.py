import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Encounter(Base):
    """Clinical visit/encounter — SOAP notes authored by a doctor.

    The core EMR entity for a consultation. `appointment_id` is optional so
    walk-in encounters can be recorded without a booked appointment.
    `vitals_snapshot` captures a point-in-time copy of recorded vitals.
    """

    __tablename__ = "encounters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    doctor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("doctors.id"), nullable=False)
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("appointments.id"), nullable=True)
    clinic_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=True)

    # SOAP note sections
    subjective: Mapped[str | None] = mapped_column(Text, nullable=True)
    objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    assessment: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan: Mapped[str | None] = mapped_column(Text, nullable=True)

    vitals_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    patient: Mapped["User"] = relationship(foreign_keys=[patient_id])
    doctor: Mapped["Doctor"] = relationship(foreign_keys=[doctor_id])
    appointment: Mapped["Appointment"] = relationship(foreign_keys=[appointment_id])
    clinic: Mapped["Clinic"] = relationship(foreign_keys=[clinic_id])

    __table_args__ = (
        Index("idx_encounters_doctor", "doctor_id", postgresql_where=(deleted_at.is_(None))),
        Index("idx_encounters_patient", "patient_id", postgresql_where=(deleted_at.is_(None))),
        Index("idx_encounters_appointment", "appointment_id", postgresql_where=(deleted_at.is_(None))),
        Index(
            "idx_encounters_clinic_created_at",
            "clinic_id",
            "created_at",
            postgresql_where=(deleted_at.is_(None)),
        ),
    )
