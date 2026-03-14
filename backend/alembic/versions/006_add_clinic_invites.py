"""Add ClinicInvite and ClinicJoinRequest models

Revision ID: 006_add_clinic_invites
Revises: 005_backfill_clinic_data
Create Date: 2026-03-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "006_add_clinic_invites"
down_revision = "005_backfill_clinic_data"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── clinic_invites ────────────────────────────────────────────────────
    op.create_table(
        "clinic_invites",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("clinic_id", UUID(as_uuid=True), sa.ForeignKey("clinics.id"), nullable=False),
        sa.Column("invite_type", sa.String(10), nullable=False),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("role", sa.String(20), nullable=False, server_default="doctor"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("use_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_invites_clinic", "clinic_invites", ["clinic_id"],
                    postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("idx_invites_code", "clinic_invites", ["code"],
                    postgresql_where=sa.text("deleted_at IS NULL"))

    # ── clinic_join_requests ──────────────────────────────────────────────
    op.create_table(
        "clinic_join_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("clinic_id", UUID(as_uuid=True), sa.ForeignKey("clinics.id"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("reviewed_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_join_requests_clinic", "clinic_join_requests", ["clinic_id"],
                    postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("idx_join_requests_user", "clinic_join_requests", ["user_id"],
                    postgresql_where=sa.text("deleted_at IS NULL"))


def downgrade() -> None:
    op.drop_index("idx_join_requests_user", table_name="clinic_join_requests")
    op.drop_index("idx_join_requests_clinic", table_name="clinic_join_requests")
    op.drop_table("clinic_join_requests")
    op.drop_index("idx_invites_code", table_name="clinic_invites")
    op.drop_index("idx_invites_clinic", table_name="clinic_invites")
    op.drop_table("clinic_invites")
