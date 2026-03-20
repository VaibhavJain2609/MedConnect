"""Add revoked_at to patient_clinic_links

Revision ID: 019_revoked_at_clinic_link
Revises: 018_provisional_patients
Create Date: 2026-03-17
"""
import sqlalchemy as sa
from alembic import op

revision = "019_revoked_at_clinic_link"
down_revision = "018_provisional_patients"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "patient_clinic_links",
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("patient_clinic_links", "revoked_at")
