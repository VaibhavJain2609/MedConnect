# MedConnect — Healthcare Platform

A healthcare platform integrating patient management, doctor portals, prescription handling, and ABDM (Ayushman Bharat Digital Mission) integration.

## Tech Stack

- **Backend:** FastAPI (Python 3.12), SQLAlchemy (async), PostgreSQL 16 + pgvector, Redis 7, Alembic migrations — `backend/`
- **Frontend:** Next.js 14 (TypeScript), Tailwind CSS, shadcn/ui, React Query, Zustand — `frontend/`
- **Auth:** Keycloak (auto-provisioning + role-based access: admin / doctor / patient)
- **Infrastructure:** Docker Compose, Nginx reverse proxy

## Quick Start

```bash
docker-compose up --build        # start the full stack
# Frontend: http://localhost:3000
# Backend API + docs: http://localhost:8000/docs
# Keycloak admin: http://localhost:8080 (admin/admin)
```

Two PostgreSQL databases are used: `medconnect` (app data) and `medconnect_medicines` (pharmaceutical catalog). Run migrations via `docker-compose exec backend alembic upgrade head`.

## Documentation

- **[CLAUDE.md](CLAUDE.md)** — agent/developer guidance: architecture patterns, router/route inventory, dev commands, testing, Jira workflow
- [TODO.md](TODO.md) — open work items tracked as Jira tickets
- [implementation_plans/DOCUMENTATION_INDEX.md](implementation_plans/DOCUMENTATION_INDEX.md) — index of design docs and plans
- [docs/archive/](docs/archive/) — archived audits, proposals, and diagrams
