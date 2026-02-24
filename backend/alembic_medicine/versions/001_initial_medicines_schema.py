"""Initial medicines schema - components, medicines, medicine_components

Revision ID: 001
Revises: None
Create Date: 2026-02-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create components table
    op.create_table(
        "components",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("common_names", sa.String(500), nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_components_name", "components", ["name"])
    op.create_index("idx_components_name_fts", "components", [sa.text("to_tsvector('english', name)")], postgresql_using="gin")
    op.create_index("idx_components_category", "components", ["category"])

    # Create medicines table
    op.create_table(
        "medicines",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("brand_name", sa.String(255), nullable=False),
        sa.Column("manufacturer", sa.String(255), nullable=True),
        sa.Column("dosage_form", sa.String(100), nullable=True),
        sa.Column("strength", sa.String(100), nullable=True),
        sa.Column("pack_size", sa.String(200), nullable=True),
        sa.Column("therapeutic_class", sa.String(255), nullable=True),
        sa.Column("schedule", sa.String(10), nullable=True),
        sa.Column("mrp", sa.Numeric(10, 2), nullable=True),
        sa.Column("is_discontinued", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("habit_forming", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("alternatives", postgresql.JSONB(), nullable=True),
        sa.Column("interactions", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("mrp >= 0", name="ck_medicines_mrp_positive"),
    )
    op.create_index("idx_medicines_brand", "medicines", ["brand_name"])
    op.create_index("idx_medicines_brand_fts", "medicines", [sa.text("to_tsvector('english', brand_name)")], postgresql_using="gin")
    op.create_index("idx_medicines_manufacturer", "medicines", ["manufacturer"])
    op.create_index("idx_medicines_therapeutic_class", "medicines", ["therapeutic_class"])
    op.create_index("idx_medicines_discontinued", "medicines", ["is_discontinued"], postgresql_where=sa.text("is_discontinued = false"))
    op.create_index("idx_medicines_habit_forming", "medicines", ["habit_forming"], postgresql_where=sa.text("habit_forming = true"))

    # Create medicine_components junction table
    op.create_table(
        "medicine_components",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("medicine_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("medicines.id", ondelete="CASCADE"), nullable=False),
        sa.Column("component_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("components.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("strength", sa.Numeric(10, 3), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("medicine_id", "component_id", name="uq_medicine_component"),
        sa.CheckConstraint("strength > 0", name="ck_medicine_components_strength_positive"),
    )
    op.create_index("idx_medicine_components_medicine", "medicine_components", ["medicine_id"])
    op.create_index("idx_medicine_components_component", "medicine_components", ["component_id"])
    op.create_index("idx_medicine_components_sequence", "medicine_components", ["medicine_id", "sequence"])

    # Create updated_at trigger function if not exists
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)

    # Create triggers for auto-updating updated_at
    op.execute("""
        CREATE TRIGGER update_components_updated_at
        BEFORE UPDATE ON components
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)

    op.execute("""
        CREATE TRIGGER update_medicines_updated_at
        BEFORE UPDATE ON medicines
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS update_medicines_updated_at ON medicines")
    op.execute("DROP TRIGGER IF EXISTS update_components_updated_at ON components")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column()")

    # Drop tables in reverse order
    op.drop_table("medicine_components")
    op.drop_table("medicines")
    op.drop_table("components")
