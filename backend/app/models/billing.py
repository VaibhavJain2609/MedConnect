import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

BILLING_STATUSES = ("pending", "paid", "cancelled", "refunded")
PAYMENT_METHODS = ("cash", "card", "upi", "insurance", "other")


class Billing(Base):
    __tablename__ = "billing"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    clinic_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=True)
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appointments.id"), nullable=True
    )
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    # pending | paid | cancelled | refunded
    payment_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # cash | card | upi | insurance | other
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    patient: Mapped["User"] = relationship(foreign_keys=[patient_id])
    clinic: Mapped["Clinic"] = relationship(foreign_keys=[clinic_id])
    appointment: Mapped["Appointment"] = relationship(foreign_keys=[appointment_id])

    __table_args__ = (
        Index("idx_billing_patient", "patient_id", postgresql_where=(deleted_at.is_(None))),
        Index("idx_billing_clinic_status", "clinic_id", "status", postgresql_where=(deleted_at.is_(None))),
        Index("idx_billing_created_at", "created_at", postgresql_where=(deleted_at.is_(None))),
    )
