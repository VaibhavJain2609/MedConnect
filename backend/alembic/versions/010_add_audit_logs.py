"""Add audit_logs table

Revision ID: 010_add_audit_logs
Revises: 009_add_patient_vitals
Create Date: 2026-03-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "010_add_audit_logs"
down_revision = "009_add_patient_vitals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("table_name", sa.String(50), nullable=False),
        sa.Column("record_id", UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(10), nullable=False),
        sa.Column("changed_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("old_values", JSONB, nullable=True),
        sa.Column("new_values", JSONB, nullable=True),
    )

    op.create_index("idx_audit_table_record", "audit_logs", ["table_name", "record_id"])
    op.create_index("idx_audit_changed_by", "audit_logs", ["changed_by"])
    op.create_index(
        "idx_audit_changed_at",
        "audit_logs",
        [sa.text("changed_at DESC")],
        postgresql_using="btree",
    )


def downgrade() -> None:
    pass
