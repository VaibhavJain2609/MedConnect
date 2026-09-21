# DPDP erasure runbook

Operational checklist for completing a patient's right-to-erasure request under
the Digital Personal Data Protection Act, 2023 (DPDP). Erasure is a **two-step**
process: the self-service API anonymizes the application database, then an
operator scrubs the Keycloak identity — the app intentionally holds no IdP
admin credential, so step 2 is manual.

| Step | Where | What happens |
|------|-------|--------------|
| 1. App erasure | `POST /api/v1/patients/erasure` (patient self-service) | `users` row anonymized in place, clinic consent links revoked, notification prefs deleted, patient-entered free text blanked |
| 2. IdP erasure | `backend/scripts/keycloak_erasure.sh` (operator) | Keycloak user disabled + PII tombstoned (default) or deleted |

## Detecting a pending IdP step

The `POST /api/v1/patients/erasure` response includes
`"keycloak_identity_retained": true` on both the `erased` and
`already_processed` paths — ops automation can poll/alert on that field. The
`users.erased_at` column and the `ERASE` audit-log entry identify accounts
awaiting step 2:

```sql
SELECT id, keycloak_sub, erased_at FROM users
WHERE erased_at IS NOT NULL AND deleted_at IS NULL;
```

Each row's `keycloak_sub` is the Keycloak user id needed below (the JWT `sub`
claim is the Keycloak user UUID).

## Step 1 — app erasure (patient-triggered)

The patient calls `POST /api/v1/patients/erasure` while authenticated. The call
is idempotent — a repeat returns `{"status": "already_processed"}`. For a
support-initiated request, have the patient trigger it from the app; there is
no admin-side erasure endpoint.

Confirm the response:

```json
{"status": "erased", "erasure_requested_at": "…", "erased_at": "…",
 "keycloak_identity_retained": true}
```

## Step 2 — Keycloak erasure (operator)

Run from any host that can reach the Keycloak admin API
(`http://localhost:8080` on the compose stack; the admin URL in deployed envs).
Credentials come from env vars or an interactive prompt — they are never
written to disk or echoed:

```bash
export KEYCLOAK_URL=http://localhost:8080          # or the env's admin URL
export KEYCLOAK_ADMIN_USER=admin                    # prompted if unset
export KEYCLOAK_ADMIN_PASSWORD=…                    # prompted (silent) if unset

# preferred: anonymize + disable (default mode)
backend/scripts/keycloak_erasure.sh --sub <keycloak_sub>

# or locate by the original email (still present pre-erasure — that's the bug
# this step fixes)
backend/scripts/keycloak_erasure.sh --email patient@example.com

# preview every HTTP call without touching anything
backend/scripts/keycloak_erasure.sh --sub <keycloak_sub> --dry-run
```

### Mode tradeoffs

| | `anonymize` (default) | `delete` (`--mode delete`) |
|--|------------------------|----------------------------|
| Keycloak user id (`sub`) | Retained — tombstoned account | Freed — user record gone |
| App `users.keycloak_sub` | Still resolves to an IdP record | Dangles (harmless — it's a plain string column, no FK to Keycloak) |
| Re-registration | Same human gets a **new** sub → new app user; old sub stays occupied, no collision | Same; also frees the original email/username for reuse |
| Auditability | IdP still holds a record corroborating the app-side `ERASE` audit entry | Nothing left in the IdP to corroborate |
| Reversibility | Account disabled, not destroyed | Irreversible |

Default to `anonymize`. Use `delete` only when policy requires full IdP removal.

## Step 3 — verify

1. Script output ends with `verify: enabled=false email=erased-<id>@erased.invalid`.
2. Admin console → realm `medconnect` → **Users** → the user shows
   *Enabled: OFF* with tombstone email/name (or is absent in `--mode delete`).
3. The account can no longer log in — sessions are killed via the admin
   `logout` call before the update/delete.
4. App side: `GET /api/v1/admin/users` (admin) shows `Erased User` /
   `erased-<uuid>@erased.invalid`.

## What is erased vs retained

Erased (step 1 + 2 together):

- Account PII: `full_name`, `email`, `phone`, `emergency_contact_*` on
  `users`; Keycloak `email`/`username`/`firstName`/`lastName` and all user
  attributes.
- `NotificationPreferences` (deleted outright).
- Patient-entered free text on self-uploaded records (`description`,
  `raw_text`).
- Clinic consent: all `PatientClinicLink`s → `consent_status="revoked"`.

Retained (lawful bases — record-keeping obligations, not consent):

- **Clinical rows** — medical records, prescriptions, appointments, vitals,
  lab results. These form part of the clinical record the doctor/clinic must
  keep; they reference the patient by UUID, not by PII.
- **Audit logs** — the `ERASE` entry records *which* fields were erased and
  counts, never the erased values. `audit_logs` keep anonymized ids
  (`record_id`, `changed_by`) — permitted as they no longer identify a person
  in combination with the anonymized `users` row.
- **Backups** — database dumps/snapshots taken before the request retain the
  pre-erasure data until they rotate out (local `backups/` — no automatic
  pruning; prod RDS — 30-day PITR window; see `docs/backup-restore.md`).
  Erasure is reflected in backups only after the retention window lapses.
- **Keycloak sub** (anonymize mode) — a random UUID tombstone, not PII.

## Timing expectations

- Step 1 is synchronous and immediate.
- Step 2 should run **same business day** as the erasure request; until it
  does, the person's name/email remain visible in the Keycloak admin console
  and could still receive IdP-side mail (e.g. password-reset).
- Live sessions die within seconds (explicit admin `logout`); issued JWTs
  remain technically valid until natural expiry (≤ access-token TTL) but map
  to an anonymized app user.
- Full erasure including backups: bounded by backup retention
  (≤ 30 days in prod).

## Failure handling

- Token request fails → check `KEYCLOAK_URL` reachability and admin creds.
- `--sub` lookup 404s → the value wasn't a Keycloak id; retry with `--email`.
- PUT succeeds but verify fails → re-run the script; the operation is
  idempotent (tombstone values are deterministic).
- `--mode delete` on an already-deleted user → the initial GET 404s; the app
  row being already-anonymized is the source of truth that erasure completed.
