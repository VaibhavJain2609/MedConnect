# API Contract Types (OpenAPI → TypeScript)

The frontend's `src/lib/api/*.ts` modules are hand-written axios helpers whose
interfaces can drift from the backend's actual response shapes (the error
envelope and list/response shapes have bitten us repeatedly). This pipeline
generates TypeScript types directly from FastAPI's OpenAPI schema so contract
drift becomes a **compile-time / CI failure** instead of a runtime bug.

## Pipeline

```
backend/app (routes + pydantic models)
        │
        │  cd backend && python scripts/export_openapi.py
        ▼
frontend/openapi.json            ← gitignored intermediate (470 KB)
        │
        │  cd frontend && npm run gen:api-types
        ▼
frontend/src/lib/api/schema.d.ts ← committed artifact (checked by CI)
```

1. **`backend/scripts/export_openapi.py`** dumps `app.openapi()` to
   `frontend/openapi.json`. It runs standalone — **no DB, Redis, Keycloak or
   running server needed**. `app.openapi()` builds the schema from route and
   pydantic metadata only; the app's lifespan (JWKS prewarm, engine disposal)
   never runs because the ASGI app is never started. Engine objects are
   constructed at import time but make no connections.

2. **`frontend/scripts/gen-api-types.mjs`** wraps `openapi-typescript`
   (devDependency) and writes `src/lib/api/schema.d.ts`. Fails with
   instructions if `openapi.json` hasn't been exported yet.
   `npm run check:api-types` regenerates in-memory and exits non-zero if the
   committed file is stale (used by CI).

## Regenerating after backend changes

```bash
cd backend && python scripts/export_openapi.py
cd ../frontend && npm run gen:api-types
# commit schema.d.ts together with the backend change
```

CI's `contract` job (`.github/workflows/ci.yml`) runs the same two steps with
no docker services and fails the PR if `schema.d.ts` is out of sync — a
backend contract change can't merge without its regenerated types.

## What gets committed vs. gitignored

| File | Tracked? | Why |
|------|----------|-----|
| `frontend/openapi.json` | **No** (gitignored) | Regenerable intermediate; regenerating it in CI is cheap, and committing it would double review noise — `schema.d.ts` already shows the contract diff in reviewable form. |
| `frontend/src/lib/api/schema.d.ts` | **Yes** | The artifact TS code imports. Committing means frontend-only devs never need Python, and `--check` gives CI a drift gate. |

If you'd rather review the raw spec diff in PRs, commit `openapi.json` too —
CI regenerates it before `--check` runs, so either way works.

## Using the generated types

`schema.d.ts` exports `paths`, `operations`, `components`, `webhooks`,
`$defs`. `src/lib/api/typed.ts` (proof of concept) shows the intended
patterns:

```ts
import type { ResponseBody, QueryParams, Schema } from "@/lib/api/typed";

// Response shape straight from the spec:
type Me = ResponseBody<"/api/v1/auth/me", "get">;

// Query params typed from the spec (limit/offset/type/unread_only):
type NotifParams = QueryParams<"/api/v1/notifications", "get">;

// Or grab a pydantic model by name:
type Notification = Schema<"NotificationResponse">;
```

### Migrating an existing module

1. Delete the hand-written interface (e.g. `NotificationsListResponse`).
2. Alias the generated type (`ResponseBody<...>` or `Schema<"...">`).
3. Keep the axios call — only the annotations change.

The win: if the backend renames `unread_count` or changes the error envelope,
`tsc` fails exactly where the field is used.

## Caveats / known gaps

- **Endpoints without `response_model`** serialize in the spec as
  `"application/json": unknown`. Many routers return plain dicts; adding
  `response_model=` to FastAPI handlers is what makes their generated types
  useful. `/api/v1/auth/me` (`UserResponse`) and notifications
  (`NotificationsListResponse`) already do this — the POC uses them.
- **Duplicate operation ID**: FastAPI warns about
  `list_clinic_doctors` being defined in both `routers/clinics.py` and
  `routers/patient_links.py`. Harmless for type generation, but worth fixing
  if we ever generate an SDK keyed by `operationId`.
- **Error envelope** (`{"error": {"code", "message"}}`) is produced by
  exception handlers in `app/main.py`, not response models, so it isn't in
  the spec. If we want typed errors, define an `ErrorEnvelope` pydantic model
  and add it as a documented `responses={4xx: {...}}` on routes — or keep the
  existing axios interceptor handling it untyped.
