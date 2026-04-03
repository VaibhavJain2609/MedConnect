"""Simple medicine catalog models for admin management (medicine DB)."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import MedicineBase


class Component(MedicineBase):
    """Active Pharmaceutical Ingredient / Salt / Component."""
    __tablename__ = "components"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    common_names: Mapped[str | None] = mapped_column(String(500), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    medicine_components: Mapped[list["MedicineComponent"]] = relationship(
        "MedicineComponent", back_populates="component", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Component(id={self.id}, name={self.name})>"


class Medicine(MedicineBase):
    """Medicine/Drug product with brand name, manufacturer, pricing, etc."""
    __tablename__ = "medicines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brand_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    manufacturer: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    dosage_form: Mapped[str | None] = mapped_column(String(100), nullable=True)
    strength: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pack_size: Mapped[str | None] = mapped_column(String(200), nullable=True)
    therapeutic_class: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    schedule: Mapped[str | None] = mapped_column(String(10), nullable=True)
    mrp: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    is_discontinued: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false", index=True)
    habit_forming: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    alternatives: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    interactions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    medicine_components: Mapped[list["MedicineComponent"]] = relationship(
        "MedicineComponent",
        back_populates="medicine",
        cascade="all, delete-orphan",
        order_by="MedicineComponent.sequence",
    )

    @property
    def salt_composition(self) -> str:
        if not self.medicine_components:
            return ""
        parts = [
            f"{mc.component.name} ({mc.strength}{mc.unit})"
            for mc in sorted(self.medicine_components, key=lambda x: x.sequence)
        ]
        return " + ".join(parts)

    def __repr__(self) -> str:
        return f"<Medicine(id={self.id}, brand_name={self.brand_name})>"


class MedicineComponent(MedicineBase):
    """Junction table linking medicines to components with strength."""
    __tablename__ = "medicine_components"
    __table_args__ = (
        UniqueConstraint("medicine_id", "component_id", name="uq_medicine_component"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    medicine_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("medicines.id", ondelete="CASCADE"), nullable=False, index=True
    )
    component_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("components.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    strength: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    medicine: Mapped["Medicine"] = relationship("Medicine", back_populates="medicine_components")
    component: Mapped["Component"] = relationship("Component", back_populates="medicine_components")

    @property
    def display_strength(self) -> str:
        return f"{self.strength}{self.unit}"

    def __repr__(self) -> str:
        return f"<MedicineComponent(medicine_id={self.medicine_id}, component_id={self.component_id})>"
