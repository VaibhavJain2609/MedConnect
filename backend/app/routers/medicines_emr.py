"""EMR Medicine API endpoints - unified search and navigation."""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_medicine_db
from app.services.salt_service import SaltService
from app.services.brand_service import BrandService, ManufacturerService
from app.services.medicine_search_service import MedicineSearchService
from app.schemas.medicine_emr import (
    SaltResponse,
    SaltListResponse,
    BrandResponse,
    BrandListResponse,
    UnifiedSearchResponse,
    ManufacturerResponse,
    SaltStrengthResponse,
    BrandCompositionResponse,
)

router = APIRouter(tags=["medicines"])


# ============================================================================
# UNIFIED SEARCH
# ============================================================================

@router.get("/medicines/search", response_model=UnifiedSearchResponse)
async def search_medicines(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_medicine_db),
):
    """
    Unified search across salts and brands.
    Returns both salts and brands matching the query.
    """
    result = await MedicineSearchService.search_all(db, search=q, limit=limit)
    return result


@router.get("/medicines/autocomplete")
async def autocomplete_medicines(
    q: str = Query(..., min_length=2, description="Search query (minimum 2 characters)"),
    db: AsyncSession = Depends(get_medicine_db),
):
    """
    Optimized autocomplete endpoint for prescription forms.

    Returns top 10 brand matches with essential info only:
    - Brand name
    - Salt composition
    - Manufacturer
    - Brand ID
    - Dosage form and strength (for auto-fill)

    Prioritizes exact matches, then prefix matches, then contains matches.
    """
    from sqlalchemy import select, case, func
    from sqlalchemy.orm import selectinload, joinedload
    from app.models.medicine.commercial import Brand, BrandComposition, Manufacturer
    from app.models.medicine.salts import SaltStrength, Salt

    # Query brands with smart ranking:
    # 1. Exact match (highest priority)
    # 2. Starts with query (prefix match)
    # 3. Contains query (lowest priority)
    q_lower = q.lower()

    # Ranking logic using CASE
    rank_expr = case(
        (func.lower(Brand.brand_name) == q_lower, 1),  # Exact match
        (func.lower(Brand.brand_name).startswith(q_lower), 2),  # Prefix match
        else_=3  # Contains match
    )

    query = (
        select(Brand)
        .options(
            joinedload(Brand.manufacturer),
            selectinload(Brand.compositions)
            .joinedload(BrandComposition.salt_strength)
            .joinedload(SaltStrength.salt),
        )
        .where(
            func.lower(Brand.brand_name).like(f"%{q_lower}%"),
            Brand.is_discontinued == False
        )
        .order_by(rank_expr, Brand.brand_name)
        .limit(20)  # Fetch 20 to have better results after ranking
    )

    result = await db.execute(query)
    brands = result.unique().scalars().all()

    # Build concise response with dosage info for auto-fill
    autocomplete_results = []
    for brand in brands[:10]:  # Return top 10 after ranking
        # Build salt composition string
        salt_comp = " + ".join([
            f"{bc.salt_strength.salt.salt_name} ({bc.salt_strength.display_strength})"
            for bc in sorted(brand.compositions, key=lambda x: x.sequence)
        ])

        autocomplete_results.append({
            "brand_id": str(brand.brand_id),
            "brand_name": brand.brand_name,
            "salt_composition": salt_comp,
            "manufacturer_name": brand.manufacturer.manufacturer_name,
            "manufacturer_id": str(brand.manufacturer_id),
            "dosage_form": brand.dosage_form or "",
            "strength": salt_comp,  # Use salt composition as strength display
        })

    return {"results": autocomplete_results, "count": len(autocomplete_results)}


# ============================================================================
# SALTS
# ============================================================================

@router.get("/salts", response_model=SaltListResponse)
async def list_salts(
    search: str | None = None,
    chemical_class_id: UUID | None = None,
    therapeutic_class_id: UUID | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_medicine_db),
):
    """List salts (active pharmaceutical ingredients) with filters."""
    offset = (page - 1) * limit
    salts, total = await SaltService.search_salts(
        db,
        search=search,
        chemical_class_id=chemical_class_id,
        therapeutic_class_id=therapeutic_class_id,
        limit=limit,
        offset=offset,
    )

    pages = (total + limit - 1) // limit

    return SaltListResponse(
        salts=salts,
        total=total,
        page=page,
        pages=pages,
    )


@router.get("/salts/{salt_id}", response_model=SaltResponse)
async def get_salt(
    salt_id: UUID,
    db: AsyncSession = Depends(get_medicine_db),
):
    """Get salt details by ID."""
    salt = await SaltService.get_salt_by_id(db, salt_id)
    if not salt:
        raise HTTPException(status_code=404, detail="Salt not found")
    return salt


@router.get("/salts/{salt_id}/strengths", response_model=list[SaltStrengthResponse])
async def get_salt_strengths(
    salt_id: UUID,
    db: AsyncSession = Depends(get_medicine_db),
):
    """Get all available strengths for a salt."""
    strengths = await SaltService.get_salt_strengths(db, salt_id)
    return strengths


@router.get("/salts/{salt_id}/brands", response_model=list[dict])
async def get_brands_by_salt(
    salt_id: UUID,
    strength_value: float | None = None,
    strength_unit: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_medicine_db),
):
    """
    Get all brands containing this salt.
    Optionally filter by specific strength.
    """
    brands = await MedicineSearchService.get_brands_by_salt(
        db,
        salt_id=salt_id,
        strength_value=strength_value,
        strength_unit=strength_unit,
        limit=limit,
    )
    return brands


