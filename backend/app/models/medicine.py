import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Medicine(Base):
    """
    Medicine/Drug product with brand name, manufacturer, pricing, etc.
    Composition is stored via many-to-many relationship with Component through MedicineComponent
    """
    __tablename__ = "medicines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brand_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    # Note: salt_composition removed - now computed from medicine_components relationship
    manufacturer: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    dosage_form: Mapped[str | None] = mapped_column(String(100), nullable=True)  # "tablet", "syrup", "injection"
    strength: Mapped[str | None] = mapped_column(String(100), nullable=True)  # Computed display string like "625mg"
    pack_size: Mapped[str | None] = mapped_column(String(200), nullable=True)  # "strip of 10 tablets"
    therapeutic_class: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    schedule: Mapped[str | None] = mapped_column(String(10), nullable=True)  # Drug schedule (H, H1, X, etc.)
    mrp: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    is_discontinued: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false", index=True)
    habit_forming: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    alternatives: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # Array of alternative medicine info
    interactions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # Side effects, uses, chemical class, action class
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    medicine_components: Mapped[list["MedicineComponent"]] = relationship(
        "MedicineComponent",
        back_populates="medicine",
        cascade="all, delete-orphan",
        order_by="MedicineComponent.sequence"
    )

    @property
    def salt_composition(self) -> str:
        """
        Computed property: Generate salt composition display string from components
        Example: "Paracetamol (500mg) + Ibuprofen (200mg)"
        """
        if not self.medicine_components:
            return ""

        comp_strings = []
        for mc in sorted(self.medicine_components, key=lambda x: x.sequence):
            comp_strings.append(f"{mc.component.name} ({mc.display_strength})")

        return " + ".join(comp_strings)

    def __repr__(self) -> str:
        return f"<Medicine(id={self.id}, brand_name={self.brand_name})>"
