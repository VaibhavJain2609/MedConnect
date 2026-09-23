"""hot-path indexes — R16 index audit

Revision ID: 038_hot_path_indexes
Revises: 037_medication_reminders
Create Date: 2026-11-15

Adds the missing indexes found by auditing every ``.where(...)`` /
``order_by(...)`` / ``.join(...)`` in ``app/routers``, ``app/services`` and
``app/workers`` against the indexes already declared on the models /
created by prior migrations. See ``analysis/index-audit-r16.md`` for the
full audit. Only query paths that actually exist in code are indexed:

- ``idx_appointments_clinic_scheduled_at`` — clinic-scoped appointment
  lists filter ``clinic_id = ? AND scheduled_at`` range and order by
  ``scheduled_at`` (routers/appointments.py clinic daily schedule).
- ``idx_appointments_created_at`` — admin "recent activity" orders all
  appointments by ``created_at DESC`` (routers/admin/stats.py).
- ``idx_records_document_url`` — every file download authorizes via
  ``document_url = object_key AND deleted_at IS NULL``
  (routers/uploads.py ``_user_can_access_object``).
- ``idx_rx_valid_until`` — ``check_prescription_expiry`` ARQ task scans
  ``valid_until`` ranges daily (workers/tasks/prescription_expiry.py);
  also serves the active-prescription filter in the medication-reminder
  worker.
- ``idx_rx_created_at`` — admin stats prescription trend range scans.
- ``idx_users_created_at`` — admin user list pagination orders by
  ``created_at DESC``; admin stats patient trend range scans.
- ``idx_doctors_created_at`` — admin doctor list pagination orders by
  ``created_at DESC``; admin stats doctor trend range scans.
- ``idx_encounters_created_at`` — admin visits list pagination orders by
  ``created_at DESC`` (routers/admin/visits.py).
- ``idx_pcl_clinic_consent`` — the doctor↔patient access-control join
  ``PatientClinicLink.clinic_id = ClinicMembership.clinic_id AND
  consent_status IN (...)`` used by services/access_service.py
  (patient search, doctor patient list, record access, uploads auth).

All are plain btree partial indexes on live (``deleted_at IS NULL``) rows,
matching the project convention. No CONCURRENTLY — consistent with prior
migrations; tables are small enough at this stage.
"""
import sqlalchemy as sa
from alembic import op

revision = "038_hot_path_indexes"
down_revision = "037_medication_reminders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- appointments -------------------------------------------------------
    op.create_index(
        "idx_appointments_clinic_scheduled_at",
        "appointments",
        ["clinic_id", "scheduled_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_appointments_created_at",
        "appointments",
        ["created_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # --- medical_records -----------------------------------------------------
    op.create_index(
        "idx_records_document_url",
        "medical_records",
        ["document_url"],
        postgresql_where=sa.text("document_url IS NOT NULL AND deleted_at IS NULL"),
    )

    # --- prescriptions -------------------------------------------------------
    op.create_index(
        "idx_rx_valid_until",
        "prescriptions",
        ["valid_until"],
        postgresql_where=sa.text("valid_until IS NOT NULL AND deleted_at IS NULL"),
    )
    op.create_index(
        "idx_rx_created_at",
        "prescriptions",
        ["created_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # --- users / doctors / encounters ----------------------------------------
    op.create_index(
        "idx_users_created_at",
        "users",
        ["created_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_doctors_created_at",
        "doctors",
        ["created_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_encounters_created_at",
        "encounters",
        ["created_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # --- patient_clinic_links -------------------------------------------------
    op.create_index(
        "idx_pcl_clinic_consent",
        "patient_clinic_links",
        ["clinic_id", "consent_status"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_pcl_clinic_consent", table_name="patient_clinic_links")
    op.drop_index("idx_encounters_created_at", table_name="encounters")
    op.drop_index("idx_doctors_created_at", table_name="doctors")
    op.drop_index("idx_users_created_at", table_name="users")
    op.drop_index("idx_rx_created_at", table_name="prescriptions")
    op.drop_index("idx_rx_valid_until", table_name="prescriptions")
    op.drop_index("idx_records_document_url", table_name="medical_records")
    op.drop_index("idx_appointments_created_at", table_name="appointments")
    op.drop_index("idx_appointments_clinic_scheduled_at", table_name="appointments")
