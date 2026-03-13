"""Add appointments table

Revision ID: 008_add_appointments
Revises: 007_add_patient_links
Create Date: 2026-03-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "008_add_appointments"
down_revision = "007_add_patient_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "appointments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("doctor_id", UUID(as_uuid=True), sa.ForeignKey("doctors.id"), nullable=False),
        sa.Column("clinic_id", UUID(as_uuid=True), sa.ForeignKey("clinics.id"), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer, nullable=False, server_default="30"),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="scheduled"),
        sa.Column("chief_complaint", sa.Text, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("cancelled_reason", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_appointments_doctor_scheduled_at",
        "appointments",
        ["doctor_id", "scheduled_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_appointments_patient_scheduled_at",
        "appointments",
        ["patient_id", "scheduled_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_appointments_patient_scheduled_at", table_name="appointments")
    op.drop_index("idx_appointments_doctor_scheduled_at", table_name="appointments")
    op.drop_table("appointments")
