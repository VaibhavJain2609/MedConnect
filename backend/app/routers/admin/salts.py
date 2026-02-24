"""Admin endpoints for managing salts (active pharmaceutical ingredients) in EMR schema."""

from typing import Optional
from uuid import UUID
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.database import get_medicine_db
from app.dependencies import require_admin
from app.models.user import User
from app.services.salt_service import SaltService


# Pydantic schemas
class SaltStrengthInput(BaseModel):
    """Input for salt strength."""
    strength_value: Decimal = Field(..., gt=0)
    strength_unit: str = Field(..., min_length=1, max_length=20)
    is_standard_strength: bool = True
    pediatric_approved: bool = False


class SaltStrengthResponse(BaseModel):
    """Response for salt strength."""
    salt_strength_id: UUID
    strength_value: Decimal
    strength_unit: str
    display_strength: str
    is_standard_strength: bool
    pediatric_approved: bool

    class Config:
        from_attributes = True


class SaltCreateRequest(BaseModel):
    """Request schema for creating a salt."""
    salt_name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    chemical_formula: Optional[str] = Field(None, max_length=100)
    habit_forming: bool = False
    prescription_required: bool = True
    schedule: Optional[str] = Field(None, max_length=10)
    pregnancy_category: Optional[str] = Field(None, max_length=10)
    lactation_safe: Optional[bool] = None
    lactation_notes: Optional[str] = None
    snomed_code: Optional[str] = Field(None, max_length=50)
    rxcui: Optional[str] = Field(None, max_length=20)
    chemical_class_id: Optional[UUID] = None
    therapeutic_class_id: Optional[UUID] = None
    action_class_id: Optional[UUID] = None
    strengths: Optional[list[SaltStrengthInput]] = None


class SaltUpdateRequest(BaseModel):
    """Request schema for updating a salt (partial updates)."""
    salt_name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    chemical_formula: Optional[str] = Field(None, max_length=100)
    habit_forming: Optional[bool] = None
    prescription_required: Optional[bool] = None
    schedule: Optional[str] = Field(None, max_length=10)
    pregnancy_category: Optional[str] = Field(None, max_length=10)
    lactation_safe: Optional[bool] = None
    lactation_notes: Optional[str] = None
    snomed_code: Optional[str] = Field(None, max_length=50)
    rxcui: Optional[str] = Field(None, max_length=20)
    chemical_class_id: Optional[UUID] = None
    therapeutic_class_id: Optional[UUID] = None
    action_class_id: Optional[UUID] = None


class SaltResponse(BaseModel):
    """Response schema for salt."""
    salt_id: UUID
    salt_name: str
    description: Optional[str]
    chemical_formula: Optional[str]
    habit_forming: bool
    prescription_required: bool
    schedule: Optional[str]
    pregnancy_category: Optional[str]
    lactation_safe: Optional[bool]
    lactation_notes: Optional[str]
    snomed_code: Optional[str]
    rxcui: Optional[str]
    chemical_class_id: Optional[UUID]
    therapeutic_class_id: Optional[UUID]
    action_class_id: Optional[UUID]
    strengths: list[SaltStrengthResponse] = []

    class Config:
        from_attributes = True


router = APIRouter(
    prefix="/admin/salts",
    tags=["admin-salts"],
    dependencies=[Depends(require_admin)]
)


