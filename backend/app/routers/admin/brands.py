"""Admin endpoints for managing brands (commercial medicines) in EMR schema."""

from typing import Optional
from uuid import UUID
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, Field
import re

from app.database import get_medicine_db
from app.dependencies import require_admin
from app.models.user import User
from app.models.medicine.commercial import Brand, Manufacturer, BrandComposition
from app.models.medicine.salts import SaltStrength


# Pydantic schemas for request/response
class BrandCompositionInput(BaseModel):
    """Input for brand composition (salt + strength)."""
    salt_strength_id: UUID
    sequence: int = Field(default=1, ge=1)


class BrandCreateRequest(BaseModel):
    """Request schema for creating a brand."""
    brand_name: str = Field(..., min_length=1, max_length=255)
    manufacturer_id: UUID
    is_discontinued: bool = False
    drug_type: str = Field(default="allopathy", pattern="^(allopathy|ayurveda|homeopathy)$")
    launch_date: Optional[date] = None
    discontinuation_date: Optional[date] = None
    ndhm_code: Optional[str] = Field(None, max_length=50)
    compositions: list[BrandCompositionInput] = Field(..., min_items=1)


class BrandUpdateRequest(BaseModel):
    """Request schema for updating a brand."""
    brand_name: Optional[str] = Field(None, min_length=1, max_length=255)
    manufacturer_id: Optional[UUID] = None
    is_discontinued: Optional[bool] = None
    drug_type: Optional[str] = Field(None, pattern="^(allopathy|ayurveda|homeopathy)$")
    launch_date: Optional[date] = None
    discontinuation_date: Optional[date] = None
    ndhm_code: Optional[str] = Field(None, max_length=50)
    compositions: Optional[list[BrandCompositionInput]] = None


class BrandResponse(BaseModel):
    """Response schema for brand."""
    brand_id: UUID
    brand_name: str
    manufacturer_id: UUID
    manufacturer_name: str
    salt_composition: str
    is_discontinued: bool
    drug_type: str
    launch_date: Optional[date]
    discontinuation_date: Optional[date]
    ndhm_code: Optional[str]

    class Config:
        from_attributes = True


router = APIRouter(
    prefix="/admin/brands",
    tags=["admin-brands"],
    dependencies=[Depends(require_admin)]
)


@router.post("", response_model=BrandResponse, status_code=status.HTTP_201_CREATED)
async def create_brand(
    brand_data: BrandCreateRequest,
    db: AsyncSession = Depends(get_medicine_db),
    admin: User = Depends(require_admin),
):
    """
    Create a new brand (commercial medicine) - Admin only.

    - Validates manufacturer exists
    - Validates all salt_strength_ids exist
    - Checks for duplicate brand+manufacturer combination
    - Creates brand with compositions
    """
    # Check manufacturer exists
    manufacturer_result = await db.execute(
        select(Manufacturer).where(Manufacturer.manufacturer_id == brand_data.manufacturer_id)
    )
    manufacturer = manufacturer_result.scalar_one_or_none()
    if not manufacturer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Manufacturer {brand_data.manufacturer_id} not found"
        )

    # Check for duplicate brand+manufacturer
    existing_result = await db.execute(
        select(Brand).where(
            Brand.brand_name == brand_data.brand_name,
            Brand.manufacturer_id == brand_data.manufacturer_id
        )
    )
    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Brand '{brand_data.brand_name}' already exists for this manufacturer"
        )

    # Validate all salt_strength_ids exist
    salt_strength_ids = [comp.salt_strength_id for comp in brand_data.compositions]
    salt_strengths_result = await db.execute(
        select(SaltStrength).where(SaltStrength.salt_strength_id.in_(salt_strength_ids))
    )
    found_strengths = salt_strengths_result.scalars().all()
    if len(found_strengths) != len(salt_strength_ids):
        found_ids = {s.salt_strength_id for s in found_strengths}
        missing_ids = set(salt_strength_ids) - found_ids
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Salt strengths not found: {missing_ids}"
        )

    # Create brand
    new_brand = Brand(
        brand_name=brand_data.brand_name,
        manufacturer_id=brand_data.manufacturer_id,
        is_discontinued=brand_data.is_discontinued,
        drug_type=brand_data.drug_type,
        launch_date=brand_data.launch_date,
        discontinuation_date=brand_data.discontinuation_date,
        ndhm_code=brand_data.ndhm_code,
    )
    db.add(new_brand)
    await db.flush()  # Get brand_id

    # Create compositions
    for comp_data in brand_data.compositions:
        composition = BrandComposition(
            brand_id=new_brand.brand_id,
            salt_strength_id=comp_data.salt_strength_id,
            sequence=comp_data.sequence,
        )
        db.add(composition)

    await db.commit()

    # Reload with relationships for response
    result = await db.execute(
        select(Brand)
        .options(
            selectinload(Brand.manufacturer),
            selectinload(Brand.compositions).selectinload(BrandComposition.salt_strength)
        )
        .where(Brand.brand_id == new_brand.brand_id)
    )
    created_brand = result.scalar_one()

    return BrandResponse(
        brand_id=created_brand.brand_id,
        brand_name=created_brand.brand_name,
        manufacturer_id=created_brand.manufacturer_id,
        manufacturer_name=created_brand.manufacturer.manufacturer_name,
        salt_composition=created_brand.salt_composition,
        is_discontinued=created_brand.is_discontinued,
        drug_type=created_brand.drug_type,
        launch_date=created_brand.launch_date,
        discontinuation_date=created_brand.discontinuation_date,
        ndhm_code=created_brand.ndhm_code,
    )


