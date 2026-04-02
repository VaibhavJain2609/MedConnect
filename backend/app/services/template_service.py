from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prescription_template import PrescriptionTemplate


async def create_template(
    db: AsyncSession,
    doctor_id: UUID,
    name: str,
    medicines: list[dict],
    diagnosis: str | None = None,
    notes: str | None = None,
) -> PrescriptionTemplate:
    """Create a new prescription template."""
    # Check for duplicate name
    existing = await db.execute(
        select(PrescriptionTemplate).where(
            and_(
                PrescriptionTemplate.doctor_id == doctor_id,
                PrescriptionTemplate.name == name,
                PrescriptionTemplate.deleted_at.is_(None),
            )
        )
    )
    if existing.scalar_one_or_none():
        raise ValueError(f"Template with name '{name}' already exists")

    template = PrescriptionTemplate(
        doctor_id=doctor_id,
        name=name,
        medicines=medicines,
        diagnosis=diagnosis,
        notes=notes,
    )
    db.add(template)
    await db.flush()
    return template


async def get_template(
    db: AsyncSession,
    template_id: UUID,
    doctor_id: UUID,
) -> PrescriptionTemplate | None:
    """Get a single template by ID (doctor ownership verified)."""
    result = await db.execute(
        select(PrescriptionTemplate).where(
            and_(
                PrescriptionTemplate.id == template_id,
                PrescriptionTemplate.doctor_id == doctor_id,
                PrescriptionTemplate.deleted_at.is_(None),
            )
        )
    )
    return result.scalar_one_or_none()


async def get_doctor_templates(
    db: AsyncSession,
    doctor_id: UUID,
    cursor: UUID | None = None,
    limit: int = 20,
) -> tuple[list[PrescriptionTemplate], UUID | None, bool]:
    """Get all templates for a doctor with pagination."""
    stmt = (
        select(PrescriptionTemplate)
        .where(
            and_(
                PrescriptionTemplate.doctor_id == doctor_id,
                PrescriptionTemplate.deleted_at.is_(None),
            )
        )
        .order_by(PrescriptionTemplate.created_at.desc())
        .limit(limit + 1)
    )

    if cursor:
        cursor_result = await db.execute(select(PrescriptionTemplate.created_at).where(PrescriptionTemplate.id == cursor))
        cursor_time = cursor_result.scalar_one_or_none()
        if cursor_time:
            stmt = stmt.where(
                and_(
                    PrescriptionTemplate.created_at <= cursor_time,
                    PrescriptionTemplate.id != cursor,
                )
            )

    result = await db.execute(stmt)
    items = result.scalars().all()

    has_more = len(items) > limit
    templates = list(items[:limit])
    next_cursor = str(templates[-1].id) if templates and has_more else None

    return templates, next_cursor, has_more


async def update_template(
    db: AsyncSession,
    template_id: UUID,
    doctor_id: UUID,
    name: str | None = None,
    medicines: list[dict] | None = None,
    diagnosis: str | None = None,
    notes: str | None = None,
) -> PrescriptionTemplate:
    """Update a template (doctor ownership verified)."""
    template = await get_template(db, template_id, doctor_id)
    if not template:
        raise ValueError("Template not found")

    # Check for duplicate name if changing name
    if name and name != template.name:
        existing = await db.execute(
            select(PrescriptionTemplate).where(
                and_(
                    PrescriptionTemplate.doctor_id == doctor_id,
                    PrescriptionTemplate.name == name,
                    PrescriptionTemplate.deleted_at.is_(None),
                    PrescriptionTemplate.id != template_id,
                )
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"Template with name '{name}' already exists")

    if name is not None:
        template.name = name
    if medicines is not None:
        template.medicines = medicines
    if diagnosis is not None:
        template.diagnosis = diagnosis
    if notes is not None:
        template.notes = notes

    await db.flush()
    return template


async def delete_template(
    db: AsyncSession,
    template_id: UUID,
    doctor_id: UUID,
) -> bool:
    """Soft delete a template (doctor ownership verified)."""
    template = await get_template(db, template_id, doctor_id)
    if not template:
        raise ValueError("Template not found")

    template.deleted_at = datetime.utcnow()
    await db.flush()
    return True
