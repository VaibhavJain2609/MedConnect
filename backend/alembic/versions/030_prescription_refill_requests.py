"""Prescription refill requests table

Revision ID: 030_rx_refill_requests
Revises: 029_billing_items
Create Date: 2026-10-21

- Create ``prescription_refill_requests``: one row per patient refill/renewal
  request against an existing prescription. ``status`` transitions
  pending → approved | declined; on approve ``new_prescription_id`` links to
  the cloned prescription issued by the responding doctor.
- Partial unique index ``uq_refill_pending_per_rx`` enforces at most one
  pending request per prescription (the double-request guard).
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "030_rx_refill_requests"
down_revision = "029_billing_items"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prescription_refill_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "prescription_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("prescriptions.id"),
            nullable=False,
        ),
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
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("response_note", sa.Text(), nullable=True),
        sa.Column(
            "responded_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("doctors.id"),
            nullable=True,
        ),
        sa.Column(
            "new_prescription_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("prescriptions.id"),
            nullable=True,
        ),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
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
        "uq_refill_pending_per_rx",
        "prescription_refill_requests",
        ["prescription_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending' AND deleted_at IS NULL"),
    )
    op.create_index(
        "idx_refill_patient",
        "prescription_refill_requests",
        ["patient_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_refill_clinic_status",
        "prescription_refill_requests",
        ["clinic_id", "status"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_refill_doctor",
        "prescription_refill_requests",
        ["doctor_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_refill_doctor", table_name="prescription_refill_requests")
    op.drop_index("idx_refill_clinic_status", table_name="prescription_refill_requests")
    op.drop_index("idx_refill_patient", table_name="prescription_refill_requests")
    op.drop_index("uq_refill_pending_per_rx", table_name="prescription_refill_requests")
    op.drop_table("prescription_refill_requests")
