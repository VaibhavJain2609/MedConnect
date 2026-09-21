"""EMR Medicine API endpoints - unified search and navigation."""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_medicine_db
from app.dependencies import get_current_user
from app.services import medicine_cache
from app.services.salt_service import SaltService
from app.services.brand_service import BrandService, ManufacturerService
from app.services.medicine_search_service import MedicineSearchService
from app.utils.barcode import is_valid_barcode, normalize_barcode
from app.schemas.medicine_emr import (
    SaltResponse,
    SaltListResponse,
    BrandResponse,
    BrandListResponse,
    BrandPackagingResponse,
    PackFormResponse,
    UnifiedSearchResponse,
    ManufacturerResponse,
    SaltStrengthResponse,
    BrandCompositionResponse,
    SaltSideEffectItem,
    SaltContraindicationItem,
)

router = APIRouter(
    tags=["medicines"],
    dependencies=[Depends(get_current_user)],
)


def _packaging_responses(brand) -> list[BrandPackagingResponse]:
    """Flatten a brand's eager-loaded packaging rows to response models."""
    return [
        BrandPackagingResponse(
            brand_pack_id=pack.brand_pack_id,
            pack_form_id=pack.pack_form_id,
            pack_form_name=pack.pack_form.form_name if pack.pack_form else None,
            quantity=pack.quantity,
            pack_type=pack.pack_type,
            sku=pack.sku,
            barcode=pack.barcode,
            is_primary_pack=pack.is_primary_pack,
        )
        for pack in brand.packaging
    ]


def _brand_detail_response(
    brand,
    side_effects: list[SaltSideEffectItem] | None = None,
) -> BrandResponse:
    """Build the brand detail response (compositions + packaging + side effects).

    Requires manufacturer, compositions (→ salt_strength → salt) and
    packaging (→ pack_form) to be eager-loaded on ``brand``.
    """
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
        packaging=_packaging_responses(brand),
        salt_composition=brand.salt_composition,
        side_effects=side_effects or [],
        is_discontinued=brand.is_discontinued,
        drug_type=brand.drug_type,
        launch_date=brand.launch_date,
        discontinuation_date=brand.discontinuation_date,
        created_at=brand.created_at,
        updated_at=brand.updated_at,
    )


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
    cache_key = medicine_cache.make_key("search", q.strip().lower(), limit)
    cached = await medicine_cache.get_cached(cache_key)
    if cached is not None:
        return cached

    result = await MedicineSearchService.search_all(db, search=q, limit=limit)
    await medicine_cache.set_cached(cache_key, result)
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
    from sqlalchemy import select, case
    from sqlalchemy.orm import selectinload, joinedload
    from app.models.medicine.commercial import Brand, BrandComposition, Manufacturer
    from app.models.medicine.salts import SaltStrength, Salt

    cache_key = medicine_cache.make_key("autocomplete", q.strip().lower())
    cached = await medicine_cache.get_cached(cache_key)
    if cached is not None:
        return cached

    # Query brands with smart ranking:
    # 1. Exact match (highest priority)
    # 2. Starts with query (prefix match)
    # 3. Contains query (lowest priority)
    # ILIKE is used (not lower() + LIKE) so the pg_trgm GIN index on
    # brand_name can be used instead of a sequential scan.
    rank_expr = case(
        (Brand.brand_name.ilike(q), 1),  # Exact match (case-insensitive)
        (Brand.brand_name.ilike(f"{q}%"), 2),  # Prefix match
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
            Brand.brand_name.ilike(f"%{q}%"),
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
        sorted_compositions = sorted(brand.compositions, key=lambda x: x.sequence)
        salt_comp = " + ".join([
            f"{bc.salt_strength.salt.salt_name} ({bc.salt_strength.display_strength})"
            for bc in sorted_compositions
        ])

        # Get the primary salt_id (first composition by sequence) for interaction checks
        primary_salt_id = None
        if sorted_compositions:
            primary_salt_id = str(sorted_compositions[0].salt_strength.salt.salt_id)

        autocomplete_results.append({
            "brand_id": str(brand.brand_id),
            "brand_name": brand.brand_name,
            "salt_composition": salt_comp,
            "salt_id": primary_salt_id,  # Primary salt for drug interaction checking
            "manufacturer_name": brand.manufacturer.manufacturer_name,
            "manufacturer_id": str(brand.manufacturer_id),
            "dosage_form": brand.drug_type.title() if brand.drug_type else "Medicine",
            "strength": salt_comp,  # Use salt composition as strength display
        })

    response = {"results": autocomplete_results, "count": len(autocomplete_results)}
    await medicine_cache.set_cached(cache_key, response)
    return response


# ============================================================================
# BARCODE LOOKUP & PACK FORMS
# ============================================================================

@router.get("/medicines/by-barcode/{code}", response_model=BrandResponse)
async def get_medicine_by_barcode(
    code: str,
    db: AsyncSession = Depends(get_medicine_db),
):
    """
    Look up a brand by pack barcode (GTIN/EAN).

    Barcodes are stored per-pack on ``brand_packaging.barcode`` (Indian packs
    carry a barcode per pack size). The code must be digits only, 8-14
    characters; surrounding/embedded whitespace is stripped. When multiple
    brands share a barcode (non-unique index by design), the first by brand
    name is returned — its ``packaging`` list carries all packs so callers
    can disambiguate.
    """
    normalized = normalize_barcode(code)
    if normalized is None or not is_valid_barcode(normalized):
        # dict detail passes through the 422 handler untouched (see main.py)
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "INVALID_BARCODE",
                    "message": "Invalid barcode format — expected 8-14 digits (GTIN/EAN)",
                }
            },
        )

    cache_key = medicine_cache.make_key("barcode", normalized)
    cached = await medicine_cache.get_cached(cache_key)
    if cached is not None:
        return cached

    brands = await BrandService.get_brands_by_barcode(db, normalized)
    if not brands:
        raise HTTPException(status_code=404, detail="No medicine found for this barcode")

    response = _brand_detail_response(brands[0])
    await medicine_cache.set_cached(
        cache_key, response, ttl=medicine_cache.DETAIL_TTL_SECONDS
    )
    return response


