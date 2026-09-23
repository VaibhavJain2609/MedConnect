"""message_threads + thread_messages — secure patient↔clinic messaging

Revision ID: 038_message_threads
Revises: 037_medication_reminders
Create Date: 2026-11-21

- ``message_threads``: one thread per (patient, clinic, subject). ``clinic_id``
  is nullable + ON DELETE SET NULL so a patient's history survives clinic
  deletion. Per-side read cursors ``patient_last_seen_at`` /
  ``clinic_last_seen_at`` back the unread-badge counts (clinic cursor is
  shared by all staff of that clinic — intentionally simple).
- ``thread_messages``: immutable message bodies (no edit surface); soft
  delete retained for moderation only.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "038_message_threads"
down_revision = "037_medication_reminders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "message_threads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "patient_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "clinic_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("clinics.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("patient_last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("clinic_last_seen_at", sa.DateTime(timezone=True), nullable=True),
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
        "idx_threads_patient",
        "message_threads",
        ["patient_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_threads_clinic",
        "message_threads",
        ["clinic_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "thread_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "thread_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("message_threads.id"),
            nullable=False,
        ),
        sa.Column(
            "sender_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("body", sa.Text(), nullable=False),
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
        "idx_thread_messages_thread",
        "thread_messages",
        ["thread_id", "created_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_thread_messages_thread", table_name="thread_messages")
    op.drop_table("thread_messages")
    op.drop_index("idx_threads_clinic", table_name="message_threads")
    op.drop_index("idx_threads_patient", table_name="message_threads")
    op.drop_table("message_threads")