@router.put("/{brand_id}", response_model=BrandResponse)
async def update_brand(
    brand_id: UUID,
    brand_data: BrandUpdateRequest,
    db: AsyncSession = Depends(get_medicine_db),
    admin: User = Depends(require_admin),
):
    """
    Update a brand - Admin only.

    - Partial updates supported
    - If compositions provided, replaces all existing compositions
    - Validates manufacturer and salt_strength_ids if changed
    """
    # Fetch existing brand
    result = await db.execute(
        select(Brand)
        .options(selectinload(Brand.compositions))
        .where(Brand.brand_id == brand_id)
    )
    brand = result.scalar_one_or_none()
    if not brand:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Brand {brand_id} not found"
        )

    # Update basic fields
    if brand_data.brand_name is not None:
        # Check for duplicate if name or manufacturer changed
        if (brand_data.brand_name != brand.brand_name or
            (brand_data.manufacturer_id and brand_data.manufacturer_id != brand.manufacturer_id)):

            check_manufacturer_id = brand_data.manufacturer_id or brand.manufacturer_id
            existing_result = await db.execute(
                select(Brand).where(
                    Brand.brand_name == brand_data.brand_name,
                    Brand.manufacturer_id == check_manufacturer_id,
                    Brand.brand_id != brand_id
                )
            )
            if existing_result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Brand '{brand_data.brand_name}' already exists for this manufacturer"
                )

        brand.brand_name = brand_data.brand_name

    if brand_data.manufacturer_id is not None:
        # Validate manufacturer exists
        manufacturer_result = await db.execute(
            select(Manufacturer).where(Manufacturer.manufacturer_id == brand_data.manufacturer_id)
        )
        if not manufacturer_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Manufacturer {brand_data.manufacturer_id} not found"
            )
        brand.manufacturer_id = brand_data.manufacturer_id

    if brand_data.is_discontinued is not None:
        brand.is_discontinued = brand_data.is_discontinued

    if brand_data.drug_type is not None:
        brand.drug_type = brand_data.drug_type

    if brand_data.launch_date is not None:
        brand.launch_date = brand_data.launch_date

    if brand_data.discontinuation_date is not None:
        brand.discontinuation_date = brand_data.discontinuation_date

    if brand_data.ndhm_code is not None:
        brand.ndhm_code = brand_data.ndhm_code

    # Update compositions if provided
    if brand_data.compositions is not None:
        # Validate salt_strength_ids
        salt_strength_ids = [comp.salt_strength_id for comp in brand_data.compositions]
        salt_strengths_result = await db.execute(
            select(SaltStrength).where(SaltStrength.salt_strength_id.in_(salt_strength_ids))
        )
        found_strengths = salt_strengths_result.scalars().all()
        if len(found_strengths) != len(salt_strength_ids):
            found_ids = {s.salt_strength_id for s in found_strengths}
            missing_ids = set(salt_strength_ids) - found_ids
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Salt strengths not found: {missing_ids}"
            )

        # Delete existing compositions
        for existing_comp in brand.compositions:
            await db.delete(existing_comp)

        # Create new compositions
        for comp_data in brand_data.compositions:
            composition = BrandComposition(
                brand_id=brand_id,
                salt_strength_id=comp_data.salt_strength_id,
                sequence=comp_data.sequence,
            )
            db.add(composition)

    await db.commit()

    # Reload with relationships for response
    result = await db.execute(
        select(Brand)
        .options(
            selectinload(Brand.manufacturer),
            selectinload(Brand.compositions).selectinload(BrandComposition.salt_strength)
        )
        .where(Brand.brand_id == brand_id)
    )
    updated_brand = result.scalar_one()

    return BrandResponse(
        brand_id=updated_brand.brand_id,
        brand_name=updated_brand.brand_name,
        manufacturer_id=updated_brand.manufacturer_id,
        manufacturer_name=updated_brand.manufacturer.manufacturer_name,
        salt_composition=updated_brand.salt_composition,
        is_discontinued=updated_brand.is_discontinued,
        drug_type=updated_brand.drug_type,
        launch_date=updated_brand.launch_date,
        discontinuation_date=updated_brand.discontinuation_date,
        ndhm_code=updated_brand.ndhm_code,
    )


