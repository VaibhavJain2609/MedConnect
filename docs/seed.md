# Demo data seed

`backend/scripts/seed_demo_data.py` populates the **main** application
database with a small, self-consistent dataset for local development and
demos. It is idempotent — every entity is looked up by a stable key (users
by email, children by FK pairs, appointments by patient + doctor +
scheduled_at), so running it repeatedly creates no duplicates.

## Usage

Via Docker Compose (recommended — uses the backend container's env):

```bash
make seed                    # seed (idempotent)
make seed ARGS="--drop"      # delete seeded rows only
```

Directly against a reachable Postgres:

```bash
cd backend
python scripts/seed_demo_data.py          # seed
python scripts/seed_demo_data.py --drop   # delete seeded rows only
```

The script honours `DATABASE_URL` (default: the compose value
`postgresql+asyncpg://medconnect:medconnect@postgres:5432/medconnect` from
`app.config`). Point it at another database when needed:

```bash
DATABASE_URL="postgresql+asyncpg://medconnect:medconnect@localhost:5432/medconnect" \
    python scripts/seed_demo_data.py
```

## What it creates

| Entity | Count | Notes |
|--------|-------|-------|
| Users | 6 | 1 admin, 2 doctors, 3 patients |
| Doctor profiles | 2 | `verified=True`, `onboarding_step="completed"` |
| Clinic + branch | 1 + 1 | "Sunrise Family Clinic (Demo)", "Main Branch" |
| ClinicMemberships | 2 | Dr. Priya = `owner`, Dr. Arjun = `doctor` |
| PatientClinicLinks | 3 | all `consent_status="approved"` |
| Appointments | 5 | today/tomorrow; statuses: completed, arrived, scheduled, scheduled, cancelled; types: in-person, teleconsult, follow-up |
| Queue entries | 2 | for today: one `in_consultation`, one `waiting` |
| Notifications | 2 | appointment confirmation + patient-linked system notice |

Seeded user emails (all `@medconnect.demo`):

- `admin@medconnect.demo` — admin
- `dr.priya@medconnect.demo` — Dr. Priya Sharma (General Medicine, owner)
- `dr.arjun@medconnect.demo` — Dr. Arjun Mehta (Pediatrics)
- `rohan.verma@medconnect.demo`, `ananya.iyer@medconnect.demo`,
  `kabir.singh@medconnect.demo` — patients

## Credentials / login note

Seeded users' `keycloak_sub` values are fixed UUIDs
(`5eed0000-0000-4000-8000-000000000001` … `…0006`) that match the demo
users in `keycloak/realm-export.json`. On a **fresh** `docker compose up`,
the realm import creates those Keycloak users — all with password
`demo-password` — so seeded accounts can log in directly (and the e2e
suite can mint tokens for them; see docs/e2e.md).

Two caveats:

- **Existing volumes:** `--import-realm` is skipped when the realm already
  exists in Keycloak's DB, so on a stack that pre-dates the demo users they
  won't appear. Recreate the volume (`docker compose down -v && docker
  compose up -d`, then `make seed`) or create the users manually in the
  admin console (`http://localhost:8080`, admin/admin).
- **Databases seeded before the UUID subs:** re-running `make seed` heals
  rows whose `keycloak_sub` still has a legacy `seed-*` placeholder; a sub
  that doesn't start with `seed-` was mapped deliberately and is preserved.
  To start clean instead: `make seed ARGS="--drop" && make seed`.

To point a seeded row at a different Keycloak user, update its
`keycloak_sub` to the `sub` Keycloak assigns:

```sql
UPDATE users SET keycloak_sub = '<keycloak-sub>' WHERE email = 'dr.priya@medconnect.demo';
```

Because auto-provisioning matches on `keycloak_sub`, this makes the JWT
resolve to the seeded account with its role, profile, and clinic
memberships intact.

## `--drop` semantics

`--drop` finds seeded users by email and the clinic by its seeded email,
then **hard-deletes** dependent rows in FK-safe order (queue entries →
notifications → appointments → patient links → memberships → branches →
clinic → doctor profiles → users). Hard delete is deliberate: soft deletes
would keep the unique `keycloak_sub` values occupied and block re-seeding.

Caveats for a shared/dev database:

- Rows that reference seeded entities but weren't created by the script
  (e.g. a queue entry a real user added to the seeded clinic today, or an
  appointment booked with a seeded doctor) are also deleted.
- It only targets the seeded dataset; unrelated data is untouched.
