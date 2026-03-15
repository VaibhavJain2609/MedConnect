import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class LabResult(Base):
    __tablename__ = "lab_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    doctor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    test_name: Mapped[str] = mapped_column(String(255), nullable=False)
    test_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    appointment_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    result_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    result_unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    normal_range: Mapped[str | None] = mapped_column(String(100), nullable=True)
    abnormal_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    patient: Mapped["User"] = relationship(foreign_keys=[patient_id])
    doctor: Mapped["User"] = relationship(foreign_keys=[doctor_id])

    __table_args__ = (
        Index("idx_lab_results_patient", "patient_id", postgresql_where=(deleted_at.is_(None))),
        Index("idx_lab_results_doctor", "doctor_id", postgresql_where=(deleted_at.is_(None))),
        Index("idx_lab_results_status", "status", postgresql_where=(deleted_at.is_(None))),
        Index("idx_lab_results_deleted_at", "deleted_at"),
    )
