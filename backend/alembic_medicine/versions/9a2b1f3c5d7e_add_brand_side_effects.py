"""add brand_side_effects table

Revision ID: 9a2b1f3c5d7e
Revises: 8e7b05567dfb
Create Date: 2026-05-04 09:00:00.000000

Side effects in the source dataset are per-brand (Consolidated_Side_Effects
on each row of the A_Z medicines CSV), not per-salt. Aggregating them up
to salt level and re-projecting through compositions caused every brand
that shared an active ingredient to inherit the union of all reported
effects, which is wrong. This table holds the per-brand mapping.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9a2b1f3c5d7e"
down_revision: Union[str, None] = "8e7b05567dfb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "brand_side_effects",
        sa.Column("brand_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("side_effect_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["brand_id"], ["brands.brand_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["side_effect_id"], ["side_effects.side_effect_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("brand_id", "side_effect_id"),
    )
    op.create_index(
        "idx_bse_brand", "brand_side_effects", ["brand_id"]
    )
    op.create_index(
        "idx_bse_side_effect", "brand_side_effects", ["side_effect_id"]
    )


def downgrade() -> None:
    op.drop_index("idx_bse_side_effect", table_name="brand_side_effects")
    op.drop_index("idx_bse_brand", table_name="brand_side_effects")
    op.drop_table("brand_side_effects")
