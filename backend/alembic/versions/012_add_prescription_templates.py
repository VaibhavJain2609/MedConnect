"""Add prescription_templates table

Revision ID: 012_add_prescription_templates
Revises: 011_add_amended_from_id
Create Date: 2026-03-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "012_add_prescription_templates"
down_revision = "011_add_amended_from_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prescription_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "doctor_id",
            UUID(as_uuid=True),
            sa.ForeignKey("doctors.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("medicines", JSONB, nullable=False),
        sa.Column("diagnosis", sa.Text, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index(
        "idx_rx_templates_doctor",
        "prescription_templates",
        ["doctor_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_rx_templates_doctor", table_name="prescription_templates")
    op.drop_table("prescription_templates")
