"""Add amended_from_id to medical_records

Revision ID: 011_add_amended_from_id
Revises: 010_add_audit_logs
Create Date: 2026-03-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "011_add_amended_from_id"
down_revision = "010_add_audit_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "medical_records",
        sa.Column(
            "amended_from_id",
            UUID(as_uuid=True),
            sa.ForeignKey("medical_records.id"),
            nullable=True,
        ),
    )
    op.create_index(
        "idx_records_amended_from",
        "medical_records",
        ["amended_from_id"],
        postgresql_where=sa.text("amended_from_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_records_amended_from", "medical_records")
    op.drop_column("medical_records", "amended_from_id")
