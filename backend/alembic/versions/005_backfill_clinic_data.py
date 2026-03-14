"""Backfill clinic data from doctor facility fields

Revision ID: 005_backfill_clinic_data
Revises: 004_add_clinic_models
Create Date: 2026-03-13

Creates Clinic rows from distinct (facility_name, facility_city) combinations,
creates ClinicMembership rows for each doctor, backfills clinic_id on records
and prescriptions, and marks existing verified doctors as onboarding_step=completed.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "005_backfill_clinic_data"
down_revision = "004_add_clinic_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Create clinics from distinct (facility_name, facility_city) combos
    #    Only for doctors with a non-null facility_name
    conn.execute(sa.text("""
        INSERT INTO clinics (id, name, city, is_active, record_sharing_mode, created_at, updated_at)
        SELECT
            gen_random_uuid(),
            facility_name,
            facility_city,
            true,
            'per_clinic',
            now(),
            now()
        FROM (
            SELECT DISTINCT facility_name, facility_city
            FROM doctors
            WHERE facility_name IS NOT NULL
              AND deleted_at IS NULL
        ) sub
    """))

    # 2. Create ClinicMembership for each doctor → their clinic
    conn.execute(sa.text("""
        INSERT INTO clinic_memberships (id, clinic_id, user_id, role, is_active, joined_at, created_at, updated_at)
        SELECT
            gen_random_uuid(),
            c.id,
            d.user_id,
            'owner',
            true,
            d.created_at,
            now(),
            now()
        FROM doctors d
        JOIN clinics c
          ON c.name = d.facility_name
         AND (c.city = d.facility_city OR (c.city IS NULL AND d.facility_city IS NULL))
        WHERE d.facility_name IS NOT NULL
          AND d.deleted_at IS NULL
          AND c.deleted_at IS NULL
        ON CONFLICT ON CONSTRAINT uq_membership_user_clinic DO NOTHING
    """))

    # 3. Backfill clinic_id on medical_records
    conn.execute(sa.text("""
        UPDATE medical_records mr
        SET clinic_id = (
            SELECT cm.clinic_id
            FROM clinic_memberships cm
            WHERE cm.user_id = (
                SELECT d.user_id FROM doctors d WHERE d.id = mr.doctor_id AND d.deleted_at IS NULL
            )
              AND cm.deleted_at IS NULL
              AND cm.is_active = true
            LIMIT 1
        )
        WHERE mr.doctor_id IS NOT NULL
          AND mr.deleted_at IS NULL
          AND mr.clinic_id IS NULL
    """))

    # 4. Backfill clinic_id on prescriptions
    conn.execute(sa.text("""
        UPDATE prescriptions p
        SET clinic_id = (
            SELECT cm.clinic_id
            FROM clinic_memberships cm
            WHERE cm.user_id = (
                SELECT d.user_id FROM doctors d WHERE d.id = p.doctor_id AND d.deleted_at IS NULL
            )
              AND cm.deleted_at IS NULL
              AND cm.is_active = true
            LIMIT 1
        )
        WHERE p.doctor_id IS NOT NULL
          AND p.deleted_at IS NULL
          AND p.clinic_id IS NULL
    """))

    # 5. Mark existing verified doctors as onboarding_step='completed'
    conn.execute(sa.text("""
        UPDATE doctors
        SET onboarding_step = 'completed'
        WHERE verified = true
          AND deleted_at IS NULL
    """))


def downgrade() -> None:
    conn = op.get_bind()

    # Revert onboarding_step to 'pending' for previously-verified doctors
    conn.execute(sa.text("""
        UPDATE doctors SET onboarding_step = 'pending' WHERE deleted_at IS NULL
    """))

    # Clear backfilled clinic_ids
    conn.execute(sa.text("UPDATE prescriptions SET clinic_id = NULL"))
    conn.execute(sa.text("UPDATE medical_records SET clinic_id = NULL"))

    # Remove memberships and clinics created during upgrade
    # (only safe if no new data was added after this migration)
    conn.execute(sa.text("DELETE FROM clinic_memberships"))
    conn.execute(sa.text("DELETE FROM clinics"))