@router.get("/pack-forms", response_model=list[PackFormResponse])
async def list_pack_forms(
    db: AsyncSession = Depends(get_medicine_db),
):
    """List dosage/pack forms (dropdown source for pack/barcode management UIs)."""
    from sqlalchemy import select
    from app.models.medicine.packaging import PackForm

    cache_key = medicine_cache.make_key("pack-forms")
    cached = await medicine_cache.get_cached(cache_key)
    if cached is not None:
        return cached

    result = await db.execute(select(PackForm).order_by(PackForm.form_name))
    items = [PackFormResponse.model_validate(pf) for pf in result.scalars().all()]
    await medicine_cache.set_cached(
        cache_key, items, ttl=medicine_cache.DETAIL_TTL_SECONDS
    )
    return items


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
    cache_key = medicine_cache.make_key(
        "salts",
        (search or "-").strip().lower(),
        chemical_class_id or "-",
        therapeutic_class_id or "-",
        page,
        limit,
    )
    cached = await medicine_cache.get_cached(cache_key)
    if cached is not None:
        return cached

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

    # The list view doesn't eagerly load side_effects/contraindications (those
    # are detail-only). Construct each item explicitly with empty lists so
    # Pydantic doesn't trigger an async lazy load through from_attributes.
    salt_items = [
        SaltResponse(
            salt_id=s.salt_id,
            salt_name=s.salt_name,
            description=s.description,
            chemical_formula=s.chemical_formula,
            habit_forming=s.habit_forming,
            prescription_required=s.prescription_required,
            schedule=s.schedule,
            pregnancy_category=s.pregnancy_category,
            lactation_safe=s.lactation_safe,
            lactation_notes=s.lactation_notes,
            chemical_class=s.chemical_class,
            therapeutic_class=s.therapeutic_class,
            action_class=s.action_class,
            strengths=s.strengths,
            side_effects=[],
            contraindications=[],
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in salts
    ]

    response = SaltListResponse(
        salts=salt_items,
        total=total,
        page=page,
        pages=pages,
    )
    await medicine_cache.set_cached(cache_key, response)
    return response


@router.get("/salts/{salt_id}", response_model=SaltResponse)
async def get_salt(
    salt_id: UUID,
    db: AsyncSession = Depends(get_medicine_db),
):
    """Get salt details by ID, including side effects and contraindications."""
    cache_key = medicine_cache.make_key("salt", salt_id)
    cached = await medicine_cache.get_cached(cache_key)
    if cached is not None:
        return cached

    salt = await SaltService.get_salt_by_id(db, salt_id)
    if not salt:
        raise HTTPException(status_code=404, detail="Salt not found")

    # Flatten the join-table rows so the API exposes a SideEffect-shaped item
    # (with overrides from SaltSideEffect.frequency/notes) rather than the
    # raw association-object structure.
    side_effects = [
        SaltSideEffectItem(
            side_effect_id=sse.side_effect.side_effect_id,
            side_effect_name=sse.side_effect.side_effect_name,
            severity=sse.side_effect.severity,
            frequency=sse.frequency or sse.side_effect.frequency,
            description=sse.side_effect.description,
            notes=sse.notes,
        )
        for sse in salt.side_effects
        if sse.side_effect is not None
    ]
    contraindications = [
        SaltContraindicationItem(
            contraindication_id=sc.contraindication.contraindication_id,
            contraindication_name=sc.contraindication.contraindication_name,
            description=sc.contraindication.description,
            icd10_code=sc.contraindication.icd10_code,
            severity=sc.severity or sc.contraindication.severity,
            notes=sc.notes,
        )
        for sc in salt.contraindications
        if sc.contraindication is not None
    ]

    response = SaltResponse(
        salt_id=salt.salt_id,
        salt_name=salt.salt_name,
        description=salt.description,
        chemical_formula=salt.chemical_formula,
        habit_forming=salt.habit_forming,
        prescription_required=salt.prescription_required,
        schedule=salt.schedule,
        pregnancy_category=salt.pregnancy_category,
        lactation_safe=salt.lactation_safe,
        lactation_notes=salt.lactation_notes,
        chemical_class=salt.chemical_class,
        therapeutic_class=salt.therapeutic_class,
        action_class=salt.action_class,
        strengths=salt.strengths,
        side_effects=side_effects,
        contraindications=contraindications,
        created_at=salt.created_at,
        updated_at=salt.updated_at,
    )
    await medicine_cache.set_cached(
        cache_key, response, ttl=medicine_cache.DETAIL_TTL_SECONDS
    )
    return response


@router.get("/salts/{salt_id}/strengths", response_model=list[SaltStrengthResponse])
async def get_salt_strengths(
    salt_id: UUID,
    db: AsyncSession = Depends(get_medicine_db),
):
    """Get all available strengths for a salt."""
    cache_key = medicine_cache.make_key("salt", salt_id, "strengths")
    cached = await medicine_cache.get_cached(cache_key)
    if cached is not None:
        return cached

    strengths = await SaltService.get_salt_strengths(db, salt_id)
    # Validate to response models so the cached payload is JSON-safe.
    items = [SaltStrengthResponse.model_validate(s) for s in strengths]
    await medicine_cache.set_cached(
        cache_key, items, ttl=medicine_cache.DETAIL_TTL_SECONDS
    )
    return items


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
    cache_key = medicine_cache.make_key(
        "salt", salt_id, "brands", strength_value or "-", strength_unit or "-", limit
    )
    cached = await medicine_cache.get_cached(cache_key)
    if cached is not None:
        return cached

    brands = await MedicineSearchService.get_brands_by_salt(
        db,
        salt_id=salt_id,
        strength_value=strength_value,
        strength_unit=strength_unit,
        limit=limit,
    )
    await medicine_cache.set_cached(
        cache_key, brands, ttl=medicine_cache.DETAIL_TTL_SECONDS
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
    cache_key = medicine_cache.make_key(
        "brands",
        (search or "-").strip().lower(),
        salt_id or "-",
        manufacturer_id or "-",
        include_discontinued,
        page,
        limit,
    )
    cached = await medicine_cache.get_cached(cache_key)
    if cached is not None:
        return cached

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

    response = BrandListResponse(
        brands=brand_responses,
        total=total,
        page=page,
        pages=pages,
    )
    await medicine_cache.set_cached(cache_key, response)
    return response


@router.get("/brands/{brand_id}", response_model=BrandResponse)
async def get_brand(
    brand_id: UUID,
    db: AsyncSession = Depends(get_medicine_db),
):
    """Get brand details by ID, with side effects aggregated across composition salts."""
    cache_key = medicine_cache.make_key("brand", brand_id)
    cached = await medicine_cache.get_cached(cache_key)
    if cached is not None:
        return cached

    brand = await BrandService.get_brand_by_id(db, brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    # Side effects come straight from the brand_side_effects mapping —
    # the per-row data shipped with the dataset. No salt-level aggregation.
    side_effects: list[SaltSideEffectItem] = [
        SaltSideEffectItem(
            side_effect_id=bse.side_effect.side_effect_id,
            side_effect_name=bse.side_effect.side_effect_name,
            severity=bse.side_effect.severity,
            frequency=bse.side_effect.frequency,
            description=bse.side_effect.description,
            notes=None,
        )
        for bse in brand.side_effects
        if bse.side_effect is not None
    ]
    side_effects.sort(key=lambda s: s.side_effect_name.lower())

    response = _brand_detail_response(brand, side_effects=side_effects)
    await medicine_cache.set_cached(
        cache_key, response, ttl=medicine_cache.DETAIL_TTL_SECONDS
    )
    return response


@router.get("/brands/{brand_id}/alternatives", response_model=list[BrandResponse])
async def get_brand_alternatives(
    brand_id: UUID,
    db: AsyncSession = Depends(get_medicine_db),
):
    """Get alternative brands with same salt composition."""
    cache_key = medicine_cache.make_key("brand", brand_id, "alternatives")
    cached = await medicine_cache.get_cached(cache_key)
    if cached is not None:
        return cached

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

    await medicine_cache.set_cached(
        cache_key, brand_responses, ttl=medicine_cache.DETAIL_TTL_SECONDS
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
    cache_key = medicine_cache.make_key(
        "manufacturers",
        (search or "-").strip().lower(),
        is_active if is_active is not None else "-",
        limit,
        offset,
    )
    cached = await medicine_cache.get_cached(cache_key)
    if cached is not None:
        return cached

    manufacturers, total = await ManufacturerService.search_manufacturers(
        db,
        search=search,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )
    # Validate to response models so the cached payload is JSON-safe.
    items = [ManufacturerResponse.model_validate(m) for m in manufacturers]
    await medicine_cache.set_cached(cache_key, items)
    return items


@router.get("/manufacturers/{manufacturer_id}", response_model=ManufacturerResponse)
async def get_manufacturer(
    manufacturer_id: UUID,
    db: AsyncSession = Depends(get_medicine_db),
):
    """Get manufacturer details by ID."""
    cache_key = medicine_cache.make_key("manufacturer", manufacturer_id)
    cached = await medicine_cache.get_cached(cache_key)
    if cached is not None:
        return cached

    manufacturer = await ManufacturerService.get_manufacturer_by_id(db, manufacturer_id)
    if not manufacturer:
        raise HTTPException(status_code=404, detail="Manufacturer not found")
    item = ManufacturerResponse.model_validate(manufacturer)
    await medicine_cache.set_cached(
        cache_key, item, ttl=medicine_cache.DETAIL_TTL_SECONDS
    )
    return item
