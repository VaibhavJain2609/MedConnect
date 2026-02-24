"""Dosing guidelines model."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, Boolean, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import MedicineBase

if TYPE_CHECKING:
    from .salts import Salt
    from .indications import Use


class DosingGuideline(MedicineBase):
    """Standard dosing recommendations."""

    __tablename__ = "dosing_guidelines"

    dosing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    salt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("salts.salt_id", ondelete="CASCADE"), nullable=False, index=True
    )
    use_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("uses.use_id"), nullable=True, index=True
    )

    # Patient population
    age_group: Mapped[str | None] = mapped_column(String(50), nullable=True)  # adult, pediatric, geriatric
    min_age_years: Mapped[Decimal | None] = mapped_column(Numeric(4, 1), nullable=True)
    max_age_years: Mapped[Decimal | None] = mapped_column(Numeric(4, 1), nullable=True)
    weight_based: Mapped[bool] = mapped_column(Boolean, default=False)

    # Dosing
    standard_dose: Mapped[str] = mapped_column(String(255), nullable=False)
    frequency: Mapped[str | None] = mapped_column(String(100), nullable=True)  # "Once daily", "BID", "TID", "QID"
    route: Mapped[str | None] = mapped_column(String(50), nullable=True)
    duration: Mapped[str | None] = mapped_column(String(100), nullable=True)
    max_daily_dose: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Adjustments
    renal_adjustment: Mapped[str | None] = mapped_column(Text, nullable=True)
    hepatic_adjustment: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    salt: Mapped["Salt"] = relationship("Salt", back_populates="dosing_guidelines")
    use: Mapped["Use | None"] = relationship("Use", back_populates="dosing_guidelines")

    def __repr__(self):
        return f"<DosingGuideline(id={self.dosing_id}, salt={self.salt_id}, dose={self.standard_dose})>"
