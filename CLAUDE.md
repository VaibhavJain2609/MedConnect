# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commit Convention

**Never** add `Co-Authored-By: Claude` or any Claude/Anthropic authorship lines to commit messages.

---

# MedConnect - Healthcare Platform

A healthcare platform integrating patient management, doctor portals, prescription handling, and ABDM (Ayushman Bharat Digital Mission) integration.

## Tech Stack

- **Backend:** FastAPI (Python 3.12), SQLAlchemy (async), PostgreSQL 16 + pgvector, Redis 7, Alembic migrations
- **Frontend:** Next.js 14 (TypeScript), Tailwind CSS, shadcn/ui, React Query, Zustand
- **Auth:** Keycloak (with auto-provisioning and role-based access)
- **Infrastructure:** Docker Compose, Nginx reverse proxy

## Key Architecture Patterns

### Dual Database Architecture

Two separate PostgreSQL databases:

1. **Main Application DB** (`medconnect`):
   - Users, doctors, patients, medical records, prescriptions, notifications, clinics, appointments, vitals
   - Also contains `Medicine`, `Component`, `MedicineComponent` models (denormalized medicine references used by prescriptions)
   - Session: `get_db()` → `async_session`
   - Models inherit from `Base` (in `app.database`)

2. **Medicine Database** (`medconnect_medicines`):
   - Detailed pharmaceutical catalog: `Salt`, `Brand`, `Manufacturer`, `BrandComposition`, `DrugInteraction`, `SideEffect`, etc.
   - All models live in `backend/app/models/medicine/` subdirectory
   - Session: `get_medicine_db()` → `medicine_async_session`
   - Models inherit from `MedicineBase` (in `app.database`)

**Critical:** `app/models/medicine.py` (the `Medicine` class) uses `Base` (main DB), not `MedicineBase`. The medicine DB models are exclusively in `app/models/medicine/` (subdirectory).

### Authentication & Authorization

**Keycloak auto-provisioning flow:**
1. Frontend sends JWT in Authorization header
2. Backend validates via JWKS; extracts `keycloak_sub` and `realm_access.roles`
3. If user not in local DB → auto-provision (creates User; also creates Doctor profile if role=doctor)
4. Role synced from token on every request (priority: admin > doctor > patient)

**Dependencies** (`app/dependencies.py`):
- `get_current_user` → Returns `User` (any authenticated user); handles auto-provisioning
- `get_current_doctor` → Returns `(User, Doctor)` tuple; requires doctor role
- `get_verified_doctor` → Returns `(User, Doctor)`; requires doctor role + `verified=True` + `onboarding_step="completed"`
- `require_patient` → Requires patient role
- `require_admin` → Requires admin role
- `get_active_clinic` → Reads `X-Clinic-Id` header; verifies `ClinicMembership`; returns `(clinic_id, role) | None`
- `require_active_clinic` → Same as above but raises 400 if header missing (use for clinic-scoped endpoints)

### Clinic Architecture

Clinics have a three-layer hierarchy: `Clinic` → `ClinicBranch` → `ClinicMembership`.

- `ClinicMembership` links a `User` (doctor) to a clinic with role: `owner | admin | doctor`
- `PatientClinicLink` links a patient `User` to a `Clinic` with `consent_status: pending | approved | revoked`
- `PatientLinkCode` is a short-lived code patients share with clinics to initiate the link

Clinic context is passed via the `X-Clinic-Id` request header. Use `get_active_clinic` (optional) or `require_active_clinic` (mandatory) dependency to validate membership. The patient list for doctors is clinic-scoped when this header is present.

### Appointment Model

`Appointment` links `patient_id` (User) + `doctor_id` (Doctor) + optional `clinic_id`/`branch_id`. Status transitions are enforced server-side:

```
scheduled → arrived | cancelled | no-show
arrived   → in-progress | cancelled
in-progress → completed | cancelled
completed / cancelled / no-show → (terminal)
```

### API Router Organization

All active routers in `backend/app/routers/`:

