# MedConnect - Healthcare Platform

A comprehensive healthcare platform integrating patient management, doctor portals, prescription handling, and ABDM (Ayushman Bharat Digital Mission) integration.

## Project Overview

**Tech Stack:**
- **Backend:** Python (FastAPI/Flask), PostgreSQL, Alembic migrations
- **Frontend:** (to be determined - check frontend/ directory)
- **Infrastructure:** Docker Compose, Nginx, Keycloak (auth)
- **Project Management:** Jira Cloud

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

- **TDD Enforced:** All implementations use Test-Driven Development
- **Coverage Target:** 80%+ coverage required
- **Test Location:** `backend/tests/`

## Database

- **Type:** PostgreSQL
- **Migrations:** Alembic
- **Run migrations:**
  ```bash
  cd backend
  alembic upgrade head
  ```

## Docker Services

```bash
# Start all services
docker-compose up -d

# Check status
docker ps

# View logs
docker-compose logs -f [service-name]

# Restart service
docker-compose restart [service-name]
```

## Environment Variables

See `.env.example` for required variables. Key sections:

- **Database:** PostgreSQL connection
- **Jira:** API credentials and project key
- **Keycloak:** Authentication configuration
- **Backend:** API configuration

## Notes for Claude

- **Always fetch fresh Jira tickets** before implementation
- **Keep ticket state in sync** with actual progress
- **Use TDD** for all implementations
- **Reference Jira tickets** in all commits
- **Verify tests pass** before marking tickets as Done
- **Consider Epic context** when implementing stories
- **Follow existing code patterns** in backend/app/
- **Use Alembic** for any database schema changes