@router.delete("/{brand_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_brand(
    brand_id: UUID,
    db: AsyncSession = Depends(get_medicine_db),
    admin: User = Depends(require_admin),
):
    """
    Delete a brand - Admin only.

    - Cascade deletes brand compositions
    - Soft delete preferred in production (set is_discontinued=True instead)
    """
    result = await db.execute(
        select(Brand).where(Brand.brand_id == brand_id)
    )
    brand = result.scalar_one_or_none()
    if not brand:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Brand {brand_id} not found"
        )

    await db.delete(brand)
    await db.commit()
    return None


class BulkImportRow(BaseModel):
    """Single row in bulk import CSV."""
    brand_name: str
    manufacturer_name: str
    salt_compositions: str  # Format: "Salt1(strength1) + Salt2(strength2)"
    drug_type: str = "allopathy"
    is_discontinued: bool = False
    launch_date: Optional[str] = None


class BulkImportResult(BaseModel):
    """Result for a single row."""
    row: int
    brand_name: str
    status: str  # "success", "error", "skipped"
    message: str
    brand_id: Optional[str] = None


class BulkImportResponse(BaseModel):
    """Response for bulk import operation."""
    total: int
    successful: int
    failed: int
    skipped: int
    results: list[BulkImportResult]


@router.post("/bulk-import", response_model=BulkImportResponse)
async def bulk_import_brands(
    rows: list[BulkImportRow],
    db: AsyncSession = Depends(get_medicine_db),
    admin: User = Depends(require_admin),
):
    """
    Bulk import brands from CSV data - Admin only.

    Expected CSV format:
    brand_name,manufacturer_name,salt_compositions,drug_type,is_discontinued,launch_date
    Crocin 500,GSK,Paracetamol(500mg),allopathy,false,2020-01-01

    - Creates manufacturers if they don't exist
    - Creates salts and strengths if they don't exist
    - Skips duplicate brands
    - Returns detailed results for each row
    """
    results: list[BulkImportResult] = []
    successful = 0
    failed = 0
    skipped = 0

    for idx, row in enumerate(rows, start=1):
        try:
            # Find or create manufacturer
            mfr_result = await db.execute(
                select(Manufacturer).where(
                    func.lower(Manufacturer.manufacturer_name) == row.manufacturer_name.lower()
                )
            )
            manufacturer = mfr_result.scalar_one_or_none()

            if not manufacturer:
                manufacturer = Manufacturer(
                    manufacturer_name=row.manufacturer_name,
                    is_active=True,
                )
                db.add(manufacturer)
                await db.flush()

            # Check for existing brand
            existing_result = await db.execute(
                select(Brand).where(
                    func.lower(Brand.brand_name) == row.brand_name.lower(),
                    Brand.manufacturer_id == manufacturer.manufacturer_id,
                )
            )
            if existing_result.scalar_one_or_none():
                results.append(BulkImportResult(
                    row=idx,
                    brand_name=row.brand_name,
                    status="skipped",
                    message="Brand already exists for this manufacturer",
                ))
                skipped += 1
                continue

            # Parse salt compositions (simplified - production would need robust parsing)
            # Format: "Paracetamol(500mg) + Caffeine(65mg)"
            composition_parts = [p.strip() for p in row.salt_compositions.split("+")]
            composition_data: list[BrandCompositionInput] = []

            for seq, comp_str in enumerate(composition_parts, start=1):
                # Extract salt name and strength
                if "(" not in comp_str or ")" not in comp_str:
                    raise ValueError(f"Invalid composition format: {comp_str}")

                salt_name = comp_str[:comp_str.index("(")].strip()
                strength_str = comp_str[comp_str.index("(") + 1:comp_str.index(")")].strip()

                # Find or create salt
                salt_result = await db.execute(
                    select(Salt).where(func.lower(Salt.salt_name) == salt_name.lower())
                )
                salt = salt_result.scalar_one_or_none()

                if not salt:
                    salt = Salt(salt_name=salt_name, prescription_required=True)
                    db.add(salt)
                    await db.flush()

                # Parse strength value and unit (e.g., "500mg" -> 500, "mg")
                import re
                match = re.match(r"(\d+(?:\.\d+)?)\s*([a-zA-Z]+)", strength_str)
                if not match:
                    raise ValueError(f"Invalid strength format: {strength_str}")

                strength_value = float(match.group(1))
                strength_unit = match.group(2)

                # Find or create strength
                strength_result = await db.execute(
                    select(SaltStrength).where(
                        SaltStrength.salt_id == salt.salt_id,
                        SaltStrength.strength_value == strength_value,
                        SaltStrength.strength_unit == strength_unit,
                    )
                )
                salt_strength = strength_result.scalar_one_or_none()

                if not salt_strength:
                    salt_strength = SaltStrength(
                        salt_id=salt.salt_id,
                        strength_value=strength_value,
                        strength_unit=strength_unit,
                    )
                    db.add(salt_strength)
                    await db.flush()

                composition_data.append(BrandCompositionInput(
                    salt_strength_id=str(salt_strength.salt_strength_id),
                    sequence=seq,
                ))

            # Create brand
            new_brand = Brand(
                brand_name=row.brand_name,
                manufacturer_id=manufacturer.manufacturer_id,
                drug_type=row.drug_type,
                is_discontinued=row.is_discontinued,
                launch_date=date.fromisoformat(row.launch_date) if row.launch_date else None,
            )
            db.add(new_brand)
            await db.flush()

            # Create compositions
            for comp_input in composition_data:
                composition = BrandComposition(
                    brand_id=new_brand.brand_id,
                    salt_strength_id=UUID(comp_input.salt_strength_id),
                    sequence=comp_input.sequence,
                )
                db.add(composition)

            await db.flush()

            results.append(BulkImportResult(
                row=idx,
                brand_name=row.brand_name,
                status="success",
                message="Brand created successfully",
                brand_id=str(new_brand.brand_id),
            ))
            successful += 1

        except Exception as e:
            results.append(BulkImportResult(
                row=idx,
                brand_name=row.brand_name,
                status="error",
                message=str(e),
            ))
            failed += 1
            # Rollback this row's changes but continue with others
            await db.rollback()
            # Reconnect session for next iteration
            continue

    # Commit all successful rows
    if successful > 0:
        await db.commit()

    return BulkImportResponse(
        total=len(rows),
        successful=successful,
        failed=failed,
        skipped=skipped,
        results=results,
    )
