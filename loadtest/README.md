# Load testing MedConnect

Locust-based load tests for the backend API. The mix is weighted toward
`GET /api/v1/medicines/search` — the hot read path fronted by the `medcat:*`
Redis cache (`backend/app/services/medicine_cache.py`) — plus notification and
appointment list polls and `/health` deep-readiness probes.

## Prerequisites

```bash
pip install locust          # or: pipx install locust
make up                     # stack must be running (backend on :8000)
```

## Quickstart

```bash
# Authenticated profile — needs a Keycloak token (see below)
export LOCUST_TOKEN=<keycloak access token>
make loadtest TARGET=http://localhost:8000 USERS=50 RATE=5 TIME=5m

# No-auth smoke — SmokeUser only (/health + /docs), 10 users for 1m
make loadtest-smoke

# Interactive web UI instead of headless
locust -f loadtest/locustfile.py --host http://localhost:8000
# → http://localhost:8089
```

`make loadtest` wraps `locust -f loadtest/locustfile.py --headless --host
$(TARGET) -u $(USERS) -r $(RATE) -t $(TIME)`. Defaults:
`TARGET=http://localhost:8000 USERS=50 RATE=5 TIME=5m`. Pass extra flags via
the `LOCUST` var if needed (e.g. `LOCUST="locust --csv=loadtest/out"`).

## User classes

| Class | Auth | Traffic | Purpose |
|---|---|---|---|
| `MedConnectUser` | `LOCUST_TOKEN` required | `medicines/search` ×6, `notifications` ×3, `appointments` ×2, `/health` ×1 | Realistic portal mix; exercises the medcat cache |
| `SmokeUser` | none | `/health` ×3, `/docs` ×1 | Anonymous sanity load — both paths are rate-limit exempt |
| `SoakUser` | `LOCUST_TOKEN` required | same mix as `MedConnectUser`, waits 2–5s | Long runs (hours) for leaks / pool drift |

Run a single class by naming it positionally:

```bash
locust -f loadtest/locustfile.py --headless --host http://localhost:8000 \
    -u 20 -r 1 -t 2h SoakUser
```

With no class filter, Locust picks a class per spawn weighted 3:1:1
(MedConnectUser : SmokeUser : SoakUser).

## Minting a token (`LOCUST_TOKEN`)

The realm (`medconnect`) ships with `directAccessGrantsEnabled: false` on all
clients, so two options:

**Option A — browser token (no config change).** Log in at
http://localhost:3000, then in DevTools → Network pick any
`/api/v1/...` request and copy the `Authorization: Bearer …` value, or read
the token Keycloak stores in session storage
(Application → Session Storage → `http://localhost:3000`).

**Option B — password grant (one-time admin toggle).** In the Keycloak admin
console (http://localhost:8080, `admin`/`admin` from `.env`):

1. Realm `medconnect` → Clients → `medconnect-frontend` → Capability config
   → enable **Direct access grants** → Save.
2. Then:

```bash
LOCUST_TOKEN=$(curl -s \
  http://localhost:8080/realms/medconnect/protocol/openid-connect/token \
  -d grant_type=password \
  -d client_id=medconnect-frontend \
  -d username='<keycloak-user-email>' \
  -d password='<password>' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
export LOCUST_TOKEN
```

Use a real Keycloak realm user — i.e. one created via the frontend signup
flow or the admin console. **The seeded demo users (`dr.priya@medconnect.demo`
etc.) will not work**: `make seed` gives them placeholder `keycloak_sub`
values, not Keycloak accounts (see `docs/seed.md` for how to link a seeded
row to a real Keycloak user if you want both). Access tokens are short-lived
(~5 min default); re-mint between long runs or expect 401s once it expires.
If `LOCUST_TOKEN` is unset, `MedConnectUser`/`SoakUser` instances stop on
start rather than generating a 401 storm — only `SmokeUser` traffic runs.

## Rate limits — read this before scaling up

`app/middleware/rate_limit.py` throttles **per bearer token**: a single
`LOCUST_TOKEN` shares one `token:<hash>` read bucket capped at **100
GETs/min (~1.7 rps)** and a per-`sub` bucket (`RATE_LIMIT_USER_PER_MINUTE`,
default 240/min). Above that you get 429s with `X-RateLimit-Bucket: ip|user`
— useful data in itself, but it means one token cannot saturate the backend.
For real throughput either:

- mint several tokens and run one Locust worker per token
  (`LOCUST_TOKEN=<t> locust ... --headless --csv=out-<n>`), or
- measure single-caller behaviour deliberately and treat 429s as the ceiling.

`/health`, `/docs`, `/livez`, `/metrics`, `/openapi.json` are exempt, which is
why `SmokeUser` can push volume unauthenticated.

## What to watch

- **Locust stats**: per-endpoint p50/p95, RPS, failure rate. 401s mean the
  token expired; 429s mean the rate limit (see above); 503 on `/health`
  names the failing dependency in the body.
- **p95 latency** — Prometheus histogram at `:8000/metrics`:
  ```
  histogram_quantile(0.95,
    sum(rate(http_request_duration_seconds_bucket[5m])) by (le, handler))
  ```
  Or eyeball `curl -s localhost:8000/metrics | grep request_duration`. With
  `UVICORN_WORKERS>1` each worker exports its own series.
- **Postgres connections**: `make psql` →
  `select state, count(*) from pg_stat_activity group by 1;` and
  `make psql-medicine` for the catalog DB. App traffic funnels through
  PgBouncer (`DEFAULT_POOL_SIZE=20`, `MAX_CLIENT_CONN=200`) — watch
  `SHOW POOLS;`/`SHOW CLIENTS;` via `psql -h localhost -p 6432 -U medconnect
  pgbouncer` for pool saturation under load.
- **medcat cache effectiveness**: cache hits aren't logged (misses/errors
  are, as `medcat cache get failed` warnings in `make logs SERVICE=backend`).
  Instead watch `make redis-cli` → `INFO stats` (`keyspace_hits` vs
  `keyspace_misses` — note the rate limiter shares this Redis), `SCAN 0
  MATCH 'medcat:*'` for key growth, and the medicine DB's `pg_stat_activity`
  query rate dropping on repeated terms. Search keys TTL 300s; detail keys
  3600s. The fixed `SEARCH_TERMS` list in the locustfile deliberately
  repeats terms so a warm cache should absorb most search load.
- **Backend errors**: `make logs SERVICE=backend` — structlog JSON, one
  `request_id` per request; or Loki (`docker compose --profile
  observability up -d`, Grafana on :3001) per `docs/logging.md`.

## Ramp guidance

1. `make loadtest-smoke` — proves the stack and plumbing first.
2. `make loadtest USERS=10 RATE=2 TIME=2m` — cold baseline; watch p95 settle
   and `medcat:*` keys appear.
3. Scale gradually: `USERS=50 RATE=5` → `USERS=150 RATE=10`. Keep `RATE`
   modest (≤10/s) so failures surface as latency, not a thundering spawn
   wave. Remember the per-token ceiling — beyond ~50 authed users you are
   mostly benchmarking the rate limiter.
4. **Spike**: `LOCUST_SPIKE=1 make loadtest` — activates the `SpikeShape`
   (baseline → 150-user spike → drop, ~2.5 min); `-u`/`-r` are ignored in
   shape mode.
5. **Soak**: `locust ... SoakUser` for hours-long runs to catch pool
   exhaustion and memory growth that short bursts hide.

Save artifacts for comparison runs with `--csv=loadtest/results/<name>` and
`--html`.
