"""Audit and logging models for search and prescriptions."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import MedicineBase

if TYPE_CHECKING:
    from .commercial import Brand
    from .salts import Salt


class MedicineSearchLog(MedicineBase):
    """Track medicine searches for analytics."""

    __tablename__ = "medicine_search_log"

    log_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    search_query: Mapped[str | None] = mapped_column(String(500), nullable=True)
    search_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # brand, salt, indication
    results_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    selected_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<MedicineSearchLog(id={self.log_id}, query={self.search_query}, type={self.search_type})>"


class PrescriptionAudit(MedicineBase):
    """Track medicine prescriptions for safety monitoring."""

    __tablename__ = "prescription_audit"

    audit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    prescription_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    doctor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.brand_id"), nullable=True, index=True
    )
    salt_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("salts.salt_id"), nullable=True
    )

    dosage: Mapped[str | None] = mapped_column(String(255), nullable=True)
    duration: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Alert tracking
    interaction_alerts: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    contraindication_alerts: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    allergy_alerts: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    prescribed_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    brand: Mapped["Brand | None"] = relationship("Brand", back_populates="prescriptions")
    salt: Mapped["Salt | None"] = relationship("Salt")

    def __repr__(self):
        return f"<PrescriptionAudit(id={self.audit_id}, prescription={self.prescription_id})>"
