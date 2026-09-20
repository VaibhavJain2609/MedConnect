# Jira Board Status Map

*Source: `jira-import.csv` (git history, commit 2694230). Compared against codebase state after the audit-fix merge (6fb7cde). Jira API unavailable (no `JIRA_*` creds in `.env`) — apply these transitions when credentials are provided.*

## Mark DONE — exists and works (verified in code)

**Medicine Database & Dataset**
- Research/acquire Indian medicine dataset → loaded (EMR catalog: brands/salts/manufacturers)
- Source drug interaction data → `DrugInteraction` model + `/api/v1/interactions`
- Alternative/generic mappings → `BrandComposition`, `SaltAlternative`, alternatives endpoint
- Data ingestion pipeline → `scripts/load_indian_medicines.py`, `03_import_emr_medicine_data.py`
- Therapeutic class categorization → `TherapeuticClass` model
- Schedule classification (H/H1/X) → `Salt.schedule` field
- dosage_form standardization → `Brand.dosage_form`
- Medicine search API → `medicines_emr.py` search endpoints
- Medicine autocomplete → `medicines_emr.py` autocomplete (now trigram-indexed)
- Search indexes migration → `alembic_medicine` `b3f0c1d2e4a5` (moved to correct chain)
- Medicine detail endpoint → exists

**Admin Panel — Core Infrastructure**
- `require_admin()` dependency → `dependencies.py`
- Admin API router → `routers/admin/*`
- Admin dashboard + stats → `admin/dashboard/page.tsx` + `admin/stats.py` (real queries now)
- Admin sidebar → exists (Catalog group added)
- Admin Keycloak login/role mapping → auto-provision role sync
- Admin layout + AuthGuard → exists
- `audit_logs` table + migration → migration 010
- Audit service + `log_change` → `audit_service.py` (`changed_by` now populated)
- Audit list/filter API → `admin/audit.py`
- Recent activity feed → admin dashboard (actionable now)
- Frontend route protection → `AuthGuard`

**Admin Panel — Medicine Management**
- List page, add form, edit page (now reachable), bulk import UI, brand CRUD endpoints → all exist (`admin/brands.py`, `admin/salts.py`, `admin/manufacturers.py`)

**Admin Panel — User Management**
- User list, detail, activate/deactivate (now with confirm), role change (now syncs to Keycloak), walk-in user creation, user CRUD endpoints

**Admin Panel — Doctor Verification**
- Pending queue, verification detail, approve/reject endpoint, notification on verify, doctor list + filters, suspension (is_active)

**Prescription Enhancement**
- Autocomplete in form, auto-populate fields, interaction warnings UI, alternatives display, PDF generation + print view (now downloadable via authenticated blob), templates (endpoints fixed: `/doctors/prescription-templates`, added to sidebar)

**Patient Portal**
- Profile edit, medical history, appointment booking, notification center (now in sidebar), document upload (secured), vitals tracking + paired BP entry, vitals charts (Recharts), record download (authenticated download helper)

**Doctor Portal**
- Appointment management, patient search, patient history quick-view, prescription templates, doctor notifications (sidebar entry added)

**Notifications**
- In-app notification system + unread badge → exists (reminders now actually create notifications)
- Notification preferences page → backend fixed (was 500ing)

**Security & Compliance**
- Rate limiting → `rate_limit.py` (XFF hardened)
- RBAC audit → **done this session** (all audit findings verified + fixed)

**Testing & Quality**
- CI/CD pipeline → `.github/workflows/*` (hardened: gated CD, scan-before-push, security-scan, dependabot)
- Frontend Jest setup → now functional (lint + jest + build all green)

**Infrastructure & DevOps**
- Staging/prod K8s + Terraform → `infra/` (deploy-blockers fixed — pending first apply)
- Prometheus + Grafana → `kube-prometheus-stack` + ServiceMonitor
- Redis layer → exists (rate limit + ARQ; caching still TODO)
- S3 storage → `storage_service` has s3 backend path (IRSA pending)

## Mark PARTIAL — exists but incomplete

- Bulk medicine export → client-side CSV only; no backend `/admin/reports/export`
- Bulk user export CSV → not implemented
- User activity timeline → not on user detail page
- Doctor document upload → onboarding captures fields; file upload path partial
- Verified badge patient-facing → partial
- Prescription validity tracking → `valid_until` exists; expiry notifications missing
- Patient booking → works but free-text datetime (slot system is a new task)
- DB backups → RDS retention raised to 30d; no restore drill/pg_dump
- Backend unit/integration tests → suites expanded this session but coverage far from 80%
- Pre-commit hooks → not configured

## NOT DONE — candidates for next implementation rounds

- **High-value unblocked:** Rx safety gate server-side; doctor availability + slot booking; teleconsult link; reminder channels (email/SMS/WhatsApp abstraction); patient lab results + billing pages; visit/SOAP notes; receptionist roles; medications view; announcements + settings; admin doctor/visits CRUD endpoints (frontend calls them → 405); global `/api/v1/search` (frontend calls → 404); audit trail for PHI reads; queue/appointment DB constraints; access_service centralization; Keycloak prod realm hardening; CSP re-add (currently removed from BOTH nginx and next.config — regression); design-system primitives; record export (FHIR); seed script; template PATCH endpoint
- **Blocked/external:** ABHA/ABDM (needs sandbox creds), SMS/WhatsApp providers (need accounts), OCR/AI features (need model/provider decision), load testing (needs env), i18n (needs translation assets), barcode lookup (needs data source), push notifications (needs VAPID/push service)

## Apply when Jira creds available

`python3 .claude/jira_cli.py list` → match tickets by summary → `complete <KEY>` for the DONE list above. The CSV has no issue keys — they were assigned at import; match by Summary text.
