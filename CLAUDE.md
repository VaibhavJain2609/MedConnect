# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

# MedConnect - Healthcare Platform

A comprehensive healthcare platform integrating patient management, doctor portals, prescription handling, and ABDM (Ayushman Bharat Digital Mission) integration.

## Project Overview

**Tech Stack:**
- **Backend:** FastAPI (Python 3.12), SQLAlchemy (async), PostgreSQL 16 + pgvector, Redis 7, Alembic migrations
- **Frontend:** Next.js 14 (TypeScript), Tailwind CSS, shadcn/ui, React Query, Zustand
- **Auth:** Keycloak (with auto-provisioning and role-based access)
- **Infrastructure:** Docker Compose, Nginx reverse proxy
- **Project Management:** Jira Cloud

## Key Architecture Patterns

### Dual Database Architecture

The application uses **two separate PostgreSQL databases**:

1. **Main Application DB** (`medconnect`):
   - Users, doctors, patients
   - Medical records, prescriptions
   - Session: `get_db()` → `async_session`
   - Models inherit from `Base`

2. **Medicine Database** (`medconnect_medicines`):
   - Medicine catalog (brands, salts, manufacturers)
   - Drug interactions
   - Session: `get_medicine_db()` → `medicine_async_session`
   - Models inherit from `MedicineBase`

**Important:** Always use the correct database session when working with models. Medicine-related operations must use `get_medicine_db()`.

### Authentication & Authorization

**Keycloak Integration with Auto-Provisioning:**

1. User authenticates with Keycloak
2. Frontend sends JWT token in Authorization header
3. Backend validates token against Keycloak public keys
4. If user doesn't exist locally → **auto-provision** from token claims
5. Role synced from Keycloak `realm_access.roles` on every request

**Role Hierarchy:**
- `admin` → Full system access
- `doctor` → Doctor-specific features (creates Doctor profile automatically)
- `patient` → Patient portal access (default role)

**Dependencies:**
- `get_current_user` → Returns User for any authenticated user
- `get_current_doctor` → Returns (User, Doctor) tuple, requires doctor role
- `require_patient` → Requires patient role
- `require_admin` → Requires admin role

### API Router Organization

Routers in `backend/app/routers/`:
- `auth.py` → Authentication endpoints (`/api/v1/auth/*`)
- `patients.py` → Patient portal endpoints (`/api/v1/patients/*`)
- `doctors.py` → Doctor portal endpoints (`/api/v1/doctors/*`)
- `medicines_emr.py` → Medicine search/lookup (uses medicine DB)
- `interactions.py` → Drug interaction checking (uses medicine DB)
- `admin/` → Admin-only endpoints:
  - `brands.py` → Medicine brand management
  - `manufacturers.py` → Manufacturer management
  - `salts.py` → Salt (active ingredient) management

All admin routes require `require_admin` dependency.

## Jira Integration Workflow

This project uses automated Jira integration for ticket management and implementation.

### Quick Start

```bash
# Work on Jira tickets
/jira

# This will:
# 1. Fetch all TODO tickets from Jira
# 2. Let you select which ticket(s) to implement
# 3. Create a branch for each ticket
# 4. Implement using /workflow
# 5. Link commits back to Jira
# 6. Move tickets to Done when complete
```

### Setup (First Time Only)

1. **Create Jira API Token:**
   - Go to https://id.atlassian.com/manage-profile/security/api-tokens
   - Click "Create API token"
   - Copy the token

2. **Configure Environment:**
   Create `.env` in project root:
   ```bash
   # Jira Configuration
   JIRA_BASE_URL=https://your-domain.atlassian.net
   JIRA_EMAIL=your-email@example.com
   JIRA_API_TOKEN=your-api-token-here
   JIRA_PROJECT_KEY=MED
   ```

3. **Make CLI executable:**
   ```bash
   chmod +x .claude/jira_cli.py
   ```

### Manual Jira CLI Usage

If you need direct control:

```bash
# List all TODO tickets
python3 .claude/jira_cli.py list

# Show ticket details
python3 .claude/jira_cli.py show MED-15

# Start work on a ticket (creates branch, moves to In Progress)
python3 .claude/jira_cli.py start MED-15

# Complete ticket (adds comment, moves to Done)
python3 .claude/jira_cli.py complete MED-15
```

## Development Workflow

### Standard Workflow (with Jira)

```bash
/jira                    # Select and implement Jira tickets
```

### Manual Workflow (without Jira)

```bash
/workflow [feature]      # Research → Plan → Implement → Test → Commit
```

### Step-by-Step Control

```bash
/research [topic]        # Fetch documentation
/plan [feature]          # Create implementation plan
/implement               # Execute the plan with TDD
```

## Common Development Commands

### Backend (Local Development)

```bash
# Setup virtual environment
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "Description"

# Start development server (with hot reload)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
pytest
pytest tests/test_specific.py  # Single test file
pytest -v                      # Verbose output
pytest --cov=app              # With coverage report

# Check health endpoint
curl http://localhost:8000/health
```

