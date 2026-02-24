#!/usr/bin/env python3
"""
Load Indian medicine dataset into EMR database.

Reads the Extensive_A_Z_medicines_dataset_of_India.csv and imports:
- Manufacturers
- Salts (active pharmaceutical ingredients)
- Salt Strengths
- Brands (commercial medicines)
- Brand Compositions

Usage:
    python scripts/load_indian_medicines.py [--limit N] [--dry-run]
"""

import asyncio
import csv
import re
import sys
from pathlib import Path
from decimal import Decimal
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import medicine_async_session
from app.models.medicine.commercial import Manufacturer, Brand, BrandComposition
from app.models.medicine.salts import Salt, SaltStrength


class DatasetLoader:
    """Loads Indian medicine dataset into EMR database."""

    def __init__(self, db: AsyncSession, dry_run: bool = False):
        self.db = db
        self.dry_run = dry_run
        self.stats = {
            "manufacturers_created": 0,
            "salts_created": 0,
            "strengths_created": 0,
            "brands_created": 0,
            "brands_skipped": 0,
            "errors": 0,
        }

    async def get_or_create_manufacturer(self, name: str) -> Manufacturer:
        """Get existing manufacturer or create new one."""
        result = await self.db.execute(
            select(Manufacturer).where(
                func.lower(Manufacturer.manufacturer_name) == name.lower()
            )
        )
        manufacturer = result.scalar_one_or_none()

        if not manufacturer:
            manufacturer = Manufacturer(
                manufacturer_name=name,
                country="India",  # Assumption based on dataset
                is_active=True,
            )
            self.db.add(manufacturer)
            await self.db.flush()
            self.stats["manufacturers_created"] += 1

        return manufacturer

    def parse_composition(self, comp_str: str) -> Optional[tuple[str, Decimal, str]]:
        """
        Parse composition string like 'Amoxycillin  (500mg)' into (salt_name, strength_value, unit).

        Returns None if parsing fails.
        """
        if not comp_str or comp_str.strip() == "":
            return None

        # Remove extra spaces
        comp_str = " ".join(comp_str.split())

        # Pattern: "Salt Name (123mg)" or "Salt Name (123 mg)"
        match = re.match(r"^(.+?)\s*\((\d+(?:\.\d+)?)\s*([a-zA-Z]+)\)$", comp_str.strip())
        if not match:
            return None

        salt_name = match.group(1).strip()
        strength_value = Decimal(match.group(2))
        strength_unit = match.group(3).lower()

        return (salt_name, strength_value, strength_unit)

    async def get_or_create_salt(self, name: str) -> Salt:
        """Get existing salt or create new one."""
        result = await self.db.execute(
            select(Salt).where(func.lower(Salt.salt_name) == name.lower())
        )
        salt = result.scalar_one_or_none()

        if not salt:
            salt = Salt(
                salt_name=name,
                prescription_required=True,  # Default to true for safety
                habit_forming=False,
            )
            self.db.add(salt)
            await self.db.flush()
            self.stats["salts_created"] += 1

        return salt

    async def get_or_create_strength(
        self, salt: Salt, value: Decimal, unit: str
    ) -> SaltStrength:
        """Get existing strength or create new one."""
        result = await self.db.execute(
            select(SaltStrength).where(
                SaltStrength.salt_id == salt.salt_id,
                SaltStrength.strength_value == value,
                SaltStrength.strength_unit == unit,
            )
        )
        strength = result.scalar_one_or_none()

        if not strength:
            strength = SaltStrength(
                salt_id=salt.salt_id,
                strength_value=value,
                strength_unit=unit,
                is_standard_strength=True,
                pediatric_approved=False,
            )
            self.db.add(strength)
            await self.db.flush()
            self.stats["strengths_created"] += 1

        return strength

    async def load_row(self, row: dict) -> bool:
        """
        Load a single row from CSV.

        Returns True if successful, False if skipped/error.
        """
        try:
            brand_name = row["name"].strip()
            manufacturer_name = row["manufacturer_name"].strip()
            is_discontinued = row["Is_discontinued"].lower() == "true"
            drug_type = row.get("type", "allopathy").strip()

            if not brand_name or not manufacturer_name:
                return False

            # Get or create manufacturer
            manufacturer = await self.get_or_create_manufacturer(manufacturer_name)

            # Check if brand already exists
            existing = await self.db.execute(
                select(Brand).where(
                    func.lower(Brand.brand_name) == brand_name.lower(),
                    Brand.manufacturer_id == manufacturer.manufacturer_id,
                )
            )
            if existing.scalar_one_or_none():
                self.stats["brands_skipped"] += 1
                return False

            # Parse compositions
            compositions = []
            for i in [1, 2]:
                comp_key = f"short_composition{i}"
                if comp_key in row and row[comp_key]:
                    parsed = self.parse_composition(row[comp_key])
                    if parsed:
                        compositions.append(parsed)

            if not compositions:
                # Skip brands without valid compositions
                return False

            # Create brand
            brand = Brand(
                brand_name=brand_name,
                manufacturer_id=manufacturer.manufacturer_id,
                is_discontinued=is_discontinued,
                drug_type=drug_type,
            )
            self.db.add(brand)
            await self.db.flush()

            # Create compositions
            for sequence, (salt_name, strength_value, strength_unit) in enumerate(
                compositions, start=1
            ):
                salt = await self.get_or_create_salt(salt_name)
                strength = await self.get_or_create_strength(
                    salt, strength_value, strength_unit
                )

                composition = BrandComposition(
                    brand_id=brand.brand_id,
                    salt_strength_id=strength.salt_strength_id,
                    sequence=sequence,
                )
                self.db.add(composition)

            self.stats["brands_created"] += 1
            return True

        except Exception as e:
            print(f"Error loading row: {brand_name if 'brand_name' in locals() else 'unknown'}: {e}")
            self.stats["errors"] += 1
            return False

    async def load_csv(self, csv_path: Path, limit: Optional[int] = None):
        """Load CSV file into database."""
        print(f"Loading dataset from: {csv_path}")
        if self.dry_run:
            print("DRY RUN MODE - No data will be committed")

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            rows_processed = 0
            for row in reader:
                if limit and rows_processed >= limit:
                    break

                await self.load_row(row)
                rows_processed += 1

                # Progress indicator
                if rows_processed % 100 == 0:
                    print(f"Processed {rows_processed} rows...")

        if not self.dry_run:
            await self.db.commit()
            print("✓ Data committed to database")
        else:
            await self.db.rollback()
            print("✗ Dry run complete - data rolled back")

        # Print statistics
        print("\n" + "=" * 60)
        print("IMPORT STATISTICS")
        print("=" * 60)
        print(f"Rows processed:        {rows_processed}")
        print(f"Manufacturers created: {self.stats['manufacturers_created']}")
        print(f"Salts created:         {self.stats['salts_created']}")
        print(f"Strengths created:     {self.stats['strengths_created']}")
        print(f"Brands created:        {self.stats['brands_created']}")
        print(f"Brands skipped:        {self.stats['brands_skipped']}")
        print(f"Errors:                {self.stats['errors']}")
        print("=" * 60)


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Load Indian medicine dataset")
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path(__file__).parent.parent.parent / "Dataset" / "Extensive_A_Z_medicines_dataset_of_India.csv",
        help="Path to CSV file",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of rows to process (for testing)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without committing to database",
    )

    args = parser.parse_args()

    if not args.csv.exists():
        print(f"Error: CSV file not found: {args.csv}")
        sys.exit(1)

    async with medicine_async_session() as db:
        loader = DatasetLoader(db, dry_run=args.dry_run)
        await loader.load_csv(args.csv, limit=args.limit)


if __name__ == "__main__":
    asyncio.run(main())