# ============================================================================
# BRANDS
# ============================================================================

@router.get("/brands", response_model=BrandListResponse)
async def list_brands(
    search: str | None = None,
    salt_id: UUID | None = None,
    manufacturer_id: UUID | None = None,
    include_discontinued: bool = False,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_medicine_db),
):
    """List brands (commercial medicines) with filters."""
    offset = (page - 1) * limit
    brands, total = await BrandService.search_brands(
        db,
        search=search,
        salt_id=salt_id,
        manufacturer_id=manufacturer_id,
        include_discontinued=include_discontinued,
        limit=limit,
        offset=offset,
    )

    pages = (total + limit - 1) // limit

    # Convert to response format
    brand_responses = []
    for brand in brands:
        compositions = [
            BrandCompositionResponse(
                composition_id=bc.composition_id,
                salt_name=bc.salt_strength.salt.salt_name,
                strength_value=bc.salt_strength.strength_value,
                strength_unit=bc.salt_strength.strength_unit,
                display_strength=bc.salt_strength.display_strength,
                sequence=bc.sequence,
            )
            for bc in sorted(brand.compositions, key=lambda x: x.sequence)
        ]

        brand_responses.append(
            BrandResponse(
                brand_id=brand.brand_id,
                brand_name=brand.brand_name,
                manufacturer=brand.manufacturer,
                compositions=compositions,
                salt_composition=brand.salt_composition,
                is_discontinued=brand.is_discontinued,
                drug_type=brand.drug_type,
                launch_date=brand.launch_date,
                discontinuation_date=brand.discontinuation_date,
                created_at=brand.created_at,
                updated_at=brand.updated_at,
            )
        )

    return BrandListResponse(
        brands=brand_responses,
        total=total,
        page=page,
        pages=pages,
    )


@router.get("/brands/{brand_id}", response_model=BrandResponse)
async def get_brand(
    brand_id: UUID,
    db: AsyncSession = Depends(get_medicine_db),
):
    """Get brand details by ID."""
    brand = await BrandService.get_brand_by_id(db, brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    compositions = [
        BrandCompositionResponse(
            composition_id=bc.composition_id,
            salt_name=bc.salt_strength.salt.salt_name,
            strength_value=bc.salt_strength.strength_value,
            strength_unit=bc.salt_strength.strength_unit,
            display_strength=bc.salt_strength.display_strength,
            sequence=bc.sequence,
        )
        for bc in sorted(brand.compositions, key=lambda x: x.sequence)
    ]

    return BrandResponse(
        brand_id=brand.brand_id,
        brand_name=brand.brand_name,
        manufacturer=brand.manufacturer,
        compositions=compositions,
        salt_composition=brand.salt_composition,
        is_discontinued=brand.is_discontinued,
        drug_type=brand.drug_type,
        launch_date=brand.launch_date,
        discontinuation_date=brand.discontinuation_date,
        created_at=brand.created_at,
        updated_at=brand.updated_at,
    )


@router.get("/brands/{brand_id}/alternatives", response_model=list[BrandResponse])
async def get_brand_alternatives(
    brand_id: UUID,
    db: AsyncSession = Depends(get_medicine_db),
):
    """Get alternative brands with same salt composition."""
    alternatives = await BrandService.get_brand_alternatives(db, brand_id)

    brand_responses = []
    for brand in alternatives:
        compositions = [
            BrandCompositionResponse(
                composition_id=bc.composition_id,
                salt_name=bc.salt_strength.salt.salt_name,
                strength_value=bc.salt_strength.strength_value,
                strength_unit=bc.salt_strength.strength_unit,
                display_strength=bc.salt_strength.display_strength,
                sequence=bc.sequence,
            )
            for bc in sorted(brand.compositions, key=lambda x: x.sequence)
        ]

        brand_responses.append(
            BrandResponse(
                brand_id=brand.brand_id,
                brand_name=brand.brand_name,
                manufacturer=brand.manufacturer,
                compositions=compositions,
                salt_composition=brand.salt_composition,
                is_discontinued=brand.is_discontinued,
                drug_type=brand.drug_type,
                launch_date=brand.launch_date,
                discontinuation_date=brand.discontinuation_date,
                created_at=brand.created_at,
                updated_at=brand.updated_at,
            )
        )

    return brand_responses


# ============================================================================
# MANUFACTURERS
# ============================================================================

@router.get("/manufacturers", response_model=list[ManufacturerResponse])
async def list_manufacturers(
    search: str | None = None,
    is_active: bool | None = True,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_medicine_db),
):
    """List manufacturers."""
    manufacturers, total = await ManufacturerService.search_manufacturers(
        db,
        search=search,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )
    return manufacturers


@router.get("/manufacturers/{manufacturer_id}", response_model=ManufacturerResponse)
async def get_manufacturer(
    manufacturer_id: UUID,
    db: AsyncSession = Depends(get_medicine_db),
):
    """Get manufacturer details by ID."""
    manufacturer = await ManufacturerService.get_manufacturer_by_id(db, manufacturer_id)
    if not manufacturer:
        raise HTTPException(status_code=404, detail="Manufacturer not found")
    return manufacturer
