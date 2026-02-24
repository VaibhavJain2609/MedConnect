import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Component(Base):
    """
    Active Pharmaceutical Ingredient (API) / Salt / Component
    Master table for all medicine components (e.g., Paracetamol, Ibuprofen, Amoxycillin)
    """
    __tablename__ = "components"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    common_names: Mapped[str | None] = mapped_column(String(500), nullable=True)  # Comma-separated alternatives
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)  # "Analgesic", "Antibiotic", etc.
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    medicine_components: Mapped[list["MedicineComponent"]] = relationship(
        "MedicineComponent", back_populates="component", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Component(id={self.id}, name={self.name})>"
