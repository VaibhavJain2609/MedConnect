"""Packaging models - dosage forms and packaging details."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Boolean, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import MedicineBase

if TYPE_CHECKING:
    from .commercial import Brand


class PackForm(MedicineBase):
    """Dosage forms (tablet, capsule, syrup, injection, etc.)."""

    __tablename__ = "pack_forms"

    pack_form_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    form_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    route_of_administration: Mapped[str | None] = mapped_column(String(50), nullable=True)  # Oral, IV, IM, Topical, etc.
    is_solid: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_liquid: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    requires_reconstitution: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    brand_packaging: Mapped[list["BrandPackaging"]] = relationship("BrandPackaging", back_populates="pack_form")

    def __repr__(self):
        return f"<PackForm(id={self.pack_form_id}, name={self.form_name})>"


class BrandPackaging(MedicineBase):
    """Packaging details for each brand."""

    __tablename__ = "brand_packaging"
    __table_args__ = (
        UniqueConstraint("brand_id", "pack_form_id", "quantity", name="uq_brand_pack"),
    )

    brand_pack_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.brand_id", ondelete="CASCADE"), nullable=False, index=True
    )
    pack_form_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pack_forms.pack_form_id"), nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)  # Number of units
    pack_type: Mapped[str | None] = mapped_column(String(100), nullable=True)  # "strip of 10 tablets", "bottle of 100ml"
    sku: Mapped[str | None] = mapped_column(String(100), nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_primary_pack: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    brand: Mapped["Brand"] = relationship("Brand", back_populates="packaging")
    pack_form: Mapped["PackForm"] = relationship("PackForm", back_populates="brand_packaging")

    def __repr__(self):
        return f"<BrandPackaging(id={self.brand_pack_id}, brand={self.brand_id}, form={self.pack_form_id})>"
