import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RecordAccessConsent(Base):
    __tablename__ = "record_access_consents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doctor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("doctors.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    clinic_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|approved|rejected|revoked
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_duration_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    doctor: Mapped["Doctor"] = relationship(foreign_keys=[doctor_id])
    patient: Mapped["User"] = relationship(foreign_keys=[patient_id])
    clinic: Mapped["Clinic"] = relationship(foreign_keys=[clinic_id])

    __table_args__ = (
        Index("idx_rac_doctor_patient", "doctor_id", "patient_id",
              postgresql_where=(deleted_at.is_(None))),
        Index("idx_rac_patient", "patient_id",
              postgresql_where=(deleted_at.is_(None))),
        Index("idx_rac_expires", "expires_at",
              postgresql_where=(deleted_at.is_(None))),
    )
