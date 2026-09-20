"""Add encounters table (SOAP notes)

Revision ID: 024_add_encounters
Revises: 023_schema_repairs
Create Date: 2026-04-10

Creates the `encounters` table — the core EMR entity for clinical visits
with SOAP note sections (subjective/objective/assessment/plan), an optional
appointment link (nullable for walk-ins), an optional clinic link, and a
JSONB vitals snapshot. Partial indexes on the hot query paths
(WHERE deleted_at IS NULL) per project convention.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "024_add_encounters"
down_revision = "024_doctor_availability"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "encounters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("doctor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("doctors.id"), nullable=False),
        sa.Column("appointment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("appointments.id"), nullable=True),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clinics.id"), nullable=True),
        sa.Column("subjective", sa.Text(), nullable=True),
        sa.Column("objective", sa.Text(), nullable=True),
        sa.Column("assessment", sa.Text(), nullable=True),
        sa.Column("plan", sa.Text(), nullable=True),
        sa.Column("vitals_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_encounters_doctor "
        "ON encounters (doctor_id) WHERE deleted_at IS NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_encounters_patient "
        "ON encounters (patient_id) WHERE deleted_at IS NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_encounters_appointment "
        "ON encounters (appointment_id) WHERE deleted_at IS NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_encounters_clinic_created_at "
        "ON encounters (clinic_id, created_at) WHERE deleted_at IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_encounters_clinic_created_at")
    op.execute("DROP INDEX IF EXISTS idx_encounters_appointment")
    op.execute("DROP INDEX IF EXISTS idx_encounters_patient")
    op.execute("DROP INDEX IF EXISTS idx_encounters_doctor")
    op.drop_table("encounters")
