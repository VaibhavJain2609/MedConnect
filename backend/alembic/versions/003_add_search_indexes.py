"""Add search performance indexes for EMR medicine tables

Revision ID: 003
Revises: 002
Create Date: 2026-02-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add search performance indexes for frequently queried fields."""

    # Brands table - optimize for search queries
    # Note: Basic index on brand_name already exists from model definition (index=True)
    # Add trigram index for fuzzy search (ILIKE queries)
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_index(
        "idx_brands_name_trgm",
        "brands",
        [sa.text("brand_name gin_trgm_ops")],
        postgresql_using="gin",
    )

    # Salts table - optimize for search queries
    # Note: Basic index on salt_name already exists from model definition
    # Add trigram index for fuzzy search
    op.create_index(
        "idx_salts_name_trgm",
        "salts",
        [sa.text("salt_name gin_trgm_ops")],
        postgresql_using="gin",
    )

    # Manufacturers table - optimize for search queries
    # Note: manufacturer_name is unique and indexed
    # Add trigram index for fuzzy search
    op.create_index(
        "idx_manufacturers_name_trgm",
        "manufacturers",
        [sa.text("manufacturer_name gin_trgm_ops")],
        postgresql_using="gin",
    )

    # Composite index for brand compositions (frequently joined)
    # Already indexed individually, but composite helps with specific queries
    op.create_index(
        "idx_brand_compositions_brand_salt",
        "brand_compositions",
        ["brand_id", "salt_strength_id"],
    )

    # Index for salt strengths lookup by salt
    # Already has index on salt_id, but composite with value helps sorting
    op.create_index(
        "idx_salt_strengths_salt_value",
        "salt_strengths",
        ["salt_id", "strength_value"],
    )

    # Index for prescription audit queries (if table exists)
    # Helps with "find all prescriptions for a brand" queries
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'prescription_audits') THEN
                CREATE INDEX IF NOT EXISTS idx_prescription_audits_brand_timestamp
                ON prescription_audits(brand_id, timestamp DESC);
            END IF;
        END $$;
    """)


def downgrade() -> None:
    """Remove search performance indexes."""

    # Drop trigram indexes
    op.drop_index("idx_brands_name_trgm", table_name="brands", postgresql_using="gin")
    op.drop_index("idx_salts_name_trgm", table_name="salts", postgresql_using="gin")
    op.drop_index("idx_manufacturers_name_trgm", table_name="manufacturers", postgresql_using="gin")

    # Drop composite indexes
    op.drop_index("idx_brand_compositions_brand_salt", table_name="brand_compositions")
    op.drop_index("idx_salt_strengths_salt_value", table_name="salt_strengths")

    # Drop prescription audit index
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'prescription_audits') THEN
                DROP INDEX IF EXISTS idx_prescription_audits_brand_timestamp;
            END IF;
        END $$;
    """)

    # Note: pg_trgm extension is left installed as it may be used elsewhere
