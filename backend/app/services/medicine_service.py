"""Admin medicine management service (main DB medicines table)."""
from typing import Optional
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.medicine import Component, Medicine, MedicineComponent
from app.schemas.medicine import MedicineCreate, MedicineUpdate


async def search_medicines(
    db: AsyncSession,
    search: Optional[str],
    therapeutic_class: Optional[str],
    include_discontinued: bool,
    limit: int,
    offset: int,
) -> tuple[list[Medicine], int]:
    stmt = (
        select(Medicine)
        .options(selectinload(Medicine.medicine_components).selectinload(MedicineComponent.component))
        .order_by(Medicine.brand_name.asc())
    )

    if search:
        pattern = f"%{search.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Medicine.brand_name).like(pattern),
                func.lower(Medicine.manufacturer).like(pattern),
            )
        )

    if therapeutic_class:
        stmt = stmt.where(Medicine.therapeutic_class == therapeutic_class)

    if not include_discontinued:
        stmt = stmt.where(Medicine.is_discontinued.is_(False))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total: int = total_result.scalar_one()

    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    medicines = list(result.scalars().all())
    return medicines, total


async def create_medicine(db: AsyncSession, data: MedicineCreate) -> Medicine:
    # Validate all component IDs exist
    component_ids = [c.component_id for c in data.components]
    result = await db.execute(select(Component).where(Component.id.in_(component_ids)))
    found = {c.id for c in result.scalars().all()}
    missing = set(component_ids) - found
    if missing:
        raise ValueError(f"Component IDs not found: {missing}")

    medicine = Medicine(
        brand_name=data.brand_name,
        manufacturer=data.manufacturer,
        dosage_form=data.dosage_form,
        pack_size=data.pack_size,
        therapeutic_class=data.therapeutic_class,
        schedule=data.schedule,
        mrp=data.mrp,
        is_discontinued=data.is_discontinued,
        habit_forming=data.habit_forming,
        alternatives=data.alternatives,
        interactions=data.interactions,
    )
    db.add(medicine)
    await db.flush()  # get medicine.id

    for seq, comp in enumerate(data.components, start=1):
        mc = MedicineComponent(
            medicine_id=medicine.id,
            component_id=comp.component_id,
            strength=comp.strength,
            unit=comp.unit,
            sequence=seq,
        )
        db.add(mc)

    await db.flush()
    await db.refresh(medicine, ["medicine_components"])
    return medicine


async def update_medicine(
    db: AsyncSession, medicine_id: UUID, data: MedicineUpdate
) -> Optional[Medicine]:
    result = await db.execute(
        select(Medicine)
        .options(selectinload(Medicine.medicine_components).selectinload(MedicineComponent.component))
        .where(Medicine.id == medicine_id)
    )
    medicine = result.scalar_one_or_none()
    if not medicine:
        return None

    update_fields = data.model_dump(exclude_unset=True, exclude={"components"})
    for field, value in update_fields.items():
        setattr(medicine, field, value)

    if data.components is not None:
        # Replace all components
        for mc in list(medicine.medicine_components):
            await db.delete(mc)
        await db.flush()

        component_ids = [c.component_id for c in data.components]
        comp_result = await db.execute(select(Component).where(Component.id.in_(component_ids)))
        found = {c.id for c in comp_result.scalars().all()}
        missing = set(component_ids) - found
        if missing:
            raise ValueError(f"Component IDs not found: {missing}")

        for seq, comp in enumerate(data.components, start=1):
            mc = MedicineComponent(
                medicine_id=medicine.id,
                component_id=comp.component_id,
                strength=comp.strength,
                unit=comp.unit,
                sequence=seq,
            )
            db.add(mc)

    await db.flush()
    await db.refresh(medicine, ["medicine_components"])
    return medicine


async def delete_medicine(db: AsyncSession, medicine_id: UUID) -> bool:
    result = await db.execute(select(Medicine).where(Medicine.id == medicine_id))
    medicine = result.scalar_one_or_none()
    if not medicine:
        return False
    await db.delete(medicine)
    await db.flush()
    return True
