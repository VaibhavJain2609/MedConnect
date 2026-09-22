"""Outbound webhook tables

Revision ID: 030_webhooks
Revises: 029_billing_items
Create Date: 2026-10-27

- Create ``webhook_endpoints``: per-clinic outbound webhook subscriptions
  (url, plaintext HMAC signing secret, subscribed ``event_types`` text array,
  ``is_active``). Soft-deletable per model convention.
- Create ``webhook_deliveries``: append-only delivery log, one row per
  (endpoint, emitted event). Child table — no ``deleted_at`` (follows the
  reminder_logs / billing_items convention; FK ``ON DELETE CASCADE``).
- ``status`` is a plain ``String(16)`` (pending|sent|failed) — mirrors
  ``clinic_memberships.role``, avoiding a PG enum that would need ALTER TYPE
  to extend.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "030_webhooks"
down_revision = "029_billing_items"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webhook_endpoints",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "clinic_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("clinics.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("secret", sa.String(255), nullable=False),
        sa.Column("event_types", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
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
        "idx_webhook_endpoints_clinic",
        "webhook_endpoints",
        ["clinic_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "webhook_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "endpoint_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("webhook_endpoints.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_webhook_deliveries_endpoint_id", "webhook_deliveries", ["endpoint_id"])
    op.create_index("ix_webhook_deliveries_status", "webhook_deliveries", ["status"])
    op.create_index("ix_webhook_deliveries_created", "webhook_deliveries", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_webhook_deliveries_created", table_name="webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_status", table_name="webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_endpoint_id", table_name="webhook_deliveries")
    op.drop_table("webhook_deliveries")
    op.drop_index("idx_webhook_endpoints_clinic", table_name="webhook_endpoints")
    op.drop_table("webhook_endpoints")
