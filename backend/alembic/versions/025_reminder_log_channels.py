"""Reminder log: real channel enum values + per-channel uniqueness

Revision ID: 025_reminder_log_channels
Revises: 024_db_constraint_races

- Add channel enum values used by notification_channels dispatch
  (in_app/email/sms/whatsapp) and the 'skipped' status, idempotently.
- Rebuild uq_reminder_log_appointment_type as UNIQUE
  (appointment_id, reminder_type, channel) — one log row per attempted
  channel instead of per reminder_type.
"""
from alembic import op

revision = "025_reminder_log_channels"
down_revision = "024_db_constraint_races"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for value in ("in_app", "log", "email", "sms", "whatsapp"):
        op.execute(
            f"ALTER TYPE reminder_channel_enum ADD VALUE IF NOT EXISTS '{value}'"
        )
    op.execute("ALTER TYPE reminder_status_enum ADD VALUE IF NOT EXISTS 'skipped'")
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_reminder_log_appointment_type'
            ) THEN
                ALTER TABLE reminder_logs
                    DROP CONSTRAINT uq_reminder_log_appointment_type;
            END IF;
        END $$;
    """)
    op.execute("""
        ALTER TABLE reminder_logs
            ADD CONSTRAINT uq_reminder_log_appointment_type
            UNIQUE (appointment_id, reminder_type, channel)
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE reminder_logs
            DROP CONSTRAINT IF EXISTS uq_reminder_log_appointment_type
    """)
    op.execute("""
        ALTER TABLE reminder_logs
            ADD CONSTRAINT uq_reminder_log_appointment_type
            UNIQUE (appointment_id, reminder_type)
    """)
    # enum value removal is not supported; values stay on downgrade.
