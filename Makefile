# MedConnect Makefile — common dev/ops entry points.
#
# Prerequisites:
#   - Docker with the Compose plugin (`docker compose`); docker-compose v1
#     is auto-detected as a fallback.
#   - A filled-in .env at the repo root (cp .env.example .env) — compose
#     interpolates POSTGRES_USER / POSTGRES_PASSWORD / REDIS_PASSWORD /
#     KEYCLOAK_ADMIN* from it.
#   - For test-backend / lint-backend without containers: Python 3.12 +
#     `make backend-install`, and Node 20 + `make frontend-install`.
#
# Layout: `make up` starts the full stack (postgres, redis, keycloak,
# backend, reminder-worker, frontend, nginx) with health-gated ordering.
# See RUNBOOK.md for the ops flow and CLAUDE.md for architecture notes.

SHELL := /bin/bash
.DEFAULT_GOAL := help

# Compose v2 preferred; fall back to docker-compose v1 binary.
COMPOSE := $(shell docker compose version >/dev/null 2>&1 && echo "docker compose" || echo "docker-compose")

# Load .env for DB credentials used by psql/test targets (compose reads the
# file itself; this is only for recipe expansion).
-include .env
POSTGRES_USER ?= medconnect
POSTGRES_PASSWORD ?= medconnect

SERVICE ?=            # set SERVICE=backend (etc.) for per-service logs
PYTEST ?= $(if $(wildcard backend/.venv/bin/pytest),backend/.venv/bin/pytest,pytest)

# Test URLs: conftest defaults point at the in-network `postgres` hostname;
# local runs go through the published port.
TEST_DB_MAIN := postgresql+asyncpg://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@localhost:5432/medconnect_test
TEST_DB_MEDICINE := postgresql+asyncpg://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@localhost:5432/medicine_db_test

.PHONY: help up up-build down down-v restart ps logs health \
        migrate migrate-new migrate-down seed \
        psql psql-medicine redis-cli backup restore-drill \
        test-backend test-frontend lint lint-backend lint-frontend typecheck \
        backend-install frontend-install build clean \
        k8s-render k8s-alerts-staging k8s-alerts-prod

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

# --- stack lifecycle --------------------------------------------------------

up: ## Start the full stack (detached)
	$(COMPOSE) up -d --build

up-build: ## Rebuild images from scratch and start
	$(COMPOSE) up -d --build --force-recreate

down: ## Stop all services (volumes kept)
	$(COMPOSE) down

down-v: ## Stop all services and DELETE volumes (wipes local DBs)
	$(COMPOSE) down -v

restart: ## Restart all services
	$(COMPOSE) restart

ps: ## Show service status
	$(COMPOSE) ps

logs: ## Tail logs — SERVICE=backend|frontend|postgres|redis|keycloak|nginx (default: all)
	$(COMPOSE) logs -f $(SERVICE)

health: ## Curl the backend deep-health endpoint
	@curl -s http://localhost:8000/health | python3 -m json.tool || curl -s http://localhost:8000/health

# --- database ---------------------------------------------------------------

migrate: ## Run both alembic migrations inside the backend container
	$(COMPOSE) exec backend alembic upgrade head
	$(COMPOSE) exec backend alembic -c alembic_medicine.ini upgrade head

migrate-new: ## Autogenerate a new revision — NAME="add foo" required
	@test -n "$(NAME)" || (echo "usage: make migrate-new NAME=\"description\""; exit 1)
	$(COMPOSE) exec backend alembic revision --autogenerate -m "$(NAME)"

migrate-down: ## Roll back the last main-DB migration
	$(COMPOSE) exec backend alembic downgrade -1

seed: ## Seed demo data into the main DB (idempotent; pass ARGS="--drop" to remove it — see docs/seed.md)
	$(COMPOSE) exec backend python scripts/seed_demo_data.py $(ARGS)

psql: ## psql into the medconnect database
	$(COMPOSE) exec postgres psql -U $(POSTGRES_USER) -d medconnect

psql-medicine: ## psql into the medconnect_medicines database
	$(COMPOSE) exec postgres psql -U $(POSTGRES_USER) -d medconnect_medicines

redis-cli: ## redis-cli into the Redis container
	$(COMPOSE) exec redis redis-cli -a $(REDIS_PASSWORD) --no-auth-warning

# --- backup & restore drill --------------------------------------------------
# Both scripts live in backend/scripts/ and drive the compose `postgres`
# service. See docs/backup-restore.md for the full workflow and the
# production RDS path (snapshots — these targets are compose-only).

backup: ## pg_dump both databases to ./backups (ARGS: --out DIR, --latest)
	backend/scripts/backup_db.sh $(ARGS)

restore-drill: ## End-to-end drill: fresh backup → restore into scratch DBs → row-count sanity → drop scratch DBs
	@set -euo pipefail; \
	tmpdir=$$(mktemp -d); \
	trap 'rm -rf "$$tmpdir"' EXIT; \
	echo "== step 1/3: backup both databases into $$tmpdir"; \
	backend/scripts/backup_db.sh --out "$$tmpdir"; \
	echo "== step 2/3: restore each dump into a scratch database + sanity counts"; \
	backend/scripts/restore_db.sh --db restore_drill_medconnect \
	    --file "$$tmpdir"/medconnect_*.dump --recreate --cleanup; \
	backend/scripts/restore_db.sh --db restore_drill_medicines \
	    --file "$$tmpdir"/medconnect_medicines_*.dump --recreate --cleanup; \
	echo "== step 3/3: done — restore drill PASSED (live databases untouched)"

# --- tests & lint -----------------------------------------------------------
# Backend tests need the compose postgres running (init.sql creates the
# medconnect_test + medicine_db_test databases). Redis is faked via
# fakeredis — no live Redis needed for the test suite.

test-backend: ## Run backend pytest locally (needs `make up` postgres + backend-install)
	cd backend && TEST_DATABASE_URL="$(TEST_DB_MAIN)" TEST_MEDICINE_DATABASE_URL="$(TEST_DB_MEDICINE)" $(PYTEST) -v

test-frontend: ## Run frontend jest tests
	cd frontend && npm test

lint: lint-backend lint-frontend ## Lint backend (ruff) + frontend (eslint)

lint-backend: ## ruff check backend/
	cd backend && ruff check .

lint-frontend: ## next lint frontend/
	cd frontend && npm run lint

typecheck: ## tsc --noEmit on the frontend
	cd frontend && npm run typecheck

# --- local toolchain --------------------------------------------------------

backend-install: ## Create backend venv and install runtime + dev deps
	cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt ruff==0.8.4

frontend-install: ## npm ci the frontend
	cd frontend && npm ci

# --- docker images ----------------------------------------------------------

build: ## Build all service images
	$(COMPOSE) build

clean: ## Remove build artifacts (keeps volumes; use down-v for those)
	$(COMPOSE) rm -f
	rm -rf backend/htmlcov backend/.coverage frontend/.next

# --- kubernetes -------------------------------------------------------------

k8s-render: ## Render overlays for inspection (no cluster needed)
	kubectl kustomize infra/k8s/overlays/staging > /dev/null && echo "staging OK"
	kubectl kustomize infra/k8s/overlays/prod > /dev/null && echo "prod OK"

k8s-alerts-staging: ## Apply alert rules to medconnect-staging
	kubectl -n medconnect-staging apply -f infra/k8s/monitoring/alerts.yaml

k8s-alerts-prod: ## Apply alert rules to medconnect-prod
	kubectl -n medconnect-prod apply -f infra/k8s/monitoring/alerts.yaml
