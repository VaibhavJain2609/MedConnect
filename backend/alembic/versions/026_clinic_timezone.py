"""Add timezone column to clinics

Clinic-local timezone used when interpreting naive availability window
times into absolute (UTC) instants for slot generation.

Revision ID: 026_clinic_timezone
Revises: 025_reminder_log_channels
Create Date: 2026-09-21
"""

from alembic import op
import sqlalchemy as sa

revision = "026_clinic_timezone"
down_revision = "025_reminder_log_channels"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "clinics",
        sa.Column(
            "timezone",
            sa.String(length=50),
            nullable=False,
            server_default="Asia/Kolkata",
        ),
    )


def downgrade() -> None:
    op.drop_column("clinics", "timezone")
