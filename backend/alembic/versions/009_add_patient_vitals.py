"""Add patient vitals table

Revision ID: 009_add_patient_vitals
Revises: 008_add_appointments
Create Date: 2026-03-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "009_add_patient_vitals"
down_revision = "008_add_appointments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "patient_vitals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("vital_type", sa.String(30), nullable=False),
        sa.Column("value", sa.Numeric(8, 2), nullable=False),
        sa.Column("unit", sa.String(10), nullable=False),
        sa.Column("recorded_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_patient_vitals_patient_type_recorded_at",
        "patient_vitals",
        ["patient_id", "vital_type", "recorded_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "idx_patient_vitals_patient_type_recorded_at",
        table_name="patient_vitals",
    )
    op.drop_table("patient_vitals")