@router.post("", response_model=SaltResponse, status_code=status.HTTP_201_CREATED)
async def create_salt(
    salt_data: SaltCreateRequest,
    db: AsyncSession = Depends(get_medicine_db),
    admin: User = Depends(require_admin),
):
    """
    Create a new salt (active pharmaceutical ingredient) - Admin only.

    - Validates salt_name is required
    - Checks for duplicate names (case-insensitive)
    - Optionally creates initial strengths
    - Returns 201 with created salt
    """
    try:
        # Convert strengths to dict format
        strengths_data = None
        if salt_data.strengths:
            strengths_data = [s.dict() for s in salt_data.strengths]

        salt = await SaltService.create_salt(
            db,
            salt_name=salt_data.salt_name,
            description=salt_data.description,
            chemical_formula=salt_data.chemical_formula,
            habit_forming=salt_data.habit_forming,
            prescription_required=salt_data.prescription_required,
            schedule=salt_data.schedule,
            pregnancy_category=salt_data.pregnancy_category,
            lactation_safe=salt_data.lactation_safe,
            lactation_notes=salt_data.lactation_notes,
            snomed_code=salt_data.snomed_code,
            rxcui=salt_data.rxcui,
            chemical_class_id=salt_data.chemical_class_id,
            therapeutic_class_id=salt_data.therapeutic_class_id,
            action_class_id=salt_data.action_class_id,
            strengths=strengths_data,
        )
        await db.commit()

        # Reload with strengths
        salt = await SaltService.get_salt_by_id(db, salt.salt_id)

        # Build response
        strengths_response = [
            SaltStrengthResponse(
                salt_strength_id=s.salt_strength_id,
                strength_value=s.strength_value,
                strength_unit=s.strength_unit,
                display_strength=s.display_strength,
                is_standard_strength=s.is_standard_strength,
                pediatric_approved=s.pediatric_approved,
            )
            for s in salt.strengths
        ]

        return SaltResponse(
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
            snomed_code=salt.snomed_code,
            rxcui=salt.rxcui,
            chemical_class_id=salt.chemical_class_id,
            therapeutic_class_id=salt.therapeutic_class_id,
            action_class_id=salt.action_class_id,
            strengths=strengths_response,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )


@router.put("/{salt_id}", response_model=SaltResponse)
async def update_salt(
    salt_id: UUID,
    salt_data: SaltUpdateRequest,
    db: AsyncSession = Depends(get_medicine_db),
    admin: User = Depends(require_admin),
):
    """
    Update a salt - Admin only.

    - Partial updates supported
    - Validates duplicate names if name changed
    - Returns updated salt with strengths
    """
    try:
        salt = await SaltService.update_salt(
            db,
            salt_id=salt_id,
            salt_name=salt_data.salt_name,
            description=salt_data.description,
            chemical_formula=salt_data.chemical_formula,
            habit_forming=salt_data.habit_forming,
            prescription_required=salt_data.prescription_required,
            schedule=salt_data.schedule,
            pregnancy_category=salt_data.pregnancy_category,
            lactation_safe=salt_data.lactation_safe,
            lactation_notes=salt_data.lactation_notes,
            snomed_code=salt_data.snomed_code,
            rxcui=salt_data.rxcui,
            chemical_class_id=salt_data.chemical_class_id,
            therapeutic_class_id=salt_data.therapeutic_class_id,
            action_class_id=salt_data.action_class_id,
        )

        if not salt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Salt {salt_id} not found"
            )

        await db.commit()

        # Reload with strengths
        salt = await SaltService.get_salt_by_id(db, salt_id)

        # Build response
        strengths_response = [
            SaltStrengthResponse(
                salt_strength_id=s.salt_strength_id,
                strength_value=s.strength_value,
                strength_unit=s.strength_unit,
                display_strength=s.display_strength,
                is_standard_strength=s.is_standard_strength,
                pediatric_approved=s.pediatric_approved,
            )
            for s in salt.strengths
        ]

        return SaltResponse(
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
            snomed_code=salt.snomed_code,
            rxcui=salt.rxcui,
            chemical_class_id=salt.chemical_class_id,
            therapeutic_class_id=salt.therapeutic_class_id,
            action_class_id=salt.action_class_id,
            strengths=strengths_response,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )


@router.delete("/{salt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_salt(
    salt_id: UUID,
    db: AsyncSession = Depends(get_medicine_db),
    admin: User = Depends(require_admin),
):
    """
    Delete a salt - Admin only.

    Safety checks:
    - Returns 404 if salt not found
    - Returns 409 if salt has any strengths (must delete strengths first)
    - Returns 204 on successful deletion
    """
    success, error_msg = await SaltService.delete_salt(db, salt_id)

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
