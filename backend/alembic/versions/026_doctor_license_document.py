"""Add license_document_url to doctors for onboarding document upload

Revision ID: 026_doctor_license_document
Revises: 026_clinic_timezone
Create Date: 2026-04-24
"""
from alembic import op
import sqlalchemy as sa

revision = "026_doctor_license_document"
down_revision = "026_clinic_timezone"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "doctors",
        sa.Column("license_document_url", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("doctors", "license_document_url")
