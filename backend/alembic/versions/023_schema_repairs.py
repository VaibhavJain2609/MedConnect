"""Schema repairs: partial uniques, orphan tables, missing indexes, constraints

Revision ID: 023_schema_repairs
Revises: 022_add_reminder_logs
Create Date: 2026-04-02

Covers:
- Convert hard unique constraints to partial unique indexes
  (WHERE deleted_at IS NULL) so soft-deleted rows don't block
  re-inserts/re-links/re-invites:
    * patient_link_codes.patient_id  (rotation in routers/patient_links.py)
    * clinic_memberships (user_id, clinic_id)  uq_membership_user_clinic
    * patient_clinic_links (patient_id, clinic_id)  uq_patient_clinic_link
- Drop orphaned tables: `medicines` (created by 001, model removed) and
  `audit_log` (created by 001, superseded by `audit_logs` from 010).
- Add uq_reminder_log_appointment_type on reminder_logs(appointment_id,
  reminder_type) to prevent duplicate reminder sends.
- Add uq_prescriptions_record_id on prescriptions(record_id) — the
  MedicalRecord.prescription relationship is uselist=False (1:1).
- Add missing query-path indexes: appointments.clinic_id / status,
  queue_entries.doctor_id / patient_id / appointment_id,
  billing.appointment_id, lab_results.test_category.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "023_schema_repairs"
down_revision = "022_add_reminder_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Hard uniques -> partial unique indexes (WHERE deleted_at IS NULL)
    # ------------------------------------------------------------------

    # patient_link_codes.patient_id: inline `unique=True` in 007 produced the
    # auto-named constraint patient_link_codes_patient_id_key.
    op.execute(
        "ALTER TABLE patient_link_codes "
        "DROP CONSTRAINT IF EXISTS patient_link_codes_patient_id_key"
    )
    op.execute("DROP INDEX IF EXISTS patient_link_codes_patient_id_key")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_patient_link_codes_patient_id "
        "ON patient_link_codes (patient_id) WHERE deleted_at IS NULL"
    )

    # clinic_memberships (user_id, clinic_id)
    op.execute(
        "ALTER TABLE clinic_memberships "
        "DROP CONSTRAINT IF EXISTS uq_membership_user_clinic"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_membership_user_clinic "
        "ON clinic_memberships (user_id, clinic_id) WHERE deleted_at IS NULL"
    )

    # patient_clinic_links (patient_id, clinic_id)
    op.execute(
        "ALTER TABLE patient_clinic_links "
        "DROP CONSTRAINT IF EXISTS uq_patient_clinic_link"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_patient_clinic_link "
        "ON patient_clinic_links (patient_id, clinic_id) WHERE deleted_at IS NULL"
    )

    # ------------------------------------------------------------------
    # 2. Drop orphaned main-DB tables
    #    `medicines`    — created by 001; model deleted (superseded by the
    #                     medicine DB catalog + prescriptions.medicines JSONB)
    #    `audit_log`    — created by 001; superseded by `audit_logs` (010)
    # ------------------------------------------------------------------
    op.execute("DROP TABLE IF EXISTS medicines CASCADE")
    op.execute("DROP TABLE IF EXISTS audit_log CASCADE")

    # ------------------------------------------------------------------
    # 3. reminder_logs: one reminder per (appointment_id, reminder_type)
    # ------------------------------------------------------------------
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'uq_reminder_log_appointment_type'
            ) THEN
                ALTER TABLE reminder_logs
                ADD CONSTRAINT uq_reminder_log_appointment_type
                UNIQUE (appointment_id, reminder_type);
            END IF;
        END $$;
    """)

    # ------------------------------------------------------------------
    # 4. prescriptions.record_id is 1:1 with medical_records
    # ------------------------------------------------------------------
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'uq_prescriptions_record_id'
            ) THEN
                ALTER TABLE prescriptions
                ADD CONSTRAINT uq_prescriptions_record_id UNIQUE (record_id);
            END IF;
        END $$;
    """)

    # ------------------------------------------------------------------
    # 5. Missing indexes for hot query paths (partial on deleted_at IS NULL)
    # ------------------------------------------------------------------
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_appointments_clinic "
        "ON appointments (clinic_id) WHERE deleted_at IS NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_appointments_status "
        "ON appointments (status) WHERE deleted_at IS NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_queue_entries_doctor "
        "ON queue_entries (doctor_id) WHERE deleted_at IS NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_queue_entries_patient "
        "ON queue_entries (patient_id) WHERE deleted_at IS NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_queue_entries_appointment "
        "ON queue_entries (appointment_id) WHERE deleted_at IS NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_billing_appointment "
        "ON billing (appointment_id) WHERE deleted_at IS NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_lab_results_category "
        "ON lab_results (test_category) WHERE deleted_at IS NULL"
    )


def downgrade() -> None:
    # 5. Drop added indexes
    op.execute("DROP INDEX IF EXISTS idx_lab_results_category")
    op.execute("DROP INDEX IF EXISTS idx_billing_appointment")
    op.execute("DROP INDEX IF EXISTS idx_queue_entries_appointment")
    op.execute("DROP INDEX IF EXISTS idx_queue_entries_patient")
    op.execute("DROP INDEX IF EXISTS idx_queue_entries_doctor")
    op.execute("DROP INDEX IF EXISTS idx_appointments_status")
    op.execute("DROP INDEX IF EXISTS idx_appointments_clinic")

    # 4/3. Drop added unique constraints
    op.execute(
        "ALTER TABLE prescriptions "
        "DROP CONSTRAINT IF EXISTS uq_prescriptions_record_id"
    )
    op.execute(
        "ALTER TABLE reminder_logs "
        "DROP CONSTRAINT IF EXISTS uq_reminder_log_appointment_type"
    )

    # 2. Recreate orphaned tables (as defined by 001)
    op.create_table(
        "medicines",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("brand_name", sa.String(255), nullable=False),
        sa.Column("salt_composition", sa.String(500), nullable=False),
        sa.Column("manufacturer", sa.String(255), nullable=True),
        sa.Column("dosage_form", sa.String(100), nullable=True),
        sa.Column("strength", sa.String(100), nullable=True),
        sa.Column("therapeutic_class", sa.String(255), nullable=True),
        sa.Column("schedule", sa.String(10), nullable=True),
        sa.Column("mrp", sa.Numeric(10, 2), nullable=True),
        sa.Column("alternatives", postgresql.JSONB(), nullable=True),
        sa.Column("interactions", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_medicines_brand", "medicines", [sa.text("to_tsvector('english', brand_name)")], postgresql_using="gin")
    op.create_index("idx_medicines_salt", "medicines", [sa.text("to_tsvector('english', salt_composition)")], postgresql_using="gin")

    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=True),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_audit_user", "audit_log", ["user_id", "created_at"])
    op.create_index("idx_audit_resource", "audit_log", ["resource_type", "resource_id"])
    op.create_index("idx_audit_action", "audit_log", ["action", "created_at"])

    # 1. Restore the original hard unique constraints.
    # NOTE: fails if rows with deleted_at IS NOT NULL share the same key —
    # hard-delete or merge those rows before downgrading.
    op.execute("DROP INDEX IF EXISTS uq_patient_clinic_link")
    op.execute(
        "ALTER TABLE patient_clinic_links "
        "ADD CONSTRAINT uq_patient_clinic_link UNIQUE (patient_id, clinic_id)"
    )
    op.execute("DROP INDEX IF EXISTS uq_membership_user_clinic")
    op.execute(
        "ALTER TABLE clinic_memberships "
        "ADD CONSTRAINT uq_membership_user_clinic UNIQUE (user_id, clinic_id)"
    )
    op.execute("DROP INDEX IF EXISTS uq_patient_link_codes_patient_id")
    op.execute(
        "ALTER TABLE patient_link_codes "
        "ADD CONSTRAINT patient_link_codes_patient_id_key UNIQUE (patient_id)"
    )
