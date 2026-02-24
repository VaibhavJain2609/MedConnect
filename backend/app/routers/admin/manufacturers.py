"""Admin endpoints for managing manufacturers in EMR schema."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.database import get_medicine_db
from app.dependencies import require_admin
from app.models.user import User
from app.services.brand_service import ManufacturerService


# Pydantic schemas
class ManufacturerCreateRequest(BaseModel):
    """Request schema for creating a manufacturer."""
    manufacturer_name: str = Field(..., min_length=1, max_length=255)
    country: Optional[str] = Field(None, max_length=100)
    license_number: Optional[str] = Field(None, max_length=100)
    contact_info: Optional[dict] = None
    is_active: bool = True


class ManufacturerUpdateRequest(BaseModel):
    """Request schema for updating a manufacturer (partial updates)."""
    manufacturer_name: Optional[str] = Field(None, min_length=1, max_length=255)
    country: Optional[str] = Field(None, max_length=100)
    license_number: Optional[str] = Field(None, max_length=100)
    contact_info: Optional[dict] = None
    is_active: Optional[bool] = None


class ManufacturerResponse(BaseModel):
    """Response schema for manufacturer."""
    manufacturer_id: UUID
    manufacturer_name: str
    country: Optional[str]
    license_number: Optional[str]
    contact_info: Optional[dict]
    is_active: bool

    class Config:
        from_attributes = True


router = APIRouter(
    prefix="/admin/manufacturers",
    tags=["admin-manufacturers"],
    dependencies=[Depends(require_admin)]
)


@router.post("", response_model=ManufacturerResponse, status_code=status.HTTP_201_CREATED)
async def create_manufacturer(
    manufacturer_data: ManufacturerCreateRequest,
    db: AsyncSession = Depends(get_medicine_db),
    admin: User = Depends(require_admin),
):
    """
    Create a new manufacturer - Admin only.

    - Validates manufacturer_name is required
    - Checks for duplicate names (case-insensitive)
    - Returns 201 with created manufacturer
    """
    try:
        manufacturer = await ManufacturerService.create_manufacturer(
            db,
            manufacturer_name=manufacturer_data.manufacturer_name,
            country=manufacturer_data.country,
            license_number=manufacturer_data.license_number,
            contact_info=manufacturer_data.contact_info,
            is_active=manufacturer_data.is_active,
        )
        await db.commit()
        await db.refresh(manufacturer)

        return ManufacturerResponse(
            manufacturer_id=manufacturer.manufacturer_id,
            manufacturer_name=manufacturer.manufacturer_name,
            country=manufacturer.country,
            license_number=manufacturer.license_number,
            contact_info=manufacturer.contact_info,
            is_active=manufacturer.is_active,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )


@router.put("/{manufacturer_id}", response_model=ManufacturerResponse)
async def update_manufacturer(
    manufacturer_id: UUID,
    manufacturer_data: ManufacturerUpdateRequest,
    db: AsyncSession = Depends(get_medicine_db),
    admin: User = Depends(require_admin),
):
    """
    Update a manufacturer - Admin only.

    - Partial updates supported
    - Validates duplicate names if name changed
    - Returns updated manufacturer
    """
    try:
        manufacturer = await ManufacturerService.update_manufacturer(
            db,
            manufacturer_id=manufacturer_id,
            manufacturer_name=manufacturer_data.manufacturer_name,
            country=manufacturer_data.country,
            license_number=manufacturer_data.license_number,
            contact_info=manufacturer_data.contact_info,
            is_active=manufacturer_data.is_active,
        )

        if not manufacturer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Manufacturer {manufacturer_id} not found"
            )

        await db.commit()
        await db.refresh(manufacturer)

        return ManufacturerResponse(
            manufacturer_id=manufacturer.manufacturer_id,
            manufacturer_name=manufacturer.manufacturer_name,
            country=manufacturer.country,
            license_number=manufacturer.license_number,
            contact_info=manufacturer.contact_info,
            is_active=manufacturer.is_active,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )


@router.delete("/{manufacturer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_manufacturer(
    manufacturer_id: UUID,
    db: AsyncSession = Depends(get_medicine_db),
    admin: User = Depends(require_admin),
):
    """
    Delete a manufacturer - Admin only.

    Safety checks:
    - Returns 404 if manufacturer not found
    - Returns 409 if manufacturer has any brands (active or discontinued)
    - Returns 204 on successful deletion
    """
    success, error_msg = await ManufacturerService.delete_manufacturer(db, manufacturer_id)

    if not success:
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=error_msg
            )

    await db.commit()
    return None
