# MedConnect Documentation Index

**Last Updated:** 2026-03-20
**Project:** MedConnect Healthcare Platform

Index of documentation that actually exists in this repository.

---

## Root

| File | Contents |
|------|----------|
| [`README.md`](../README.md) | Project overview and quick start |
| [`CLAUDE.md`](../CLAUDE.md) | Agent/developer guidance: architecture, routers, commands, Jira workflow |
| [`TODO.md`](../TODO.md) | Open work items (Jira tickets) and recently completed work |
| [`docker-compose.yml`](../docker-compose.yml) | Full-stack services: postgres, redis, keycloak, backend, frontend, nginx |
| [`.env.example`](../.env.example) | Environment variable template |
| [`docs/archive/`](../docs/archive/) | Archived audits, proposals, diagrams, and scratch notes |

## Backend Docs (`backend/docs/`)

| File | Contents |
|------|----------|
| [`API_EMR_MEDICINE.md`](../backend/docs/API_EMR_MEDICINE.md) | API reference for medicine endpoints (search, salts, brands, manufacturers, interactions) |
| [`EMR_IMPLEMENTATION_SUMMARY.md`](../backend/docs/EMR_IMPLEMENTATION_SUMMARY.md) | Medicine database implementation summary (schema, import, models, services) |
| [`medicine_schema_v2.md`](../backend/docs/medicine_schema_v2.md) | Specification of the medicine database tables |

## Frontend Docs (`frontend/`)

| File | Contents |
|------|----------|
| [`README_INTERACTIONS.md`](../frontend/README_INTERACTIONS.md) | Drug interaction/alternatives integration guide (components, hooks, types) |

## Implementation Plans (`implementation_plans/`)

| File | Contents |
|------|----------|
| [`IMPLEMENTATION_MD18_MD19_MD29.md`](IMPLEMENTATION_MD18_MD19_MD29.md) | Drug interactions, alternatives, duplicate prevention |
| [`ImplementationPlan.md`](ImplementationPlan.md) | General implementation plan |
| [`ImplementationPlan_MD76.md`](ImplementationPlan_MD76.md) | MD-76 implementation plan |
| [`MD-72_IMPLEMENTATION_SUMMARY.md`](MD-72_IMPLEMENTATION_SUMMARY.md) | MD-72 summary |
| [`MD-76_IMPLEMENTATION_SUMMARY.md`](MD-76_IMPLEMENTATION_SUMMARY.md) | MD-76 summary |
| [`PLATFORM_IMPROVEMENT_PLAN.md`](PLATFORM_IMPROVEMENT_PLAN.md) | Platform improvement plan |
| [`ResearchPack.md`](ResearchPack.md) / [`ResearchPack_MD76.md`](ResearchPack_MD76.md) | Research notes |
| [`JIRA_SETUP.md`](JIRA_SETUP.md) | Jira integration setup (API token, env config, CLI usage) |
| [`PR_DESCRIPTION.md`](PR_DESCRIPTION.md) / [`QUICK_TEST.md`](QUICK_TEST.md) / [`README.md`](README.md) | Misc notes |

## Jira CLI

[`.claude/jira_cli.py`](../.claude/jira_cli.py):

```bash
python3 .claude/jira_cli.py list              # List TODO tickets
python3 .claude/jira_cli.py show MED-15       # Show ticket details
python3 .claude/jira_cli.py start MED-15      # Start work (branch + In Progress)
python3 .claude/jira_cli.py complete MED-15   # Complete (comment + Done)
```

## Development

See [CLAUDE.md](../CLAUDE.md) for commands. Common:

```bash
docker-compose up --build                              # full stack
docker-compose exec backend alembic upgrade head       # migrations
cd backend && pytest                                   # backend tests
cd frontend && npm run dev                             # frontend dev server
```

Health check: `http://localhost:8000/health` · API docs: `http://localhost:8000/docs`
