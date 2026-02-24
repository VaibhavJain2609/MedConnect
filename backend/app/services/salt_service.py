"""Service layer for Salt and SaltStrength operations."""

from uuid import UUID
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Salt, SaltStrength, ChemicalClass, TherapeuticClass, ActionClass


class SaltService:
    """Service for managing salts (active pharmaceutical ingredients)."""

    @staticmethod
    async def get_salt_by_id(db: AsyncSession, salt_id: UUID) -> Salt | None:
        """Get salt by ID with all relationships."""
        result = await db.execute(
            select(Salt)
            .options(
                selectinload(Salt.strengths),
                selectinload(Salt.chemical_class),
                selectinload(Salt.therapeutic_class),
                selectinload(Salt.action_class),
            )
            .where(Salt.salt_id == salt_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def search_salts(
        db: AsyncSession,
        search: str | None = None,
        chemical_class_id: UUID | None = None,
        therapeutic_class_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Salt], int]:
        """Search salts with filters."""
        # Build count query (faster without joins/loads)
        count_query = select(func.count(Salt.salt_id))

        # Search filter
        if search:
            count_query = count_query.where(
                or_(
                    Salt.salt_name.ilike(f"%{search}%"),
                    Salt.description.ilike(f"%{search}%"),
                )
            )

        # Classification filters
        if chemical_class_id:
            count_query = count_query.where(Salt.chemical_class_id == chemical_class_id)
        if therapeutic_class_id:
            count_query = count_query.where(Salt.therapeutic_class_id == therapeutic_class_id)

        # Get total count
        total = await db.scalar(count_query)

        # Build main query with optimized loading
        query = select(Salt).options(
            selectinload(Salt.strengths),
            joinedload(Salt.chemical_class),
            joinedload(Salt.therapeutic_class),
            joinedload(Salt.action_class),
        )

        # Apply same filters
        if search:
            query = query.where(
                or_(
                    Salt.salt_name.ilike(f"%{search}%"),
                    Salt.description.ilike(f"%{search}%"),
                )
            )

        if chemical_class_id:
            query = query.where(Salt.chemical_class_id == chemical_class_id)
        if therapeutic_class_id:
            query = query.where(Salt.therapeutic_class_id == therapeutic_class_id)

        # Apply pagination
        query = query.order_by(Salt.salt_name).limit(limit).offset(offset)

        result = await db.execute(query)
        salts = list(result.scalars().unique().all())

        return salts, total or 0

    @staticmethod
    async def get_salt_strengths(db: AsyncSession, salt_id: UUID) -> list[SaltStrength]:
        """Get all strengths for a salt."""
        result = await db.execute(
            select(SaltStrength)
            .where(SaltStrength.salt_id == salt_id)
            .order_by(SaltStrength.strength_value)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_strength_by_id(db: AsyncSession, strength_id: UUID) -> SaltStrength | None:
        """Get salt strength by ID."""
        result = await db.execute(
            select(SaltStrength)
            .options(joinedload(SaltStrength.salt))
            .where(SaltStrength.salt_strength_id == strength_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create_salt(
        db: AsyncSession,
        salt_name: str,
        description: str | None = None,
        chemical_formula: str | None = None,
        habit_forming: bool = False,
        prescription_required: bool = True,
        schedule: str | None = None,
        pregnancy_category: str | None = None,
        lactation_safe: bool | None = None,
        lactation_notes: str | None = None,
        snomed_code: str | None = None,
        rxcui: str | None = None,
        chemical_class_id: UUID | None = None,
        therapeutic_class_id: UUID | None = None,
        action_class_id: UUID | None = None,
        strengths: list[dict] | None = None,
    ) -> Salt:
        """Create a new salt with duplicate check and optional strengths."""
        # Check for duplicate name (case-insensitive)
        existing = await db.execute(
            select(Salt).where(
                func.lower(Salt.salt_name) == salt_name.lower()
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"Salt '{salt_name}' already exists")

        salt = Salt(
            salt_name=salt_name,
            description=description,
            chemical_formula=chemical_formula,
            habit_forming=habit_forming,
            prescription_required=prescription_required,
            schedule=schedule,
            pregnancy_category=pregnancy_category,
            lactation_safe=lactation_safe,
            lactation_notes=lactation_notes,
            snomed_code=snomed_code,
            rxcui=rxcui,
            chemical_class_id=chemical_class_id,
            therapeutic_class_id=therapeutic_class_id,
            action_class_id=action_class_id,
        )
        db.add(salt)
        await db.flush()

        # Add initial strengths if provided
        if strengths:
            for strength_data in strengths:
                strength = SaltStrength(
                    salt_id=salt.salt_id,
                    strength_value=strength_data["strength_value"],
                    strength_unit=strength_data["strength_unit"],
                    is_standard_strength=strength_data.get("is_standard_strength", True),
                    pediatric_approved=strength_data.get("pediatric_approved", False),
                )
                db.add(strength)
            await db.flush()

        return salt

    @staticmethod
    async def update_salt(
        db: AsyncSession,
        salt_id: UUID,
        salt_name: str | None = None,
        description: str | None = None,
        chemical_formula: str | None = None,
        habit_forming: bool | None = None,
        prescription_required: bool | None = None,
        schedule: str | None = None,
        pregnancy_category: str | None = None,
        lactation_safe: bool | None = None,
        lactation_notes: str | None = None,
        snomed_code: str | None = None,
        rxcui: str | None = None,
        chemical_class_id: UUID | None = None,
        therapeutic_class_id: UUID | None = None,
        action_class_id: UUID | None = None,
    ) -> Salt | None:
        """Update salt with duplicate check."""
        result = await db.execute(
            select(Salt).where(Salt.salt_id == salt_id)
        )
        salt = result.scalar_one_or_none()
        if not salt:
            return None

        # Check for duplicate name if changing name
        if salt_name is not None and salt_name.lower() != salt.salt_name.lower():
            existing = await db.execute(
                select(Salt).where(
                    func.lower(Salt.salt_name) == salt_name.lower(),
                    Salt.salt_id != salt_id,
                )
            )
            if existing.scalar_one_or_none():
                raise ValueError(f"Salt '{salt_name}' already exists")
            salt.salt_name = salt_name

        # Update optional fields
        if description is not None:
            salt.description = description
        if chemical_formula is not None:
            salt.chemical_formula = chemical_formula
        if habit_forming is not None:
            salt.habit_forming = habit_forming
        if prescription_required is not None:
            salt.prescription_required = prescription_required
        if schedule is not None:
            salt.schedule = schedule
        if pregnancy_category is not None:
            salt.pregnancy_category = pregnancy_category
        if lactation_safe is not None:
            salt.lactation_safe = lactation_safe
        if lactation_notes is not None:
            salt.lactation_notes = lactation_notes
        if snomed_code is not None:
            salt.snomed_code = snomed_code
        if rxcui is not None:
            salt.rxcui = rxcui
        if chemical_class_id is not None:
            salt.chemical_class_id = chemical_class_id
        if therapeutic_class_id is not None:
            salt.therapeutic_class_id = therapeutic_class_id
        if action_class_id is not None:
            salt.action_class_id = action_class_id

        await db.flush()
        return salt

    @staticmethod
    async def delete_salt(
        db: AsyncSession,
        salt_id: UUID,
    ) -> tuple[bool, str | None]:
        """
        Delete salt with safety check.
        Returns (success: bool, error_message: str | None)
        """
        result = await db.execute(
            select(Salt).where(Salt.salt_id == salt_id)
        )
        salt = result.scalar_one_or_none()
        if not salt:
            return False, "Salt not found"

        # Safety check: verify no strengths exist
        strength_count = await db.scalar(
            select(func.count(SaltStrength.salt_strength_id)).where(
                SaltStrength.salt_id == salt_id
            )
        )
        if strength_count > 0:
            return False, f"Cannot delete salt with {strength_count} existing strength(s)"

        await db.delete(salt)
        await db.flush()
        return True, None
