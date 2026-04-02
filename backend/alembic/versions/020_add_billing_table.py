"""Add billing table

Revision ID: 020_add_billing_table
Revises: 019_revoked_at_clinic_link
Create Date: 2026-03-31
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "020_add_billing_table"
down_revision = "019_revoked_at_clinic_link"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "billing",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("clinic_id", UUID(as_uuid=True), sa.ForeignKey("clinics.id"), nullable=True),
        sa.Column("appointment_id", UUID(as_uuid=True), sa.ForeignKey("appointments.id"), nullable=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("payment_method", sa.String(20), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index(
        "idx_billing_patient",
        "billing",
        ["patient_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_billing_clinic_status",
        "billing",
        ["clinic_id", "status"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_billing_created_at",
        "billing",
        ["created_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_billing_created_at", table_name="billing")
    op.drop_index("idx_billing_clinic_status", table_name="billing")
    op.drop_index("idx_billing_patient", table_name="billing")
    op.drop_table("billing")
