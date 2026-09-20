"""DB-level fixes for queue-number and appointment-booking race conditions

Revision ID: 024_db_constraint_races
Revises: 023_schema_repairs
Create Date: 2026-04-09

Race fixes:

1. Queue numbers — routers/queue.py assigns `max(queue_number)+1` per
   (clinic, UTC day of created_at) with no uniqueness, so concurrent
   check-ins can pick the same number. Adds a generated `queue_date`
   column ((created_at AT TIME ZONE 'UTC')::date — the same "day"
   boundary the router computes) and a partial unique index on
   (clinic_id, queue_date, queue_number) WHERE deleted_at IS NULL,
   matching the router's max() filter. Existing same-day duplicates are
   renumbered above the day's current max before the index is created.

2. Appointment double-booking TOCTOU — routers/appointments.py
   _check_doctor_conflict is SELECT-then-INSERT. Adds a GiST exclusion
   constraint (needs btree_gist) that rejects overlapping
   [scheduled_at, scheduled_at + duration_minutes) ranges for the same
   doctor.

   Scope deliberately mirrors _check_doctor_conflict exactly:
   status IN ('scheduled','arrived','in-progress') AND deleted_at IS NULL.
   'completed'/'cancelled'/'no-show' and soft-deleted rows do NOT block
   slots — a DB constraint broader than the app check would turn
   app-allowed inserts into unhandled IntegrityError/500s.

   PROD NOTE: the constraint is created inside a guard that first scans
   for pre-existing overlapping rows in scope. If any exist the migration
   raises with the offending appointment ids — run a data cleanup
   (cancel/soft-delete the loser of each overlapping pair) and re-run.
   Auto-cancelling appointments is NOT trivially safe, so no automatic
   dedupe is attempted here (unlike the queue renumber above).
"""
from alembic import op

revision = "024_db_constraint_races"
down_revision = "023_schema_repairs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 0. btree_gist: required for EXCLUDE ... WITH = on a uuid column
    # ------------------------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    # ------------------------------------------------------------------
    # 1. queue_entries: one queue_number per (clinic_id, UTC day)
    # ------------------------------------------------------------------

    # Generated "queue day" column — same boundary routers/queue.py uses
    # (UTC calendar date of created_at). AT TIME ZONE 'UTC' yields a
    # timestamp (immutable), so this is valid in a generated column.
    op.execute("""
        ALTER TABLE queue_entries
        ADD COLUMN IF NOT EXISTS queue_date date
        GENERATED ALWAYS AS ((created_at AT TIME ZONE 'UTC')::date) STORED
    """)

    # Defensive dedupe: renumber same-day duplicates to above the day's
    # max before creating the unique index. Keeps the earliest row's
    # number; later duplicates get shifted up. Renumbering a queued entry
    # is safe (it's just display order within the day).
    op.execute("""
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY clinic_id, queue_date, queue_number
                       ORDER BY created_at, id
                   ) AS rn,
                   MAX(queue_number) OVER (PARTITION BY clinic_id, queue_date) AS day_max
            FROM queue_entries
            WHERE deleted_at IS NULL
        )
        UPDATE queue_entries q
        SET queue_number = r.day_max + r.rn - 1
        FROM ranked r
        WHERE q.id = r.id AND r.rn > 1
    """)

    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_queue_entries_daily_number "
        "ON queue_entries (clinic_id, queue_date, queue_number) "
        "WHERE deleted_at IS NULL"
    )

    # ------------------------------------------------------------------
    # 2. appointments: exclusion constraint against doctor double-booking
    # ------------------------------------------------------------------

    # Guard: refuse to create the constraint if existing rows already
    # violate it. Cancelling/merging real appointments is a business
    # decision — surface the conflicting ids and abort instead.
    op.execute("""
        DO $$
        DECLARE
            conflict_count int;
        BEGIN
            SELECT count(*) INTO conflict_count
            FROM appointments a
            JOIN appointments b
              ON a.doctor_id = b.doctor_id
             AND a.id < b.id
             AND a.deleted_at IS NULL AND b.deleted_at IS NULL
             AND a.status IN ('scheduled','arrived','in-progress')
             AND b.status IN ('scheduled','arrived','in-progress')
             AND tstzrange(
                     a.scheduled_at,
                     a.scheduled_at + (a.duration_minutes * interval '1 minute'),
                     '[)')
              && tstzrange(
                     b.scheduled_at,
                     b.scheduled_at + (b.duration_minutes * interval '1 minute'),
                     '[)');

            IF conflict_count > 0 THEN
                RAISE NOTICE 'Conflicting appointment pairs: %',
                    (SELECT string_agg(format('(%s, %s)', a.id, b.id), ', ')
                     FROM appointments a
                     JOIN appointments b
                       ON a.doctor_id = b.doctor_id
                      AND a.id < b.id
                      AND a.deleted_at IS NULL AND b.deleted_at IS NULL
                      AND a.status IN ('scheduled','arrived','in-progress')
                      AND b.status IN ('scheduled','arrived','in-progress')
                      AND tstzrange(
                              a.scheduled_at,
                              a.scheduled_at + (a.duration_minutes * interval '1 minute'),
                              '[)')
                       && tstzrange(
                              b.scheduled_at,
                              b.scheduled_at + (b.duration_minutes * interval '1 minute'),
                              '[)'));
                RAISE EXCEPTION
                    'Cannot add excl_appointments_doctor_no_overlap: % existing '
                    'appointment pair(s) overlap for the same doctor. Cancel or '
                    'soft-delete one appointment in each pair listed in the '
                    'NOTICE above, then re-run this migration.', conflict_count;
            END IF;
        END $$;
    """)

    # Half-open [) ranges so back-to-back appointments (end == start) are
    # allowed, matching the strict-inequality overlap check in
    # _check_doctor_conflict.
    op.execute("""
        ALTER TABLE appointments
        ADD CONSTRAINT excl_appointments_doctor_no_overlap
        EXCLUDE USING gist (
            doctor_id WITH =,
            tstzrange(
                scheduled_at,
                scheduled_at + (duration_minutes * interval '1 minute'),
                '[)'
            ) WITH &&
        )
        WHERE (
            status IN ('scheduled','arrived','in-progress')
            AND deleted_at IS NULL
        )
    """)


def downgrade() -> None:
    op.execute(
        "ALTER TABLE appointments "
        "DROP CONSTRAINT IF EXISTS excl_appointments_doctor_no_overlap"
    )
    op.execute("DROP INDEX IF EXISTS uq_queue_entries_daily_number")
    op.execute("ALTER TABLE queue_entries DROP COLUMN IF EXISTS queue_date")
    # btree_gist is left installed — harmless and possibly shared.
