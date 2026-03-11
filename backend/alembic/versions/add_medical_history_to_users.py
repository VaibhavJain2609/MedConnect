"""add medical history to users

Revision ID: add_medical_history
Revises: add_emergency_contact
Create Date: 2026-03-11

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "add_medical_history"
down_revision = "add_emergency_contact"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("blood_group", sa.String(5), nullable=True))
    op.add_column("users", sa.Column("allergies", JSONB, nullable=True))
    op.add_column("users", sa.Column("chronic_conditions", JSONB, nullable=True))
    op.add_column("users", sa.Column("height_cm", sa.Float, nullable=True))
    op.add_column("users", sa.Column("weight_kg", sa.Float, nullable=True))


def downgrade() -> None:
    op.drop_column("users", "weight_kg")
    op.drop_column("users", "height_cm")
    op.drop_column("users", "chronic_conditions")
    op.drop_column("users", "allergies")
    op.drop_column("users", "blood_group")
