"""Add record_access_consents table

Revision ID: 017_record_access_consent
Revises: 016_family_accounts
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "017_record_access_consent"
down_revision = "016_family_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "record_access_consents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("doctor_id", UUID(as_uuid=True), sa.ForeignKey("doctors.id"), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("clinic_id", UUID(as_uuid=True), sa.ForeignKey("clinics.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("purpose", sa.Text, nullable=True),
        sa.Column("access_duration_days", sa.Integer, nullable=False, server_default="30"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_rac_doctor_patient",
        "record_access_consents",
        ["doctor_id", "patient_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_rac_patient",
        "record_access_consents",
        ["patient_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_rac_expires",
        "record_access_consents",
        ["expires_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_rac_expires", "record_access_consents")
    op.drop_index("idx_rac_patient", "record_access_consents")
    op.drop_index("idx_rac_doctor_patient", "record_access_consents")
    op.drop_table("record_access_consents")
