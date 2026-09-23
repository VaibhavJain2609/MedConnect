"""medication_reminders — opt-in per-prescription adherence reminders

Revision ID: 035_medication_reminders
Revises: 033_audit_log_archive
Create Date: 2026-11-14

- Create ``medication_reminders``: a patient's reminder schedule for one of
  their own prescriptions — ``times_of_day`` is a JSON list of "HH:MM"
  strings interpreted in Asia/Kolkata by the ``send_medication_reminders``
  ARQ cron task (registered on a 15-minute cadence in reminder_worker.py).
- Partial unique index ``uq_medication_reminders_user_rx`` enforces one live
  reminder per (user, prescription) while allowing re-enable after a soft
  delete.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "037_medication_reminders"
down_revision = "036_lab_orders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "medication_reminders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "prescription_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("prescriptions.id"),
            nullable=False,
        ),
        sa.Column("times_of_day", postgresql.JSONB(), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
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
    op.create_index("ix_medication_reminders_user_id", "medication_reminders", ["user_id"])
    op.create_index(
        "ix_medication_reminders_prescription_id",
        "medication_reminders",
        ["prescription_id"],
    )
    # One live reminder per (user, prescription); soft-deleted rows don't count.
    op.create_index(
        "uq_medication_reminders_user_rx",
        "medication_reminders",
        ["user_id", "prescription_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_medication_reminders_enabled",
        "medication_reminders",
        ["enabled"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_medication_reminders_enabled", table_name="medication_reminders")
    op.drop_index("uq_medication_reminders_user_rx", table_name="medication_reminders")
    op.drop_index("ix_medication_reminders_prescription_id", table_name="medication_reminders")
    op.drop_index("ix_medication_reminders_user_id", table_name="medication_reminders")
    op.drop_table("medication_reminders")
