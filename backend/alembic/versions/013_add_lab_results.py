"""Add lab_results table

Revision ID: 013_add_lab_results
Revises: 012_add_prescription_templates
Create Date: 2026-03-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "013_add_lab_results"
down_revision = "012_add_prescription_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lab_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("test_id", sa.String(50), nullable=False, unique=True),
        sa.Column(
            "patient_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "doctor_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("test_name", sa.String(255), nullable=False),
        sa.Column("test_category", sa.String(100), nullable=True),
        sa.Column("appointment_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("result_value", sa.String(255), nullable=True),
        sa.Column("result_unit", sa.String(50), nullable=True),
        sa.Column("normal_range", sa.String(100), nullable=True),
        sa.Column("abnormal_flag", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index(
        "idx_lab_results_patient",
        "lab_results",
        ["patient_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_lab_results_doctor",
        "lab_results",
        ["doctor_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_lab_results_status",
        "lab_results",
        ["status"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_lab_results_deleted_at",
        "lab_results",
        ["deleted_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_lab_results_deleted_at", table_name="lab_results")
    op.drop_index("idx_lab_results_status", table_name="lab_results")
    op.drop_index("idx_lab_results_doctor", table_name="lab_results")
    op.drop_index("idx_lab_results_patient", table_name="lab_results")
    op.drop_table("lab_results")
