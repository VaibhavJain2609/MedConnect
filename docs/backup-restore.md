# Database backup & restore drill

MedConnect has **two logical PostgreSQL databases** on one server:

| Database | Contents |
|----------|----------|
| `medconnect` | users, doctors, patients, records, prescriptions, appointments, billing, queue — plus the `keycloak` schema (Keycloak stores its data here, so a dump of this DB covers Keycloak too) |
| `medconnect_medicines` | pharmaceutical catalog (salts, brands, manufacturers, interactions, side effects) — needs `pg_trgm` + `vector` extensions, which travel inside the dump |

The tooling differs by environment:

- **Local / docker-compose** — `backend/scripts/backup_db.sh` +
  `backend/scripts/restore_db.sh` (Makefile: `make backup`,
  `make restore-drill`). This page's main focus.
- **Production (AWS RDS)** — automated snapshots configured by Terraform;
  see [Production RDS path](#production-rds-path) below. The compose
  scripts are *not* how production is backed up.

## Local backups (`make backup`)

```bash
make backup                          # dumps both DBs to ./backups/
make backup ARGS="--latest"          # also refresh <db>_latest.dump symlinks
make backup ARGS="--out /mnt/dumps"  # custom output directory
```

or directly:

```bash
backend/scripts/backup_db.sh --out ./backups --latest
```

Each run streams `pg_dump -Fc` (compressed custom format) out of the compose
`postgres` container over stdout — nothing is written inside the container.
Files are named `<db>_<YYYYMMDD_HHMMSS>.dump`:

```
backups/medconnect_20250610_031500.dump
backups/medconnect_medicines_20250610_031500.dump
backups/medconnect_latest.dump -> medconnect_20250610_031500.dump
```

`backups/` is gitignored — dumps can contain PHI-shaped data and must never
be committed. The postgres service must be running (`make up`); the script
sources the repo `.env` for `POSTGRES_USER` (default `medconnect`).

### Retention

Nothing prunes `./backups` automatically. A simple 30-day retention cron:

```cron
15 3 * * *  find /path/to/repo/backups -name '*.dump' -mtime +30 -delete
```

## Restore drill (`make restore-drill`)

A backup that has never been restored is a hypothesis, not a backup. The
drill exercises the full loop without touching the live databases:

```bash
make restore-drill
```

What it does:

1. Fresh `pg_dump` of both databases into a temp dir.
2. `restore_db.sh` restores each dump into a **scratch database**
   (`restore_drill_medconnect`, `restore_drill_medicines`), then prints a
   per-table `count(*)` sanity report.
3. Drops the scratch databases and the temp dir.

A passing drill proves the dumps are loadable end-to-end. Run it after any
change to the backup path and periodically (e.g. weekly/monthly) — see
[Suggested schedule](#suggested-schedule).

### Manual restores

```bash
# restore a specific archive into a scratch DB and keep it for inspection
backend/scripts/restore_db.sh --db drill_medconnect \
    --file backups/medconnect_20250610_031500.dump

# same, but drop the scratch DB afterwards
backend/scripts/restore_db.sh --db drill_medicines \
    --file backups/medconnect_medicines_latest.dump --cleanup
```

Safety rails (all deliberate — this script is also the recovery tool):

- `--db` is **required**; there is no default target.
- The live names (`medconnect`, `medconnect_medicines`) and system DBs are
  refused unless `--i-know-what-im-doing` is passed.
- An existing target is refused unless `--recreate` is passed.
- Database names are validated as identifiers before touching SQL.
- `pg_restore` runs with `--no-owner --no-privileges` so archives can move
  between environments with different role names.

The restore also exercises `CREATE EXTENSION` entries embedded in the dump
(`pg_trgm`, `vector` on the medicines DB), so extension-dependent restores
are covered.

## Production RDS path

Production backup is **snapshot-based**, configured in Terraform
(`infra/terraform/environments/prod/main.tf` → `module "rds"`):

| Setting | Value |
|---------|-------|
| `backup_retention_period` | 30 days (automated snapshots + WAL → point-in-time recovery to any second in the window) |
| `backup_window` | `20:00-21:00` UTC (≈ 01:30-02:30 IST, lowest traffic) |
| `skip_final_snapshot` | `false` — a final snapshot is taken on destroy |
| `copy_tags_to_snapshot` | `true` |
| `deletion_protection` | `true` |
| `storage_encrypted` | `true` (gp3) |

Terraform changes are **out of scope** for this tooling — retention/window
tuning happens in `infra/terraform/environments/*/main.tf` and the
`modules/rds` variables (`backup_retention_period`, `backup_window`).

### Restoring in production

- **Point-in-time recovery** (preferred — no data loss to snapshot granularity):
  `aws rds restore-db-instance-to-point-in-time` creates a **new** instance;
  you never restore over the live one. Repoint `DATABASE_URL*` /
  `MEDICINE_DB_URL*` Secrets-Manager values (see
  `infra/terraform/environments/prod/main.tf` `local.rds_secret`) after
  verifying the new instance.
- **Snapshot restore**: `aws rds restore-db-instance-from-db-snapshot` —
  same "new instance" model, coarser granularity.
- **Logical dumps** (for cross-account copies, dev refresh, or surgical
  restores): run `pg_dump -Fc` from a bastion/in-VPC host against the RDS
  endpoint — the same `pg_dump`/`pg_restore` flags used by the compose
  scripts apply verbatim.

Note: RDS snapshots cover the whole instance, so both `medconnect` and
`medconnect_medicines` (and the `keycloak` schema) are captured together —
no per-database snapshot handling needed.

### Quarterly restore test (production)

The compose drill proves the *tooling*; it does not prove RDS snapshots.
Once a quarter:

1. `restore-db-instance-to-point-in-time` to a scratch instance (e.g.
   `medconnect-prod-restore-test`) with a throwaway identifier.
2. From a VPC-reachable host, run row-count sanity queries against
   `medconnect` and `medconnect_medicines` on the restored instance.
3. Tear the scratch instance down (`skip_final_snapshot` on the scratch —
   it is not managed by Terraform).

Record the drill date and row counts in the ops log/RUNBOOK.

## Suggested schedule

| Cadence | Action |
|---------|--------|
| Continuous (prod) | RDS automated backups — already on (30d PITR window) |
| Daily (where dumps are wanted) | `backup_db.sh --out <dir> --latest` via cron + 30-day `find -mtime` prune |
| Weekly/monthly (local) | `make restore-drill` — verify dumps load |
| Quarterly (prod) | RDS point-in-time restore test to a scratch instance |
