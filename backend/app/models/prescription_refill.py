import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PrescriptionRefillRequest(Base):
    """A patient's request to renew/refill an existing prescription.

    Lifecycle: pending → approved | declined. On approve the responding
    doctor issues a NEW prescription cloned from the original's medicines
    (`new_prescription_id` links back to it). The partial unique index
    guarantees at most one pending request per prescription.
    """

    __tablename__ = "prescription_refill_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prescription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prescriptions.id"), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    # Denormalized from the prescription so lists/notifications don't join.
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("doctors.id"), nullable=False
    )
    clinic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )  # pending | approved | declined
    response_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    responded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("doctors.id"), nullable=True
    )
    new_prescription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prescriptions.id"), nullable=True
    )
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    prescription: Mapped["Prescription"] = relationship(foreign_keys=[prescription_id])
    patient: Mapped["User"] = relationship(foreign_keys=[patient_id])
    doctor: Mapped["Doctor"] = relationship(foreign_keys=[doctor_id])
    responder: Mapped["Doctor"] = relationship(foreign_keys=[responded_by_id])
    new_prescription: Mapped["Prescription"] = relationship(foreign_keys=[new_prescription_id])

    __table_args__ = (
        # One pending request per prescription — the DB-level guard behind
        # the double-request check in the request endpoint.
        Index(
            "uq_refill_pending_per_rx",
            "prescription_id",
            unique=True,
            postgresql_where=text("status = 'pending' AND deleted_at IS NULL"),
        ),
        Index("idx_refill_patient", "patient_id", postgresql_where=text("deleted_at IS NULL")),
        Index(
            "idx_refill_clinic_status",
            "clinic_id",
            "status",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("idx_refill_doctor", "doctor_id", postgresql_where=text("deleted_at IS NULL")),
    )
