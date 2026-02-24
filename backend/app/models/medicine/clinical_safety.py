"""Clinical safety models - side effects, contraindications, drug interactions."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, ForeignKey, PrimaryKeyConstraint, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import MedicineBase

if TYPE_CHECKING:
    from .salts import Salt


class SideEffect(MedicineBase):
    """Known adverse effects."""

    __tablename__ = "side_effects"

    side_effect_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    side_effect_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)  # mild, moderate, severe, life-threatening
    frequency: Mapped[str | None] = mapped_column(String(20), nullable=True)  # rare, uncommon, common, very common
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    salt_side_effects: Mapped[list["SaltSideEffect"]] = relationship("SaltSideEffect", back_populates="side_effect")

    def __repr__(self):
        return f"<SideEffect(id={self.side_effect_id}, name={self.side_effect_name})>"


class SaltSideEffect(MedicineBase):
    """Many-to-Many: Salts to Side Effects."""

    __tablename__ = "salt_side_effects"
    __table_args__ = (
        PrimaryKeyConstraint("salt_id", "side_effect_id"),
    )

    salt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("salts.salt_id", ondelete="CASCADE"), nullable=False, index=True
    )
    side_effect_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("side_effects.side_effect_id", ondelete="CASCADE"), nullable=False, index=True
    )
    frequency: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    salt: Mapped["Salt"] = relationship("Salt", back_populates="side_effects")
    side_effect: Mapped["SideEffect"] = relationship("SideEffect", back_populates="salt_side_effects")

    def __repr__(self):
        return f"<SaltSideEffect(salt={self.salt_id}, effect={self.side_effect_id})>"


class Contraindication(MedicineBase):
    """Conditions where drug should not be used."""

    __tablename__ = "contraindications"

    contraindication_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    contraindication_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icd10_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)  # absolute, relative
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    salt_contraindications: Mapped[list["SaltContraindication"]] = relationship("SaltContraindication", back_populates="contraindication")

    def __repr__(self):
        return f"<Contraindication(id={self.contraindication_id}, name={self.contraindication_name})>"


class SaltContraindication(MedicineBase):
    """Many-to-Many: Salts to Contraindications."""

    __tablename__ = "salt_contraindications"
    __table_args__ = (
        PrimaryKeyConstraint("salt_id", "contraindication_id"),
    )

    salt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("salts.salt_id", ondelete="CASCADE"), nullable=False, index=True
    )
    contraindication_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contraindications.contraindication_id", ondelete="CASCADE"), nullable=False
    )
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    salt: Mapped["Salt"] = relationship("Salt", back_populates="contraindications")
    contraindication: Mapped["Contraindication"] = relationship("Contraindication", back_populates="salt_contraindications")

    def __repr__(self):
        return f"<SaltContraindication(salt={self.salt_id}, contraindication={self.contraindication_id})>"


class DrugInteraction(MedicineBase):
    """Drug-drug interactions."""

    __tablename__ = "drug_interactions"
    __table_args__ = (
        UniqueConstraint("salt_id_1", "salt_id_2", name="uq_drug_interaction"),
        CheckConstraint("salt_id_1 < salt_id_2", name="chk_interaction_order"),
    )

    interaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    salt_id_1: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("salts.salt_id", ondelete="CASCADE"), nullable=False, index=True
    )
    salt_id_2: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("salts.salt_id", ondelete="CASCADE"), nullable=False, index=True
    )
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # minor, moderate, major, contraindicated
    effect: Mapped[str] = mapped_column(Text, nullable=False)
    mechanism: Mapped[str | None] = mapped_column(Text, nullable=True)
    management: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_level: Mapped[str | None] = mapped_column(String(20), nullable=True)  # theoretical, case-report, study-based
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    salt_1: Mapped["Salt"] = relationship("Salt", foreign_keys=[salt_id_1], back_populates="interactions_as_salt1")
    salt_2: Mapped["Salt"] = relationship("Salt", foreign_keys=[salt_id_2], back_populates="interactions_as_salt2")

    def __repr__(self):
        return f"<DrugInteraction(id={self.interaction_id}, severity={self.severity})>"
