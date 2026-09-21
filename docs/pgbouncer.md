# PgBouncer + multi-worker uvicorn (local production parity)

The base `docker-compose.yml` runs a `pgbouncer` service in front of
`postgres` so local traffic exercises the same topology as production:
application connections go through a transaction-mode pooler instead of
hitting Postgres directly.

## Topology

```
backend ──────────┐   asyncpg :6432
reminder-worker ──┤
                  ▼
              pgbouncer ────► postgres:5432 ──► medconnect
              (pool_mode=transaction)         ──► medconnect_medicines
                                                  └── keycloak schema

keycloak ─────────► postgres:5432 (direct; JDBC manages its own pool)
alembic ──────────► postgres:5432 (direct via *_SYNC URLs — see below)
```

Both app databases sit behind **one** pooler. The `edoburu/pgbouncer` image
auto-generates `pgbouncer.ini` + `userlist.txt` from env vars at container
start: `DATABASE_URL` is passed **without** a database name, which produces a
wildcard `[databases]` entry (`* = host=postgres port=5432`) routing every
database on that host through the same pool.

`AUTH_TYPE=scram-sha-256` is required: PG16 defaults to
`scram-sha-256` password storage, and with this auth type the image writes the
plaintext password into `userlist.txt`, which lets PgBouncer complete SCRAM
both client→bouncer and bouncer→postgres. With the default `md5` auth type the
server leg would fail.

## Prepared-statement caveat (IMPORTANT)

`pool_mode=transaction` recycles server connections per transaction, so
asyncpg's **client-side** prepared-statement cache goes stale and queries fail
with `prepared statement ... does not exist`. The app sets
`statement_cache_size=0` whenever `DB_TRANSACTION_POOLING=1` is in the
environment (see `backend/app/database.py` — `_asyncpg_connect_args`, and
`backend/app/workers/reminder_worker.py`).

The compose stack already sets `DB_TRANSACTION_POOLING=true` for `backend` and
`reminder-worker`. If you point `DATABASE_URL`/`MEDICINE_DB_URL` at a
transaction-mode pooler anywhere else, set it there too. Conversely, if you
ever run the async URLs direct to `postgres:5432`, you may unset it to regain
the statement cache.

> If a deployment needs prepared statements *and* transaction pooling, the
> alternative is PgBouncer ≥1.21's `max_prepared_statements` server-side
> tracking — not enabled here; `statement_cache_size=0` is the simpler,
> well-trodden route.

## Migrations bypass PgBouncer

Alembic uses the **sync** URLs, which intentionally stay on `postgres:5432`:

- `DATABASE_URL_SYNC` → `alembic/env.py` (`alembic upgrade head`)
- `MEDICINE_DB_URL_SYNC` → `alembic_medicine/env.py`

Running migrations through a transaction-mode pooler breaks on session-level
state such as advisory locks. Because the sync URLs bypass the pooler,
`docker compose exec backend alembic upgrade head` (and the
`alembic -c alembic_medicine.ini upgrade head` in the backend `command:`)
continue to work unchanged. **Never point the `*_SYNC` URLs at pgbouncer
while `POOL_MODE=transaction`.**

## Multi-worker uvicorn

Both the image `CMD` and the compose `command:` honor `UVICORN_WORKERS`
(default `1`):

```bash
# .env
UVICORN_WORKERS=2
```

```bash
docker compose -f docker-compose.yml up --build
```

Notes:

- Lifespan handlers run per worker process — the JWKS prewarm and engine
  disposal are per-process, which is correct.
- Per-process caches (e.g. the user-cache TTL dict in `app/dependencies.py`)
  are duplicated across workers — fine for a cache, just don't expect shared
  state.
- **Metrics caveat:** `prometheus-fastapi-instrumentator` exposes `/metrics`
  per process. With `UVICORN_WORKERS>1`, whichever worker serves the scrape
  reports only its own counters, so series will flap between scrapes. Local
  parity only — real multi-worker deployments need the Prometheus
  multiprocess collector (`PROMETHEUS_MULTIPROC_DIR` + a custom `/metrics`
  endpoint). Keep `UVICORN_WORKERS=1` if you rely on `/metrics` locally.
- `docker-compose.override.yml` keeps `--reload` for dev; reload mode is
  single-process and ignores the workers flag.

## Operating the pooler

```bash
# Pool stats via the admin console (ADMIN_USERS is set to $POSTGRES_USER)
docker compose exec pgbouncer psql -h 127.0.0.1 -p 6432 -U "$POSTGRES_USER" pgbouncer -c "SHOW POOLS"
docker compose exec pgbouncer psql -h 127.0.0.1 -p 6432 -U "$POSTGRES_USER" pgbouncer -c "SHOW STATS"

# Direct check that the pooler answers
pg_isready -h 127.0.0.1 -p 6432
```

Tunables live in the `pgbouncer` service's `environment:` block
(`DEFAULT_POOL_SIZE`, `MAX_CLIENT_CONN`, `SERVER_IDLE_TIMEOUT`, …) — each maps
straight onto a `pgbouncer.ini` setting via the image's entrypoint.

## When to bypass it

The base stack routes the app through the pooler unconditionally — that *is*
the parity point. To compare against a direct connection temporarily, override
in a shell env or a `docker-compose.*.yml`:

```yaml
services:
  backend:
    environment:
      DATABASE_URL: postgresql+asyncpg://medconnect:medconnect@postgres:5432/medconnect
      MEDICINE_DB_URL: postgresql+asyncpg://medconnect:medconnect@postgres:5432/medconnect_medicines
      DB_TRANSACTION_POOLING: "false"
```
