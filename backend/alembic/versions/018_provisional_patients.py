"""Add provisional patient support

Revision ID: 018_provisional_patients
Revises: 017_record_access_consent
Create Date: 2026-03-17
"""
import sqlalchemy as sa
from alembic import op

revision = "018_provisional_patients"
down_revision = "017_record_access_consent"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("users", "keycloak_sub", nullable=True)
    op.add_column(
        "users",
        sa.Column("is_provisional", sa.Boolean, nullable=False, server_default="false"),
    )


def downgrade():
    op.drop_column("users", "is_provisional")
    op.alter_column("users", "keycloak_sub", nullable=False)
