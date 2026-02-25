"""Tests for alternative medicine detection (MD-19)."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.medicine.commercial import Manufacturer, Brand, BrandComposition
from app.models.medicine.salts import Salt, SaltStrength
from app.services.brand_service import BrandService


@pytest.mark.asyncio
async def test_get_brand_alternatives_same_composition(medicine_db: AsyncSession):
    """Test finding alternative brands with exact same salt composition."""
    # Create manufacturer
    mfr1 = Manufacturer(manufacturer_name="Pharma A", country="India")
    mfr2 = Manufacturer(manufacturer_name="Pharma B", country="India")
    medicine_db.add_all([mfr1, mfr2])
    await medicine_db.flush()

    # Create salt and strength (Paracetamol 500mg)
    salt = Salt(salt_name="Paracetamol", prescription_required=False)
    medicine_db.add(salt)
    await medicine_db.flush()

    strength = SaltStrength(
        salt_id=salt.salt_id,
        strength_value=500,
        strength_unit="mg",
    )
    medicine_db.add(strength)
    await medicine_db.flush()

    # Create two brands with SAME composition
    brand1 = Brand(
        brand_name="BrandA Para",
        manufacturer_id=mfr1.manufacturer_id,
        is_discontinued=False,
    )
    brand2 = Brand(
        brand_name="BrandB Para",
        manufacturer_id=mfr2.manufacturer_id,
        is_discontinued=False,
    )
    medicine_db.add_all([brand1, brand2])
    await medicine_db.flush()

    # Add same composition to both brands
    comp1 = BrandComposition(
        brand_id=brand1.brand_id,
        salt_strength_id=strength.salt_strength_id,
        sequence=1,
    )
    comp2 = BrandComposition(
        brand_id=brand2.brand_id,
        salt_strength_id=strength.salt_strength_id,
        sequence=1,
    )
    medicine_db.add_all([comp1, comp2])
    await medicine_db.flush()

    # Get alternatives for brand1
    alternatives = await BrandService.get_brand_alternatives(
        medicine_db,
        brand1.brand_id,
    )

    # Should return brand2 (but not brand1 itself)
    assert len(alternatives) == 1
    assert alternatives[0].brand_id == brand2.brand_id


@pytest.mark.asyncio
async def test_get_brand_alternatives_different_strength_excluded(medicine_db: AsyncSession):
    """Test that brands with different strengths are NOT alternatives."""
    # Create manufacturer
    mfr = Manufacturer(manufacturer_name="Test Pharma", country="India")
    medicine_db.add(mfr)
    await medicine_db.flush()

    # Create salt with two different strengths
    salt = Salt(salt_name="Ibuprofen", prescription_required=False)
    medicine_db.add(salt)
    await medicine_db.flush()

    strength_200 = SaltStrength(
        salt_id=salt.salt_id,
        strength_value=200,
        strength_unit="mg",
    )
    strength_400 = SaltStrength(
        salt_id=salt.salt_id,
        strength_value=400,
        strength_unit="mg",
    )
    medicine_db.add_all([strength_200, strength_400])
    await medicine_db.flush()

    # Create two brands with DIFFERENT strengths
    brand_200 = Brand(
        brand_name="Ibuprofen 200",
        manufacturer_id=mfr.manufacturer_id,
    )
    brand_400 = Brand(
        brand_name="Ibuprofen 400",
        manufacturer_id=mfr.manufacturer_id,
    )
    medicine_db.add_all([brand_200, brand_400])
    await medicine_db.flush()

    comp1 = BrandComposition(
        brand_id=brand_200.brand_id,
        salt_strength_id=strength_200.salt_strength_id,
        sequence=1,
    )
    comp2 = BrandComposition(
        brand_id=brand_400.brand_id,
        salt_strength_id=strength_400.salt_strength_id,
        sequence=1,
    )
    medicine_db.add_all([comp1, comp2])
    await medicine_db.flush()

    # Get alternatives for brand_200
    alternatives = await BrandService.get_brand_alternatives(
        medicine_db,
        brand_200.brand_id,
    )

    # Should NOT return brand_400 (different strength)
    assert len(alternatives) == 0


@pytest.mark.asyncio
async def test_get_brand_alternatives_combination_drug(medicine_db: AsyncSession):
    """Test finding alternatives for combination drugs (multiple salts)."""
    # Create manufacturer
    mfr1 = Manufacturer(manufacturer_name="Combo Pharma A", country="India")
    mfr2 = Manufacturer(manufacturer_name="Combo Pharma B", country="India")
    medicine_db.add_all([mfr1, mfr2])
    await medicine_db.flush()

    # Create two salts
    paracetamol = Salt(salt_name="Paracetamol", prescription_required=False)
    caffeine = Salt(salt_name="Caffeine", prescription_required=False)
    medicine_db.add_all([paracetamol, caffeine])
    await medicine_db.flush()

    # Create strengths
    para_500 = SaltStrength(
        salt_id=paracetamol.salt_id,
        strength_value=500,
        strength_unit="mg",
    )
    caff_65 = SaltStrength(
        salt_id=caffeine.salt_id,
        strength_value=65,
        strength_unit="mg",
    )
    medicine_db.add_all([para_500, caff_65])
    await medicine_db.flush()

    # Create two combination brands
    brand1 = Brand(
        brand_name="Combo Brand A",
        manufacturer_id=mfr1.manufacturer_id,
    )
    brand2 = Brand(
        brand_name="Combo Brand B",
        manufacturer_id=mfr2.manufacturer_id,
    )
    medicine_db.add_all([brand1, brand2])
    await medicine_db.flush()

    # Add SAME combination to both brands
    comps_brand1 = [
        BrandComposition(
            brand_id=brand1.brand_id,
            salt_strength_id=para_500.salt_strength_id,
            sequence=1,
        ),
        BrandComposition(
            brand_id=brand1.brand_id,
            salt_strength_id=caff_65.salt_strength_id,
            sequence=2,
        ),
    ]
    comps_brand2 = [
        BrandComposition(
            brand_id=brand2.brand_id,
            salt_strength_id=para_500.salt_strength_id,
            sequence=1,
        ),
        BrandComposition(
            brand_id=brand2.brand_id,
            salt_strength_id=caff_65.salt_strength_id,
            sequence=2,
        ),
    ]
    medicine_db.add_all(comps_brand1 + comps_brand2)
    await medicine_db.flush()

    # Get alternatives
    alternatives = await BrandService.get_brand_alternatives(
        medicine_db,
        brand1.brand_id,
    )

    # Should return brand2
    assert len(alternatives) == 1
    assert alternatives[0].brand_id == brand2.brand_id


@pytest.mark.asyncio
async def test_get_brand_alternatives_partial_match_excluded(medicine_db: AsyncSession):
    """Test that brands with partial composition match are NOT alternatives."""
    # Create manufacturer
    mfr = Manufacturer(manufacturer_name="Test Pharma", country="India")
    medicine_db.add(mfr)
    await medicine_db.flush()

    # Create two salts
    salt1 = Salt(salt_name="Salt A", prescription_required=False)
    salt2 = Salt(salt_name="Salt B", prescription_required=False)
    medicine_db.add_all([salt1, salt2])
    await medicine_db.flush()

    strength1 = SaltStrength(
        salt_id=salt1.salt_id,
        strength_value=100,
        strength_unit="mg",
    )
    strength2 = SaltStrength(
        salt_id=salt2.salt_id,
        strength_value=50,
        strength_unit="mg",
    )
    medicine_db.add_all([strength1, strength2])
    await medicine_db.flush()

    # Create brands
    # brand1: Salt A only
    # brand2: Salt A + Salt B (different composition)
    brand1 = Brand(brand_name="Single Salt", manufacturer_id=mfr.manufacturer_id)
    brand2 = Brand(brand_name="Combo Salt", manufacturer_id=mfr.manufacturer_id)
    medicine_db.add_all([brand1, brand2])
    await medicine_db.flush()

    # brand1: only Salt A
    comp1 = BrandComposition(
        brand_id=brand1.brand_id,
        salt_strength_id=strength1.salt_strength_id,
        sequence=1,
    )
    # brand2: Salt A + Salt B
    comp2_1 = BrandComposition(
        brand_id=brand2.brand_id,
        salt_strength_id=strength1.salt_strength_id,
        sequence=1,
    )
    comp2_2 = BrandComposition(
        brand_id=brand2.brand_id,
        salt_strength_id=strength2.salt_strength_id,
        sequence=2,
    )
    medicine_db.add_all([comp1, comp2_1, comp2_2])
    await medicine_db.flush()

    # Get alternatives for brand1
    alternatives = await BrandService.get_brand_alternatives(
        medicine_db,
        brand1.brand_id,
    )

    # Should NOT return brand2 (different number of salts)
    assert len(alternatives) == 0


@pytest.mark.asyncio
async def test_get_brand_alternatives_includes_discontinued(medicine_db: AsyncSession):
    """Test that discontinued brands are included in alternatives."""
    # Create manufacturer
    mfr1 = Manufacturer(manufacturer_name="Pharma A", country="India")
    mfr2 = Manufacturer(manufacturer_name="Pharma B", country="India")
    medicine_db.add_all([mfr1, mfr2])
    await medicine_db.flush()

    # Create salt and strength
    salt = Salt(salt_name="TestSalt", prescription_required=False)
    medicine_db.add(salt)
    await medicine_db.flush()

    strength = SaltStrength(
        salt_id=salt.salt_id,
        strength_value=10,
        strength_unit="mg",
    )
    medicine_db.add(strength)
    await medicine_db.flush()

    # Create active and discontinued brands with same composition
    brand_active = Brand(
        brand_name="Active Brand",
        manufacturer_id=mfr1.manufacturer_id,
        is_discontinued=False,
    )
    brand_discontinued = Brand(
        brand_name="Discontinued Brand",
        manufacturer_id=mfr2.manufacturer_id,
        is_discontinued=True,
    )
    medicine_db.add_all([brand_active, brand_discontinued])
    await medicine_db.flush()

    # Same composition
    comp1 = BrandComposition(
        brand_id=brand_active.brand_id,
        salt_strength_id=strength.salt_strength_id,
        sequence=1,
    )
    comp2 = BrandComposition(
        brand_id=brand_discontinued.brand_id,
        salt_strength_id=strength.salt_strength_id,
        sequence=1,
    )
    medicine_db.add_all([comp1, comp2])
    await medicine_db.flush()

    # Get alternatives
    alternatives = await BrandService.get_brand_alternatives(
        medicine_db,
        brand_active.brand_id,
    )

    # Should include discontinued brand
    assert len(alternatives) == 1
    assert alternatives[0].brand_id == brand_discontinued.brand_id
    assert alternatives[0].is_discontinued is True
