"""Salt (Active Pharmaceutical Ingredient) models."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, Boolean, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import MedicineBase

if TYPE_CHECKING:
    from .classifications import ChemicalClass, TherapeuticClass, ActionClass
    from .clinical_safety import SaltSideEffect, SaltContraindication, DrugInteraction
    from .indications import SaltUse
    from .alternatives import SaltAlternative
    from .dosing import DosingGuideline
    from .commercial import BrandComposition


class Salt(MedicineBase):
    """Active Pharmaceutical Ingredient (Salt/Generic Drug)."""

    __tablename__ = "salts"

    salt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    salt_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    chemical_formula: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Classifications
    chemical_class_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chemical_classes.chemical_class_id"), nullable=True
    )
    therapeutic_class_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("therapeutic_classes.therapeutic_class_id"), nullable=True
    )
    action_class_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("action_classes.action_class_id"), nullable=True
    )

    # Clinical Safety
    habit_forming: Mapped[bool] = mapped_column(Boolean, default=False)
    prescription_required: Mapped[bool] = mapped_column(Boolean, default=True)
    schedule: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Pregnancy & Lactation
    pregnancy_category: Mapped[str | None] = mapped_column(String(10), nullable=True)
    lactation_safe: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    lactation_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ABDM Integration
    snomed_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rxcui: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Relationships
    chemical_class: Mapped["ChemicalClass | None"] = relationship("ChemicalClass", back_populates="salts")
    therapeutic_class: Mapped["TherapeuticClass | None"] = relationship("TherapeuticClass", back_populates="salts")
    action_class: Mapped["ActionClass | None"] = relationship("ActionClass", back_populates="salts")

    strengths: Mapped[list["SaltStrength"]] = relationship("SaltStrength", back_populates="salt", cascade="all, delete-orphan")
    side_effects: Mapped[list["SaltSideEffect"]] = relationship("SaltSideEffect", back_populates="salt", cascade="all, delete-orphan")
    contraindications: Mapped[list["SaltContraindication"]] = relationship("SaltContraindication", back_populates="salt", cascade="all, delete-orphan")
    uses: Mapped[list["SaltUse"]] = relationship("SaltUse", back_populates="salt", cascade="all, delete-orphan")

    # Drug interactions (both directions)
    interactions_as_salt1: Mapped[list["DrugInteraction"]] = relationship(
        "DrugInteraction", foreign_keys="DrugInteraction.salt_id_1", back_populates="salt_1"
    )
    interactions_as_salt2: Mapped[list["DrugInteraction"]] = relationship(
        "DrugInteraction", foreign_keys="DrugInteraction.salt_id_2", back_populates="salt_2"
    )

    # Alternatives
    alternatives: Mapped[list["SaltAlternative"]] = relationship(
        "SaltAlternative", foreign_keys="SaltAlternative.salt_id", back_populates="salt"
    )
    alternative_for: Mapped[list["SaltAlternative"]] = relationship(
        "SaltAlternative", foreign_keys="SaltAlternative.alternative_salt_id", back_populates="alternative_salt"
    )

    dosing_guidelines: Mapped[list["DosingGuideline"]] = relationship("DosingGuideline", back_populates="salt")

    def __repr__(self):
        return f"<Salt(id={self.salt_id}, name={self.salt_name})>"


class SaltStrength(MedicineBase):
    """Available strengths for each salt."""

    __tablename__ = "salt_strengths"
    __table_args__ = (
        UniqueConstraint("salt_id", "strength_value", "strength_unit", name="uq_salt_strength"),
    )

    salt_strength_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    salt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("salts.salt_id", ondelete="CASCADE"), nullable=False, index=True
    )
    strength_value: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    strength_unit: Mapped[str] = mapped_column(String(20), nullable=False)
    is_standard_strength: Mapped[bool] = mapped_column(Boolean, default=True)
    pediatric_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    salt: Mapped["Salt"] = relationship("Salt", back_populates="strengths")
    brand_compositions: Mapped[list["BrandComposition"]] = relationship("BrandComposition", back_populates="salt_strength")

    @property
    def display_strength(self) -> str:
        """Format strength for display."""
        return f"{self.strength_value}{self.strength_unit}"

    def __repr__(self):
        return f"<SaltStrength(id={self.salt_strength_id}, salt={self.salt_id}, strength={self.display_strength})>"
