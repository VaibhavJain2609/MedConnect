#!/usr/bin/env python3
"""
Initialize medicine database schema.

Creates all EMR tables (manufacturers, salts, brands, etc.) in the medicine database.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.database import medicine_engine, MedicineBase

# Import all models to register them with MedicineBase
from app.models.medicine.commercial import Manufacturer, Brand, BrandComposition
from app.models.medicine.salts import Salt, SaltStrength
from app.models.medicine.classifications import ChemicalClass, TherapeuticClass, ActionClass
from app.models.medicine.packaging import PackForm, BrandPackaging
from app.models.medicine.clinical_safety import SideEffect, Contraindication, SaltSideEffect, SaltContraindication, DrugInteraction
from app.models.medicine.indications import Use, SaltUse
from app.models.medicine.alternatives import SaltAlternative
from app.models.medicine.dosing import DosingGuideline
from app.models.medicine.audit import MedicineSearchLog, PrescriptionAudit


async def init_medicine_db():
    """Create all medicine database tables."""

    print("🏥 Initializing Medicine Database Schema...")
    print("=" * 60)

    async with medicine_engine.begin() as conn:
        # Enable required extensions
        print("📦 Enabling PostgreSQL extensions...")
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        print("✓ Extensions enabled")

        # Create all tables
        print("\n🔨 Creating EMR tables...")
        await conn.run_sync(MedicineBase.metadata.create_all)
        print("✓ All tables created")

        # Verify tables
        print("\n📊 Verifying tables...")
        result = await conn.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """))
        tables = [row[0] for row in result.fetchall()]

        print(f"✓ Created {len(tables)} tables:")
        for table in tables:
            print(f"  - {table}")

    print("\n" + "=" * 60)
    print("✅ Medicine database initialized successfully!")
    print("\nNext steps:")
    print("  1. Run: alembic upgrade head (to add indexes)")
    print("  2. Run: python scripts/load_indian_medicines.py")


if __name__ == "__main__":
    asyncio.run(init_medicine_db())
