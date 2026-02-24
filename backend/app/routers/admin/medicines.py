from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_medicine_db
from app.schemas.medicine import (
    MedicineCreate,
    MedicineResponse,
    MedicineSearchResponse,
    MedicineUpdate,
)
from app.services import medicine_service

router = APIRouter(prefix="/admin/medicines", tags=["admin-medicines"])

# TODO: Add admin authentication dependency
# from app.dependencies import require_admin
# router = APIRouter(prefix="/admin/medicines", tags=["admin-medicines"], dependencies=[Depends(require_admin)])


@router.get("", response_model=MedicineSearchResponse)
async def list_medicines(
    search: Optional[str] = Query(None, description="Search by brand name or manufacturer"),
    therapeutic_class: Optional[str] = Query(None),
    include_discontinued: bool = Query(True, description="Include discontinued medicines"),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_medicine_db),
):
    """
    List/search medicines - Admin only
    - Search by brand name or manufacturer
    - Filter by therapeutic class
    - Option to include/exclude discontinued
    """
    offset = (page - 1) * limit

    medicines, total = await medicine_service.search_medicines(
        db=db,
        search=search,
        therapeutic_class=therapeutic_class,
        include_discontinued=include_discontinued,
        limit=limit,
        offset=offset,
    )

    # Convert to list items
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


@router.post("", response_model=MedicineResponse, status_code=status.HTTP_201_CREATED)
async def create_medicine(
    medicine_data: MedicineCreate,
    db: AsyncSession = Depends(get_medicine_db),
):
    """
    Create a new medicine - Admin only
    - Must specify at least one component with component_id
    - Component IDs must exist in components table
    """
    try:
        medicine = await medicine_service.create_medicine(db, medicine_data)
        await db.commit()

        # Build response
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

        salt_composition = " + ".join([
            f"{mc.component.name} ({mc.strength}{mc.unit})"
            for mc in sorted(medicine.medicine_components, key=lambda x: x.sequence)
        ])

        return {
            **medicine.__dict__,
            "components": components,
            "salt_composition": salt_composition,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{medicine_id}", response_model=MedicineResponse)
async def update_medicine(
    medicine_id: UUID,
    medicine_data: MedicineUpdate,
    db: AsyncSession = Depends(get_medicine_db),
):
    """
    Update medicine - Admin only
    - Can update all fields including components
    - If components provided, replaces all existing components
    """
    try:
        medicine = await medicine_service.update_medicine(db, medicine_id, medicine_data)
        if not medicine:
            raise HTTPException(status_code=404, detail="Medicine not found")

        await db.commit()

        # Build response
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

        salt_composition = " + ".join([
            f"{mc.component.name} ({mc.strength}{mc.unit})"
            for mc in sorted(medicine.medicine_components, key=lambda x: x.sequence)
        ]) if medicine.medicine_components else ""

        return {
            **medicine.__dict__,
            "components": components,
            "salt_composition": salt_composition,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{medicine_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_medicine(
    medicine_id: UUID,
    db: AsyncSession = Depends(get_medicine_db),
):
    """
    Delete medicine - Admin only
    - Cascade deletes medicine-component relationships
    """
    deleted = await medicine_service.delete_medicine(db, medicine_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Medicine not found")

    await db.commit()
    return None