| Router | Prefix | Auth |
|--------|--------|------|
| `auth.py` | `/api/v1/auth` | — |
| `patients.py` | `/api/v1/patients` | `require_patient` |
| `doctors.py` | `/api/v1/doctors` | `get_current_doctor` |
| `notifications.py` | `/api/v1/notifications` | `get_current_user` |
| `clinics.py` | `/api/v1/clinics` | `get_current_user` |
| `onboarding.py` | `/api/v1/onboarding` | `get_current_doctor` |
| `clinic_invites.py` | `/api/v1/clinic-invites` | `get_current_user` |
| `patient_links.py` | `/api/v1/patient-links` | `get_current_user` |
| `appointments.py` | `/api/v1/appointments` | mixed |
| `uploads.py` | `/api/v1/uploads` | `get_current_user` |
| `vitals.py` | `/api/v1/vitals` | `get_current_user` |
| `medicines_emr.py` | `/api/v1` | — |
| `interactions.py` | `/api/v1` | — |
| `admin/brands.py`, `admin/manufacturers.py`, `admin/salts.py` | `/api/v1` | `require_admin` |
| `admin/stats.py`, `admin/users.py`, `admin/clinics.py`, `admin/doctors.py`, `admin/audit.py`, `admin/lab_results.py` | (own prefixes) | `require_admin` |

**Commented out in `main.py`** (missing service modules): `admin/medicines.py`, `admin/components.py`.

### Doctor Onboarding Flow

`Doctor.onboarding_step` tracks progress: `pending → ...  → completed`. `Doctor.verified` is set by admin. Use `get_verified_doctor` dependency for endpoints that require a fully onboarded doctor.

### Frontend Portal Structure

Three portals, each with its own layout (AuthGuard + sidebar):

| Portal | Layout Component | Auth | Route |
|--------|-----------------|------|-------|
| Admin | `components/admin/admin-layout.tsx` | `AuthGuard("admin")` | `/admin/*` |
| Doctor | `components/layout/doctor-layout.tsx` | `AuthGuard("doctor")` | `/doctor/*` |
| Patient | `components/layout/patient-layout.tsx` | `AuthGuard("patient")` | `/patient/*` |

**Admin routes:** `/admin/dashboard`, `/admin/patients`, `/admin/doctors`, `/admin/doctors/[id]`, `/admin/doctors/pending`, `/admin/appointments`, `/admin/visits`, `/admin/lab-results`, `/admin/medicines`, `/admin/salts`, `/admin/manufacturers`, `/admin/clinics`, `/admin/clinics/[id]`, `/admin/users`, `/admin/users/[id]`, `/admin/audit-logs`, `/admin/notifications`, `/admin/settings`

**Doctor routes:** `/doctor/dashboard`, `/doctor/prescriptions`, `/doctor/prescriptions/new`, `/doctor/prescriptions/[id]`, `/doctor/records/new`, `/doctor/patients`, `/doctor/patients/[id]`, `/doctor/patients/[id]/prescriptions`, `/doctor/appointments`, `/doctor/clinic`, `/doctor/clinic/invites`, `/doctor/onboarding`

**Patient routes:** `/patient/timeline`, `/patient/records`, `/patient/records/[id]`, `/patient/records/new`, `/patient/appointments`, `/patient/vitals`, `/patient/profile`, `/patient/medical-history`, `/patient/clinics`

**Page convention:** Pages no longer wrap in `<AuthGuard>` or `<Navbar>` — the route `layout.tsx` handles that. Pages return `<div className="space-y-6">` with content only.

### Frontend Key Files

- `src/lib/api.ts` — Axios instance with auto-token refresh interceptor
- `src/lib/api/` — Typed API sub-modules: `users.ts`, `admin-users.ts`, `patients.ts`, `doctors.ts`, `medicines.ts`, `medicines-emr.ts`, `prescriptions.ts`, `notifications.ts`, `appointments.ts`, `clinics.ts`, `vitals.ts`, `visits.ts`, `lab-results.ts`, `stats.ts`, `search.ts`
- `src/lib/auth.ts` — `initKeycloak()`, `loginRedirect()`, `signupRedirect()`, `logout()`, `getMe()`
- `src/stores/auth-store.ts` — Zustand store with `useAuthStore`; `initAuth()` initializes Keycloak and fetches user
- `src/components/layout/auth-guard.tsx` — Wraps protected portals; checks role

