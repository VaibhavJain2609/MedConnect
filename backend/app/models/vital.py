import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

VITAL_TYPES = frozenset({
    "bp_systolic",
    "bp_diastolic",
    "glucose_fasting",
    "glucose_pp",
    "weight_kg",
    "spo2",
    "pulse",
    "temperature_c",
})


class PatientVital(Base):
    __tablename__ = "patient_vitals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    vital_type: Mapped[str] = mapped_column(String(30), nullable=False)
    value: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    unit: Mapped[str] = mapped_column(String(10), nullable=False)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    patient: Mapped["User"] = relationship(
        back_populates="vitals", foreign_keys=[patient_id]
    )
    recorder: Mapped["User"] = relationship(
        foreign_keys=[recorded_by]
    )

    __table_args__ = (
        Index(
            "idx_patient_vitals_patient_type_recorded_at",
            "patient_id",
            "vital_type",
            "recorded_at",
            postgresql_where=(deleted_at.is_(None)),
        ),
    )
