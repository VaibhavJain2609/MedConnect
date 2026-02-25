"""Test duplicate prevention constraints for MD-29."""

import pytest
from uuid import uuid4
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.medicine.commercial import Manufacturer, Brand, BrandComposition
from app.models.medicine.salts import Salt, SaltStrength


@pytest.mark.asyncio
async def test_duplicate_brand_same_manufacturer_rejected(medicine_db: AsyncSession):
    """Test that duplicate brand name from same manufacturer is rejected."""
    # Create manufacturer
    manufacturer = Manufacturer(
        manufacturer_name="Test Pharma Ltd",
        country="India",
        is_active=True,
    )
    medicine_db.add(manufacturer)
    await medicine_db.flush()

    # Create first brand
    brand1 = Brand(
        brand_name="TestMedicine",
        manufacturer_id=manufacturer.manufacturer_id,
        is_discontinued=False,
    )
    medicine_db.add(brand1)
    await medicine_db.flush()

    # Try to create duplicate brand (same name, same manufacturer)
    brand2 = Brand(
        brand_name="TestMedicine",  # Duplicate!
        manufacturer_id=manufacturer.manufacturer_id,
        is_discontinued=False,
    )
    medicine_db.add(brand2)

    # Should raise IntegrityError due to unique constraint
    with pytest.raises(IntegrityError) as exc_info:
        await medicine_db.flush()

    assert "uq_brand_manufacturer" in str(exc_info.value)


@pytest.mark.asyncio
async def test_same_brand_name_different_manufacturers_allowed(medicine_db: AsyncSession):
    """Test that same brand name from different manufacturers is allowed."""
    # Create two manufacturers
    manufacturer1 = Manufacturer(
        manufacturer_name="Pharma A",
        country="India",
        is_active=True,
    )
    manufacturer2 = Manufacturer(
        manufacturer_name="Pharma B",
        country="India",
        is_active=True,
    )
    medicine_db.add_all([manufacturer1, manufacturer2])
    await medicine_db.flush()

    # Create brand with same name but different manufacturers
    brand1 = Brand(
        brand_name="GenericMedicine",
        manufacturer_id=manufacturer1.manufacturer_id,
        is_discontinued=False,
    )
    brand2 = Brand(
        brand_name="GenericMedicine",  # Same name
        manufacturer_id=manufacturer2.manufacturer_id,  # Different manufacturer
        is_discontinued=False,
    )
    medicine_db.add_all([brand1, brand2])

    # Should NOT raise error - different manufacturers
    await medicine_db.flush()
    assert brand1.brand_id != brand2.brand_id


@pytest.mark.asyncio
async def test_duplicate_salt_strength_rejected(medicine_db: AsyncSession):
    """Test that duplicate salt strength (same value + unit) is rejected."""
    # Create salt
    salt = Salt(
        salt_name="Paracetamol",
        prescription_required=False,
    )
    medicine_db.add(salt)
    await medicine_db.flush()

    # Create first strength
    strength1 = SaltStrength(
        salt_id=salt.salt_id,
        strength_value=500,
        strength_unit="mg",
        is_standard_strength=True,
    )
    medicine_db.add(strength1)
    await medicine_db.flush()

    # Try to create duplicate strength
    strength2 = SaltStrength(
        salt_id=salt.salt_id,
        strength_value=500,  # Duplicate value
        strength_unit="mg",  # Duplicate unit
        is_standard_strength=True,
    )
    medicine_db.add(strength2)

    # Should raise IntegrityError
    with pytest.raises(IntegrityError) as exc_info:
        await medicine_db.flush()

    assert "uq_salt_strength" in str(exc_info.value)


@pytest.mark.asyncio
async def test_duplicate_manufacturer_name_rejected(medicine_db: AsyncSession):
    """Test that duplicate manufacturer name is rejected."""
    # Create first manufacturer
    manufacturer1 = Manufacturer(
        manufacturer_name="Unique Pharma Ltd",
        country="India",
    )
    medicine_db.add(manufacturer1)
    await medicine_db.flush()

    # Try to create manufacturer with same name (case-insensitive handled by app logic)
    manufacturer2 = Manufacturer(
        manufacturer_name="Unique Pharma Ltd",  # Duplicate
        country="USA",
    )
    medicine_db.add(manufacturer2)

    # Should raise IntegrityError
    with pytest.raises(IntegrityError) as exc_info:
        await medicine_db.flush()

    assert "manufacturer_name" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_duplicate_brand_composition_rejected(medicine_db: AsyncSession):
    """Test that duplicate brand composition (same brand + same salt strength) is rejected."""
    # Setup: manufacturer, salt, strength, brand
    manufacturer = Manufacturer(manufacturer_name="Test Mfr", country="India")
    salt = Salt(salt_name="Aspirin", prescription_required=False)
    medicine_db.add_all([manufacturer, salt])
    await medicine_db.flush()

    strength = SaltStrength(
        salt_id=salt.salt_id,
        strength_value=100,
        strength_unit="mg",
    )
    brand = Brand(
        brand_name="TestBrand",
        manufacturer_id=manufacturer.manufacturer_id,
    )
    medicine_db.add_all([strength, brand])
    await medicine_db.flush()

    # Create first composition
    composition1 = BrandComposition(
        brand_id=brand.brand_id,
        salt_strength_id=strength.salt_strength_id,
        sequence=1,
    )
    medicine_db.add(composition1)
    await medicine_db.flush()

    # Try to add same salt strength again to same brand
    composition2 = BrandComposition(
        brand_id=brand.brand_id,  # Same brand
        salt_strength_id=strength.salt_strength_id,  # Same strength
        sequence=2,  # Different sequence doesn't matter
    )
    medicine_db.add(composition2)

    # Should raise IntegrityError
    with pytest.raises(IntegrityError) as exc_info:
        await medicine_db.flush()

    assert "uq_brand_salt_strength" in str(exc_info.value)
