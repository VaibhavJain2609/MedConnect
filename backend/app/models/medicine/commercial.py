"""Commercial layer models - manufacturers, brands, compositions."""

import uuid
from datetime import datetime, date
from typing import TYPE_CHECKING

from sqlalchemy import String, Boolean, ForeignKey, Integer, Date, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import MedicineBase

if TYPE_CHECKING:
    from .salts import SaltStrength
    from .packaging import BrandPackaging
    from .audit import PrescriptionAudit


class Manufacturer(MedicineBase):
    """Pharmaceutical companies."""

    __tablename__ = "manufacturers"

    manufacturer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    manufacturer_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    license_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contact_info: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    brands: Mapped[list["Brand"]] = relationship("Brand", back_populates="manufacturer")

    def __repr__(self):
        return f"<Manufacturer(id={self.manufacturer_id}, name={self.manufacturer_name})>"


class Brand(MedicineBase):
    """Commercial products."""

    __tablename__ = "brands"
    __table_args__ = (
        UniqueConstraint("brand_name", "manufacturer_id", name="uq_brand_manufacturer"),
    )

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    brand_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    manufacturer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("manufacturers.manufacturer_id"), nullable=False, index=True
    )
    is_discontinued: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    drug_type: Mapped[str] = mapped_column(String(50), default="allopathy")  # allopathy, ayurveda, homeopathy
    launch_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    discontinuation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    ndhm_code: Mapped[str | None] = mapped_column(String(50), nullable=True)  # ABDM integration
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    manufacturer: Mapped["Manufacturer"] = relationship("Manufacturer", back_populates="brands")
    compositions: Mapped[list["BrandComposition"]] = relationship("BrandComposition", back_populates="brand", cascade="all, delete-orphan")
    packaging: Mapped[list["BrandPackaging"]] = relationship("BrandPackaging", back_populates="brand", cascade="all, delete-orphan")
    prescriptions: Mapped[list["PrescriptionAudit"]] = relationship("PrescriptionAudit", back_populates="brand")
    side_effects: Mapped[list["BrandSideEffect"]] = relationship(
        "BrandSideEffect", back_populates="brand", cascade="all, delete-orphan"
    )

    @property
    def salt_composition(self) -> str:
        """Get formatted salt composition string."""
        if not self.compositions:
            return ""
        comp_strings = []
        for bc in sorted(self.compositions, key=lambda x: x.sequence):
            salt_name = bc.salt_strength.salt.salt_name
            strength = bc.salt_strength.display_strength
            comp_strings.append(f"{salt_name} ({strength})")
        return " + ".join(comp_strings)

    def __repr__(self):
        return f"<Brand(id={self.brand_id}, name={self.brand_name})>"


class BrandComposition(MedicineBase):
    """Links brands to salt strengths (supports combination drugs)."""

    __tablename__ = "brand_compositions"
    __table_args__ = (
        UniqueConstraint("brand_id", "salt_strength_id", name="uq_brand_salt_strength"),
    )

    composition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.brand_id", ondelete="CASCADE"), nullable=False, index=True
    )
    salt_strength_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("salt_strengths.salt_strength_id"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=1)  # Order in combination

    # Relationships
    brand: Mapped["Brand"] = relationship("Brand", back_populates="compositions")
    salt_strength: Mapped["SaltStrength"] = relationship("SaltStrength", back_populates="brand_compositions")

    def __repr__(self):
        return f"<BrandComposition(brand={self.brand_id}, salt_strength={self.salt_strength_id}, seq={self.sequence})>"
