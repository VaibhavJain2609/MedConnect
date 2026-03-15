"""Add appointment_id to prescriptions

Revision ID: 015_add_appointment_id_to_prescriptions
Revises: 014_add_branch_id
Create Date: 2026-03-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "015_add_appointment_id_to_prescriptions"
down_revision = "014_add_branch_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "prescriptions",
        sa.Column(
            "appointment_id",
            UUID(as_uuid=True),
            sa.ForeignKey("appointments.id"),
            nullable=True,
        ),
    )
    op.create_index(
        "idx_rx_appointment",
        "prescriptions",
        ["appointment_id"],
        postgresql_where=sa.text("appointment_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_rx_appointment", table_name="prescriptions")
    op.drop_column("prescriptions", "appointment_id")
