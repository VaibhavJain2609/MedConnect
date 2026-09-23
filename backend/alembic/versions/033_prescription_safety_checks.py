"""Prescription safety check snapshots

Revision ID: 033_prescription_safety_checks
Revises: 032_appointment_waitlist
Create Date: 2026-11-05

- Create ``prescription_safety_checks``: one row per successful prescription
  creation capturing the clinical safety gate's input snapshot
  (``items_json``) and computed ``alerts_json``, plus ``override_reason`` when
  a "major" alert was overridden. Powers
  ``GET /api/v1/prescriptions/{id}/safety-check`` so doctors can see which
  alerts were shown/overridden at issue time.
- ``ON DELETE CASCADE`` on prescription_id — audit rows die with the
  prescription. No ``deleted_at``: immutable audit data.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "033_prescription_safety_checks"
down_revision = "032_appointment_waitlist"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prescription_safety_checks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "prescription_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("prescriptions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "checked_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("items_json", postgresql.JSONB(), nullable=False),
        sa.Column("alerts_json", postgresql.JSONB(), nullable=False),
        sa.Column("override_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_rx_safety_checks_prescription",
        "prescription_safety_checks",
        ["prescription_id", "checked_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_rx_safety_checks_prescription", table_name="prescription_safety_checks")
    op.drop_table("prescription_safety_checks")
