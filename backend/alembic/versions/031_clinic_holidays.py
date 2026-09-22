"""Clinic holidays table

Revision ID: 031_clinic_holidays
Revises: 030_rx_refill_requests
Create Date: 2026-10-28

- Create ``clinic_holidays``: one row per clinic closure day
  (``clinic_id`` FK CASCADE, clinic-local ``date``, optional ``name``).
  Soft-deletable per model convention.
- Partial unique index ``uq_clinic_holidays_clinic_date`` enforces one
  holiday per clinic per date among live rows; ``idx_clinic_holidays_clinic``
  backs the per-clinic listing and the slot-generation filter.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "031_clinic_holidays"
down_revision = "030_rx_refill_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "clinic_holidays",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "clinic_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("clinics.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "uq_clinic_holidays_clinic_date",
        "clinic_holidays",
        ["clinic_id", "date"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_clinic_holidays_clinic",
        "clinic_holidays",
        ["clinic_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_clinic_holidays_clinic", table_name="clinic_holidays")
    op.drop_index("uq_clinic_holidays_clinic_date", table_name="clinic_holidays")
    op.drop_table("clinic_holidays")
