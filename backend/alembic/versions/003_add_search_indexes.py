"""Add search performance indexes for EMR medicine tables

Revision ID: 003
Revises: 002
Create Date: 2026-02-24

NOTE: brands/salts/manufacturers/brand_compositions/salt_strengths live in the
*medicine* database (alembic_medicine chain), not the main database this chain
runs against. Every statement below is wrapped in a table-existence guard so a
clean `alembic upgrade head` on the main DB is a no-op instead of failing. The
canonical versions of these indexes are created in the medicine chain by
revision b3f0c1d2e4a5.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create_index_if_table_exists(index_sql: str, table_name: str) -> None:
    """Run CREATE INDEX only when the target table exists in this database."""
    op.execute(f"""
        DO $$
        BEGIN
            IF to_regclass('{table_name}') IS NOT NULL THEN
                {index_sql}
            END IF;
        END $$;
    """)


def upgrade() -> None:
    """Add search performance indexes for frequently queried fields (guarded)."""

    # Required for the trigram indexes below; harmless if already present
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # Brands table - trigram index for fuzzy search (ILIKE queries)
    _create_index_if_table_exists(
        "CREATE INDEX IF NOT EXISTS idx_brands_name_trgm "
        "ON brands USING gin (brand_name gin_trgm_ops);",
        "brands",
    )

    # Salts table - trigram index for fuzzy search
    _create_index_if_table_exists(
        "CREATE INDEX IF NOT EXISTS idx_salts_name_trgm "
        "ON salts USING gin (salt_name gin_trgm_ops);",
        "salts",
    )

    # Manufacturers table - trigram index for fuzzy search
    _create_index_if_table_exists(
        "CREATE INDEX IF NOT EXISTS idx_manufacturers_name_trgm "
        "ON manufacturers USING gin (manufacturer_name gin_trgm_ops);",
        "manufacturers",
    )

    # Composite index for brand compositions (frequently joined)
    _create_index_if_table_exists(
        "CREATE INDEX IF NOT EXISTS idx_brand_compositions_brand_salt "
        "ON brand_compositions (brand_id, salt_strength_id);",
        "brand_compositions",
    )

    # Index for salt strengths lookup by salt
    _create_index_if_table_exists(
        "CREATE INDEX IF NOT EXISTS idx_salt_strengths_salt_value "
        "ON salt_strengths (salt_id, strength_value);",
        "salt_strengths",
    )

    # Index for prescription audit queries (if table exists)
    # Helps with "find all prescriptions for a brand" queries
    op.execute("""
        DO $$
        BEGIN
            IF to_regclass('prescription_audit') IS NOT NULL THEN
                CREATE INDEX IF NOT EXISTS idx_prescription_audit_brand_prescribed
                ON prescription_audit(brand_id, prescribed_at DESC);
            ELSIF to_regclass('prescription_audits') IS NOT NULL THEN
                CREATE INDEX IF NOT EXISTS idx_prescription_audits_brand_timestamp
                ON prescription_audits(brand_id, timestamp DESC);
            END IF;
        END $$;
    """)


def downgrade() -> None:
    """Remove search performance indexes (guarded — safe on the main DB)."""

    # DROP INDEX IF EXISTS is safe even when the table never existed here
    op.execute("DROP INDEX IF EXISTS idx_brands_name_trgm")
    op.execute("DROP INDEX IF EXISTS idx_salts_name_trgm")
    op.execute("DROP INDEX IF EXISTS idx_manufacturers_name_trgm")
    op.execute("DROP INDEX IF EXISTS idx_brand_compositions_brand_salt")
    op.execute("DROP INDEX IF EXISTS idx_salt_strengths_salt_value")
    op.execute("DROP INDEX IF EXISTS idx_prescription_audit_brand_prescribed")
    op.execute("DROP INDEX IF EXISTS idx_prescription_audits_brand_timestamp")

    # Note: pg_trgm extension is left installed as it may be used elsewhere
