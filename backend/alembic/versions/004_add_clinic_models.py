"""Add clinic models and doctor onboarding fields

Revision ID: 004_add_clinic_models
Revises: add_medical_history
Create Date: 2026-03-13

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers
revision = "004_add_clinic_models"
down_revision = "add_medical_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── clinics ──────────────────────────────────────────────────────────
    op.create_table(
        "clinics",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("state", sa.String(100), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("logo_url", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("record_sharing_mode", sa.String(20), nullable=False, server_default="per_clinic"),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_clinics_active", "clinics", ["is_active"],
                    postgresql_where=sa.text("deleted_at IS NULL"))

    # ── clinic_branches ───────────────────────────────────────────────────
    op.create_table(
        "clinic_branches",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("clinic_id", UUID(as_uuid=True), sa.ForeignKey("clinics.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("state", sa.String(100), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_branches_clinic", "clinic_branches", ["clinic_id"],
                    postgresql_where=sa.text("deleted_at IS NULL"))

    # ── clinic_memberships ────────────────────────────────────────────────
    op.create_table(
        "clinic_memberships",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("clinic_id", UUID(as_uuid=True), sa.ForeignKey("clinics.id"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("branch_id", UUID(as_uuid=True), sa.ForeignKey("clinic_branches.id"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "clinic_id", name="uq_membership_user_clinic"),
    )
    op.create_index("idx_memberships_clinic", "clinic_memberships", ["clinic_id"],
                    postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("idx_memberships_user", "clinic_memberships", ["user_id"],
                    postgresql_where=sa.text("deleted_at IS NULL"))

    # ── doctors: onboarding fields ────────────────────────────────────────
    op.add_column("doctors", sa.Column("license_council", sa.String(255), nullable=True))
    op.add_column("doctors", sa.Column("license_year", sa.Integer(), nullable=True))
    op.add_column("doctors", sa.Column("nhr_verification_status", sa.String(20),
                                        nullable=False, server_default="not_checked"))
    op.add_column("doctors", sa.Column("verification_notes", sa.Text(), nullable=True))
    op.add_column("doctors", sa.Column("onboarding_step", sa.String(20),
                                        nullable=False, server_default="pending"))

    # ── medical_records: clinic_id ────────────────────────────────────────
    op.add_column("medical_records", sa.Column("clinic_id", UUID(as_uuid=True),
                                                sa.ForeignKey("clinics.id"), nullable=True))
    op.create_index("idx_records_clinic", "medical_records", ["clinic_id"],
                    postgresql_where=sa.text("deleted_at IS NULL"))

    # ── prescriptions: clinic_id ──────────────────────────────────────────
    op.add_column("prescriptions", sa.Column("clinic_id", UUID(as_uuid=True),
                                              sa.ForeignKey("clinics.id"), nullable=True))
    op.create_index("idx_rx_clinic", "prescriptions", ["clinic_id"],
                    postgresql_where=sa.text("deleted_at IS NULL"))


def downgrade() -> None:
    op.drop_index("idx_rx_clinic", table_name="prescriptions")
    op.drop_column("prescriptions", "clinic_id")

    op.drop_index("idx_records_clinic", table_name="medical_records")
    op.drop_column("medical_records", "clinic_id")

    op.drop_column("doctors", "onboarding_step")
    op.drop_column("doctors", "verification_notes")
    op.drop_column("doctors", "nhr_verification_status")
    op.drop_column("doctors", "license_year")
    op.drop_column("doctors", "license_council")

    op.drop_index("idx_memberships_user", table_name="clinic_memberships")
    op.drop_index("idx_memberships_clinic", table_name="clinic_memberships")
    op.drop_table("clinic_memberships")
    op.drop_index("idx_branches_clinic", table_name="clinic_branches")
    op.drop_table("clinic_branches")
    op.drop_index("idx_clinics_active", table_name="clinics")
    op.drop_table("clinics")
