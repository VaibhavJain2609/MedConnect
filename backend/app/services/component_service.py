from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Component, MedicineComponent
from app.schemas.component import ComponentCreate, ComponentUpdate


async def search_components(
    db: AsyncSession,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Component], int]:
    """
    Search components by name with optional full-text search
    Returns (components, total_count)
    """
    # Build base query with usage count
    query = (
        select(
            Component,
            func.count(MedicineComponent.id).label("medicine_count")
        )
        .outerjoin(MedicineComponent, Component.id == MedicineComponent.component_id)
        .group_by(Component.id)
    )

    # Apply search filter
    if search:
        search_term = f"%{search}%"
        query = query.where(Component.name.ilike(search_term))

    # Count total
    count_query = select(func.count()).select_from(
        select(Component.id).where(Component.name.ilike(f"%{search}%") if search else True).subquery()
    )
    total = await db.scalar(count_query) or 0

    # Apply pagination and order by usage
    query = query.order_by(func.count(MedicineComponent.id).desc(), Component.name).limit(limit).offset(offset)

    # Execute
    result = await db.execute(query)
    components_with_count = result.all()

    # Attach medicine_count to component objects
    components = []
    for comp, med_count in components_with_count:
        comp.medicine_count = med_count  # Attach dynamically
        components.append(comp)

    return components, total


async def get_component_by_id(db: AsyncSession, component_id: UUID) -> Optional[Component]:
    """Get component by ID"""
    result = await db.execute(select(Component).where(Component.id == component_id))
    return result.scalar_one_or_none()


async def get_component_by_name(db: AsyncSession, name: str) -> Optional[Component]:
    """Get component by exact name (case-insensitive)"""
    result = await db.execute(select(Component).where(func.lower(Component.name) == name.lower()))
    return result.scalar_one_or_none()


async def create_component(db: AsyncSession, component_data: ComponentCreate) -> Component:
    """Create a new component"""
    # Check if component with same name exists
    existing = await get_component_by_name(db, component_data.name)
    if existing:
        raise ValueError(f"Component '{component_data.name}' already exists")

    component = Component(**component_data.model_dump())
    db.add(component)
    await db.flush()
    await db.refresh(component)
    return component


async def update_component(
    db: AsyncSession,
    component_id: UUID,
    component_data: ComponentUpdate
) -> Optional[Component]:
    """Update component"""
    component = await get_component_by_id(db, component_id)
    if not component:
        return None

    # Check name uniqueness if name is being updated
    if component_data.name and component_data.name != component.name:
        existing = await get_component_by_name(db, component_data.name)
        if existing:
            raise ValueError(f"Component '{component_data.name}' already exists")

    # Update fields
    for field, value in component_data.model_dump(exclude_unset=True).items():
        setattr(component, field, value)

    await db.flush()
    await db.refresh(component)
    return component


async def delete_component(db: AsyncSession, component_id: UUID) -> bool:
    """
    Delete component (only if not used in any medicines)
    Returns True if deleted, False if not found, raises ValueError if in use
    """
    component = await get_component_by_id(db, component_id)
    if not component:
        return False

    # Check if component is used in any medicines
    usage_count = await db.scalar(
        select(func.count(MedicineComponent.id)).where(MedicineComponent.component_id == component_id)
    )

    if usage_count > 0:
        raise ValueError(f"Cannot delete component: used in {usage_count} medicines")

    await db.delete(component)
    return True
