"""Billing line items table

Revision ID: 029_billing_items
Revises: 028_push_subscriptions
Create Date: 2026-10-20

- Create ``billing_items``: one row per line item on a bill. Follows the
  reminder_logs child-table convention — FK ``ON DELETE CASCADE`` to
  ``billing.id``, no ``deleted_at`` (the parent bill is soft-deleted; its
  items disappear only if the billing row is ever hard-deleted).
- ``amount`` is the server-computed line total (quantity * unit_amount);
  ``unit_amount`` is the per-unit price. The bill-level ``billing.amount``
  remains the authoritative invoice total.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "029_billing_items"
down_revision = "028_push_subscriptions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "billing_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "billing_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("billing.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("quantity", sa.Numeric(10, 2), nullable=False, server_default="1"),
        sa.Column("unit_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
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
    )
    op.create_index("ix_billing_items_billing_id", "billing_items", ["billing_id"])


def downgrade() -> None:
    op.drop_index("ix_billing_items_billing_id", table_name="billing_items")
    op.drop_table("billing_items")
