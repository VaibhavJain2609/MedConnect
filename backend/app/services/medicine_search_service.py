"""Unified medicine search service."""

from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.services.salt_service import SaltService
from app.services.brand_service import BrandService


class MedicineSearchResult(BaseModel):
    """Unified search result."""
    salts: list[dict]
    brands: list[dict]
    total_salts: int
    total_brands: int


class MedicineSearchService:
    """Unified search across salts and brands."""

    @staticmethod
    async def search_all(
        db: AsyncSession,
        search: str,
        limit: int = 50,
    ) -> MedicineSearchResult:
        """Search both salts and brands."""
        # Search salts
        salts, total_salts = await SaltService.search_salts(
            db, search=search, limit=limit
        )

        # Search brands
        brands, total_brands = await BrandService.search_brands(
            db, search=search, limit=limit
        )

        # Convert to dict for response
        salt_dicts = [
            {
                "id": str(s.salt_id),
                "name": s.salt_name,
                "type": "salt",
                "chemical_class": s.chemical_class.class_name if s.chemical_class else None,
                "therapeutic_class": s.therapeutic_class.class_name if s.therapeutic_class else None,
                "strengths": [
                    {
                        "id": str(ss.salt_strength_id),
                        "value": str(ss.strength_value),
                        "unit": ss.strength_unit,
                        "display": ss.display_strength,
                    }
                    for ss in s.strengths
                ],
            }
            for s in salts
        ]

        brand_dicts = [
            {
                "id": str(b.brand_id),
                "name": b.brand_name,
                "type": "brand",
                "manufacturer": b.manufacturer.manufacturer_name if b.manufacturer else None,
                "composition": b.salt_composition,
                "is_discontinued": b.is_discontinued,
            }
            for b in brands
        ]

        return MedicineSearchResult(
            salts=salt_dicts,
            brands=brand_dicts,
            total_salts=total_salts,
            total_brands=total_brands,
        )

    @staticmethod
    async def get_brands_by_salt(
        db: AsyncSession,
        salt_id: UUID,
        strength_value: float | None = None,
        strength_unit: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Get all brands containing a specific salt (optionally with specific strength)."""
        brands, _ = await BrandService.search_brands(
            db, salt_id=salt_id, limit=limit
        )

        # Filter by strength if specified
        if strength_value and strength_unit:
            filtered_brands = []
            for brand in brands:
                for comp in brand.compositions:
                    if (
                        comp.salt_strength.salt_id == salt_id
                        and float(comp.salt_strength.strength_value) == strength_value
                        and comp.salt_strength.strength_unit == strength_unit
                    ):
                        filtered_brands.append(brand)
                        break
            brands = filtered_brands

        return [
            {
                "id": str(b.brand_id),
                "name": b.brand_name,
                "manufacturer": b.manufacturer.manufacturer_name if b.manufacturer else None,
                "composition": b.salt_composition,
                "is_discontinued": b.is_discontinued,
            }
            for b in brands
        ]
