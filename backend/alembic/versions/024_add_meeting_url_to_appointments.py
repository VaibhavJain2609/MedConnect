"""Add meeting_url to appointments for teleconsultation join links

Revision ID: 024_add_meeting_url_to_appointments
Revises: 023_schema_repairs
Create Date: 2026-04-03
"""
from alembic import op
import sqlalchemy as sa

revision = "024_add_meeting_url_to_appointments"
down_revision = "024_add_encounters"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "appointments",
        sa.Column("meeting_url", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("appointments", "meeting_url")
