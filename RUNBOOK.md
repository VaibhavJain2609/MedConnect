# MedConnect Operations Runbook

Concise ops reference for running, debugging, and recovering MedConnect.
Local dev is Docker Compose; deployed environments are EKS (namespaces
`medconnect-staging` / `medconnect-prod`) with Amazon RDS (Postgres) and
ElastiCache (Redis). Monitoring is kube-prometheus-stack (namespace
`monitoring`): Prometheus + Alertmanager + Grafana.

---

## 1. Startup order

### Local (Docker Compose)

`docker-compose.yml` + `docker-compose.override.yml` are layered
automatically. `make up` runs:

```
postgres ─┬─> keycloak ─┐
redis  ───┴─────────────┴─> backend (runs alembic upgrade head +
                               alembic -c alembic_medicine.ini upgrade head,
                               then uvicorn)
                          ├─> reminder-worker
                          └─> frontend ─> nginx
```

Health gates: backend waits on postgres + redis + keycloak being healthy;
frontend/nginx wait on backend. First boot takes ~60–90s (Keycloak JVM
startup is the long pole).

### Kubernetes (first deploy / full recovery)

```bash
# 1. Cluster-admin bootstrap (once per cluster): namespaces + ClusterSecretStore
kubectl apply -k infra/k8s/bootstrap

# 2. Per-environment overlay — creates ExternalSecrets, db-bootstrap Job,
#    alembic-migrate Job, then Deployments
kubectl apply -k infra/k8s/overlays/<staging|prod>
kubectl -n medconnect-<env> wait --for=condition=complete job/db-bootstrap --timeout=300s
kubectl -n medconnect-<env> wait --for=condition=complete job/alembic-migrate --timeout=600s

# 3. Alert rules (not in the kustomization — applied per namespace)
kubectl -n medconnect-<env> apply -f infra/k8s/monitoring/alerts.yaml
```

Pods may crash-loop on first deploy until secrets sync and both Jobs
complete — expected; they settle.

## 2. Health endpoints

| Endpoint | Where | Meaning |
|---|---|---|
| `GET /livez` | backend :8000 | Shallow liveness — 200 if the process serves requests. **No dependency checks** (a DB blip must not restart the pod). |
| `GET /health` | backend :8000 | Deep readiness — 200 only if `db`, `medicine_db`, **and** `redis` all respond; 503 with a per-dependency JSON body otherwise. |
| `GET /metrics` | backend :8000 | Prometheus metrics (in-cluster scrape only, never exposed via Ingress). |
| `GET /health/ready` | keycloak :9000 (mgmt) | Keycloak readiness. |
| `/manifest.json` | frontend :3000 | Compose healthcheck for Next.js. |
| `/api/health` | frontend :3000 | Next.js route used by CD smoke tests. |

Local quick check: `make health` or
`curl -s http://localhost:8000/health | jq` — a degraded body looks like
`{"status":"degraded","db":"ok","medicine_db":"ok","redis":"error"}`.

## 3. Alerts

