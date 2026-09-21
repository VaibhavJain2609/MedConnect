# Jira Board Status Map

*Source: `jira-import.csv` (git history, commit 2694230). Jira API unavailable (no `JIRA_*` creds) — `.claude/jira_cli.py` exits with "Missing Jira credentials". This file is the authoritative local board until creds are provided. Updated through critic round 3 (commit 283127c).*

## Mark DONE — exists and works (verified in code)

**Medicine Database & Dataset**
- Research/acquire Indian medicine dataset → loaded (EMR catalog: brands/salts/manufacturers)
- Source drug interaction data → `DrugInteraction` model + `/api/v1/interactions` (auth'd)
- Alternative/generic mappings → `BrandComposition`, `SaltAlternative`, alternatives endpoint
- Data ingestion pipeline → `scripts/load_indian_medicines.py`, `03_import_emr_medicine_data.py`
- Therapeutic class categorization → `TherapeuticClass` model
- Schedule classification (H/H1/X) → `Salt.schedule` field
- dosage_form standardization → `Brand.dosage_form`
- Medicine search API → `medicines_emr.py` search endpoints
- Medicine autocomplete → trigram-indexed
- Search indexes migration → `alembic_medicine` `b3f0c1d2e4a5`
- Medicine detail endpoint → exists

**Admin Panel**
- `require_admin`, admin routers, dashboard + real stats, sidebar (incl. Catalog), Keycloak role mapping, AuthGuard
- `audit_logs` table + `log_change` service + `changed_by`; audit list/filter/export/diff
- Medicine management: list/add/edit/bulk-import UI + brand/salt/manufacturer CRUD (all authenticated now)
- User management: list/detail/activate/role-change→Keycloak/walk-in create/confirm dialogs
- Doctor verification: pending queue/detail/approve+notify/suspend
- Announcement broadcast + platform settings pages → REAL now (announcements create notifications; settings enforced: maintenance_mode middleware, max_upload_mb, reminder_channels_enabled)
- Admin visits + lab-results pages + endpoints exist
- Appointment-request approve/reject endpoints (round 3 — were live 404s)

**Prescription Enhancement**
- Autocomplete, auto-populate, interaction warnings UI, alternatives, PDF (authenticated blob download), templates CRUD + sidebar
- **Server-side clinical safety gate** — interactions + allergies + duplicate therapy + contraindications, override flow, `PrescriptionAudit` persistence, unresolved-item alerts

**Patient Portal**
- Profile edit, medical history, booking, notification center + badge, document upload (secured: presign→owner-binding→ACL), vitals + paired BP + charts, record download helper
- **Lab results page** (with categories), **billing page** (invoices + receipts), **medications view** (active Rx + adherence), live queue position

**Doctor Portal**
- Appointments, patient search (now actually filters server-side), patient history, templates, notifications
- **Availability windows + leave + slot generation** (`/doctor/schedule`, `/availability/*`)
- **SOAP encounters** (`/doctor/visits`, `/api/v1/encounters`, write-audited)
- Clinic staff invites + receptionist memberships (`/doctor/clinic/invites` in nav; `/invite` redeem page; AuthGuard membership bypass)

**Notifications**
- In-app system + unread badge; reminder worker creates notifications per channel; sms/whatsapp pref keys settable; platform channel kill-switch honored

**Security & Compliance**
- Rate limiting (trusted-proxy XFF), RBAC audit closed, upload ACL + key binding, PHI read audit middleware (incl. encounters/lab-results/search), consent write-gating on revoked links, CSP hardened (ws: gated to dev), Keycloak prod hardening, Jitsi random room tokens, admin self-delete guards, audit writes on encounters
- **Access-service centralization** — NOT done; still 5 divergent copies (flagged refactor)

**Testing & Quality**
- CI/CD hardened; backend suite 210/210 green on real Postgres 16; alembic chain verified upgrade/downgrade; test infra (NullPool, env-overridable URLs, fakeredis)

**Infrastructure & DevOps**
- Staging/prod K8s + Terraform (deploy-blockers fixed), kube-prometheus-stack + ServiceMonitor, Redis (rate limit + ARQ + upload registry), S3 backend path (IRSA pending), .dockerignore×3, non-root compose, multi-stage Dockerfiles, pinned tags, dependabot, security-scan.yml

## Mark PARTIAL — exists but incomplete

- Bulk medicine/user export → client-side CSV only; no backend export endpoint
- User activity timeline on user detail page → missing
- Doctor document upload in onboarding → fields captured, file path partial
- Verified badge patient-facing → partial
- Prescription validity → `valid_until` exists; expiry notifications missing
- Patient slot booking → availability + slot gen exists; patient-facing slot-picker UI missing
- DB backups → RDS 30d retention; no restore drill/runbook
- Coverage → suite green but far from 80%
- Pre-commit hooks → not configured
- SMS/WhatsApp → channel abstraction + prefs + kill-switch exist; provider adapters (MSG91/Twilio) not implemented
- Reminder unschedule → abort exists; true re-defer on update works, but no `unschedule` on cancel-from-status-endpoint
- Download helpers → canonical `lib/download.ts` exists; 3 inline copies remain

## NOT DONE — next implementation rounds

- **Round-5 — ALL LANDED (verified, merged, pushed):**
  - DPDP: consent capture + `POST /patients/erasure` (soft-delete/anonymize, links revoked, idempotent); claim-sync guarded so erased PII can't resurrect
  - Patient live queue-status page (`GET /queue/my-position` + `/patient/queue`)
  - Receptionist portal: `get_clinic_staff` dep — queue check-in/status/delete role-scoped; clinic appointment list; `GET /clinics/{id}/doctors` + booking-modal doctor picker
  - Doctor dashboard: real today-schedule/queue/quick-actions widgets
  - Medication adherence view (active vs expired, course progress, 3-day expiry badges)
  - Redis medicine-catalog cache (`medcat:*`, 300s/3600s TTL, admin-mutation invalidation, graceful fallback)
  - Per-user rate limiting (JWT-sub bucket, `RATE_LIMIT_USER_PER_MINUTE=240`, presign+interactions endpoint limits, `X-RateLimit-Bucket` header)
  - Playwright e2e scaffold + `e2e.yml` workflow
  - `scripts/seed_demo_data.py` (idempotent, `--drop`, `make seed`)
  - Sentry frontend init (client/server/edge configs, axios 5xx capture, Dockerfile + cd.yml args)
  - Admin verification UI: license document surfaced (detail + pending list); uploads-ACL admin-bypass ordering fixed
  - Verified badge in patient doctor search (backend field + UI)
  - Clinic timezone settable via `ClinicUpdate` (IANA-validated)
  - 46-test coverage file (exports, receptionist authz, queue ops, encounter access) — caught `GET /encounters` 500 (missing batched name-loader, fixed) + 422-handler flattening of domain codes (fixed)
- **Round-6 — LANDED:** announcement broadcast (audience/type/recipient preview, audit-backed list), admin settings wired to platform flags (maintenance confirm, upload cap, reminder channels) + settings now audit-logged, admin system-health page (`GET /admin/system/status` — deps latency, ARQ depth, counts, uptime), backup/restore drill scripts + docs
- **Round-6 — ALL LANDED (verified, merged, pushed):**
  - Receptionist front-desk full flow: book linked patients (staff clinic context via membership), status transitions (no completed), reschedule — 12 tests
  - Per-clinic admin metrics endpoint + 6 stat cards on clinic detail
  - Rx page: draft autosave (localStorage, cross-patient guard), allergy banner + allergy×medicine conflict check, submit-time interaction gate w/ ack checkbox, 409 SAFETY_OVERRIDE_REQUIRED → reason + resubmit flow (was dead end)
  - OpenAPI→TS contract gen (`scripts/export_openapi.py` + `gen:api-types` + CI contract job + schema.d.ts) — caught duplicate route collision (fixed: clinic-doctors dual-role handler + admin/visits dedup)
  - pgbouncer (transaction mode, SCRAM, statement_cache_size=0 flag) + UVICORN_WORKERS env
  - Patient onboarding checklist (5 real-data items, dismissible)
  - Loki+Promtail+Grafana under `observability` compose profile + docs/logging.md + RUNBOOK §8
- **Round-7 queue:** structured allergy→salt mapping (fuzzy matching caveat), response_model= coverage for OpenAPI gen, Web Push, i18n, load testing, OCR/AI ingest, barcode source, coverage→80%, Keycloak-side erasure (needs admin creds)
- **BLOCKED — ABDM/ABHA: awaiting regulatory approval (user-confirmed)** — do not implement: ABHA creation/linking, NRCeS-conformant FHIR, HIP module (tickets 107–116)
- **Blocked/external:** SMS/WhatsApp live provider accounts (code adapters anyway), OCR/AI features, load testing env, i18n assets, barcode data source, push VAPID/service

## Apply when Jira creds available

Drop `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_PROJECT_KEY=MED` into `.env`, then `python3 .claude/jira_cli.py list` → match by Summary → `complete <KEY>` for DONE items.
