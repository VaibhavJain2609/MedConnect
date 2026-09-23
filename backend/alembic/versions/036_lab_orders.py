"""lab_orders table — doctor lab ordering

Revision ID: 035_lab_orders
Revises: 033_audit_log_archive
Create Date: 2026-11-14

- Create ``lab_orders``: one row per lab test a doctor orders for a patient.
  ``status`` transitions ordered → completed | cancelled (enforced in the
  router, same convention as appointments). On completion
  ``result_record_id`` may link to the MedicalRecord that carries the
  uploaded result.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "036_lab_orders"
down_revision = "035_idempotency_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lab_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "patient_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "doctor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("doctors.id"),
            nullable=False,
        ),
        sa.Column(
            "clinic_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("clinics.id"),
            nullable=True,
        ),
        sa.Column("test_name", sa.String(255), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="ordered"),
        sa.Column(
            "result_record_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("medical_records.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_lab_orders_patient",
        "lab_orders",
        ["patient_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_lab_orders_doctor",
        "lab_orders",
        ["doctor_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_lab_orders_status",
        "lab_orders",
        ["status"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("idx_lab_orders_deleted_at", "lab_orders", ["deleted_at"])


def downgrade() -> None:
    op.drop_index("idx_lab_orders_deleted_at", table_name="lab_orders")
    op.drop_index("idx_lab_orders_status", table_name="lab_orders")
    op.drop_index("idx_lab_orders_doctor", table_name="lab_orders")
    op.drop_index("idx_lab_orders_patient", table_name="lab_orders")
    op.drop_table("lab_orders")