Alert rules live in `infra/k8s/monitoring/alerts.yaml` (PrometheusRule,
label `release: kube-prometheus-stack` — required by the Helm-managed
Prometheus's `ruleSelector`). It is **not** part of the kustomize base (base
is shared across namespaces and can't reference files outside its root), so
it is applied once per environment:

```bash
kubectl -n medconnect-staging apply -f infra/k8s/monitoring/alerts.yaml
kubectl -n medconnect-prod    apply -f infra/k8s/monitoring/alerts.yaml
```

Verify Prometheus picked it up: Prometheus UI → Status → Rules, or
`kubectl -n medconnect-<env> get prometheusrule medconnect`.

| Alert | Severity | Meaning | First steps |
|---|---|---|---|
| `BackendDown` | critical | Prometheus can't scrape `/metrics` for 2m — pods down/crash-looping or Service endpoints empty | `kubectl -n <ns> get pods -l app=backend` → `kubectl describe pod` (events) → `kubectl logs deploy/backend --tail=200`. Check recent deploys (`kubectl rollout history deploy/backend`). |
| `BackendUnavailable` | critical | Pods exist but 0 ready for 5m — deep `/health` failing, most often a Postgres or Redis outage | `kubectl -n <ns> exec deploy/backend -- curl -s localhost:8000/health` → the JSON body names the failing dep (`db` / `medicine_db` / `redis`) → jump to §4 failure modes. |
| `PostgresDown` | critical | `pg_up=0` (only active once a postgres exporter is deployed — see caveat below) | Check RDS instance state in AWS console; verify `backend-secrets` DATABASE_URL host + security-group ingress. Locally: `docker compose ps postgres`, `docker compose logs postgres`. |
| `RedisDown` | critical | `redis_up=0` (same exporter caveat) | Check ElastiCache node health; verify REDIS_URL + SG. Rate limiting degrades and reminder-worker stalls. Locally: `docker compose logs redis`. |
| `HighErrorRate` | warning | >5% of responses are 5xx for 5m | Find the handler: `sum by (handler) (rate(http_requests_total{status=~"5.."}[5m]))` in Prometheus/Grafana → `kubectl logs deploy/backend \| grep unhandled_exception` (JSON logs carry `path`, `error`, `request_id`). |
| `HighLatency` | warning | p95 >1.5s for 10m | Break down per handler: `histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, handler))`. Usual suspects: slow SQL (RDS Performance Insights), Redis latency, Keycloak JWKS fetch. |
| `HighMemoryUsage` | warning | Container >85% of memory limit for 10m | `kubectl -n <ns> top pods`. Check for a leak (upload spooling, pandas/reportlab jobs). If steady-state is legitimately high, raise `resources.limits.memory` in the deployment. |
| `PersistentVolumeClaimNearlyFull` | warning | PVC <15% free for 10m | `kubectl -n <ns> get pvc` → expand the PVC (`spec.resources.requests.storage`, storage class permitting) or reclaim space. No PVCs exist in base today — this fires only once one is added. |

**Postgres/Redis caveat:** in deployed environments Postgres = RDS and
Redis = ElastiCache; nothing in-cluster exports `pg_up`/`redis_up` today, so
those two rules are armed-but-inert until an exporter is added. Real
coverage for dependency loss today is `BackendUnavailable` (readiness
fails). Supplement with AWS-side alarms (RDS `DatabaseConnections`/CPU,
ElastiCache `EngineCPUUtilization`/failover events) until exporters land.

## 4. Common failure modes

### Backend can't reach Postgres

Symptoms: `/health` → `"db":"error"` and/or `"medicine_db":"error"`;
backend pods NotReady → `BackendUnavailable`; login/data endpoints 500.

- Local: `docker compose ps postgres` → `docker compose logs postgres --tail=100`.
  Dead/corrupt volume: `make down-v` (**destroys local data**) then `make up`.
- K8s: RDS down/unreachable — check AWS console; verify SG allows the node
  SG on 5432; verify `backend-secrets` synced (`kubectl -n <ns> get secret
  backend-secrets -o yaml` → DATABASE_URL host). RDS requires SSL
  (`rds.force_ssl=1`) — a client forcing `sslmode=disable` fails; remove the
  override rather than relaxing the param group.
- Bad migrations: check `alembic-migrate` Job logs (§6).

### Backend can't reach Redis

Symptoms: `/health` → `"redis":"error"`; rate limiting falls back; arq
reminder-worker stops processing (`arq --check` healthcheck fails → worker
pod restarts).

- Local: `docker compose logs redis`; test `make redis-cli` → `ping`.
- K8s: ElastiCache node state; verify REDIS_URL secret + SG on 6379.

### Backend can't reach Keycloak

Symptoms: authenticated requests 401 (JWKS fetch fails); `/health` stays
green — **Keycloak is NOT in /health**, so a Keycloak outage shows as
auth failures, not readiness. `HighErrorRate` may fire on 401/5xx mix.

- Local: `docker compose logs keycloak --tail=100`; check
  `http://localhost:8080/health/ready`. Realm import errors kill startup.
- K8s: `kubectl -n <ns> logs deploy/keycloak`; verify
  `keycloak.medconnect-<env>.svc.cluster.local:8080` resolves and the
  `keycloak` DB schema exists (db-bootstrap Job creates it).

### Pods crash-looping on first deploy

Expected until ExternalSecrets sync + both Jobs finish (§1). If it
persists >10m: `kubectl -n <ns> get externalsecret` → check
`ClusterSecretStore` status → `kubectl describe pod` for mount/env errors.

## 5. Rollback

### Preferred: GitHub Actions `rollback.yml`

Actions → **Rollback** → inputs: `environment` (staging|production),
`deployment` (backend|frontend|keycloak|all), `revision` (blank = previous).
It runs `kubectl rollout undo`, waits, and smoke-tests `/health` +
`/api/health`. The `cd.yml` `notify` job posts deploy/rollback status to the
`DEPLOY_WEBHOOK_URL` webhook (Slack/Discord) when configured — watch it for
confirmation, or check the workflow run.

### Manual

```bash
aws eks update-kubeconfig --name medconnect --region ap-south-1
kubectl -n medconnect-<env> rollout history deploy/backend        # pick revision
kubectl -n medconnect-<env> rollout undo deploy/backend --to-revision=<N>
kubectl -n medconnect-<env> rollout status deploy/backend --timeout=300s
# verify
kubectl -n <ns> exec deploy/backend -- curl -fsS localhost:8000/health
```

**Migrations are not rolled back** by `rollout undo` — if the bad release
applied a schema change, `alembic downgrade -1` via `kubectl exec` (or a
one-off Job) must be run deliberately, and only after confirming the older
code tolerates the current schema. Most MedConnect migrations are
additive; downgrading a destructive migration loses data.

## 6. Migrations

Local (backend container runs both on startup; to re-run manually):

```bash
make migrate                                    # both, via docker compose exec
# or: docker compose exec backend alembic upgrade head
#     docker compose exec backend alembic -c alembic_medicine.ini upgrade head
docker compose exec backend alembic revision --autogenerate -m "description"
docker compose exec backend alembic downgrade -1
```

K8s: the `alembic-migrate` Job (`infra/k8s/base/migrations/job.yaml`) runs
on every deploy — CD extracts and re-applies it ahead of the manifests.
Manual re-run:

```bash
kubectl -n medconnect-<env> delete job alembic-migrate --ignore-not-found
kubectl -n medconnect-<env> apply -f <(kubectl kustomize infra/k8s/overlays/<env> | yq 'select(.metadata.name=="alembic-migrate")')
kubectl -n medconnect-<env> wait --for=condition=complete job/alembic-migrate --timeout=600s
kubectl -n medconnect-<env> logs job/alembic-migrate
```

Or ad-hoc: `kubectl -n <ns> exec deploy/backend -- alembic upgrade head`.

## 7. Useful commands

```bash
# Local
make logs SERVICE=backend          # tail one service (default: all)
make psql                          # psql into medconnect DB
make psql-medicine                 # psql into medconnect_medicines DB
make down-v                        # full reset incl. volumes (DATA LOSS)
make gen-api-types                 # regen frontend schema.d.ts from OpenAPI
make check-api-types               # fail if schema.d.ts is stale (CI does this)

# K8s
kubectl -n <ns> logs deploy/backend --tail=200 -f          # JSON structlog
kubectl -n <ns> logs deploy/backend | jq 'select(.level=="error")'
kubectl -n <ns> get pods -w
kubectl -n <ns> exec -it deploy/backend -- sh
kubectl -n <ns> port-forward svc/backend 8000:80           # then curl localhost:8000/health
```

Structured logs: every line is JSON with `request_id` (from `X-Request-Id`
header — echoed on every response), `level`, `path`, `event`. Correlate a
failing request end-to-end by grepping for its `request_id`.

Grafana/Prometheus/Alertmanager UIs (cluster): `kubectl -n monitoring
port-forward svc/kube-prometheus-stack-grafana 3001:80` etc.

**API contract types:** after adding/changing any backend endpoint, run
`make gen-api-types` (or `cd backend && python scripts/export_openapi.py &&
cd ../frontend && npm run gen:api-types`) and commit
`frontend/src/lib/api/schema.d.ts` with the change. The `contract` CI job
rejects PRs where it's stale — see `docs/api-types.md`.

## 8. Logs (Loki aggregation)

The backend already writes structlog JSON to stdout — no app config needed.
For local development, the `observability` compose profile adds
Loki + Promtail + Grafana (opt-in; plain `docker compose up` is unchanged):

```bash
docker compose --profile observability up -d
# Grafana → http://localhost:3001 (Explore → Loki, datasource pre-wired)
# Loki API → http://localhost:3100
```

Promtail tails every compose-managed container through the Docker socket
and labels each stream `service` / `project` / `container` / `level`.
Configs: `infra/monitoring/{loki,promtail}-config.yml`,
`grafana-datasources.yml`. Full field list + LogQL examples:
**docs/logging.md**. Quick ones:

```logql
{service="backend", level="error"}                  # backend errors
{service="backend"} | json | request_id="<id>"      # one request, all lines
{service="backend"} |= "unhandled_exception"        # the 500s behind HighErrorRate
```

PHI rule for new log fields: IDs/codes only — never bodies, query strings,
or patient data (same constraint the audit middleware already enforces).

K8s has no aggregation yet — use `kubectl -n <ns> logs deploy/backend |
jq …` (§7); a promtail/alloy DaemonSet is the follow-up.

## 9. Lab-report OCR ingest (optional, off by default)

`POST /api/v1/lab-results/ingest` extracts candidate lab values from an
uploaded report image (doctor-scoped, human-in-the-loop — it returns
`candidates[]` for review and never writes `LabResult` rows). Provider
adapter: `backend/app/services/providers/ocr.py`.

Disabled by default: `OCR_PROVIDER=none` → every ingest call returns
`503 OCR_NOT_CONFIGURED`; the frontend shows a quiet "not enabled"
notice. No credentials ship with the scaffold — the `llm` provider stub
(`LlmVisionOcrProvider`) raises `OcrUnavailable` until
`_call_vision_api` is wired to a real OpenAI-compatible vision endpoint.

To enable once a backend exists:

```bash
# backend env
OCR_PROVIDER=llm
OCR_LLM_BASE_URL=https://api.example.com/v1   # OpenAI-compatible endpoint
OCR_LLM_API_KEY=<secret>                      # never commit
OCR_LLM_MODEL=<vision-model-name>
OCR_LLM_TIMEOUT_SECONDS=30                    # optional
```

Failure modes:

- `503 OCR_NOT_CONFIGURED` — `OCR_PROVIDER` unset/`none` (expected until enabled).
- `503 OCR_UNAVAILABLE` — provider selected but stub unwired or `OCR_LLM_*`
  incomplete; check backend logs for `lab_ingest`/`lab_ocr` events.
- `403 INVALID_UPLOAD_KEY` — ingest key wasn't presigned by the same doctor
  (keys expire 15 min after presign; re-upload the image).

PHI: report images stay in the uploads object store; providers log only
identifiers (provider name, candidate count) — never image bytes or values.

## 10. Production checklist (config)

`Settings.check_production_config` (`backend/app/config.py`) fails fast at
startup when `APP_ENV=production` and any setting still carries a local-dev
default — the process exits with a `ValueError` naming **every** violation
so a misconfigured deploy is fixed in one iteration, not one crash-loop per
variable. `APP_ENV` itself is restricted to
`development|test|staging|production`, so a typo like `prod` can't silently
bypass the guard.

### Must be overridden in production (names only — no values here)

Values live in AWS Secrets Manager (`medconnect/<env>/{rds,redis,keycloak-admin}`)
synced by the ExternalSecrets in `infra/k8s/base/external-secrets/`, plus the
per-overlay ConfigMap patches. Locally they come from `backend/.env`
(gitignored — copy `backend/.env.example`).

**Enforced by the startup guard:**

- `APP_ENV` — must be `production` (also disables `/docs`, enables HSTS).
- `DATABASE_URL`, `DATABASE_URL_SYNC`, `MEDICINE_DB_URL`,
  `MEDICINE_DB_URL_SYNC` — real DB hosts (no `postgres`/`pgbouncer`/
  `localhost`) and non-default credentials.
- `REDIS_URL` — real host + AUTH token.
- `KEYCLOAK_URL` — reachable internal JWKS/admin base (not the compose
  `keycloak` short name; use the FQDN, e.g. `keycloak.<ns>.svc.cluster.local`).
- `KEYCLOAK_PUBLIC_URL`, `FRONTEND_URL`, `BACKEND_URL` — public `https://`
  origins; `localhost`, wildcard `*`, and plain `http://` are rejected.
  `FRONTEND_URL` feeds CORS `allow_origins` + CSP `connect-src`.
- `KEYCLOAK_ADMIN_USER`, `KEYCLOAK_ADMIN_PASSWORD` — non-default.
- `UPLOADS_DIR` — persistent path (not `/tmp`) when `STORAGE_BACKEND=local`,
  or set `STORAGE_BACKEND=s3`.
- `VERIFY_JWT_AUDIENCE` — must stay `true`.
- `DEBUG` — must stay `false`.

**Compose-level secrets** (`docker-compose.yml` interpolates these from the
root `.env` — never commit it; `.env.example` ships `CHANGE_ME` placeholders):

- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `REDIS_PASSWORD`,
  `KEYCLOAK_ADMIN`, `KEYCLOAK_ADMIN_PASSWORD`

**Recommended (not enforced by the guard):**

- `ALLOWED_HOSTS` — comma-separated Host-header allowlist; installs
  `TrustedHostMiddleware` when set (defense-in-depth under the ALB/ingress).
- `LOG_LEVEL` — `DEBUG|INFO|WARNING|ERROR|CRITICAL` (default `INFO`).
- `SENTRY_DSN` — empty disables Sentry.
- `UVICORN_WORKERS` — uvicorn worker count (compose default 1).
- `TRUSTED_PROXY_IPS` — comma-separated proxy IPs whose `X-Forwarded-For`
  is honoured by the rate limiter (empty = never trust XFF).
- `RATE_LIMIT_USER_PER_MINUTE`, `JITSI_BASE_URL`, `DB_TRANSACTION_POOLING`.
- Notification channels — `SMTP_*`, `MSG91_*`, `WHATSAPP_*`, `VAPID_*`;
  unset = channel skipped with a logged `channel_unavailable`.
- Comm provider layer (`services/comms`) — `SMS_ENABLED` /
  `WHATSAPP_ENABLED` (both default `false`) route the sms/whatsapp
  channels through `get_comm_provider()` instead of the legacy
  MSG91/Meta adapters. Set `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`,
  `TWILIO_FROM_NUMBER`, and `TWILIO_WHATSAPP_FROM` to go live on Twilio;
  flags off or creds absent = `NullProvider` (attempts logged + skipped).
- `OCR_*` — only when enabling lab ingest (§9).

## 11. Outbound clinic webhooks (optional, off by default)

Clinics can subscribe HTTPS endpoints to receive outbound event POSTs.
Feature flag: `WEBHOOKS_ENABLED=false` by default — when off,
`webhook_service.emit_event` is a no-op (no delivery rows, no ARQ jobs).
The ARQ `deliver_webhook` task is registered on the reminder worker.

```bash
# backend env — to enable
WEBHOOKS_ENABLED=true
WEBHOOK_TIMEOUT_SECONDS=5    # optional, per-request timeout
WEBHOOK_MAX_ATTEMPTS=3       # optional, in-job retries with 1s/2s backoff
```

Events emitted (PHI-minimal payloads — **IDs, statuses and timestamps only**;
never names, diagnoses, medicines, notes or free text):

- `appointment.booked` — appointment created (patient/staff/guest booking)
- `appointment.status_changed` — status transition (includes `previous_status`)
- `prescription.issued` — prescription created

Request format: `POST <endpoint.url>` with JSON body and headers
`X-MedConnect-Event: <event_type>` and
`X-MedConnect-Signature: sha256=<HMAC-SHA256 hex of the raw body, keyed by the
endpoint secret>`. Receivers must recompute the signature over the exact raw
request body.

Admin config (clinic-scoped; requires `owner|admin` clinic membership):

```
POST   /api/v1/clinics/{id}/webhooks            — create; full `secret` returned ONCE
GET    /api/v1/clinics/{id}/webhooks            — list (secret masked whsec_****last4)
GET    /api/v1/clinics/{id}/webhooks/deliveries — delivery log (?status=&page=&limit=)
GET    /api/v1/clinics/{id}/webhooks/{ep}       — detail (masked)
PATCH  /api/v1/clinics/{id}/webhooks/{ep}       — update url/event_types/is_active
DELETE /api/v1/clinics/{id}/webhooks/{ep}       — deactivate (soft delete)
POST   /api/v1/clinics/{id}/webhooks/deliveries/{delivery_id}/redeliver
                                                — re-queue one failed delivery (409 unless status=failed)
POST   /api/v1/clinics/{id}/webhooks/{ep}/redeliver-failed
                                                — bulk re-queue up to 50 most-recent failed deliveries
```

The same actions are available in the doctor portal at
`/doctor/clinic/webhooks` (owner/admin memberships only).

Delivery state machine: `pending` → `sent` | `failed` (after
`WEBHOOK_MAX_ATTEMPTS` tries). Inspect failures via the deliveries endpoint or:

```sql
SELECT id, event_type, status, attempts, last_error
FROM webhook_deliveries ORDER BY created_at DESC LIMIT 20;
```

Failure modes: rows stuck `pending` → enqueue failed or worker down (check
`arq:health:reminder-worker` / `webhook_enqueue_failed` logs); `failed` with
`last_error` → receiver 4xx/5xx or network error. Re-delivery: use the
`redeliver` / `redeliver-failed` endpoints above (or the Redeliver buttons in
`/doctor/clinic/webhooks`) — they flip `failed` rows back to `pending` and
enqueue a fresh `deliver_webhook` job; the worker overwrites
`attempts`/`last_error`/`delivered_at` with the new outcome. If the enqueue
itself fails the row is reverted to `failed` (`webhook_redeliver_enqueue_failed`
log) so it stays redeliverable.

## 12. Running e2e locally

The Playwright suite (`frontend/e2e`, docs/e2e.md) needs the backend on
:8000, Keycloak on :8080 with the imported realm's demo users, seeded demo
data, and the frontend on :3000 (Playwright boots it itself).

```bash
# 1. Stack — on a fresh volume the realm import creates the demo Keycloak
#    users (all passwords: demo-password). Pre-existing volumes skip the
#    import; `docker compose down -v` first if the users are missing.
docker compose up -d --build
# wait for Keycloak (~60–90s first boot) + backend health:
curl -sf http://localhost:8080/realms/medconnect/.well-known/openid-configuration
curl -sf http://localhost:8000/health

# 2. Seed demo data (idempotent)
make seed

# 3. Playwright — installs browsers once, then runs the suite
cd frontend
npm ci
npx playwright install chromium        # first time only

# Public specs only (no credentials needed):
npm run test:e2e

# Full suite incl. @auth-tagged specs — point at the seeded demo users:
E2E_TEST_EMAIL=kabir.singh@medconnect.demo  E2E_TEST_PASSWORD=demo-password \
E2E_DOCTOR_EMAIL=dr.priya@medconnect.demo   E2E_DOCTOR_PASSWORD=demo-password \
E2E_ADMIN_EMAIL=admin@medconnect.demo       E2E_ADMIN_PASSWORD=demo-password \
npm run test:e2e
```

- `@auth` specs mint real tokens via Keycloak's direct-grant endpoint
  (`e2e/fixtures/auth.ts`) — no mocks. Skip them wholesale with
  `npm run test:e2e -- --grep-invert @auth`.
- `queue.spec.ts` and the patient-journey appointments test assert on
  seeded rows — they fail with a "run `make seed`" hint if the dataset is
  missing.
- Target a remote env instead: `PLAYWRIGHT_BASE_URL=https://staging…
  npm run test:e2e` (skips the local server; set `E2E_KEYCLOAK_URL` to
  that env's Keycloak for @auth specs).
- Failure triage: `npm run test:e2e:report` opens the HTML report with
  traces/screenshots; backend logs via `make logs SERVICE=backend`.
