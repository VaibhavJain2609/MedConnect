# Logging & log aggregation

How MedConnect logs are emitted, where they land, and how to query them.

## What the backend emits

`backend/app/main.py` configures structlog once at import time:

- Every log line is a single JSON object on **stdout** — one line per event,
  rendered by `structlog.processors.JSONRenderer` through a stdlib
  `StreamHandler`. There is no file logging and nothing to rotate.
- Standard fields on every line:
  - `event` — the message (`"unhandled_exception"`, `"rx_expiry_run_complete"`, …)
  - `level` — `debug` / `info` / `warning` / `error`
  - `timestamp` — ISO 8601
  - `request_id` — bound by `RequestIDMiddleware` from the inbound
    `X-Request-Id` header (or a generated UUID, echoed back on the
    `X-Request-Id` response header). Use it to correlate every line of a
    single request end-to-end.
- Plus whatever kwargs the call site passes (`path`, `method`, `error`,
  `prescription_id`, …). Example error line:

  ```json
  {"request_id":"b1f2…","level":"error","event":"unhandled_exception","path":"/api/v1/appointments","method":"GET","error":"…","timestamp":"2026-…"}
  ```

- Stdlib-originated records (uvicorn, the `logging.getLogger` call sites in
  middleware/services) go through the same formatter via
  `foreign_pre_chain`, so they render as JSON too.
- Stack traces land in the `exception` key (`format_exc_info`).

### PHI / data-safety note

Logs must never contain request or response bodies, query strings, or PHI.
The audit middleware (`backend/app/middleware/audit_middleware.py`) stores
only method, path (no query string), status, user id, IP and request_id —
keep the same discipline when adding log fields: IDs and codes are fine,
payloads are not.

## Local: Loki + Promtail + Grafana

The `observability` compose profile adds a full local aggregation stack.
Plain `docker compose up` is unchanged — opt in explicitly:

```bash
docker compose --profile observability up -d
```

| Piece | Where | What it does |
|---|---|---|
| Loki | http://localhost:3100 | Log store (7-day retention, `loki_data` volume) |
| Promtail | (no port) | Tails all compose containers via the Docker socket, pushes to Loki |
| Grafana | http://localhost:3001 | Explore UI; Loki datasource pre-provisioned; anonymous admin (local only) |

Configs live in `infra/monitoring/` (`loki-config.yml`,
`promtail-config.yml`, `grafana-datasources.yml`). Promtail labels each
stream with `service` (compose service name), `project`, `container`, and
`level` (extracted from the JSON line). Everything else stays in the line —
**don't** promote `request_id` or similar to a label; high-cardinality
labels are the one thing Loki can't handle.

## Querying (LogQL cheat sheet)

In Grafana → Explore → Loki, or via
`curl -s 'http://localhost:3100/loki/api/v1/query_range' --data-urlencode 'query=…'`:

```logql
{service="backend"}                                  # all backend logs
{service="backend", level="error"}                   # errors only (level is a label)
{service="backend"} |= "unhandled_exception"         # substring filter
{service="backend"} | json | request_id="b1f2…"      # correlate one request
{service="backend"} | json | path="/api/v1/appointments" | line_format "{{.timestamp}} {{.event}}"
{service=~"backend|reminder-worker", level="error"}  # errors across app containers
```

Metric-style queries work too, e.g. error volume per service:

```logql
sum by (service) (count_over_time({level="error"}[5m]))
```

Tips: narrow by time range first; `| json` only parses lines that are
actually JSON (shell noise passes through untouched); `|=` is the cheapest
filter — put it before `| json`.

## Kubernetes

There is **no** in-cluster aggregation yet — the local Loki stack is
compose-only. In `medconnect-staging` / `medconnect-prod`, read logs
straight off the pods (they're already JSON):

```bash
kubectl -n <ns> logs deploy/backend --tail=200 -f
kubectl -n <ns> logs deploy/backend | jq 'select(.level=="error")'
kubectl -n <ns> logs deploy/backend | jq 'select(.request_id=="b1f2…")'
```

A natural follow-up is a promtail/alloy DaemonSet or the Loki Helm chart
shipping to S3; the alert rules in `infra/k8s/monitoring/alerts.yaml` are
metric-based and don't depend on it.
