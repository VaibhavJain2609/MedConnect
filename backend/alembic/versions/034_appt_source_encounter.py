"""appointments.source_encounter_id — link a follow-up booking to its encounter

Revision ID: 034_appt_source_encounter
Revises: 033_audit_log_archive
Create Date: 2026-11-02

- ``appointments.source_encounter_id`` (nullable FK → encounters.id):
  records which encounter a follow-up appointment was booked from
  (POST /api/v1/encounters/{id}/follow-up).
- Unique partial index ``uq_appointments_source_encounter`` guarantees at
  most one live follow-up appointment per encounter — the endpoint returns
  the existing row on repeat calls, and the index makes that idempotency
  race-safe under concurrent requests.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "034_appt_source_encounter"
down_revision = "033_audit_log_archive"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "appointments",
        sa.Column(
            "source_encounter_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    # Separate ALTER (mirrors use_alter=True on the model) — encounters and
    # appointments already reference each other via encounters.appointment_id.
    op.create_foreign_key(
        "fk_appointments_source_encounter",
        "appointments",
        "encounters",
        ["source_encounter_id"],
        ["id"],
    )
    op.create_index(
        "uq_appointments_source_encounter",
        "appointments",
        ["source_encounter_id"],
        unique=True,
        postgresql_where=sa.text(
            "source_encounter_id IS NOT NULL AND deleted_at IS NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index("uq_appointments_source_encounter", table_name="appointments")
    op.drop_constraint(
        "fk_appointments_source_encounter", "appointments", type_="foreignkey"
    )
    op.drop_column("appointments", "source_encounter_id")
