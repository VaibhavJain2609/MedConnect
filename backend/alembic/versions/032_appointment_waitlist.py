"""Appointment waitlist table

Revision ID: 032_appointment_waitlist
Revises: 031_clinic_holidays
Create Date: 2026-10-28

- Create ``appointment_waitlist``: one row per patient request to be notified
  when a slot opens for a doctor on a fully-booked day. ``status`` transitions
  pending → notified | expired | cancelled; ``notified_at`` records when the
  patient was told a slot freed up.
- Partial unique index ``uq_waitlist_pending_per_patient_doctor_date`` enforces
  at most one pending entry per (patient, doctor, desired_date) — the
  double-join guard.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "032_appointment_waitlist"
down_revision = "032_family_members"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "appointment_waitlist",
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
        sa.Column("desired_date", sa.Date(), nullable=False),
        sa.Column("slot_window", sa.String(20), nullable=False, server_default="any"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
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
        "uq_waitlist_pending_per_patient_doctor_date",
        "appointment_waitlist",
        ["patient_id", "doctor_id", "desired_date"],
        unique=True,
        postgresql_where=sa.text("status = 'pending' AND deleted_at IS NULL"),
    )
    op.create_index(
        "idx_waitlist_doctor_date_status",
        "appointment_waitlist",
        ["doctor_id", "desired_date", "status"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_waitlist_patient",
        "appointment_waitlist",
        ["patient_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_waitlist_clinic_status",
        "appointment_waitlist",
        ["clinic_id", "status"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_waitlist_clinic_status", table_name="appointment_waitlist")
    op.drop_index("idx_waitlist_patient", table_name="appointment_waitlist")
    op.drop_index("idx_waitlist_doctor_date_status", table_name="appointment_waitlist")
    op.drop_index("uq_waitlist_pending_per_patient_doctor_date", table_name="appointment_waitlist")
    op.drop_table("appointment_waitlist")