### Frontend (Local Development)

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev              # Runs on http://localhost:3000

# Build for production
npm run build

# Start production server
npm start

# Lint code
npm run lint
```

### Docker (Full Stack)

```bash
# Start all services (build if needed)
docker-compose up --build

# Start in detached mode
docker-compose up -d

# View logs
docker-compose logs -f backend    # Backend logs
docker-compose logs -f frontend   # Frontend logs
docker-compose logs -f postgres   # Database logs

# Execute commands in containers
docker-compose exec backend alembic upgrade head
docker-compose exec backend pytest
docker-compose exec postgres psql -U medconnect -d medconnect

# Stop all services
docker-compose down

# Stop and remove volumes (clean slate)
docker-compose down -v

# Restart specific service
docker-compose restart backend
```

### Health Checks

```bash
# Backend health (checks DB + Redis + Medicine DB)
curl http://localhost:8000/health

# API documentation
open http://localhost:8000/docs

# Frontend
open http://localhost:3000

# Keycloak admin console
open http://localhost:8080
# Username: admin
# Password: admin
```

## Project Structure

```
MedConnect/
├── backend/             # Python backend (FastAPI/Flask)
│   ├── app/            # Application code
│   ├── alembic/        # Database migrations
│   ├── tests/          # Test suite
│   └── requirements.txt
├── frontend/            # Frontend application
├── postgres/            # PostgreSQL configuration
├── keycloak/            # Keycloak auth configuration
├── nginx/               # Nginx reverse proxy
├── .claude/             # Claude Code configuration
│   ├── jira_cli.py     # Jira integration CLI
│   └── commands/       # Custom commands
└── docker-compose.yml   # Docker orchestration
```

## Epics Overview

From Jira (imported 2024-02-23):

1. **Medicine Database & Dataset** (Highest Priority)
   - Acquire and load Indian medicine dataset
   - Build search APIs
   - Maintain data quality

2. **Admin Panel - Core Infrastructure** (Highest Priority)
   - Role enforcement
   - Dashboard
   - Audit logging

3. **Admin Panel - Medicine Management** (High Priority)
   - CRUD interface for medicines
   - Bulk import/export

4. **Admin Panel - User Management** (High Priority)
   - User list, activation, role changes

5. **Admin Panel - Doctor Verification** (High Priority)
   - Doctor verification workflow
   - Document upload and review

6. **Prescription Enhancement** (High Priority)
   - Medicine autocomplete
   - Drug interaction warnings
   - PDF generation

7. **Patient Portal Enhancement** (Medium Priority)
   - Profile editing
   - Document upload
   - Vitals tracking

8. **Doctor Portal Enhancement** (Medium Priority)
   - Patient search
   - Appointment management
   - Clinical templates

9. **ABDM Integration** (Medium Priority)
   - ABHA ID integration
   - Health Information Provider/User modules
   - Consent management

## Git Workflow

### Branch Naming

Jira tickets automatically create branches:
- Format: `{ticket-key}-{slugified-summary}`
- Example: `med-15-implement-medicine-autocomplete-api`

### Commit Messages

Always reference Jira tickets:
```
[MED-15] Implement medicine autocomplete API

- Added search endpoint with fuzzy matching
- Implemented caching for performance
- Added unit tests

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

### Push Strategy

- Commits are made locally automatically
- Push to remote manually or when prompted
- Jira tickets are updated with branch/commit info

## Testing

**TDD Enforced:** All implementations use Test-Driven Development

### Backend Tests

```bash
cd backend

# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_patients.py

# Run specific test function
pytest tests/test_patients.py::test_get_timeline

# Run with verbose output
pytest -v

# Run and stop on first failure
pytest -x

# Coverage target: 80%+ required
```

**Test Organization:**
- `tests/` → All backend tests
- Use pytest fixtures for database sessions
- Mock external services (Keycloak, Redis)
- Test both success and error cases

### Frontend Tests

Frontend testing setup TBD (consider Jest + React Testing Library)

## Database

**Type:** PostgreSQL 16 with pgvector extension

### Dual Database Setup

1. **Main Application Database** (`medconnect`)
   - Connection: `DATABASE_URL` / `DATABASE_URL_SYNC`
   - Migrations: Alembic in `backend/alembic/`
   - Models: Inherit from `Base` (in `app.database`)

2. **Medicine Database** (`medconnect_medicines`)
   - Connection: `MEDICINE_DB_URL` / `MEDICINE_DB_URL_SYNC`
   - Separate migrations needed
   - Models: Inherit from `MedicineBase` (in `app.database`)

### Running Migrations

```bash
cd backend

# Upgrade to latest
alembic upgrade head

# Create new migration (auto-detect model changes)
alembic revision --autogenerate -m "Description of changes"

# Downgrade one version
alembic downgrade -1

# View migration history
alembic history

# View current version
alembic current
```

