"""Add reminder_logs table for appointment reminders

Revision ID: 022_add_reminder_logs
Revises: 021_add_queue_table
Create Date: 2026-03-31
"""
from alembic import op

revision = "022_add_reminder_logs"
down_revision = "021_add_queue_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DO $$ BEGIN CREATE TYPE reminder_type_enum AS ENUM ('24h', '2h'); EXCEPTION WHEN duplicate_object THEN null; END $$")
    op.execute("DO $$ BEGIN CREATE TYPE reminder_channel_enum AS ENUM ('log', 'sms', 'whatsapp'); EXCEPTION WHEN duplicate_object THEN null; END $$")
    op.execute("DO $$ BEGIN CREATE TYPE reminder_status_enum AS ENUM ('pending', 'sent', 'failed'); EXCEPTION WHEN duplicate_object THEN null; END $$")

    op.execute("""
        CREATE TABLE IF NOT EXISTS reminder_logs (
            id UUID PRIMARY KEY NOT NULL,
            appointment_id UUID NOT NULL REFERENCES appointments(id) ON DELETE CASCADE,
            reminder_type reminder_type_enum NOT NULL,
            channel reminder_channel_enum NOT NULL DEFAULT 'log',
            status reminder_status_enum NOT NULL DEFAULT 'pending',
            message TEXT,
            sent_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_reminder_logs_appointment_id ON reminder_logs (appointment_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS reminder_logs")
    op.execute("DROP TYPE IF EXISTS reminder_status_enum")
    op.execute("DROP TYPE IF EXISTS reminder_channel_enum")
    op.execute("DROP TYPE IF EXISTS reminder_type_enum")
