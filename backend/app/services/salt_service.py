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