**Important:** Alembic is currently configured for the main database only. Medicine database schema changes may need manual SQL or separate Alembic configuration.

### Direct Database Access

```bash
# Via Docker
docker-compose exec postgres psql -U medconnect -d medconnect
docker-compose exec postgres psql -U medconnect -d medconnect_medicines

# Via local psql (if running Docker)
psql -h localhost -U medconnect -d medconnect
# Password: medconnect
```

## Environment Variables

**Backend** (`.env` in `backend/` or set via docker-compose):

```bash
# Application
APP_ENV=development
DEBUG=true

# Main Database
DATABASE_URL=postgresql+asyncpg://medconnect:medconnect@postgres:5432/medconnect
DATABASE_URL_SYNC=postgresql://medconnect:medconnect@postgres:5432/medconnect

# Medicine Database
MEDICINE_DB_URL=postgresql+asyncpg://medconnect:medconnect@postgres:5432/medconnect_medicines
MEDICINE_DB_URL_SYNC=postgresql://medconnect:medconnect@postgres:5432/medconnect_medicines

# Redis
REDIS_URL=redis://redis:6379/0

# Keycloak
KEYCLOAK_URL=http://keycloak:8080              # Internal URL
KEYCLOAK_PUBLIC_URL=http://localhost:8080      # Public URL for frontend
KEYCLOAK_REALM=medconnect
KEYCLOAK_CLIENT_ID=medconnect-backend

# URLs
BACKEND_URL=http://localhost:8000
FRONTEND_URL=http://localhost:3000

# Optional: Sentry
SENTRY_DSN=

# Jira (for /jira command)
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=your-api-token-here
JIRA_PROJECT_KEY=MED
```

**Frontend** (environment variables in docker-compose or `.env.local`):

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_KEYCLOAK_URL=http://localhost:8080
NEXT_PUBLIC_KEYCLOAK_REALM=medconnect
NEXT_PUBLIC_KEYCLOAK_CLIENT_ID=medconnect-frontend
```

## Implementation Patterns to Follow

### Backend Patterns

**Database Sessions:**
```python
# Main DB - use get_db()
from app.database import get_db

@router.get("/patients/{id}")
async def get_patient(id: str, db: AsyncSession = Depends(get_db)):
    # Work with User, Doctor, MedicalRecord, Prescription models
    pass

# Medicine DB - use get_medicine_db()
from app.database import get_medicine_db

@router.get("/medicines/search")
async def search_medicines(db: AsyncSession = Depends(get_medicine_db)):
    # Work with Medicine, Brand, Salt, Manufacturer models
    pass
```

**Authentication:**
```python
from app.dependencies import get_current_user, get_current_doctor, require_admin

# Any authenticated user
@router.get("/profile")
async def get_profile(user: User = Depends(get_current_user)):
    pass

# Doctor-only endpoint
@router.post("/prescriptions")
async def create_prescription(
    user: User = Depends(get_current_user),
    doctor: Doctor = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db)
):
    # user and doctor are both available
    pass

# Admin-only endpoint
@router.post("/admin/users")
async def manage_users(admin: User = Depends(require_admin)):
    pass
```

**Error Responses:**
```python
# Consistent error format
raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail={
        "error": {
            "code": "NOT_FOUND",
            "message": "Resource not found"
        }
    }
)
```

**Model Conventions:**
- Soft deletes: Use `deleted_at` timestamp (not hard delete)
- All queries should filter `deleted_at.is_(None)`
- UUID primary keys: `id: Mapped[uuid.UUID]`
- Timestamps: `created_at`, `updated_at`, `deleted_at`

### Frontend Patterns

**API Calls:**
```typescript
// Use the centralized API client from lib/api.ts
import { api } from '@/lib/api'

const response = await api.get('/api/v1/patients/timeline')
```

**Authentication:**
```typescript
// Keycloak auth is handled in lib/keycloak.ts
// Protected routes use AuthGuard component
```

**State Management:**
- React Query for server state
- Zustand for client state
- Form state: React Hook Form + Zod validation

## Notes for Claude

**Critical Rules:**
- **Use correct database session** → Main DB vs Medicine DB (see patterns above)
- **Always fetch fresh Jira tickets** before implementation
- **Use TDD** for all implementations (write tests first)
- **Reference Jira tickets** in all commits (`[MED-123] Description`)
- **Verify tests pass** before marking tickets as Done
- **Use Alembic** for any database schema changes (main DB only)
- **Soft deletes** → Never hard delete, use `deleted_at` timestamp
- **Follow existing patterns** → Check similar endpoints/components before implementing

**When working with:**
- **Users/Doctors/Patients** → Use `get_db()` (main database)
- **Medicines/Brands/Salts** → Use `get_medicine_db()` (medicine database)
- **Authentication** → Token auto-provisions users, roles sync from Keycloak
- **Authorization** → Use appropriate dependency (`get_current_user`, `require_admin`, etc.)
- **API errors** → Use consistent error format with `code` and `message`
