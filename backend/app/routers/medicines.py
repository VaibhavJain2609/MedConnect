from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_medicine_db
from app.schemas.medicine import (
    MedicineAlternativesResponse,
    MedicineListItem,
    MedicineResponse,
    MedicineSearchResponse,
)
from app.services import medicine_service

router = APIRouter(prefix="/medicines", tags=["medicines"])


@router.get("/search", response_model=MedicineSearchResponse)
async def search_medicines(
    q: Optional[str] = Query(None, description="Search by brand name or manufacturer"),
    component_id: Optional[UUID] = Query(None, description="Filter by component ID"),
    therapeutic_class: Optional[str] = Query(None, description="Filter by therapeutic class"),
    include_discontinued: bool = Query(False, description="Include discontinued medicines"),
    limit: int = Query(50, ge=1, le=100, description="Results per page"),
    page: int = Query(1, ge=1, description="Page number"),
    db: AsyncSession = Depends(get_medicine_db),
):
    """
    Search medicines with filters
    - Search by brand name or manufacturer
    - Filter by component (get all medicines containing specific component)
    - Filter by therapeutic class
    - Pagination support
    """
    offset = (page - 1) * limit

    medicines, total = await medicine_service.search_medicines(
        db=db,
        search=q,
        component_id=component_id,
        therapeutic_class=therapeutic_class,
        include_discontinued=include_discontinued,
        limit=limit,
        offset=offset,
    )

    # Convert to list items with component info
    medicine_items = []
    for med in medicines:
        components = [
            {
                "component_id": mc.component_id,
                "component_name": mc.component.name,
                "strength": mc.strength,
                "unit": mc.unit,
                "sequence": mc.sequence,
            }
            for mc in sorted(med.medicine_components, key=lambda x: x.sequence)
        ]

        medicine_items.append({
            "id": med.id,
            "brand_name": med.brand_name,
            "manufacturer": med.manufacturer,
            "dosage_form": med.dosage_form,
            "strength": med.strength,
            "mrp": med.mrp,
            "is_discontinued": med.is_discontinued,
            "components": components,
        })

    pages = (total + limit - 1) // limit if total > 0 else 0

    return {
        "medicines": medicine_items,
        "total": total,
        "page": page,
        "pages": pages,
    }


@router.get("/{medicine_id}", response_model=MedicineResponse)
async def get_medicine(
    medicine_id: UUID,
    db: AsyncSession = Depends(get_medicine_db),
):
    """
    Get medicine details by ID
    - Full medicine information
    - All components with strengths
    - Interactions, side effects, uses
    - Alternatives
    """
    medicine = await medicine_service.get_medicine_by_id(db, medicine_id)
    if not medicine:
        raise HTTPException(status_code=404, detail="Medicine not found")

    # Build component response
    components = [
        {
            "component_id": mc.component_id,
            "component_name": mc.component.name,
            "strength": mc.strength,
            "unit": mc.unit,
            "sequence": mc.sequence,
        }
        for mc in sorted(medicine.medicine_components, key=lambda x: x.sequence)
    ]

    # Compute salt composition
    salt_composition = " + ".join([
        f"{mc.component.name} ({mc.strength}{mc.unit})"
        for mc in sorted(medicine.medicine_components, key=lambda x: x.sequence)
    ])

    return {
        "id": medicine.id,
        "brand_name": medicine.brand_name,
        "manufacturer": medicine.manufacturer,
        "dosage_form": medicine.dosage_form,
        "strength": medicine.strength,
        "pack_size": medicine.pack_size,
        "therapeutic_class": medicine.therapeutic_class,
        "schedule": medicine.schedule,
        "mrp": medicine.mrp,
        "is_discontinued": medicine.is_discontinued,
        "habit_forming": medicine.habit_forming,
        "alternatives": medicine.alternatives,
        "interactions": medicine.interactions,
        "components": components,
        "salt_composition": salt_composition,
        "created_at": medicine.created_at,
        "updated_at": medicine.updated_at,
    }


@router.get("/{medicine_id}/alternatives", response_model=MedicineAlternativesResponse)
async def get_medicine_alternatives(
    medicine_id: UUID,
    db: AsyncSession = Depends(get_medicine_db),
):
    """
    Get alternative/substitute medicines for a given medicine
    """
    result = await medicine_service.get_medicine_alternatives(db, medicine_id)
    if not result:
        raise HTTPException(status_code=404, detail="Medicine not found")

    return result
