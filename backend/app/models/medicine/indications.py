"""Clinical indications (uses) models."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, Boolean, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import MedicineBase

if TYPE_CHECKING:
    from .salts import Salt
    from .dosing import DosingGuideline


class Use(MedicineBase):
    """Approved and off-label uses/indications."""

    __tablename__ = "uses"

    use_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    use_name: Mapped[str] = mapped_column(String(500), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icd10_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_primary_indication: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    salt_uses: Mapped[list["SaltUse"]] = relationship("SaltUse", back_populates="use")
    dosing_guidelines: Mapped[list["DosingGuideline"]] = relationship("DosingGuideline", back_populates="use")

    def __repr__(self):
        return f"<Use(id={self.use_id}, name={self.use_name[:50]})>"


class SaltUse(MedicineBase):
    """Many-to-Many: Salts to Uses."""

    __tablename__ = "salt_uses"
    __table_args__ = (
        PrimaryKeyConstraint("salt_id", "use_id"),
    )

    salt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("salts.salt_id", ondelete="CASCADE"), nullable=False, index=True
    )
    use_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("uses.use_id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_approved: Mapped[bool] = mapped_column(Boolean, default=True)  # FDA/CDSCO approved vs off-label
    age_restriction: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    salt: Mapped["Salt"] = relationship("Salt", back_populates="uses")
    use: Mapped["Use"] = relationship("Use", back_populates="salt_uses")

    def __repr__(self):
        return f"<SaltUse(salt={self.salt_id}, use={self.use_id}, approved={self.is_approved})>"
