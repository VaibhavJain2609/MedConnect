"""audit_log_archive table for retention sweeps

Revision ID: 033_audit_log_archive
Revises: 032_appointment_waitlist
Create Date: 2026-11-01

- Create ``audit_log_archive``: same columns as ``audit_logs`` plus
  ``archived_at``. The daily ``audit_retention`` ARQ cron task copies
  ``audit_logs`` rows older than ``settings.AUDIT_RETENTION_DAYS`` here, then
  deletes them from the live table in 1000-row batches — keeping the hot
  query path small while retaining a compliant long-term record.
- ``changed_by`` intentionally has no FK to ``users.id``: archive inserts must
  never fail on a missing user row, and the archive must stay readable even
  if a user is hard-deleted later.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "033_audit_log_archive"
down_revision = "033_prescription_safety_checks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_log_archive",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("table_name", sa.String(50), nullable=False),
        sa.Column("record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(10), nullable=False),
        sa.Column("changed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("old_values", postgresql.JSONB(), nullable=True),
        sa.Column("new_values", postgresql.JSONB(), nullable=True),
        sa.Column(
            "archived_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_audit_archive_table_record",
        "audit_log_archive",
        ["table_name", "record_id"],
    )
    op.create_index(
        "idx_audit_archive_changed_by",
        "audit_log_archive",
        ["changed_by"],
    )
    op.create_index(
        "idx_audit_archive_changed_at",
        "audit_log_archive",
        ["changed_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_audit_archive_changed_at", table_name="audit_log_archive")
    op.drop_index("idx_audit_archive_changed_by", table_name="audit_log_archive")
    op.drop_index("idx_audit_archive_table_record", table_name="audit_log_archive")
    op.drop_table("audit_log_archive")