### Design System (Dreams EMR)

Tailwind custom classes defined in `frontend/tailwind.config.ts`:

```
bg-dreams-darkSidebar   (#1A1D1F) — sidebar background
bg-dreams-lightBg       (#F5F7FA) — page background
border-dreams-border    (#E5E7EB) — standard border
text-dreams-textPrimary (#1A1D1F) — primary text
text-dreams-textSecondary (#6B7280) — secondary text
text-dreams-blue / bg-dreams-blue (#4169E1) — primary accent
```

Status colors: `status-inProgress`, `status-completed`, `status-pending`, `status-overdue`, `status-upcoming`.

### Model Conventions

- Soft deletes: `deleted_at` timestamp — **never hard delete**
- All queries must filter `deleted_at.is_(None)`
- UUID primary keys; timestamps: `created_at`, `updated_at`, `deleted_at`
- Prescriptions store medicine list as JSONB in `medicines` column

## Development Commands

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Migrations — always run via docker-compose (not local venv)
docker-compose exec backend alembic upgrade head
docker-compose exec backend alembic revision --autogenerate -m "Description"
docker-compose exec backend alembic downgrade -1

# Tests
pytest                                             # all tests
pytest tests/test_auth.py                          # single file
pytest tests/test_auth.py::test_function_name      # single test
pytest -v --cov=app                                # verbose + coverage
```

### Frontend

```bash
cd frontend
npm install
npm run dev      # http://localhost:3000
npm run build
npm run lint
```

### Docker (Full Stack)

```bash
docker-compose up --build         # start all services
docker-compose up -d              # detached
docker-compose logs -f backend
docker-compose down -v            # remove volumes (clean slate)
docker-compose exec backend alembic upgrade head
docker-compose exec postgres psql -U medconnect -d medconnect
docker-compose exec postgres psql -U medconnect -d medconnect_medicines
```

### Health Checks

```bash
curl http://localhost:8000/health   # checks main DB + medicine DB + Redis
# API docs: http://localhost:8000/docs
# Keycloak admin: http://localhost:8080 (admin/admin)
```

## Testing Infrastructure

Tests use separate test databases (see `conftest.py`):
- Main: `medconnect_test` on port 5432
- Medicine: `medicine_db_test` on port 5433

**Key fixtures** (`tests/conftest.py`):
- `db` / `medicine_db` — Per-test async sessions (creates/drops schema each test)
- `client` — Unauthenticated `AsyncClient` with both DB overrides and mocked JWKS
- `admin_client` / `patient_client` — Pre-authenticated clients
- `admin_user` / `patient_user` — Pre-created User fixtures
- `sample_manufacturer` / `sample_salt` / `sample_brand` — Medicine DB fixtures
- `create_test_token(sub, email, name, roles)` — Creates signed JWT mimicking Keycloak

JWKS validation is mocked via `patch("app.utils.security.get_jwks_client", ...)` — no real Keycloak needed for tests.

## Implementation Patterns

### Backend

```python
# Correct DB session selection
from app.database import get_db, get_medicine_db

# Main DB (users, doctors, prescriptions, records, Medicine model)
async def endpoint(db: AsyncSession = Depends(get_db)): ...

# Medicine DB (Salt, Brand, Manufacturer, DrugInteraction, etc.)
async def endpoint(db: AsyncSession = Depends(get_medicine_db)): ...

# Auth dependencies
from app.dependencies import (
    get_current_user, get_current_doctor, get_verified_doctor,
    require_admin, require_patient,
    get_active_clinic, require_active_clinic,
)

# Clinic-scoped endpoint (optional clinic context)
async def endpoint(clinic_ctx = Depends(get_active_clinic)): ...
# clinic_ctx is (clinic_id, role) | None

