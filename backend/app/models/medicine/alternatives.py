"""Therapeutic alternatives model."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, ForeignKey, PrimaryKeyConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import MedicineBase

if TYPE_CHECKING:
    from .salts import Salt


class SaltAlternative(MedicineBase):
    """Therapeutic alternatives (self-referencing many-to-many)."""

    __tablename__ = "salt_alternatives"
    __table_args__ = (
        PrimaryKeyConstraint("salt_id", "alternative_salt_id"),
        CheckConstraint("salt_id != alternative_salt_id", name="chk_no_self_alternative"),
    )

    salt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("salts.salt_id", ondelete="CASCADE"), nullable=False, index=True
    )
    alternative_salt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("salts.salt_id", ondelete="CASCADE"), nullable=False, index=True
    )
    equivalence_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # therapeutic, generic, biosimilar
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    salt: Mapped["Salt"] = relationship("Salt", foreign_keys=[salt_id], back_populates="alternatives")
    alternative_salt: Mapped["Salt"] = relationship("Salt", foreign_keys=[alternative_salt_id], back_populates="alternative_for")

    def __repr__(self):
        return f"<SaltAlternative(salt={self.salt_id}, alternative={self.alternative_salt_id}, type={self.equivalence_type})>"
