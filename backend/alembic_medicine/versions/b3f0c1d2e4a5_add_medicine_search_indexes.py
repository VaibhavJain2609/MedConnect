"""add_medicine_search_indexes

Creates the EMR medicine search indexes that were mistakenly placed in the
main-DB chain (alembic/versions/003_add_search_indexes.py). Those tables —
brands, salts, manufacturers, brand_compositions, salt_strengths — live in
this medicine database, so the indexes are created here with IF NOT EXISTS
guards for idempotency.

Revision ID: b3f0c1d2e4a5
Revises: 9a2b1f3c5d7e
Create Date: 2026-04-02
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3f0c1d2e4a5"
down_revision: Union[str, None] = "9a2b1f3c5d7e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add trigram + composite search indexes for the medicine catalog."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # Trigram indexes for fuzzy search (ILIKE '%term%') on name columns
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_brands_name_trgm "
        "ON brands USING gin (brand_name gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_salts_name_trgm "
        "ON salts USING gin (salt_name gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_manufacturers_name_trgm "
        "ON manufacturers USING gin (manufacturer_name gin_trgm_ops)"
    )

    # Composite index for brand compositions (frequently joined pair)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_brand_compositions_brand_salt "
        "ON brand_compositions (brand_id, salt_strength_id)"
    )

    # Index for salt strengths lookup by salt (helps sorting by strength)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_salt_strengths_salt_value "
        "ON salt_strengths (salt_id, strength_value)"
    )

    # Prescription audit queries: "find all prescriptions for a brand"
    op.execute("""
        DO $$
        BEGIN
            IF to_regclass('prescription_audit') IS NOT NULL THEN
                CREATE INDEX IF NOT EXISTS idx_prescription_audit_brand_prescribed
                ON prescription_audit(brand_id, prescribed_at DESC);
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_prescription_audit_brand_prescribed")
    op.execute("DROP INDEX IF EXISTS idx_salt_strengths_salt_value")
    op.execute("DROP INDEX IF EXISTS idx_brand_compositions_brand_salt")
    op.execute("DROP INDEX IF EXISTS idx_manufacturers_name_trgm")
    op.execute("DROP INDEX IF EXISTS idx_salts_name_trgm")
    op.execute("DROP INDEX IF EXISTS idx_brands_name_trgm")

    # Note: pg_trgm extension is left installed as it may be used elsewhere
