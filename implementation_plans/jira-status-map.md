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

- **Unblocked, prioritized:**
  1. Patient slot-picker booking UI (backend ready)
  2. access_service centralization (5 divergent copies — root cause of past authz bugs)
  3. Write-side `log_change` coverage: vitals, billing, queue, appointments, uploads, clinics
  4. Notification preferences UI page (API exists, zero callers)
  5. Receptionist backend role-enforcement on clinical endpoints (currently relies on global role)
  6. Doctor onboarding document upload completion
  7. Record export endpoint (FHIR bundles already generated)
  8. SMS/WhatsApp provider adapters (code the interface; no live creds needed)
  9. Prescription expiry notifications
  10. Verified badge patient-facing completion
  11. User activity timeline on admin user detail
  12. Backend export endpoints (CSV) for medicines/users/audit
  13. Pre-commit hooks config
  14. PrometheusRule alert set + Grafana dashboards + RUNBOOK.md
  15. Download-helper convergence (3 inline copies → `lib/download.ts`)
- **BLOCKED — ABDM/ABHA: awaiting regulatory approval (user-confirmed)** — do not implement: ABHA creation/linking, NRCeS-conformant FHIR, HIP module (tickets 107–116)
- **Blocked/external:** SMS/WhatsApp live provider accounts (code adapters anyway), OCR/AI features, load testing env, i18n assets, barcode data source, push VAPID/service

## Apply when Jira creds available

Drop `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_PROJECT_KEY=MED` into `.env`, then `python3 .claude/jira_cli.py list` → match by Summary → `complete <KEY>` for DONE items.