# Clinic-scoped endpoint (clinic required)
async def endpoint(clinic_ctx: tuple = Depends(require_active_clinic)): ...

# Error format (consistent across all endpoints)
raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail={"error": {"code": "NOT_FOUND", "message": "Resource not found"}}
)
```

### Frontend

```typescript
// API calls — use lib/api.ts axios instance (auto-attaches Bearer token)
import api from '@/lib/api'
const response = await api.get('/api/v1/patients/timeline')

// Or use typed sub-modules
import { getPatientTimeline } from '@/lib/api/patients'

// Auth state
import { useAuthStore } from '@/stores/auth-store'
const { user } = useAuthStore()
```

**State management:** React Query for server state, Zustand for client state, React Hook Form + Zod for forms.

## Jira Integration

```bash
/jira   # Fetch TODO tickets, select, create branch, implement, link commits, move to Done

# Manual CLI
python3 .claude/jira_cli.py list
python3 .claude/jira_cli.py show MED-15
python3 .claude/jira_cli.py start MED-15
python3 .claude/jira_cli.py complete MED-15
```

> **Important:** The Jira CLI (`jira_cli.py`) does **not** support ticket creation. Always use the Jira REST API directly to create tickets.

**Commit format:** `[MED-15] Description` (always reference ticket).
**Branch format:** `med-15-slugified-summary`

Requires `.env` in project root with `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_PROJECT_KEY=MED`.

## Preferred Development Workflow

Follow this sequence for any new feature or significant change:

### 1. Planning Mode
Start by entering plan mode to explore the codebase and design an approach before touching any code.

### 2. Research & Ticket Creation
Run `/workflow <feature>` to conduct in-depth research (docs, patterns, API accuracy) and generate a quality-gated implementation plan. Use `/jira` to create Jira tickets from the plan — one ticket per logical unit of work — so each piece of implementation is tracked.

### 3. Implementation
Run `/jira` to pull the TODO tickets, select one, create the branch, implement, link commits, and move the ticket to Done. Repeat per ticket until the feature is complete.

### 4. Parallel Task Execution (Multiple Tasks)
When implementing multiple independent tasks simultaneously, **always run them in parallel** using the Agent tool with multiple simultaneous subagent calls in a single message. Do not implement tasks sequentially when they can be parallelized.

After all parallel tasks complete, **create a new verification task** to:
- Check for compilation errors (`npm run build` for frontend, `python -m py_compile` or import checks for backend)
- Validate that all changes are consistent and non-conflicting
- Catch any type errors, missing imports, or broken references introduced across the parallel changes

```
Planning Mode → /workflow (research + plan) → /jira (create tickets) → implement all tasks in parallel → verification task (compile + error check)
```

## Environment Variables

**Backend** (`.env` in `backend/`):

```bash
APP_ENV=development
DATABASE_URL=postgresql+asyncpg://medconnect:medconnect@postgres:5432/medconnect
DATABASE_URL_SYNC=postgresql://medconnect:medconnect@postgres:5432/medconnect
MEDICINE_DB_URL=postgresql+asyncpg://medconnect:medconnect@postgres:5432/medconnect_medicines
MEDICINE_DB_URL_SYNC=postgresql://medconnect:medconnect@postgres:5432/medconnect_medicines
REDIS_URL=redis://redis:6379/0
KEYCLOAK_URL=http://keycloak:8080
KEYCLOAK_PUBLIC_URL=http://localhost:8080
KEYCLOAK_REALM=medconnect
KEYCLOAK_CLIENT_ID=medconnect-backend
BACKEND_URL=http://localhost:8000
FRONTEND_URL=http://localhost:3000
SENTRY_DSN=   # optional
```

**Frontend** (`.env.local` or docker-compose):

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_KEYCLOAK_URL=http://localhost:8080
NEXT_PUBLIC_KEYCLOAK_REALM=medconnect
NEXT_PUBLIC_KEYCLOAK_CLIENT_ID=medconnect-frontend
```
