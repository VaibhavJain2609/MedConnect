"""Add platform_settings table (feature flags + platform config)

Revision ID: 024_platform_settings
Revises: 023_schema_repairs
Create Date: 2026-04-03

Creates the `platform_settings` key/value table used by
/api/v1/admin/settings and seeds the default keys:
  - maintenance_mode (bool)
  - registration_enabled (bool)
  - reminder_channels_enabled (object: in_app/email/sms/whatsapp)
  - max_upload_mb (int)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "024_platform_settings"
down_revision = "024_add_meeting_url_to_appointments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_settings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column(
            "updated_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("key", name="uq_platform_settings_key"),
    )
    op.create_index("idx_platform_settings_key", "platform_settings", ["key"])

    # Seed defaults — idempotent so re-running on a partially-seeded DB is safe.
    op.execute("""
        INSERT INTO platform_settings (key, value, description)
        VALUES
          ('maintenance_mode', 'false'::jsonb,
           'When true, the platform is in maintenance mode for non-admin users'),
          ('registration_enabled', 'true'::jsonb,
           'When false, new user registration is disabled'),
          ('reminder_channels_enabled',
           '{"in_app": true, "email": false, "sms": false, "whatsapp": false}'::jsonb,
           'Which channels appointment/notification reminders may use'),
          ('max_upload_mb', '10'::jsonb,
           'Maximum allowed upload size in megabytes')
        ON CONFLICT (key) DO NOTHING
    """)


def downgrade() -> None:
    op.drop_index("idx_platform_settings_key", table_name="platform_settings")
    op.drop_table("platform_settings")
