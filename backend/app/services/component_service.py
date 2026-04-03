"""Admin component management service (main DB components table)."""
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.medicine import Component, MedicineComponent
from app.schemas.component import ComponentCreate, ComponentUpdate


async def search_components(
    db: AsyncSession,
    search: Optional[str],
    limit: int,
    offset: int,
) -> tuple[list, int]:
    stmt = select(
        Component,
        func.count(MedicineComponent.id).label("medicine_count"),
    ).outerjoin(
        MedicineComponent, MedicineComponent.component_id == Component.id
    ).group_by(Component.id).order_by(Component.name.asc())

    if search:
        pattern = f"%{search.lower()}%"
        stmt = stmt.where(func.lower(Component.name).like(pattern))

    count_stmt = select(func.count()).select_from(
        select(Component).where(
            func.lower(Component.name).like(f"%{search.lower()}%") if search else True
        ).subquery()
    )
    total_result = await db.execute(count_stmt)
    total: int = total_result.scalar_one()

    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    rows = result.all()

    # Attach medicine_count as attribute for the router to use
    components = []
    for row in rows:
        component = row[0]
        component.medicine_count = row[1]
        components.append(component)

    return components, total


async def get_component_by_id(db: AsyncSession, component_id: UUID) -> Optional[Component]:
    result = await db.execute(select(Component).where(Component.id == component_id))
    return result.scalar_one_or_none()


async def create_component(db: AsyncSession, data: ComponentCreate) -> Component:
    # Enforce unique name
    existing = await db.execute(
        select(Component).where(func.lower(Component.name) == data.name.lower())
    )
    if existing.scalar_one_or_none():
        raise ValueError(f"Component '{data.name}' already exists")

    component = Component(
        name=data.name,
        common_names=data.common_names,
        category=data.category,
        description=data.description,
    )
    db.add(component)
    await db.flush()
    await db.refresh(component)
    return component


async def update_component(
    db: AsyncSession, component_id: UUID, data: ComponentUpdate
) -> Optional[Component]:
    result = await db.execute(select(Component).where(Component.id == component_id))
    component = result.scalar_one_or_none()
    if not component:
        return None

    update_fields = data.model_dump(exclude_unset=True)
    for field, value in update_fields.items():
        setattr(component, field, value)

    await db.flush()
    await db.refresh(component)
    return component


async def delete_component(db: AsyncSession, component_id: UUID) -> bool:
    result = await db.execute(select(Component).where(Component.id == component_id))
    component = result.scalar_one_or_none()
    if not component:
        return False

    # Check if any medicines use this component
    usage = await db.execute(
        select(func.count()).where(MedicineComponent.component_id == component_id)
    )
    if usage.scalar_one() > 0:
        raise ValueError("Cannot delete component: it is used by one or more medicines")

    await db.delete(component)
    await db.flush()
    return True
