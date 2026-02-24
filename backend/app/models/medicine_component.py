import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MedicineComponent(Base):
    """
    Junction table linking medicines to their components with strength and unit
    Example: CombiFlam contains Paracetamol (500mg) + Ibuprofen (200mg)
    """
    __tablename__ = "medicine_components"
    __table_args__ = (
        UniqueConstraint('medicine_id', 'component_id', name='uq_medicine_component'),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    medicine_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("medicines.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    component_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("components.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    strength: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)  # 500, 125, 0.5
    unit: Mapped[str] = mapped_column(String(20), nullable=False)  # "mg", "mcg", "g", "ml", "%", "IU"
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=1)  # Display order
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    medicine: Mapped["Medicine"] = relationship("Medicine", back_populates="medicine_components")
    component: Mapped["Component"] = relationship("Component", back_populates="medicine_components")

    def __repr__(self) -> str:
        return f"<MedicineComponent(medicine_id={self.medicine_id}, component_id={self.component_id}, strength={self.strength}{self.unit})>"

    @property
    def display_strength(self) -> str:
        """Format strength for display: '500mg', '0.5g', etc."""
        return f"{self.strength}{self.unit}"
