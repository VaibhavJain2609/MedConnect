"""Add branch_id to prescriptions and appointments tables [MD-274]

Revision ID: 014_add_branch_id
Revises: 013_add_lab_results
Create Date: 2026-03-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "014_add_branch_id"
down_revision = "013_add_lab_results"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add branch_id to prescriptions
    op.add_column(
        "prescriptions",
        sa.Column(
            "branch_id",
            UUID(as_uuid=True),
            sa.ForeignKey("clinic_branches.id"),
            nullable=True,
        ),
    )
    op.create_index(
        "idx_rx_branch",
        "prescriptions",
        ["branch_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # Add branch_id to appointments
    op.add_column(
        "appointments",
        sa.Column(
            "branch_id",
            UUID(as_uuid=True),
            sa.ForeignKey("clinic_branches.id"),
            nullable=True,
        ),
    )
    op.create_index(
        "idx_appointments_branch",
        "appointments",
        ["branch_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_appointments_branch", table_name="appointments")
    op.drop_column("appointments", "branch_id")

    op.drop_index("idx_rx_branch", table_name="prescriptions")
    op.drop_column("prescriptions", "branch_id")
