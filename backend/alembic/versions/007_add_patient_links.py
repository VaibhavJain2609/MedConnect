"""Add PatientClinicLink and PatientLinkCode models

Revision ID: 007_add_patient_links
Revises: 006_add_clinic_invites
Create Date: 2026-03-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "007_add_patient_links"
down_revision = "006_add_clinic_invites"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── patient_clinic_links ──────────────────────────────────────────────
    op.create_table(
        "patient_clinic_links",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("clinic_id", UUID(as_uuid=True), sa.ForeignKey("clinics.id"), nullable=False),
        sa.Column("linked_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("consent_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("patient_id", "clinic_id", name="uq_patient_clinic_link"),
    )
    op.create_index("idx_pcl_patient", "patient_clinic_links", ["patient_id"],
                    postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("idx_pcl_clinic", "patient_clinic_links", ["clinic_id"],
                    postgresql_where=sa.text("deleted_at IS NULL"))

    # ── patient_link_codes ────────────────────────────────────────────────
    op.create_table(
        "patient_link_codes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("code", sa.String(10), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_plc_patient", "patient_link_codes", ["patient_id"],
                    postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("idx_plc_code", "patient_link_codes", ["code"],
                    postgresql_where=sa.text("deleted_at IS NULL"))


def downgrade() -> None:
    op.drop_index("idx_plc_code", table_name="patient_link_codes")
    op.drop_index("idx_plc_patient", table_name="patient_link_codes")
    op.drop_table("patient_link_codes")
    op.drop_index("idx_pcl_clinic", table_name="patient_clinic_links")
    op.drop_index("idx_pcl_patient", table_name="patient_clinic_links")
    op.drop_table("patient_clinic_links")
