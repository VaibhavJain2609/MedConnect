"""Push subscriptions table + 'push' reminder channel

Revision ID: 028_push_subscriptions
Revises: 027_user_consent_erasure
Create Date: 2026-09-21

- Create ``push_subscriptions``: one row per Web Push browser subscription,
  upserted by the globally-unique push-service ``endpoint``. ``p256dh`` /
  ``auth`` are the client encryption keys needed to build the payload.
- Add ``push`` to ``reminder_channel_enum`` so ReminderLog rows can record
  push dispatch attempts alongside in_app/email/sms/whatsapp.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "028_push_subscriptions"
down_revision = "027_user_consent_erasure"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "push_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("endpoint", sa.Text(), nullable=False, unique=True),
        sa.Column("p256dh", sa.String(length=255), nullable=False),
        sa.Column("auth", sa.String(length=255), nullable=False),
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
        "idx_push_subscriptions_user",
        "push_subscriptions",
        ["user_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    # ReminderLog.channel is a native enum — the new dispatch channel needs a
    # matching DB value or inserts of 'push' rows fail.
    op.execute(
        "ALTER TYPE reminder_channel_enum ADD VALUE IF NOT EXISTS 'push'"
    )


def downgrade() -> None:
    # Enum value removal is not supported by Postgres; 'push' stays.
    op.drop_index("idx_push_subscriptions_user", table_name="push_subscriptions")
    op.drop_table("push_subscriptions")
