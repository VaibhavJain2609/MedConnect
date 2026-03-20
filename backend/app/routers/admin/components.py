from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_medicine_db
from app.dependencies import require_admin
from app.schemas.component import (
    ComponentCreate,
    ComponentResponse,
    ComponentSearchResponse,
    ComponentUpdate,
)
from app.services import component_service

router = APIRouter(prefix="/admin/components", tags=["admin-components"], dependencies=[Depends(require_admin)])


@router.get("", response_model=ComponentSearchResponse)
async def list_components(
    search: Optional[str] = Query(None, description="Search by component name"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_medicine_db),
):
    """
    List/search components with usage statistics
    - Admin only
    - Search by name
    - Returns usage count (number of medicines using each component)
    """
    components, total = await component_service.search_components(
        db=db,
        search=search,
        limit=limit,
        offset=offset,
    )

    # Convert to response format
    component_list = [
        {
            **{
                "id": c.id,
                "name": c.name,
                "common_names": c.common_names,
                "category": c.category,
                "description": c.description,
                "created_at": c.created_at,
                "updated_at": c.updated_at,
            },
            "medicine_count": getattr(c, 'medicine_count', 0),
        }
        for c in components
    ]

    return {
        "components": component_list,
        "total": total,
    }


@router.get("/{component_id}", response_model=ComponentResponse)
async def get_component(
    component_id: UUID,
    db: AsyncSession = Depends(get_medicine_db),
):
    """Get component by ID - Admin only"""
    component = await component_service.get_component_by_id(db, component_id)
    if not component:
        raise HTTPException(status_code=404, detail="Component not found")

    return component


@router.post("", response_model=ComponentResponse, status_code=status.HTTP_201_CREATED)
async def create_component(
    component_data: ComponentCreate,
    db: AsyncSession = Depends(get_medicine_db),
):
    """
    Create a new component - Admin only
    - Name must be unique
    """
    try:
        component = await component_service.create_component(db, component_data)
        await db.commit()
        return component
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{component_id}", response_model=ComponentResponse)
async def update_component(
    component_id: UUID,
    component_data: ComponentUpdate,
    db: AsyncSession = Depends(get_medicine_db),
):
    """Update component - Admin only"""
    try:
        component = await component_service.update_component(db, component_id, component_data)
        if not component:
            raise HTTPException(status_code=404, detail="Component not found")

        await db.commit()
        return component
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{component_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_component(
    component_id: UUID,
    db: AsyncSession = Depends(get_medicine_db),
):
    """
    Delete component - Admin only
    - Only if not used in any medicines
    """
    try:
        deleted = await component_service.delete_component(db, component_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Component not found")

        await db.commit()
        return None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
