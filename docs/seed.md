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

Seeded users get **placeholder** `keycloak_sub` values (`seed-admin-1`,
`seed-doctor-1`, `seed-doctor-2`, `seed-patient-1..3`). They exist only in
the application database — **no Keycloak users are created**, so these
accounts cannot log in as-is.

To log in as a seeded user, create the user in the `medconnect` Keycloak
realm (admin console at `http://localhost:8080`, admin/admin) and set the
user's Keycloak `sub` to match — or simply update the seeded row's
`keycloak_sub` to the `sub` Keycloak assigns:

```sql
UPDATE users SET keycloak_sub = '<keycloak-sub>' WHERE email = 'dr.priya@medconnect.demo';
```

Because auto-provisioning matches on `keycloak_sub`, either approach makes
the JWT resolve to the seeded account with its role, profile, and clinic
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
