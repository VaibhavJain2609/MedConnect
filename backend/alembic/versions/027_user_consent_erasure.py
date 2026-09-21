"""Add DPDP consent + erasure columns to users

Adds four nullable columns to ``users`` for India's Digital Personal Data
Protection Act primitives:

* ``consent_at`` / ``consent_version`` — when the user accepted the privacy
  notice and which version of it.
* ``erasure_requested_at`` / ``erased_at`` — right-to-erasure request and
  completion timestamps (erasure is applied immediately in this release, so
  they are set together).

Revision ID: 027_user_consent_erasure
Revises: 026_doctor_license_document
Create Date: 2026-04-27
"""
from alembic import op
import sqlalchemy as sa

revision = "027_user_consent_erasure"
down_revision = "026_doctor_license_document"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("consent_version", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("erasure_requested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("erased_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "erased_at")
    op.drop_column("users", "erasure_requested_at")
    op.drop_column("users", "consent_version")
    op.drop_column("users", "consent_at")
