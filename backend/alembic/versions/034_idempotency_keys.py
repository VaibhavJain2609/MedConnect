"""idempotency_keys table for Idempotency-Key double-submit protection

Revision ID: 034_idempotency_keys
Revises: 033_audit_log_archive
Create Date: 2026-11-15

- ``idempotency_keys`` stores one claim row per (key, user_id, endpoint):
  NULL ``response_json`` = request in-flight (409 for duplicates); a stored
  response is replayed verbatim with ``Idempotent-Replay: true``.
- Retention is lazy — rows older than 24h are deleted on read; no worker.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "034_idempotency_keys"
down_revision = "033_audit_log_archive"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "idempotency_keys",
        sa.Column("key", sa.String(255), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("endpoint", sa.String(255), primary_key=True, nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response_json", postgresql.JSONB(), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_idempotency_keys_created_at",
        "idempotency_keys",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_idempotency_keys_created_at", table_name="idempotency_keys")
    op.drop_table("idempotency_keys")
