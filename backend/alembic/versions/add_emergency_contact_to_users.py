"""add emergency contact to users

Revision ID: add_emergency_contact
Revises: 6074bdcadb5b
Create Date: 2026-03-11

"""
from alembic import op
import sqlalchemy as sa

revision = "add_emergency_contact"
down_revision = "6074bdcadb5b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("emergency_contact_name", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("emergency_contact_phone", sa.String(15), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "emergency_contact_phone")
    op.drop_column("users", "emergency_contact_name")
