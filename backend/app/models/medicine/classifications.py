"""Classification models for medicines."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import MedicineBase

if TYPE_CHECKING:
    from .salts import Salt


class ChemicalClass(MedicineBase):
    """Chemical classification of drugs."""

    __tablename__ = "chemical_classes"

    chemical_class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    class_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_class_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chemical_classes.chemical_class_id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    parent: Mapped["ChemicalClass | None"] = relationship(
        "ChemicalClass", remote_side=[chemical_class_id], back_populates="children"
    )
    children: Mapped[list["ChemicalClass"]] = relationship(
        "ChemicalClass", back_populates="parent", foreign_keys=[parent_class_id]
    )
    salts: Mapped[list["Salt"]] = relationship("Salt", back_populates="chemical_class")

    def __repr__(self):
        return f"<ChemicalClass(id={self.chemical_class_id}, name={self.class_name})>"


class TherapeuticClass(MedicineBase):
    """Therapeutic/pharmacological classification."""

    __tablename__ = "therapeutic_classes"

    therapeutic_class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    class_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icd10_codes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    salts: Mapped[list["Salt"]] = relationship("Salt", back_populates="therapeutic_class")

    def __repr__(self):
        return f"<TherapeuticClass(id={self.therapeutic_class_id}, name={self.class_name})>"


class ActionClass(MedicineBase):
    """Mechanism of action classification."""

    __tablename__ = "action_classes"

    action_class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    class_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    mechanism: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    salts: Mapped[list["Salt"]] = relationship("Salt", back_populates="action_class")

    def __repr__(self):
        return f"<ActionClass(id={self.action_class_id}, name={self.class_name})>"
