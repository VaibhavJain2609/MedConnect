# MedConnect — Platform Improvement Plan

*Generated 2026-09-20 from a 30-agent audit: 26 domain specialists + 4 adversarial critics who re-verified every claim against the code. Raw cluster reports in `analysis/`.*

## Executive summary

MedConnect has real architectural depth (dual-DB medicine catalog, clinic tenancy, consent model, OIDC/Trivy/cosign CD pipeline) but is **not production-ready** in three distinct ways:

1. **Security**: multiple confirmed cross-tenant PHI exposure paths — the worst being self-assignable doctor role (`auth.py:32-60`) combined with `get_current_doctor` never checking `verified`, unauthenticated drug-interaction writes, revoked-consent bypass, and uploads with no object ACL.
2. **Deployment**: the k8s/Terraform stack is well-architected but has never been applied and contains **≥10 deploy-breaking defects** — the backend literally cannot start (ConfigMap sets values the app's own prod validator rejects).
3. **Functionality**: several shipped features are broken end-to-end — queue page reads a nonexistent localStorage key, admin catalog mutations 401 via raw `fetch`, all Rx PDF links 401, notification preferences 500, admin pagination renders nothing past page 1, migration 003 breaks fresh installs.

---

## Tier 0 — Launch blockers (fix first, before any real deploy or users)

### 0A. Security launch-blockers (all code-verified by critic)

| # | Issue | Location | Fix |
|---|---|---|---|
| 1 | Self-service privesc: any user → doctor realm role via `POST /auth/set-role`; `get_current_doctor` never checks `verified` → instant read access to all doctor endpoints | `routers/auth.py:32-60`, `dependencies.py:148-166`, `auth/callback/page.tsx:29` | Gate role assignment behind invite/admin approval; check `verified` on doctor read paths |
| 2 | Revoked consent: omitting `X-Clinic-Id` skips `revoked_at` cutoff entirely; revoked links also *widen* scope to all doctors' records | `vitals.py:304-339`, `doctors.py:282-298, 363-365, 436-441` | Treat revoked as denied/cutoff regardless of header; scope revoked reads to the link's clinic |
| 3 | Amendment IDOR: `GET /doctors/records/{id}/amendments` returns full PHI with zero relationship check | `doctors.py:513-563` | Reuse relationship + consent gating |
| 4 | Billing IDOR: doctors read/write all bills platform-wide, no membership checks | `billing.py:71-269` | Scope all doctor billing to `ClinicMembership`-verified clinics |
| 5 | Anonymous write/delete on drug-interaction data (docstring claims admin-only, no dependency) | `interactions.py:97-186` | `Depends(require_admin)` on writes, `get_current_user` on reads |
| 6 | Uploads: PUT to any key (presign cosmetic), GET any key, no size cap | `uploads.py:93-170` | Track issued keys (Redis SETEX), reject unknown/overwrite, per-object ACL via record mapping, size cap + streaming |
| 7 | Clinic invite role unvalidated (mint `owner`); any user can create clinic + become owner; link-provisional silently re-approves revoked consent + bulk-transfers records | `clinic_invites.py:48-53`, `clinics.py:68-75`, `appointments.py:848-973` | Whitelist role to `doctor`; `get_current_doctor` on clinic create; reset revoked links to `pending`, require membership role |

### 0B. Deploy-blockers — k8s/Terraform "works on paper" only

Confirmed by critic: **the stack has never been applied and the first deploy fails at ≥10 independent points**:

| # | Defect | Location |
|---|---|---|
| 1 | **Backend can never start**: ConfigMap sets `APP_ENV=production` + `KEYCLOAK_URL=http://keycloak:8080` — exactly the banned default `config.py:37-52` rejects; `FRONTEND_URL`/`BACKEND_URL` absent under `infra/` → localhost defaults → crash-loop for pods AND the alembic Job | `infra/k8s/base/backend/configmap.yaml:6,22` |
| 2 | ExternalSecret placeholders (`PLACEHOLDER_SECRET_STORE_NAME`, `ENVIRONMENT_PLACEHOLDER`, region, namespace) never patched by overlays → secrets never sync | `base/external-secrets/*`, `overlays/*/kustomization.yaml` |
| 3 | `ClusterSecretStore` references SA `external-secrets-irsa` that doesn't exist/isn't IRSA-trusted | `cluster-secret-store.yaml:17` vs `addons/irsa.tf:9-12` |
| 4 | `kubectl apply` includes cluster-scoped `Namespace` + `ClusterSecretStore` the CD role's EKSEditPolicy can't touch | `shared/main.tf:83-92`, `base/kustomization.yaml:7,23` |
| 5 | OIDC sub mismatch: allows `environment:prod`, workflows send `environment:production` → prod deploys always fail | `iam-oidc-github/main.tf:13` |
| 6 | ACM/WAF ARN placeholders in ingress never substituted by the pipeline (deploy.yml only sets images) | `overlays/*/kustomization.yaml:41-49` |
| 7 | ALB `healthcheck-path: /health` applied to all TGs — frontend serves `/api/health`, Keycloak health is on :9000 → frontend+keycloak TGs permanently unhealthy | `ingress.yaml:27` |
| 8 | ElastiCache `transit_encryption_enabled=true` but secrets emit `redis://` → Redis connect fails → `/health` 503 → backend never ready | `elasticache/main.tf:68`, `prod/main.tf:95`, `staging/main.tf:119` |
| 9 | RDS has no `db_name` and nothing creates `medconnect`/`medconnect_medicines`/`keycloak` schema — alembic Job + Keycloak dead on arrival | `rds/main.tf:64-98` |
| 10 | Migration `003_add_search_indexes` in the **main** chain indexes medicine-DB tables → fresh `alembic upgrade head` fails (backend crash-loops on every fresh compose too) | `alembic/versions/003` → move to `alembic_medicine` |

*Also blocking real users post-boot:* frontend image bakes `localhost` (no `NEXT_PUBLIC_*` build-args in `cd.yml:53-60` / `frontend/Dockerfile`); `next.config.js:9` rewrite targets `backend:8000` but the k8s Service listens on :80; reminder-worker Deployment absent from k8s → reminders dead-letter by design.

### 0C. Broken shipped functionality (fix before any demo)

| # | Broken thing | Evidence | Fix size |
|---|---|---|---|
| 1 | Doctor queue page dead — reads `localStorage["activeClinicId"]` but store persists `"clinic-store"` → permanent "No active clinic" (also breaks BillPatientModal) | `doctor/queue/page.tsx:179-181` vs `clinic-store.ts:31`; interceptor already sends `X-Clinic-Id` (`api.ts:33-38`) | S |
| 2 | `GET/PUT /notifications/preferences` 500 — filters on nonexistent `NotificationPreferences.deleted_at` | `notifications.py:291,320` | 1-line |
| 3 | `patient_link_codes` rotation 500s — hard `unique` on `patient_id` + soft-delete-then-reinsert | `patient_link.py:40`, `patient_links.py:62-71` | partial unique index |
| 4 | `/admin/medicines*` + `/admin/components*` all 500 — query tables dropped by destructive migration `8e7b05567dfb` (which auto-runs at every fresh deploy) | `main.py:148-149`, `alembic_medicine/8e7b` | unmount or restore |
| 5 | Route shadowing: `admin/stats.py` GET `/admin/lab-results` + `/categories` serves fabricated `MedicalRecord` rows while real `LabResult` CRUD exists — list vs CRUD disagree | `main.py:131 vs 135` | dedupe routers |
| 6 | Admin salts/manufacturers/medicines mutations use raw `fetch` without `Authorization` → silent 401s (GETs work because catalog reads are public) | `salts/page.tsx:37-76`, `manufacturers:35-74`, `medicines:47-128` | switch to `api` |
| 7 | Admin doctors/patients/visits/lab-results pagination never rendered — only first page reachable | `doctors/page.tsx`, `patients/page.tsx:388-396`, `visits`, `lab-results` | S |
| 8 | ALL PDF/doc downloads broken — `<a href>` carries no Bearer → 401s (Rx print page, patient records, document_url). `document_url` not even rendered on record detail | `prescriptions_pdf.py:362`, `uploads.py:140`, `print/page.tsx:117,125` | blob-download helper |
| 9 | Error envelope misread — interceptor reads `data.detail.message`, real message at `data.detail.error.message` → users never see real backend errors | `api.ts:88-95` | 1-line |
| 10 | Phantom frontend endpoints: `/api/v1/search*`, `/patients/{id}*` variants, `/admin/visits` CRUD, `/admin/doctors` CRUD, `/doctors/templates` | `search.ts`, `patients.ts:135-167`, `visits.ts:95-115`, `doctors.ts:116-135`, `templates/page.tsx:38` | fix paths or implement |
| 11 | Frontend test CI red by construction: 70-80% thresholds vs ~2% real coverage; tautological test file; MSW disabled; no `.eslintrc` (next lint hangs) | `jest.config.js:21-28`, `package.json` | S |
| 12 | `_user_cache` detached-User bug — mutations silently lost (set-role!), deactivated users valid 30s, leaks across tests | `dependencies.py:24,64-71` | cache DTO or drop |
| 13 | Toast system is a stub (console.log only, no `<Toaster>`); GlobalSearch trigger dead in all 3 layouts (⌘K only) | `use-toast.ts:18-27`, all `*-layout.tsx` | S |
| 14 | Shadowed `models/medicine.py` (+component.py, medicine_component.py) → next `--autogenerate` emits `drop_table("medicines")` on main DB | package shadows file | delete files + migration |
| 15 | Admin stats dashboard runs ~360 sequential per-day COUNTs with index-defeating `func.date()` | `stats.py:195-363` | GROUP BY rewrite |
| 16 | Autocomplete `lower(brand_name).like` can't use trigram index → seq scan per keystroke (index also lives in wrong DB per 0B#10) | `medicines_emr.py:74-89` | `ilike` + move index |
| 17 | `audit_logs.changed_by` always NULL — `set_audit_user` never set with real user | `main.py:74-81` | 1-line fix |

---

## Phase 1 — Security hardening (post-blockers, pre-launch)

1. **Centralize access policy**: extract `access_service` (consent, relationship, record-access) — same logic currently re-implemented 5 ways with divergent revoked semantics. Highest-risk drift in the codebase.
2. **Clinical safety gate server-side**: run interaction + allergy + duplicate-therapy + contraindication checks inside `create_prescription` (all tables exist unused); block `contraindicated`, persist `PrescriptionAudit`. The client-side check fails open (`catch → []`).
3. **Keycloak prod hygiene**: `sslRequired:"external"`, email verification + brute-force detection, restrict `/admin`+master realm at ingress/WAF, replace `admin-cli` password grant with service account, `start` not `start-dev`.
4. **Validation gaps**: `duration_minutes` bounds + past `scheduled_at` on appointment create; `branch_id↔clinic_id` consistency; membership check on body `clinic_id`; guest booking doctor-membership; `document_url`/`action_url` scheme allowlist (stored XSS); ReportLab `escape()` all user strings (server-side file-read primitive); `secrets` not `random` for link codes + consume codes on use; `max_uses` on onboarding join path; `list_clinic_patients` consent_only leaks revoked patients' PII.
5. **Audit trail**: `log_change` on consent grant/revoke (none today — DPDP-fatal); read/export auditing on PHI endpoints; persist failed-auth attempts; fix `changed_by`.
6. **Race conditions**: queue `max+1` → unique constraint; appointment conflict check → exclusion constraint/`SELECT FOR UPDATE` (TOCTOU confirmed).
7. **Frontend**: single-source CSP without unsafe-eval in prod; clear SW caches + React Query + stores on logout; blob-based authenticated downloads; remove `?token=` temptation permanently; upgrade Next.js (≥14.2.25 for CVE-2025-29927; stable 14.2.21 is likely *not* hit by React2Shell — critic correction — but still upgrade); upgrade Keycloak 24→26 (EOL, real CVEs) + `keycloak-js` in lockstep.
8. **Encryption at rest** decision: volume/disk encryption documented as minimum; field-level (Fernet/KMS) for `fhir_bundle`, `description`, lab values if targeting ABDM/DPDP-grade posture.
9. **JWKS**: pre-warm at startup + wrap sync fetch in threadpool (blocks event loop on rotation); share JWKS via Redis.
10. **Rate limiter**: `request.client.host` not raw XFF; consider fail-closed for code-redemption/auth paths.

## Phase 2 — DevOps roadmap

**What exists (good bones):** OIDC-based AWS auth (no static keys), immutable SHA image tags, Trivy scan, cosign keyless signing, migration-Job-before-rollout ordering, env-gated manual rollback, kube-prometheus-stack provisioned, ExternalSecrets architecture, PDBs/HPAs/probes, kubeconform in CI, dual-DB migration verification.

**After Tier 0B fixes, add:**

| Priority | Addition | Why |
|---|---|---|
| P0 | `PrometheusRule`s + Alertmanager receivers + external uptime check | kube-prometheus is deployed with zero alerts — outages found by users |
| P0 | Reminder-worker Deployment + Sentry init in worker | reminders are write-only logs in prod today |
| P0 | `.dockerignore` ×3 + drop `user:root` + `127.0.0.1:` port bindings + frontend dev stage | `.env` baked into signed images is the top supply-chain risk |
| P1 | `security-scan.yml`: CodeQL + dependency-review + `pip-audit`/`npm audit` + scheduled Trivy rescan; `.github/dependabot.yml` (pip/npm/docker/gha/terraform) | zero dep-vuln detection today; Keycloak/Next staleness proves it |
| P1 | Scan-before-push ordering for Trivy; CD gated on CI (`workflow_run` or branch protection); `timeout-minutes` everywhere; `rollback.yml` input injection fix (`env:` + `^[0-9]+$`) | pipeline correctness |
| P1 | Migration safety: expand/contract policy doc, `alembic check`/empty-autogen gate in CI, optional `alembic downgrade` input on rollback + post-rollback smoke | rollback currently never reverts schema |
| P1 | Sentry completion: `environment`/`release`, `capture_exception` in global handler, `@sentry/nextjs` frontend | currently configured-but-blind |
| P1 | Structured logging: request-ID middleware + `merge_contextvars` + stdlib→structlog bridge; scrub PHI from reminder logs; Loki/Promtail on existing Grafana | ~16 log call sites total; PHI in INFO logs today |
| P1 | Probe split: shallow `/health` liveness vs deep `/health/ready` readiness (DB blip currently restart-loops pods) | cascading restarts |
| P1 | Backups/DR: RDS retention →30d + backup_window + cross-region copy; ElastiCache `snapshot_retention_limit`; `docs/RUNBOOK.md` (DB restore, Redis loss, Keycloak outage); quarterly restore test | 7-day snapshots only, restore never tested |
| P2 | NetworkPolicy default-deny; securityContext hardening (readOnlyRootFilesystem, drop ALL, seccomp); PodSecurity labels; topologySpreadConstraints; helm version pinning; EKS endpoint CIDR restriction | defense in depth |
| P2 | Backend IRSA + S3 for uploads (emptyDir loses files across replicas); Container Insights/fluent-bit; pgbouncer or pool sizing for multi-worker uvicorn; `pg_stat_statements` + tuned postgresql.conf | scale/ops |
| P2 | Python lockfile (`uv`/`pip-tools` + `--generate-hashes`); SBOM via `sbom:true` + `cosign attest`; actions pinned to SHAs; digest-pin base images | supply chain |
| P2 | DevEx: `docker-compose.override.yml` split, Makefile, placeholder-lint CI step (`grep PLACEHOLDER_` on rendered manifests — would have caught a whole defect class), `medicine_db_test` on :5433 or conftest fix | tests currently can't run against compose |
| Later | PR preview envs, `release.yml` (v-tag → changelog → deploy), e2e workflow (Playwright vs compose stack), terraform plan-on-PR + drift detection, CODEOWNERS | maturity |

## Phase 3 — UI/UX overhaul

**Immediate (all S-effort, high visible payoff):** mount a real `<Toaster>` (sonner) + replace `alert()`/`confirm()`; wire GlobalSearch triggers; associate `htmlFor`/`id` on the 11 Rx-form labels; remove `maximumScale:1` (WCAG violation); `useClinicStore()` on queue page; `?patient_id` param fix; records/new UUID-as-name fix; server pagers on 4 admin pages; delete `/patient/[id]` catch-all (or make it real) + add `/patient` redirect; notifications in both sidebars + prefs UI; blob-download helper; templates page endpoint fix + sidebar entry.

**Design-system work:** shared `Skeleton`/`Spinner`/`EmptyState` primitives (kills 85 hand-rolled spinners); centralize status→badge variant map with AA-safe `-700` text shades; consolidate 3 table stacks onto extended `DataTable` (server pagination + row selection + aria-sort); route all overlays through Radix Dialog/Sheet (focus trap, Escape); decide dark mode (ship tokens or remove dead `.dark`); lint rule banning raw palette classes; per-portal `loading.tsx`/`error.tsx`; PWA `start_url:"/"` + role redirect.

**Accessibility program:** jest-axe sweeps + `eslint-plugin-jsx-a11y`; keyboard nav on MedicineAutocomplete; accessible modals everywhere; 44px touch targets; hamburger aria-labels; label association sweep.

## Phase 4 — Feature roadmap (merged, dependency-ordered)

| # | Feature | Effort | Depends on |
|---|---|---|---|
| 1 | Server-side Rx safety gate (interactions + allergy + duplicate-therapy + contraindications; persist `PrescriptionAudit`) | M | — |
| 2 | Authenticated download path (signed URL/blob) — unblocks PDFs, docs, receipts | S | — |
| 3 | DOB + sex on User; NMC-compliant Rx PDF (age, qualifications, signature) | S-M | — |
| 4 | Doctor availability model + slot generation | M | — |
| 5 | Slot-based booking + patient reschedule | M | #4 |
| 6 | Teleconsult join link (`meeting_url` on Appointment) | S-M | #5 |
| 7 | Real SMS/WhatsApp/email reminder channels (~80% plumbing exists) | S-M | — |
| 8 | Patient lab-results + documents view | S | #2 |
| 9 | Patient billing page + receipts | S | #2 |
| 10 | Fix stats.py fabricated appointment metrics (real `Appointment` queries) | S | — |
| 11 | Receptionist/staff clinic roles | M | — |
| 12 | Visit/encounter SOAP notes | M | — |
| 13 | Medications view: active-meds list + adherence reminders | M | #7 helps |
| 14 | Audit hardening (`changed_by` fix, retention, per-record history) | S-M | — |
| 15 | Announcement broadcast + platform settings/feature flags (fills the 2 stub admin pages) | S-M | — |

**Later:** doctor analytics dashboard, waiting-room display + ETA, lab orders for doctors, e-signature, follow-up plans, per-clinic usage metrics, bulk ops + CSV export, secure messaging, family/dependant profiles (L — biggest scope), DPDP data-principal rights (export/erasure), ABHA + ABDM-conformant FHIR + HIP module (XL — Jira tickets 107-116 already drafted).

**Explicitly deprioritized:** symptom checker (clinical liability), health goals, insurance fields, impersonation tooling (security risk — audit first).

## Phase 5 — Testing & hygiene

**Testing:** autouse `_user_cache.clear()` fixture; fix test-DB topology (conftest wants :5433 `medicine_db_test` that doesn't exist); session-scoped schema via migrations + per-test rollback; `--cov-fail-under` ratchet; `requirements-dev.txt`; appointment state-machine + clinic-isolation test suites (highest-risk untested logic); fakeredis for rate-limit middleware; frontend: realistic coverage thresholds, `.eslintrc.json`, MSW re-enable + real component tests, Zod schema tests, Playwright smoke (login→dashboard per role).

**Hygiene:** delete dead code (`routers/medicines.py`, `routers/prescriptions.py`, `services/pdf_service.py`, `services/template_service.py`, `models/medicine.py` + `component.py` + `medicine_component.py`, `medicines.ts`, `page.old.tsx`, `PrescriptionFormExample.tsx`, PhotoUpload); decide fate of `admin/medicines`+`admin/components` (query dropped tables); medicine catalog single pipeline (delete scripts 01/02, version-pin dataset); `target_metadata = MedicineBase.metadata` in `alembic_medicine/env.py`; CLAUDE.md drift fixes (mounted routers wrong, missing routers); `.gitignore` add `graphify-out/`, `.serena/`; drop orphan `audit_log` + main-DB `medicines` tables; reconcile TODO.md vs done.md.

## Critic corrections (claims adjusted after verification)

- Next.js 14.2.21: *not* live RCE (React2Shell affects React 19/Next≥15; stable 14.2.21 likely unaffected); still upgrade for CVE-2025-29927 latency → **P1 not P0**.
- Service-worker PHI caching: precaches the HTML shell only (navigate-mode fetch) → **P2**, though logout-cache-clearing still required.
- "RDS creates no databases" is *intentionally* deferred-but-undocumented → still a first-deploy blocker (P0 in Tier 0B).
- RDS `sslmode` unverified (drivers default `prefer`, likely connects) → flag, not blocker.
- Admin appointments "case-sensitive search" claim partially wrong — only the id-substring search is case-sensitive.
- Several auditors' P2s upgraded by critics: provisional-link revoked-consent resurrection (**P1**), ReportLab markup injection as server-side file read (**P1**), unverified-doctor read surface (**P0** chained with set-role).

## Suggested sequencing

```
Week 1-2:  Tier 0C broken-functionality fixes (1-2 devs, mostly S-effort) +
           Tier 0A security items 1-7 (security-focused dev)
Week 2-3:  Tier 0B infra fixes + first successful terraform apply to STAGING only;
           .dockerignore / CI quick wins; Dependabot
Week 3-5:  Phase 1 hardening (access_service, Rx safety gate, audit trail, races)
           + Phase 3 UX quick wins
Week 5-8:  Phase 2 DevOps (alerting, sentry, backups, scan gates) +
           Feature roadmap #4-#9 (availability → booking → teleconsult → reminders)
Later:     DPDP compliance, ABDM track (ABHA→FHIR profiles→HIP), family profiles
```
