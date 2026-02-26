#!/usr/bin/env python3
"""Create Jira tickets for Backend Integration and Testing phases."""

import os
import sys
import json
from pathlib import Path
import requests
from requests.auth import HTTPBasicAuth

# Load .env file
try:
    from dotenv import load_dotenv
    project_root = Path(__file__).parent.parent
    env_path = project_root / '.env'
    load_dotenv(env_path)
except ImportError:
    # Manual .env loading
    project_root = Path(__file__).parent.parent
    env_path = project_root / '.env'
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

JIRA_BASE_URL = os.getenv("JIRA_BASE_URL", "").rstrip("/")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "MD")

if not all([JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN]):
    print("❌ Missing Jira credentials in .env file")
    sys.exit(1)

# Setup auth
auth = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)
headers = {
    "Accept": "application/json",
    "Content-Type": "application/json"
}

def text_to_adf(text):
    """Convert plain text to Atlassian Document Format."""
    paragraphs = []
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        paragraphs.append({
            "type": "paragraph",
            "content": [{
                "type": "text",
                "text": line
            }]
        })

    return {
        "version": 1,
        "type": "doc",
        "content": paragraphs
    }

# Define tickets
tickets = [
    # Backend Integration Tasks
    {
        "summary": "Backend Integration - Authentication & User Management",
        "description": """Connect frontend authentication and user management to backend APIs.

*Tasks:*
• Connect login/logout to /api/v1/auth/login and /api/v1/auth/logout
• Implement token refresh logic
• Connect user profile endpoints (GET/PUT /api/v1/users/me)
• Add photo upload to /api/v1/users/photo
• Implement role-based access control validation
• Add error handling for auth failures
• Store tokens securely (httpOnly cookies or secure storage)

*Files to Modify:*
• frontend/src/lib/auth.ts
• frontend/src/lib/api.ts
• frontend/src/stores/auth-store.ts
• frontend/src/components/profile/photo-upload.tsx

*Backend Endpoints Needed:*
• POST /api/v1/auth/login
• POST /api/v1/auth/logout
• POST /api/v1/auth/refresh
• GET /api/v1/users/me
• PUT /api/v1/users/me
• POST /api/v1/users/photo

*Acceptance Criteria:*
• Login/logout works with real backend
• Token refresh happens automatically
• Profile updates save to database
• Photo upload stores files and returns URLs
• Auth errors display user-friendly messages
""",
        "priority": "Highest",
        "type": "Task",
    },
    {
        "summary": "Backend Integration - Patient & Doctor Data",
        "description": """Connect patient and doctor pages to backend CRUD APIs.

*Tasks:*
• Replace mock data in admin/patients page with real API calls
• Connect admin/doctors page to backend
• Implement patient details page API integration
• Add patient vitals history endpoint
• Connect patient appointments to backend
• Implement pagination for large datasets
• Add loading states and error handling
• Cache data with React Query

*API Endpoints:*
• GET /api/v1/admin/patients (list with pagination)
• GET /api/v1/patients/{id} (patient details)
• GET /api/v1/patients/{id}/vitals (current vitals)
• GET /api/v1/patients/{id}/vitals/history (historical data)
• GET /api/v1/patients/{id}/appointments (appointments list)
• GET /api/v1/admin/doctors (doctors list)
• GET /api/v1/doctors/{id} (doctor details)

*Files to Modify:*
• frontend/src/app/admin/patients/page.tsx
• frontend/src/app/admin/doctors/page.tsx
• frontend/src/app/patient/[id]/page.tsx
• frontend/src/components/patient/vitals-display.tsx
• frontend/src/lib/api.ts

*Acceptance Criteria:*
• All patient/doctor data loads from backend
• Pagination works for large lists
• Loading states display during fetch
• Errors show user-friendly messages
• Data caching reduces unnecessary API calls
""",
        "priority": "Highest",
        "type": "Task",
    },
    {
        "summary": "Backend Integration - Appointments & Visits",
        "description": """Connect appointments, visits, and lab results to backend APIs.

*Tasks:*
• Connect appointments page to /api/v1/admin/appointments
• Implement appointment creation/editing
• Connect visits page to backend
• Integrate lab results API
• Add status update functionality
• Implement real-time appointment updates
• Add calendar view integration

*API Endpoints:*
• GET /api/v1/admin/appointments (with filters)
• POST /api/v1/admin/appointments (create)
• PUT /api/v1/admin/appointments/{id} (update)
• DELETE /api/v1/admin/appointments/{id} (cancel)
• GET /api/v1/admin/visits
• GET /api/v1/admin/lab-results

*Files to Modify:*
• frontend/src/app/admin/appointments/page.tsx
• frontend/src/app/admin/visits/page.tsx
• frontend/src/app/admin/lab-results/page.tsx

*Acceptance Criteria:*
• Appointments load from backend with filters
• Create/edit/cancel appointments works
• Visits and lab results display real data
• Real-time updates via polling or WebSocket
""",
        "priority": "High",
        "type": "Task",
    },
    {
        "summary": "Backend Integration - Global Search & Notifications",
        "description": """Implement backend integration for global search and notifications.

*Tasks:*
• Connect global search to /api/v1/search endpoint
• Implement fuzzy search with PostgreSQL full-text or Elasticsearch
• Add search result ranking/scoring
• Connect notification center to backend
• Implement WebSocket or Server-Sent Events for real-time notifications
• Add notification preferences API
• Implement mark as read/unread functionality

*API Endpoints:*
• GET /api/v1/search?q={query}&type={type} (global search)
• GET /api/v1/notifications (list)
• POST /api/v1/notifications/{id}/read (mark as read)
• POST /api/v1/notifications/read-all (mark all as read)
• WebSocket /ws/notifications (real-time updates)

*Files to Modify:*
• frontend/src/components/ui/global-search.tsx
• frontend/src/components/layout/notification-center.tsx
• frontend/src/lib/api.ts

*Acceptance Criteria:*
• Search returns relevant results from backend
• Search is fast (<500ms response time)
• Notifications load from backend
• Real-time notification updates work
• Mark as read persists to database
""",
        "priority": "High",
        "type": "Task",
    },
    {
        "summary": "Backend Integration - Dashboard Stats & Charts",
        "description": """Connect dashboard statistics and charts to backend APIs.

*Tasks:*
• Replace mock data in admin dashboard with real stats
• Implement date range filtering
• Add export functionality for reports
• Connect sparkline data to backend
• Implement patient statistics chart data
• Add caching for expensive queries

*API Endpoints:*
• GET /api/v1/admin/stats (dashboard metrics)
• GET /api/v1/admin/stats/patient-trends (chart data)
• GET /api/v1/admin/appointment-requests (pending list)
• GET /api/v1/admin/reports/export (CSV/PDF export)

*Files to Modify:*
• frontend/src/app/admin/dashboard/page.tsx
• frontend/src/components/dashboard/stat-card.tsx
• frontend/src/lib/api.ts

*Acceptance Criteria:*
• Dashboard shows real-time statistics
• Date range filtering updates data
• Charts display historical trends
• Export generates downloadable reports
""",
        "priority": "Medium",
        "type": "Task",
    },
    # Testing & Quality Tasks
    {
        "summary": "Testing - Setup Test Infrastructure",
        "description": """Setup comprehensive testing infrastructure for frontend.

*Tasks:*
• Install and configure Jest + React Testing Library
• Setup test utilities (render helpers, mock data factories)
• Configure test coverage reporting (80% target)
• Add MSW (Mock Service Worker) for API mocking
• Setup GitHub Actions for CI/CD testing
• Add pre-commit hooks for running tests
• Create test documentation and guidelines

*Dependencies to Install:*
```bash
npm install --save-dev @testing-library/react @testing-library/jest-dom
npm install --save-dev @testing-library/user-event
npm install --save-dev jest jest-environment-jsdom
npm install --save-dev msw
npm install --save-dev @testing-library/react-hooks
```

*Configuration Files:*
• jest.config.js
• .github/workflows/test.yml
• tests/setup.ts
• tests/utils/test-utils.tsx
• tests/mocks/handlers.ts

*Acceptance Criteria:*
• Jest runs tests successfully
• Test coverage report generates
• CI/CD pipeline runs tests on PR
• Pre-commit hook prevents commits with failing tests
""",
        "priority": "Highest",
        "type": "Task",
    },
    {
        "summary": "Testing - Component Unit Tests",
        "description": """Write comprehensive unit tests for all UI components.

*Components to Test:*
• Avatar component (sizes, fallback, status)
• Badge component (all variants)
• StatCard component (trend display, sparklines)
• ProfileCard component (rendering, links)
• DataTable component (sorting, pagination, search)
• NotificationCenter (mark as read, dropdown)
• GlobalSearch (keyboard shortcuts, search results)
• VitalsDisplay (status colors, trends, charts)
• PhotoUpload (drag-drop, validation, preview)

*Test Coverage:*
• Component rendering
• User interactions (clicks, keyboard)
• Props variations
• Conditional rendering
• Error states
• Accessibility (ARIA labels, keyboard nav)

*Files to Create:*
• frontend/src/components/ui/__tests__/avatar.test.tsx
• frontend/src/components/ui/__tests__/badge.test.tsx
• frontend/src/components/dashboard/__tests__/stat-card.test.tsx
• frontend/src/components/cards/__tests__/profile-card.test.tsx
• frontend/src/components/ui/__tests__/data-table.test.tsx
• ... (one test file per component)

*Acceptance Criteria:*
• 80%+ code coverage for components
• All tests pass
• Edge cases covered (empty data, errors)
• Accessibility tests included
""",
        "priority": "High",
        "type": "Task",
    },
    {
        "summary": "Testing - Page Integration Tests",
        "description": """Write integration tests for all admin pages.

*Pages to Test:*
• Admin Dashboard (stats display, date filtering)
• Patients Page (search, filter, view toggle)
• Patient Details Page (tabs, vitals, appointments)
• Doctors Page (grid view, search, filter)
• Appointments Page (table, status filter)
• Visits Page (table, search)
• Lab Results Page (table, status colors)

*Test Scenarios:*
• Data fetching with React Query
• Loading states display correctly
• Error handling shows messages
• Search/filter functionality
• Pagination works
• View toggle persists to localStorage
• Navigation between pages

*Files to Create:*
• frontend/src/app/admin/__tests__/dashboard.test.tsx
• frontend/src/app/admin/__tests__/patients.test.tsx
• frontend/src/app/patient/__tests__/[id].test.tsx
• ... (integration tests for each page)

*Acceptance Criteria:*
• All pages have integration tests
• API mocking with MSW works
• Tests simulate real user workflows
• 70%+ coverage for page components
""",
        "priority": "High",
        "type": "Task",
    },
    {
        "summary": "Testing - E2E Tests with Playwright",
        "description": """Setup and write end-to-end tests with Playwright.

*Tasks:*
• Install and configure Playwright
• Setup test database seeding
• Write critical user flow tests
• Add visual regression testing
• Configure CI/CD for E2E tests
• Add test reports and screenshots on failure

*Critical Flows to Test:*
• Login → View Dashboard → Logout
• Search patient → View details → View vitals
• Create appointment → Update status → View in list
• Upload photo → Verify display in profile
• Global search (Cmd+K) → Navigate to result
• Notification center → Mark as read

*Configuration:*
• playwright.config.ts
• tests/e2e/auth.spec.ts
• tests/e2e/patients.spec.ts
• tests/e2e/appointments.spec.ts
• tests/e2e/search.spec.ts

*Acceptance Criteria:*
• Playwright runs E2E tests successfully
• Critical flows covered (80% of user journeys)
• Tests run in CI/CD pipeline
• Screenshots captured on failures
• Test execution time < 5 minutes
""",
        "priority": "Medium",
        "type": "Task",
    },
    {
        "summary": "Testing - Accessibility & Performance Audits",
        "description": """Add accessibility tests and performance monitoring.

*Tasks:*
• Install and configure axe-core for accessibility testing
• Run Lighthouse audits on all pages
• Fix accessibility violations (WCAG 2.1 AA compliance)
• Add keyboard navigation tests
• Implement screen reader testing
• Setup performance monitoring (Sentry or similar)
• Add performance budgets to CI/CD

*Accessibility Checks:*
• Color contrast ratios (4.5:1 minimum)
• ARIA labels on interactive elements
• Keyboard navigation for all features
• Focus management in modals
• Alt text on images
• Semantic HTML structure
• Screen reader compatibility

*Performance Targets:*
• Lighthouse Performance Score: 90+
• Lighthouse Accessibility Score: 100
• First Contentful Paint: <1.5s
• Time to Interactive: <3s
• Total Bundle Size: <500KB (gzipped)

*Tools to Use:*
• @axe-core/react
• Lighthouse CI
• React DevTools Profiler
• Webpack Bundle Analyzer

*Acceptance Criteria:*
• No critical accessibility violations
• Lighthouse scores meet targets
• Performance budgets enforced in CI/CD
• Screen reader testing documented
""",
        "priority": "Medium",
        "type": "Task",
    },
]

# Create tickets
print("Creating Jira tickets...")
created_tickets = []

for ticket_data in tickets:
    try:
        payload = {
            "fields": {
                "project": {"key": JIRA_PROJECT_KEY},
                "summary": ticket_data["summary"],
                "description": text_to_adf(ticket_data["description"]),
                "issuetype": {"name": ticket_data["type"]},
                "priority": {"name": ticket_data["priority"]},
            }
        }

        response = requests.post(
            f"{JIRA_BASE_URL}/rest/api/3/issue",
            auth=auth,
            headers=headers,
            data=json.dumps(payload)
        )

        if response.status_code == 201:
            issue_key = response.json()["key"]
            created_tickets.append(issue_key)
            print(f"✅ Created {issue_key}: {ticket_data['summary']}")
        else:
            print(f"❌ Failed to create ticket: {ticket_data['summary']}")
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"❌ Failed to create ticket: {ticket_data['summary']}")
        print(f"   Error: {str(e)}")

print(f"\n🎉 Successfully created {len(created_tickets)} tickets")
print(f"Ticket keys: {', '.join(created_tickets)}")
