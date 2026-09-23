import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class LabOrder(Base):
    """A lab test ordered by a doctor for a patient.

    Status transitions (enforced server-side in routers/lab_orders.py):
        ordered → completed | cancelled
    ``result_record_id`` links to the MedicalRecord carrying the uploaded
    result (typically record_type='lab_report') once the order completes.
    """

    __tablename__ = "lab_orders"

    VALID_STATUSES = ("ordered", "completed", "cancelled")

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    doctor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("doctors.id"), nullable=False)
    clinic_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=True)
    test_name: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ordered")
    result_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("medical_records.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    patient: Mapped["User"] = relationship(foreign_keys=[patient_id])
    doctor: Mapped["Doctor"] = relationship(foreign_keys=[doctor_id])
    result_record: Mapped["MedicalRecord | None"] = relationship(foreign_keys=[result_record_id])

    __table_args__ = (
        Index("idx_lab_orders_patient", "patient_id", postgresql_where=(deleted_at.is_(None))),
        Index("idx_lab_orders_doctor", "doctor_id", postgresql_where=(deleted_at.is_(None))),
        Index("idx_lab_orders_status", "status", postgresql_where=(deleted_at.is_(None))),
        Index("idx_lab_orders_deleted_at", "deleted_at"),
    )
