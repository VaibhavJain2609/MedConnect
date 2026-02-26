# MedConnect Documentation Index

**Version:** 1.0
**Last Updated:** 2026-02-25
**Project:** MedConnect Healthcare Platform

---

## Quick Navigation

📋 **Core Documents**
- [Software Requirements Specification (SRS)](#1-software-requirements-specification-srs)
- [Technical Architecture](#2-technical-architecture)
- [Testing Strategy](#3-testing-strategy)

📚 **Reference Documents**
- [Medicine Database Schema](#4-medicine-database-schema)
- [API Documentation](#5-api-documentation)
- [Implementation Guides](#6-implementation-guides)

🔧 **Development Guides**
- [Project Setup](#7-project-setup)
- [Jira Integration](#8-jira-integration)
- [Deployment Guide](#9-deployment-guide)

---

## 1. Software Requirements Specification (SRS)

**File:** [`SRS_MEDCONNECT.md`](./SRS_MEDCONNECT.md)

**Purpose:** Comprehensive specification of all functional and non-functional requirements

**Sections:**
1. Introduction
   - Purpose, scope, definitions
   - Product overview
2. System Architecture
   - High-level architecture
   - Technology stack
3. Functional Requirements
   - User Management (FR-AUTH-001 to FR-USER-001)
   - Medical Records (FR-RECORD-001 to FR-RECORD-003)
   - Prescription Management (FR-PRESCRIPTION-001 to FR-PRESCRIPTION-005)
   - Medicine Database (FR-MEDICINE-001 to FR-MEDICINE-002)
   - Admin Functions (FR-ADMIN-001 to FR-ADMIN-002)
   - Doctor Portal (FR-DOCTOR-001 to FR-DOCTOR-005)
   - Patient Portal (FR-PATIENT-001 to FR-PATIENT-004)
4. Non-Functional Requirements
   - Performance (NFR-PERF-001 to NFR-PERF-004)
   - Scalability (NFR-SCALE-001 to NFR-SCALE-003)
   - Security (NFR-SEC-001 to NFR-SEC-006)
   - Compliance (NFR-COMP-001 to NFR-COMP-004)
5. Database Schema
6. API Specifications
7. Integration Requirements (ABDM, Keycloak, etc.)
8. Future Enhancements

**Use When:**
- Planning new features
- Understanding system requirements
- Communicating with stakeholders
- Estimating development effort

---

## 2. Technical Architecture

**File:** [`TECHNICAL_ARCHITECTURE.md`](./TECHNICAL_ARCHITECTURE.md)

**Purpose:** Deep dive into system architecture, design patterns, and technical decisions

**Sections:**
1. System Overview
   - Architecture style (three-tier layered)
   - Architectural principles (SOLID, DRY, etc.)
   - Design patterns (Repository, DI, Factory, etc.)
2. Architecture Diagrams
   - High-level system architecture
   - Backend component architecture
   - Frontend component architecture
   - Database architecture
3. Component Design
   - Authentication flow
   - Prescription creation flow
   - Medicine search flow (with caching)
4. Data Flow
   - Patient timeline request
   - Create prescription workflow
   - Medicine autocomplete
5. Technology Stack Deep Dive
   - FastAPI configuration
   - SQLAlchemy pooling
   - Next.js routing
   - TanStack Query caching
6. Infrastructure Architecture
   - Docker Compose setup
   - Production deployment
   - Scaling strategy
7. Security Architecture
   - Defense in depth layers
   - Security headers
   - JWT token structure
8. Scalability and Performance
   - Database optimization
   - Caching strategy
   - Performance targets
9. Deployment Architecture
   - CI/CD pipeline
   - Database migration strategy
   - Zero-downtime deployment
10. Monitoring and Observability
    - Metrics, logs, traces
    - Sentry integration
    - Health checks

**Use When:**
- Onboarding new developers
- Making architectural decisions
- Optimizing performance
- Troubleshooting production issues
- Planning infrastructure changes

---

## 3. Testing Strategy

**File:** [`TESTING_STRATEGY.md`](./TESTING_STRATEGY.md)

**Purpose:** Comprehensive testing approach, frameworks, and best practices

**Sections:**
1. Testing Philosophy
   - Core principles (TDD, confidence over coverage)
   - Testing goals (80% coverage, regression prevention)
2. Testing Pyramid
   - Unit tests (70%)
   - Integration tests (20%)
   - E2E tests (10%)
3. Backend Testing
   - pytest framework
   - Unit test examples (security, FHIR)
   - Integration test examples (auth, prescriptions, interactions)
   - Fixtures and factories
4. Frontend Testing
   - Vitest + React Testing Library
   - Component testing
   - Custom hook testing
   - MSW for API mocking
5. Integration Testing
   - API + Database integration
   - Medicine search with cache
6. End-to-End Testing
   - Playwright setup
   - Authentication flow
   - Prescription creation workflow
7. Performance Testing
   - Locust load testing
   - Database performance testing
8. Security Testing
   - Dependency scanning
   - SAST (Bandit, ESLint)
   - Security test cases
9. Test Data Management
   - Test database setup
   - Seed data
   - Cleanup strategies
10. CI/CD Integration
    - GitHub Actions workflow
    - Pre-commit hooks
11. Test Metrics and Coverage
    - Coverage goals (80% overall)
    - Quality gates

**Use When:**
- Writing new tests
- Setting up test infrastructure
- Running test suites
- Reviewing test coverage
- Planning QA strategy

---

## 4. Medicine Database Schema

**File:** [`backend/docs/medicine_schema_v2.md`](./backend/docs/medicine_schema_v2.md)

**Purpose:** Complete specification of the 21-table medicine database

**Key Tables:**
- **Core Pharmaceutical:** salts (1,532), salt_strengths (5,984)
- **Commercial:** brands (250,797), manufacturers (7,648), brand_compositions (331,442)
- **Clinical Safety:** drug_interactions, contraindications, side_effects
- **Classifications:** chemical_classes, therapeutic_classes, action_classes
- **Indications:** uses, salt_uses
- **Others:** dosing_guidelines, prescription_audit

**Use When:**
- Understanding medicine data structure
- Writing database queries
- Creating migrations
- Importing medicine data
- Building medicine-related features

---

## 5. API Documentation

### 5.1 EMR Medicine API

**File:** [`backend/docs/API_EMR_MEDICINE.md`](./backend/docs/API_EMR_MEDICINE.md)

**Purpose:** Complete API reference for medicine endpoints

**Endpoints:**
- Medicine search
- Salt endpoints (list, details, strengths, brands)
- Brand endpoints (list, details, alternatives)
- Manufacturer endpoints
- Drug interaction checking

**Use When:**
- Integrating frontend with backend
- Building API clients
- Understanding endpoint parameters
- Testing APIs manually

### 5.2 Interactive API Docs

**URL:** `http://localhost:8000/docs` (Swagger UI)

**Alternative:** `http://localhost:8000/redoc` (ReDoc)

**Use When:**
- Testing APIs interactively
- Generating API clients
- Exploring available endpoints

---

## 6. Implementation Guides

### 6.1 EMR Implementation Summary

**File:** [`backend/docs/EMR_IMPLEMENTATION_SUMMARY.md`](./backend/docs/EMR_IMPLEMENTATION_SUMMARY.md)

**Purpose:** Summary of medicine database implementation

**Contents:**
- Completed work (schema, migration, import, models, services, APIs)
- Database statistics (1.5K salts, 250K brands, 7.6K manufacturers)
- Doctor workflow examples
- API testing examples
- Before/after comparison
- File structure

**Use When:**
- Understanding medicine system evolution
- Onboarding to medicine features
- Reference for similar implementations

### 6.2 Drug Interactions & Alternatives

**File:** [`frontend/README_INTERACTIONS.md`](./frontend/README_INTERACTIONS.md)

**Purpose:** Frontend integration guide for MD-18, MD-19

**Contents:**
- Quick start guide
- API reference
- Components (DrugInteractionWarning, AlternativeMedicines)
- Hooks (useDrugInteractions)
- Integration patterns
- TypeScript types
- Styling guide
- Error handling

**Use When:**
- Implementing prescription forms
- Adding drug interaction checks
- Suggesting alternative medicines
- Building medicine selection UI

### 6.3 Implementation Guides (Specific Features)

**File:** [`IMPLEMENTATION_MD18_MD19_MD29.md`](./IMPLEMENTATION_MD18_MD19_MD29.md)

**Purpose:** Detailed implementation for drug interactions, alternatives, duplicate prevention

**Use When:**
- Implementing specific Jira tickets
- Understanding feature requirements
- Reviewing implementation approach

---

## 7. Project Setup

### 7.1 Main README

**File:** [`README.md`](./README.md)

**Purpose:** Quick start guide for developers

**Contents:**
- Project overview
- Quick start (Docker Compose)
- Architecture summary
- Project structure
- Development setup (without Docker)
- API endpoints summary

**Use When:**
- First time setup
- Running the project locally
- Understanding project structure

### 7.2 Project Configuration

**File:** [`CLAUDE.md`](./CLAUDE.md)

**Purpose:** Project-specific configuration for Claude Code

**Contents:**
- Project overview
- Jira integration workflow
- Development workflow (/jira, /workflow commands)
- Project structure
- Epics overview
- Git workflow
- Testing requirements
- Environment variables

**Use When:**
- Understanding project workflows
- Using Jira integration
- Setting up CI/CD
- Understanding Git conventions

---

## 8. Jira Integration

### 8.1 Jira Setup Guide

**File:** [`JIRA_SETUP.md`](./JIRA_SETUP.md)

**Purpose:** Setup instructions for Jira integration

**Contents:**
- API token creation
- Environment configuration
- CLI usage
- Workflow examples

**Use When:**
- Setting up Jira integration for first time
- Troubleshooting Jira connection
- Understanding Jira workflow

### 8.2 Jira CLI

**File:** [`.claude/jira_cli.py`](./.claude/jira_cli.py)

**Commands:**
```bash
# List TODO tickets
python3 .claude/jira_cli.py list

# Show ticket details
python3 .claude/jira_cli.py show MED-15

# Start work (creates branch, moves to In Progress)
python3 .claude/jira_cli.py start MED-15

# Complete ticket (adds comment, moves to Done)
python3 .claude/jira_cli.py complete MED-15
```

**Use When:**
- Working on Jira tickets manually
- Debugging Jira integration
- Automating ticket workflows

---

## 9. Deployment Guide

### 9.1 Docker Compose

**File:** [`docker-compose.yml`](./docker-compose.yml)

**Services:**
- PostgreSQL (main database)
- Redis (cache)
- Keycloak (authentication)
- Backend (FastAPI)
- Frontend (Next.js)
- Nginx (reverse proxy)

**Commands:**
```bash
# Start all services
docker-compose up --build

# Start in background
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f [service-name]

# Restart service
docker-compose restart [service-name]
```

### 9.2 Database Migrations

**Alembic Commands:**
```bash
# Main database
cd backend
alembic upgrade head              # Apply all migrations
alembic downgrade -1              # Rollback one migration
alembic revision --autogenerate -m "description"  # Create migration

# Medicine database
alembic -c alembic_medicine.ini upgrade head
```

### 9.3 Environment Variables

**File:** `.env.example`

**Required Variables:**
```bash
# Database
DATABASE_URL=postgresql+asyncpg://medconnect:password@localhost/medconnect
MEDICINE_DATABASE_URL=postgresql+asyncpg://medconnect:password@localhost/medconnect_emr

# Redis
REDIS_URL=redis://localhost:6379/0

# Jira
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=your-api-token
JIRA_PROJECT_KEY=MED

# Keycloak
KEYCLOAK_URL=http://localhost:8080
KEYCLOAK_REALM=medconnect
KEYCLOAK_CLIENT_ID=medconnect-backend

# Sentry
SENTRY_DSN=your-sentry-dsn
```

---

## 10. Quick Reference

### 10.1 Development Workflow

**Standard Workflow (with Jira):**
```bash
/jira                    # Select and implement Jira tickets
```

**Manual Workflow:**
```bash
/research [topic]        # Fetch documentation
/plan [feature]          # Create implementation plan
/implement               # Execute the plan with TDD
```

**Step-by-Step:**
```bash
/workflow [feature]      # Research → Plan → Implement → Test → Commit
```

### 10.2 Common Commands

**Backend:**
```bash
# Run backend
cd backend
uvicorn app.main:app --reload

# Run tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Lint
black app/
flake8 app/
```

**Frontend:**
```bash
# Run frontend
cd frontend
npm run dev

# Run tests
npm test

# Run tests with coverage
npm run test:coverage

# Lint
npm run lint

# Type check
npm run type-check
```

### 10.3 Useful URLs

**Development:**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs (Swagger): http://localhost:8000/docs
- API Docs (ReDoc): http://localhost:8000/redoc
- Health Check: http://localhost:8000/health
- Keycloak: http://localhost:8080

**Production:**
- Frontend: https://medconnect.in
- Backend API: https://api.medconnect.in

---

## 11. Troubleshooting

### 11.1 Common Issues

**Database Connection Failed:**
```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# Check connection string in .env
echo $DATABASE_URL

# Reset database
docker-compose down -v
docker-compose up -d postgres
alembic upgrade head
```

**Redis Connection Failed:**
```bash
# Check if Redis is running
docker ps | grep redis

# Test Redis connection
redis-cli -h localhost -p 6379 ping
```

**Frontend Build Errors:**
```bash
# Clear node_modules and reinstall
rm -rf node_modules package-lock.json
npm install

# Clear Next.js cache
rm -rf .next
npm run dev
```

**Backend Import Errors:**
```bash
# Rebuild virtual environment
cd backend
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 11.2 Debug Mode

**Backend Debug:**
```python
# Add to app/main.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Frontend Debug:**
```bash
# Run with debug logging
DEBUG=* npm run dev
```

---

## 12. Contributing

### 12.1 Code Style

**Python:**
- Use Black for formatting
- Follow PEP 8
- Type hints required
- Docstrings for public methods

**TypeScript:**
- Use ESLint + Prettier
- Follow Airbnb style guide
- Type everything (no `any`)
- JSDoc comments for complex functions

### 12.2 Git Conventions

**Branch Naming:**
```
{ticket-key}-{slugified-summary}
Example: med-15-implement-medicine-autocomplete-api
```

**Commit Messages:**
```
[MED-15] Implement medicine autocomplete API

- Added search endpoint with fuzzy matching
- Implemented caching for performance
- Added unit tests

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

### 12.3 Pull Request Process

1. Create feature branch from `main`
2. Implement feature with tests (TDD)
3. Ensure all tests pass
4. Run linters and fix issues
5. Push to remote
6. Create PR with description
7. Link Jira ticket
8. Request code review
9. Address review comments
10. Merge after approval

---

## 13. Support and Resources

### 13.1 Internal Resources

- **Jira Board:** https://your-domain.atlassian.net/browse/MED
- **Slack Channel:** #medconnect-dev
- **Team Wiki:** (URL to be added)

### 13.2 External Resources

**ABDM:**
- Documentation: https://abdm.gov.in
- Sandbox: https://sandbox.abdm.gov.in

**FHIR:**
- FHIR R4 Spec: https://hl7.org/fhir/R4/
- FHIR Validator: https://validator.fhir.org/

**Technologies:**
- FastAPI: https://fastapi.tiangolo.com
- Next.js: https://nextjs.org/docs
- PostgreSQL: https://www.postgresql.org/docs/
- SQLAlchemy: https://docs.sqlalchemy.org/

### 13.3 Contact

**Development Team:**
- Technical Lead: (to be added)
- Backend Team: (to be added)
- Frontend Team: (to be added)
- QA Team: (to be added)

---

## 14. Document Update History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2026-02-25 | Initial comprehensive documentation | MedConnect Team |

---

## 15. Next Steps for Documentation

**Planned Documents:**
- [ ] User Manual (Patient Portal)
- [ ] User Manual (Doctor Portal)
- [ ] Admin Guide
- [ ] Deployment Runbook (Production)
- [ ] Disaster Recovery Plan
- [ ] Security Audit Report
- [ ] Performance Optimization Guide
- [ ] ABDM Integration Guide

---

**This index is maintained by the MedConnect Development Team**
**For questions or updates, please contact the team**
