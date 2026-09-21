"""add_brand_packaging_barcode_index

Adds a non-unique btree index on ``brand_packaging.barcode`` for
scan-based pack lookup (GTIN/EAN). The column itself already exists from
8e7b05567dfb — this migration is additive only. Non-unique because the
same barcode can legitimately repeat across pack sizes/strengths in
source data.

Also seeds the common dosage/pack forms so pack rows (and their
barcodes) can actually be recorded — ``pack_forms`` ships empty in the
base schema and ``brand_packaging.pack_form_id`` is NOT NULL.

Revision ID: c5d6e7f8a9b0
Revises: b3f0c1d2e4a5
Create Date: 2026-04-20
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c5d6e7f8a9b0"
down_revision: Union[str, None] = "b3f0c1d2e4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Index brand_packaging.barcode and seed standard pack forms."""
    # Non-unique: barcodes can repeat across strengths/pack sizes.
    # Name matches SQLAlchemy's ix_<table>_<column> convention used by
    # BrandPackaging.barcode (index=True) so metadata stays in sync.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_brand_packaging_barcode "
        "ON brand_packaging (barcode)"
    )

    # Seed common dosage/pack forms (idempotent). Without these the admin
    # pack/barcode form has nothing to select and pack_form_id is NOT NULL.
    op.execute("""
        INSERT INTO pack_forms
            (pack_form_id, form_name, route_of_administration,
             is_solid, is_liquid, requires_reconstitution)
        SELECT gen_random_uuid(), v.form_name, v.roa, v.solid, v.liquid, false
        FROM (VALUES
            ('Tablet',    'Oral',    true,  false),
            ('Capsule',   'Oral',    true,  false),
            ('Syrup',     'Oral',    false, true),
            ('Suspension','Oral',    false, true),
            ('Injection', 'IV',      false, true),
            ('Cream',     'Topical', false, false),
            ('Ointment',  'Topical', false, false),
            ('Drops',     'Topical', false, true),
            ('Inhaler',   'Inhalation', false, false),
            ('Sachet',    'Oral',    true,  false),
            ('Other',     NULL,      NULL,  NULL)
        ) AS v(form_name, roa, solid, liquid)
        WHERE NOT EXISTS (
            SELECT 1 FROM pack_forms pf WHERE pf.form_name = v.form_name
        )
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_brand_packaging_barcode")
    # Seeded pack_forms rows are left in place — they may be referenced by
    # brand_packaging rows (FK) and are harmless catalog data.
