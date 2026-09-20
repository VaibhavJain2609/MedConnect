"""Add doctor_availability and doctor_leaves tables

Revision ID: 024_doctor_availability
Revises: 023_schema_repairs
Create Date: 2026-04-03

Foundation for slot-based booking:
- doctor_availability: recurring weekly windows (weekday 0-6, naive local
  start/end times, slot_duration_minutes, is_active).
- doctor_leaves: full-day leave blocks; partial unique on (doctor_id, date)
  WHERE deleted_at IS NULL so soft-deleted leaves don't block re-adding.

NOTE: this revision is written standalone on top of the current main-chain
head (023_schema_repairs). If a parallel branch adds another migration at the
same position, re-sequence down_revision when merging.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "024_doctor_availability"
down_revision = "023_schema_repairs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "doctor_availability",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("doctor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("doctors.id"), nullable=False),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clinics.id"), nullable=True),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clinic_branches.id"), nullable=True),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("slot_duration_minutes", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("weekday >= 0 AND weekday <= 6", name="ck_doctor_availability_weekday"),
        sa.CheckConstraint("start_time < end_time", name="ck_doctor_availability_time_range"),
        sa.CheckConstraint("slot_duration_minutes > 0", name="ck_doctor_availability_slot_duration"),
    )
    op.create_index(
        "idx_doctor_availability_doctor_weekday",
        "doctor_availability",
        ["doctor_id", "weekday"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_doctor_availability_clinic",
        "doctor_availability",
        ["clinic_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "doctor_leaves",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("doctor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("doctors.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "uq_doctor_leaves_doctor_date",
        "doctor_leaves",
        ["doctor_id", "date"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_doctor_leaves_doctor",
        "doctor_leaves",
        ["doctor_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_doctor_leaves_doctor", table_name="doctor_leaves")
    op.drop_index("uq_doctor_leaves_doctor_date", table_name="doctor_leaves")
    op.drop_table("doctor_leaves")
    op.drop_index("idx_doctor_availability_clinic", table_name="doctor_availability")
    op.drop_index("idx_doctor_availability_doctor_weekday", table_name="doctor_availability")
    op.drop_table("doctor_availability")
