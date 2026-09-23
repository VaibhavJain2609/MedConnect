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
- **Round-7 — ALL LANDED (387 backend tests green, 29 frontend tests, 59-page build):**
  - Consent management UI (revoke confirm + restore, status chips)
  - i18n scaffold (next-intl, EN/HI, cookie-switched, sidebar+timeline proof)
  - e2e: 3 new specs (queue/patient-journey/admin) + per-role auth setups
  - Worker tests (36) + 3 REAL BUGS FIXED: expiry-sweep rollback crash, reminder partial-enqueue loss, doctor-notif retry duplicates
  - Structured allergy→salt endpoint + Rx page wired (server match + local fallback)
  - Locust loadtest scaffolding (weighted traffic, smoke/ramp/spike modes)
  - Billing receipt/invoice PDFs + patient download
  - Web Push end-to-end (subscriptions, VAPID, provider, prefs, SW handler, kill-switch)
  - response_model= on 21 hot endpoints (OpenAPI→TS now emits real types)
  - jest-axe a11y suite (29 tests) + fixes: labels, dialog roles, aria-labels
- **Round-8 — ALL LANDED (473 backend tests, 45 frontend tests green; 0 npm high/critical vulns):**
  - Next.js 14.2.35→16.3.5 + React 19.3 (Turbopack build, flat eslint config, viewport export) — cleared all remaining CVEs
  - axios→1.20, fastapi→0.133.1, starlette→1.3.1, PyJWT→2.13, python-multipart→0.0.32, requests→2.34.2 (42 pip-audit advisories → 0)
  - Medical-record amendment history UI (patient-facing versions endpoint + field-level diff)
  - Admin audit-log CSV export (all list filters honored, 50k cap, EXPORT audit row)
  - Security headers middleware (no-store on /api/v1/* — PHI cache-poisoning fix)
  - Notification deep-linking (SPA nav, fallback, vitals emitter url added)
  - Audit-log diff viewer (diffValues + expanded-row UI)
  - +68 coverage tests (encounters lifecycle, uploads owner-binding/size-cap)
  - FIX: ReminderLog was never imported → absent from Base.metadata (alembic autogen + drop_all bug)
- **Round-9 — ALL LANDED (665 backend tests, 45 frontend tests green):**
  - react-hooks v7 triage: 45 warnings → 9; real bugs fixed (stale-closure access-before-declared, edit-modal branch discard, draft-branch restore, sidebar remounts)
  - Real-browser axe sweep (Playwright + axe-core) — contrast fixes (badge pairs, placeholders), aria-prohibited-attr, heading-order; 4-page spec for CI
  - Admin coverage: 139 tests → found + fixed 3 real 500s (UUID coerce, clinic timezone, uuid path params) + self-guard regression
  - Shared Pagination/LoadMoreButton wired to 4 pages; fixed >50-appointment silent truncation
  - Global search expanded: lab results, prescriptions, records, clinics, appointments w/ per-role scoping + per-user endpoint rate limit
  - Encounter summary PDF + doctor download button
  - Keycloak erasure ops path: anonymize/disable script + DPDP runbook + keycloak_identity_retained flag
  - starlette 1.x deprecations cleaned (status constants, TestClient)
- **Round-10 — ALL LANDED (838 backend tests, 45+ frontend tests green):**
  - pydantic ConfigDict sweep (37 class-Config blocks → 0 deprecation warnings)
  - Patient visits page (encounter list + SOAP + vitals + PDF download)
  - Coverage: auth/patient-links/clinic-invites (109 tests) → 4 REAL BUGS FIXED: /clinics/search route shadow, join-request FK 500, membership reinsert 500s on redeem+approve
  - i18n expansion: patient appointments/notifications/profile + pagination (en/hi, key-parity test)
  - Medicine barcode: pack barcode index + /by-barcode + digit-query search + admin packaging field
  - Queue-position notifications (called/next-up, meta-deduped, kill-switch gated)
  - billing_items table + itemized create/detail/list + receipt lines + admin bill-create modal
  - OCR/AI lab ingest scaffold (provider protocol, human-review ingest, disabled by default)
- **Round-11 — ALL LANDED (1007 backend tests green, warnings 519→12):**
  - datetime.utcnow() sweep — 19 medicine-model sites → shared utcnow() helper (naive-UTC for naive TIMESTAMP cols)
  - Production config guards — fail-fast on dev creds/http URLs/wildcard CORS/DEBUG/audience-check/weak admin creds; LOG_LEVEL + ALLOWED_HOSTS/TrustedHostMiddleware; RUNBOOK §10 prod checklist
  - e2e CI now real — Keycloak password-grant fixture (real token+refresh), seeded demo users in realm export, full compose→migrate→seed→serve→playwright workflow; fixed PLAYWRIGHT_BASE_URL '' bug
  - Vitals/records/health/search coverage — 112 tests; verified revoked-link cutoff + per-role search scoping
  - Patient records filters — record_type/from_date/to_date/q params + debounced filter bar w/ URL sync
  - Prescription refill flow — request → doctor approve(clones rx)/decline(notify), partial-unique dedup, cross-clinic deny
  - Outbound webhooks — endpoints CRUD + HMAC-signed ARQ delivery + deliveries log, flag-gated, PHI-minimal payloads
  - PWA — manifest+icons, install prompt (patient portal), /offline nav fallback, API never cached
- **Round-12 — ALL LANDED (1074 backend + 58 frontend tests green):**
  - Doctor weekly calendar view (list/calendar toggle, Mon–Sun grid, from/to range params on GET /appointments)
  - Vitals trend charts (recharts, normal-range bands, abnormal markers, aria summaries + sr-only tables)
  - Family members — dependent profiles + records attach/filter (031→032_family_members)
  - Teleconsult — deterministic Jitsi rooms on existing meeting_url, participant-scoped, idempotent
  - Clinic holidays — table + owner/admin CRUD + slot-generation exclusion (clinic-local dates)
  - Appointment waitlist — join on full days, notify on cancellation (never auto-books)
  - Doctor portal i18n — dashboard/appointments/queue/patients/sidebar fully EN/HI
  - N+1 audit — query-count harness + real fixes (uploads ACL 24→7 queries, clinical-safety batching ~30→5)
- **Round-13 — ALL LANDED (1107 backend + 64 frontend tests green, lint 9→0):**
  - Admin portal i18n — dashboard/users/doctors/audit-logs/sidebar, ~137 keys/locale, LanguageSwitcher in admin sidebar
  - Webhook redelivery — single + bulk(50) failed replay w/ enqueue-failure revert; /doctor/clinic/webhooks admin UI
  - e2e validation — 4 public specs run live & pass; REAL BUG FIXED: login/signup fired keycloak.login() before init() (would break on next start); @auth specs await real CI
  - Lint warnings 9→0 (useWatch migration, set-state-in-effect fixes, next/image avatar; 2 documented targeted disables)
  - Notification prefs — queue_updates opt-out wired into queue notify path; prefs page i18n'd + push status badge/denied hint
  - Bulk catalog import — POST /admin/catalog/import CSV (dry-run, per-row SAVEPOINT, idempotent upserts, 13 tests) + import UI
  - Audit retention — audit_log_archive table + daily 09:00 worker (1k-row batches, 100k/run cap) + archived endpoint + Archive tab
  - Prescription safety checks — prescription_safety_checks snapshot per rx (alerts+override_reason) + GET endpoint + detail page
- **Round-14 — ALL LANDED (8/8):**
  - OpenAPI drift gate — schema.d.ts regenerated (was ~1,885 lines stale), `make check-api-types` + CI wiring; fixed Makefile venv-path bug (482154f, dcd3152)
  - Doctor leave — i18n `DoctorLeavesCard` extracted from schedule page + CRUD/slot-exclusion tests (8b999fc)
  - Smoke test tier — `pytest -m smoke` (38 tests) + Makefile target (4fb7331, a84c028)
  - 429 rate-limit UX — typed RateLimitError, Retry-After surfacing, single GET auto-retry, deduped localized toast (c67fd7e)
  - Doctor availability UX — clinic/branch-scoped windows, clinic timezone display, 7-day slot preview (7048089→54ebf89)
  - Encounter follow-ups — `POST /encounters/{id}/follow-up`, unique partial index, idempotent + doctor/clinic-scoped, modal UI (919e609+ce8d5c1)
  - Idempotency-Key — (key,user,endpoint) claim rows, SHA-256 body-hash mismatch→409, in-progress→409, 24h TTL, verbatim replay; 6 create endpoints + frontend keys (fc8109a)
  - Admin i18n complete — every remaining admin page + global search + notification center + shared UI; 1569 keys/locale exact parity (eb67839)
- **Round-15 — ALL LANDED (6/6, 67 new tests green):**
  - Waiting-room display — PHI-free token board `GET /queue/display` (names/ids never in payload, asserted by test) + `/doctor/queue/display` TV view + patient queue ETA i18n (18c9e6a)
  - Doctor analytics — `/doctors/analytics` (status counts, 8-wk completions, avg consult, top-10 medicines, queue-today) + `/doctor/analytics` recharts page w/ a11y pattern (714838a)
  - Lab orders — `LabOrder` model + doctor CRUD/status transitions + patient visibility, consent-gated writes (05ec27b)
  - Medication adherence reminders — opt-in per-rx times_of_day (Asia/Kolkata), 15-min cron slot match, Notification-meta dedupe incl. soft-deleted, flag `MEDICATION_REMINDERS_ENABLED` (748506c)
  - Admin CSV exports — patients + appointments honoring live filters, 50k cap, EXPORT audit rows (cb96370)
  - Uploads authz audit — download path already secure; +7 regression tests (unauth 401, cross-patient 403, pending-link 403, revoked split pre/post) (bcf9b5a)
- **Round-16 queue (in flight):** secure patient↔clinic messaging, DPDP patient data export, patient reschedule, SMS/WhatsApp adapters (flag-gated), hot-path index audit, router coverage gap-fill
- **Round-14 queue:** ABDM (BLOCKED), real LLM-OCR provider when creds exist, first real e2e CI run (@auth specs), medicine_import_sample.csv cleanup (done — stale file dropped)
- **BLOCKED — ABDM/ABHA: awaiting regulatory approval (user-confirmed)** — do not implement: ABHA creation/linking, NRCeS-conformant FHIR, HIP module (tickets 107–116)
- **Blocked/external:** SMS/WhatsApp live provider accounts (code adapters anyway), OCR/AI features, load testing env, i18n assets, barcode data source, push VAPID/service

## Apply when Jira creds available

Drop `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_PROJECT_KEY=MED` into `.env`, then `python3 .claude/jira_cli.py list` → match by Summary → `complete <KEY>` for DONE items.
