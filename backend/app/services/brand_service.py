"""Service layer for Brand and Manufacturer operations."""

from uuid import UUID
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Brand,
    Manufacturer,
    BrandComposition,
    SaltStrength,
    Salt,
    BrandSideEffect,
)


class BrandService:
    """Service for managing brands (commercial medicines)."""

    @staticmethod
    async def get_brand_by_id(db: AsyncSession, brand_id: UUID) -> Brand | None:
        """Get brand by ID with compositions, manufacturer, and per-brand side effects."""
        result = await db.execute(
            select(Brand)
            .options(
                selectinload(Brand.manufacturer),
                selectinload(Brand.compositions)
                .selectinload(BrandComposition.salt_strength)
                .selectinload(SaltStrength.salt),
                selectinload(Brand.packaging),
                selectinload(Brand.side_effects).joinedload(BrandSideEffect.side_effect),
            )
            .where(Brand.brand_id == brand_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def search_brands(
        db: AsyncSession,
        search: str | None = None,
        salt_id: UUID | None = None,
        manufacturer_id: UUID | None = None,
        include_discontinued: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Brand], int]:
        """Search brands with filters."""
        # Build count query (faster without joins/loads)
        count_query = select(func.count(Brand.brand_id))

        # Search filter
        if search:
            count_query = count_query.where(Brand.brand_name.ilike(f"%{search}%"))

        # Salt filter (brands containing this salt)
        if salt_id:
            count_query = count_query.join(Brand.compositions).join(BrandComposition.salt_strength).where(
                SaltStrength.salt_id == salt_id
            )

        # Manufacturer filter
        if manufacturer_id:
            count_query = count_query.where(Brand.manufacturer_id == manufacturer_id)

        # Discontinued filter
        if not include_discontinued:
            count_query = count_query.where(Brand.is_discontinued == False)

        # Get total count
        total = await db.scalar(count_query)

        # Build main query with optimized loading
        query = select(Brand).options(
            joinedload(Brand.manufacturer),
            selectinload(Brand.compositions).joinedload(BrandComposition.salt_strength).joinedload(SaltStrength.salt),
        )

        # Apply same filters
        if search:
            query = query.where(Brand.brand_name.ilike(f"%{search}%"))

        if salt_id:
            query = query.join(Brand.compositions).join(BrandComposition.salt_strength).where(
                SaltStrength.salt_id == salt_id
            )

        if manufacturer_id:
            query = query.where(Brand.manufacturer_id == manufacturer_id)

        if not include_discontinued:
            query = query.where(Brand.is_discontinued == False)

        # Apply pagination
        query = query.order_by(Brand.brand_name).limit(limit).offset(offset)

        result = await db.execute(query)
        brands = list(result.scalars().unique().all())

        return brands, total or 0

    @staticmethod
    async def get_brand_alternatives(db: AsyncSession, brand_id: UUID) -> list[Brand]:
        """Get alternative brands with EXACT same salt composition (same salts + same strengths)."""
        # Get the salt_strength_ids for the original brand (lightweight query)
        strength_ids_query = (
            select(BrandComposition.salt_strength_id)
            .where(BrandComposition.brand_id == brand_id)
        )
        result = await db.execute(strength_ids_query)
        strength_ids = [row[0] for row in result.all()]

        if not strength_ids:
            return []

        num_components = len(strength_ids)

        # Find brands that have ALL the same salt_strength_ids and ONLY those
        # Step 1: Find brands with the exact count of matching strengths
        matching_brands_subquery = (
            select(BrandComposition.brand_id)
            .where(BrandComposition.salt_strength_id.in_(strength_ids))
            .group_by(BrandComposition.brand_id)
            .having(func.count(BrandComposition.salt_strength_id) == num_components)
            .subquery()
        )

        # Step 2: Verify these brands have ONLY these strengths (no extras)
        brands_with_correct_count = (
            select(BrandComposition.brand_id)
            .group_by(BrandComposition.brand_id)
            .having(func.count(BrandComposition.salt_strength_id) == num_components)
            .subquery()
        )

        # Step 3: Get brands that match both conditions
        query = (
            select(Brand)
            .options(
                joinedload(Brand.manufacturer),
                selectinload(Brand.compositions).joinedload(BrandComposition.salt_strength).joinedload(SaltStrength.salt),
            )
            .where(
                Brand.brand_id.in_(select(matching_brands_subquery.c.brand_id)),
                Brand.brand_id.in_(select(brands_with_correct_count.c.brand_id)),
                Brand.brand_id != brand_id,
                Brand.is_discontinued == False,
            )
            .order_by(Brand.brand_name)
            .limit(20)
        )

        result = await db.execute(query)
        return list(result.scalars().unique().all())


class ManufacturerService:
    """Service for managing manufacturers."""

    @staticmethod
    async def get_manufacturer_by_id(db: AsyncSession, manufacturer_id: UUID) -> Manufacturer | None:
        """Get manufacturer by ID."""
        result = await db.execute(
            select(Manufacturer).where(Manufacturer.manufacturer_id == manufacturer_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def search_manufacturers(
        db: AsyncSession,
        search: str | None = None,
        is_active: bool | None = True,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Manufacturer], int]:
        """Search manufacturers."""
        query = select(Manufacturer)

        if search:
            query = query.where(Manufacturer.manufacturer_name.ilike(f"%{search}%"))

        if is_active is not None:
            query = query.where(Manufacturer.is_active == is_active)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await db.scalar(count_query)

        # Apply pagination
        query = query.order_by(Manufacturer.manufacturer_name).limit(limit).offset(offset)

        result = await db.execute(query)
        manufacturers = list(result.scalars().all())

        return manufacturers, total or 0

    @staticmethod
    async def create_manufacturer(
        db: AsyncSession,
        manufacturer_name: str,
        country: str | None = None,
        license_number: str | None = None,
        contact_info: dict | None = None,
        is_active: bool = True,
    ) -> Manufacturer:
        """Create a new manufacturer with duplicate check."""
        # Check for duplicate name (case-insensitive)
        existing = await db.execute(
            select(Manufacturer).where(
                func.lower(Manufacturer.manufacturer_name) == manufacturer_name.lower()
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"Manufacturer '{manufacturer_name}' already exists")

        manufacturer = Manufacturer(
            manufacturer_name=manufacturer_name,
            country=country,
            license_number=license_number,
            contact_info=contact_info,
            is_active=is_active,
        )
        db.add(manufacturer)
        await db.flush()
        return manufacturer

    @staticmethod
    async def update_manufacturer(
        db: AsyncSession,
        manufacturer_id: UUID,
        manufacturer_name: str | None = None,
        country: str | None = None,
        license_number: str | None = None,
        contact_info: dict | None = None,
        is_active: bool | None = None,
    ) -> Manufacturer | None:
        """Update manufacturer with duplicate check."""
        result = await db.execute(
            select(Manufacturer).where(Manufacturer.manufacturer_id == manufacturer_id)
        )
        manufacturer = result.scalar_one_or_none()
        if not manufacturer:
            return None

        # Check for duplicate name if changing name
        if manufacturer_name is not None and manufacturer_name.lower() != manufacturer.manufacturer_name.lower():
            existing = await db.execute(
                select(Manufacturer).where(
                    func.lower(Manufacturer.manufacturer_name) == manufacturer_name.lower(),
                    Manufacturer.manufacturer_id != manufacturer_id,
                )
            )
            if existing.scalar_one_or_none():
                raise ValueError(f"Manufacturer '{manufacturer_name}' already exists")
            manufacturer.manufacturer_name = manufacturer_name

        # Update optional fields
        if country is not None:
            manufacturer.country = country
        if license_number is not None:
            manufacturer.license_number = license_number
        if contact_info is not None:
            manufacturer.contact_info = contact_info
        if is_active is not None:
            manufacturer.is_active = is_active

        await db.flush()
        return manufacturer

    @staticmethod
    async def delete_manufacturer(
        db: AsyncSession,
        manufacturer_id: UUID,
    ) -> tuple[bool, str | None]:
        """
        Delete manufacturer with safety check.
        Returns (success: bool, error_message: str | None)
        """
        result = await db.execute(
            select(Manufacturer).where(Manufacturer.manufacturer_id == manufacturer_id)
        )
        manufacturer = result.scalar_one_or_none()
        if not manufacturer:
            return False, "Manufacturer not found"

        # Safety check: verify no brands exist
        brand_count = await db.scalar(
            select(func.count(Brand.brand_id)).where(Brand.manufacturer_id == manufacturer_id)
        )
        if brand_count > 0:
            return False, f"Cannot delete manufacturer with {brand_count} existing brand(s)"

        await db.delete(manufacturer)
        await db.flush()
        return True, None
