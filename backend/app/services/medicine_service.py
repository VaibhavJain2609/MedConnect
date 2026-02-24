from typing import Optional
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Component, Medicine, MedicineComponent
from app.schemas.medicine import MedicineComponentInput, MedicineCreate, MedicineUpdate


async def search_medicines(
    db: AsyncSession,
    search: Optional[str] = None,
    component_id: Optional[UUID] = None,
    therapeutic_class: Optional[str] = None,
    include_discontinued: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Medicine], int]:
    """
    Search medicines with filters
    Returns (medicines, total_count)
    """
    # Build base query with eager loading
    query = select(Medicine).options(
        selectinload(Medicine.medicine_components).selectinload(MedicineComponent.component)
    )

    # Apply filters
    filters = []

    if not include_discontinued:
        filters.append(Medicine.is_discontinued == False)

    if search:
        search_term = f"%{search}%"
        filters.append(
            or_(
                Medicine.brand_name.ilike(search_term),
                Medicine.manufacturer.ilike(search_term)
            )
        )

    if component_id:
        # Join with medicine_components to filter by component
        query = query.join(MedicineComponent).where(MedicineComponent.component_id == component_id)

    if therapeutic_class:
        filters.append(Medicine.therapeutic_class.ilike(f"%{therapeutic_class}%"))

    if filters:
        query = query.where(*filters)

    # Count total
    count_query = select(func.count(Medicine.id))
    if filters:
        count_query = count_query.where(*filters)
    if component_id:
        count_query = count_query.join(MedicineComponent).where(MedicineComponent.component_id == component_id)

    total = await db.scalar(count_query) or 0

    # Apply pagination
    query = query.order_by(Medicine.brand_name).limit(limit).offset(offset)

    # Execute
    result = await db.execute(query)
    medicines = result.scalars().unique().all()

    return list(medicines), total


async def get_medicine_by_id(db: AsyncSession, medicine_id: UUID) -> Optional[Medicine]:
    """Get medicine by ID with components"""
    result = await db.execute(
        select(Medicine)
        .options(
            selectinload(Medicine.medicine_components).selectinload(MedicineComponent.component)
        )
        .where(Medicine.id == medicine_id)
    )
    return result.scalar_one_or_none()


async def create_medicine(db: AsyncSession, medicine_data: MedicineCreate) -> Medicine:
    """Create a new medicine with components"""
    # Extract components
    components_input = medicine_data.components
    medicine_dict = medicine_data.model_dump(exclude={'components'})

    # Compute strength display from components
    if components_input:
        strength_parts = [f"{c.strength}{c.unit}" for c in components_input]
        medicine_dict['strength'] = " + ".join(strength_parts)

    # Create medicine
    medicine = Medicine(**medicine_dict)
    db.add(medicine)
    await db.flush()  # Get medicine ID

    # Create medicine-component relationships
    for seq, comp_input in enumerate(components_input, start=1):
        # Verify component exists
        comp_result = await db.execute(
            select(Component).where(Component.id == comp_input.component_id)
        )
        component = comp_result.scalar_one_or_none()
        if not component:
            raise ValueError(f"Component with ID {comp_input.component_id} not found")

        # Create relationship
        med_comp = MedicineComponent(
            medicine_id=medicine.id,
            component_id=comp_input.component_id,
            strength=comp_input.strength,
            unit=comp_input.unit,
            sequence=seq
        )
        db.add(med_comp)

    await db.flush()
    await db.refresh(medicine, ['medicine_components'])
    return medicine


async def update_medicine(
    db: AsyncSession,
    medicine_id: UUID,
    medicine_data: MedicineUpdate
) -> Optional[Medicine]:
    """Update medicine and optionally its components"""
    medicine = await get_medicine_by_id(db, medicine_id)
    if not medicine:
        return None

    # Extract components if provided
    components_input = medicine_data.components
    medicine_dict = medicine_data.model_dump(exclude={'components'}, exclude_unset=True)

    # Update medicine fields
    for field, value in medicine_dict.items():
        setattr(medicine, field, value)

    # Update components if provided
    if components_input is not None:
        # Delete existing components
        await db.execute(
            select(MedicineComponent).where(MedicineComponent.medicine_id == medicine_id)
        )
        for mc in medicine.medicine_components:
            await db.delete(mc)

        # Add new components
        for seq, comp_input in enumerate(components_input, start=1):
            # Verify component exists
            comp_result = await db.execute(
                select(Component).where(Component.id == comp_input.component_id)
            )
            component = comp_result.scalar_one_or_none()
            if not component:
                raise ValueError(f"Component with ID {comp_input.component_id} not found")

            med_comp = MedicineComponent(
                medicine_id=medicine.id,
                component_id=comp_input.component_id,
                strength=comp_input.strength,
                unit=comp_input.unit,
                sequence=seq
            )
            db.add(med_comp)

        # Update strength display
        if components_input:
            strength_parts = [f"{c.strength}{c.unit}" for c in components_input]
            medicine.strength = " + ".join(strength_parts)

    await db.flush()
    await db.refresh(medicine, ['medicine_components'])
    return medicine


async def delete_medicine(db: AsyncSession, medicine_id: UUID) -> bool:
    """Delete medicine (cascade deletes components)"""
    medicine = await get_medicine_by_id(db, medicine_id)
    if not medicine:
        return False

    await db.delete(medicine)
    return True


async def get_medicine_alternatives(db: AsyncSession, medicine_id: UUID) -> Optional[dict]:
    """Get alternatives for a medicine"""
    medicine = await get_medicine_by_id(db, medicine_id)
    if not medicine:
        return None

    return {
        "medicine_id": medicine.id,
        "medicine_name": medicine.brand_name,
        "alternatives": medicine.alternatives or []
    }
