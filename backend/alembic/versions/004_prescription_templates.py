"""Add prescription_templates table

Revision ID: 004
Revises: 003
Create Date: 2026-02-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create prescription_templates table
    op.create_table(
        "prescription_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("doctor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("doctors.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("medicines", postgresql.JSONB(), nullable=False),
        sa.Column("diagnosis", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Index for doctor queries with deleted_at filter
    op.create_index(
        "idx_templates_doctor",
        "prescription_templates",
        ["doctor_id", "created_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # Unique constraint: doctor cannot have duplicate template names
    op.create_index(
        "uq_doctor_template_name",
        "prescription_templates",
        ["doctor_id", "name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # Auto-update trigger for updated_at
    op.execute("""
        CREATE TRIGGER update_prescription_templates_updated_at
        BEFORE UPDATE ON prescription_templates
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS update_prescription_templates_updated_at ON prescription_templates")
    op.drop_table("prescription_templates")
