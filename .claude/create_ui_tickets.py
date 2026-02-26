#!/usr/bin/env python3
"""
Create Jira tickets for Dreams EMR UI Transformation
"""

import os
import sys
import requests
from requests.auth import HTTPBasicAuth
from pathlib import Path

# Load .env
try:
    from dotenv import load_dotenv
    project_root = Path(__file__).parent.parent
    load_dotenv(project_root / '.env')
except ImportError:
    project_root = Path(__file__).parent.parent
    env_path = project_root / '.env'
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

BASE_URL = os.getenv('JIRA_BASE_URL', '').rstrip('/')
EMAIL = os.getenv('JIRA_EMAIL')
API_TOKEN = os.getenv('JIRA_API_TOKEN')
PROJECT_KEY = os.getenv('JIRA_PROJECT_KEY', 'MED')

if not all([BASE_URL, EMAIL, API_TOKEN]):
    print("ERROR: Missing Jira credentials")
    sys.exit(1)

auth = HTTPBasicAuth(EMAIL, API_TOKEN)
headers = {
    "Accept": "application/json",
    "Content-Type": "application/json"
}

tickets = [
    {
        "summary": "Dreams EMR UI - Phase 1: Design System Foundation",
        "description": """Establish Dreams EMR color palette, typography, and design tokens.

*Completed Tasks:*
• Updated tailwind.config.ts with Dreams colors (royal blue #4169E1, dark sidebar #1A1D1F)
• Updated globals.css with CSS variables
• Added dependencies: recharts, @tanstack/react-table
• Created test page at /test-design-system

*Files Modified:*
• frontend/tailwind.config.ts
• frontend/src/app/globals.css
• frontend/package.json
• frontend/src/app/test-design-system/page.tsx (test page)

*Status:* ✅ Complete""",
        "labels": ["dreams-emr-ui", "phase-1", "design-system"]
    },
    {
        "summary": "Dreams EMR UI - Phase 2: Core Component Library",
        "description": """Create reusable components matching Dreams EMR patterns.

*Components Created:*
• Avatar component (circular, fallback initials, sizes, status indicator)
• Enhanced Badge component (status variants: inProgress, completed, pending, overdue, upcoming)
• StatCard component (icon, metric, trend, sparkline)
• Sparkline chart component (recharts)
• ProfileCard component (large avatar, info grid, status)
• Rich DataTable component (sortable, avatars, badges, pagination)
• Icon sets: vital-icons, meal-icons, department-icons

*Files Created:*
• frontend/src/components/ui/avatar.tsx
• frontend/src/components/ui/badge.tsx (extended)
• frontend/src/components/ui/data-table.tsx
• frontend/src/components/dashboard/stat-card.tsx
• frontend/src/components/charts/sparkline.tsx
• frontend/src/components/cards/profile-card.tsx
• frontend/src/components/icons/vital-icons.tsx
• frontend/src/components/icons/meal-icons.tsx
• frontend/src/components/icons/department-icons.tsx

*Status:* ✅ Complete""",
        "labels": ["dreams-emr-ui", "phase-2", "components"]
    },
    {
        "summary": "Dreams EMR UI - Phase 3: Navigation & Layout",
        "description": """Implement Dreams EMR navigation structure with dark sidebar and enhanced top bar.

*Tasks:*
• Update admin-sidebar.tsx (dark theme #1A1D1F, grouped sections, icons, expandable menus)
• Update navbar.tsx (global search, utility icons, user dropdown)
• Create breadcrumb.tsx component
• Create view-toggle.tsx component (grid/table/list views)
• Mobile responsive sidebar (full-width overlay)

*Navigation Structure:*
MAIN: Dashboard, Applications, Layouts
HEALTH CARE: Patients, Doctors, Appointments, Visits, Laboratory, Pharmacy
MANAGEMENT: Staffs, Notifications, Settings
PAGES: Authentication, Error Pages, Other Pages

*Files to Modify/Create:*
• frontend/src/components/admin/admin-sidebar.tsx
• frontend/src/components/layout/navbar.tsx
• frontend/src/components/ui/breadcrumb.tsx
• frontend/src/components/ui/view-toggle.tsx

*Status:* 🔜 Pending""",
        "labels": ["dreams-emr-ui", "phase-3", "navigation"]
    },
    {
        "summary": "Dreams EMR UI - Phase 4.1: Redesign Admin Dashboard",
        "description": """Redesign admin dashboard to match Dreams EMR layout.

*Features:*
• 4 stat cards with sparklines (All Patients, Appointments, Total Doctors, Transactions)
• Appointment Request widget (list of pending appointments)
• Patient Statistics chart (bar chart - new vs old patients)
• Date range selector (top-right)
• Grid layout: 4 columns for stats, 2 columns below for widgets

*New API Endpoints Needed:*
• /api/v1/admin/stats - Dashboard metrics
• /api/v1/admin/appointment-requests - Pending appointment list

*Files to Modify:*
• frontend/src/app/admin/dashboard/page.tsx

*Status:* 🔜 Pending""",
        "labels": ["dreams-emr-ui", "phase-4", "dashboard"]
    },
    {
        "summary": "Dreams EMR UI - Phase 4.2: Redesign Patients Page",
        "description": """Redesign patients page with grid and table views.

*Features:*
• View toggle (grid/table) top-right
• Grid view: 2x3 cards with large profile photos, "In Patient"/"Out Patient" badges
• Table view: Rich table with avatars, status badges, sortable columns
• Search + filter controls
• "New Patient" button (blue, top-right)
• Pagination

*Components Used:*
• ProfileCard (grid view)
• DataTable (table view)
• ViewToggle
• Avatar
• Badge

*Files to Modify/Create:*
• frontend/src/app/admin/patients/page.tsx
• frontend/src/app/doctor/patients/page.tsx

*Status:* 🔜 Pending""",
        "labels": ["dreams-emr-ui", "phase-4", "patients"]
    },
    {
        "summary": "Dreams EMR UI - Phase 4.3: Create Patient Details Page",
        "description": """Create new patient details page with tabbed interface.

*Features:*
• Horizontal tab navigation (9 tabs):
  1. Patient Profile
  2. Appointments
  3. Vital Signs
  4. Visit History
  5. Lab Results
  6. Prescription
  7. Medical History
  8. Billings
  9. Documents
• Left sidebar: Patient profile card (photo, basic info, address)
• Right content area: Tab content
• "Back to Patients" button (top-right)

*Vital Signs Tab:*
• 2x3 grid of vital cards (Blood Pressure, Heart Rate, SPO2, Temperature, Respiratory Rate, Weight)
• Icons from vital-icons.tsx
• "View Past Data" link (trends over time)

*Appointments Tab:*
• 2-column card layout
• Status badges (Upcoming/Completed)
• Department + Doctor info
• Date & Time
• Action buttons

*Files to Create:*
• frontend/src/app/patient/[id]/page.tsx

*Status:* 🔜 Pending""",
        "labels": ["dreams-emr-ui", "phase-4", "patient-details"]
    },
    {
        "summary": "Dreams EMR UI - Phase 4.4: Redesign Doctors & Appointments Pages",
        "description": """Redesign doctors and appointments pages.

*Doctors Page:*
• Grid view: 2x4 cards with large circular doctor photos
• Doctor info: ID number (blue link), specialty, experience, appointments count
• Email + phone
• No action button (display only)

*Appointments Page:*
• Rich data table
• Columns: Patient ID, Patient Name (avatar), Doctor Name (avatar), Department, Appointment Date (with time), Status
• Status badges (Upcoming/In Progress/Completed)
• Sortable columns
• Submenu in sidebar: "All Appointments", "Consultation"

*Files to Modify:*
• frontend/src/app/admin/doctors/page.tsx
• frontend/src/app/admin/appointments/page.tsx

*Status:* 🔜 Pending""",
        "labels": ["dreams-emr-ui", "phase-4", "doctors", "appointments"]
    },
    {
        "summary": "Dreams EMR UI - Phase 4.5: Create Visits & Lab Results Pages",
        "description": """Create visits page and lab results page.

*Visits Page:*
• Rich data table
• Columns: Visit ID, Patient Name (avatar), Department, Doctor Name (avatar), Visit Date, Status
• Badge count (orange) showing total
• Search + sort controls

*Lab Results Page:*
• Rich data table
• Columns: Test ID, Patient Name (avatar), Gender, Appointment Date, Referred By (doctor avatar), Test Name, Status
• Status colors: Received (green), In Progress (purple), Pending (orange)

*Files to Create:*
• frontend/src/app/admin/visits/page.tsx
• frontend/src/app/admin/lab-results/page.tsx

*Status:* 🔜 Pending""",
        "labels": ["dreams-emr-ui", "phase-4", "visits", "lab-results"]
    },
    {
        "summary": "Dreams EMR UI - Phase 5: Advanced Features",
        "description": """Add advanced features to enhance the UI.

*Features:*
• Profile photo upload component (drag-drop, cropping, preview)
• Backend endpoint: /api/v1/users/photo
• Enhanced vitals display (interactive cards, historical trends)
• Additional chart components (bar chart, line chart using Recharts)
• Global search (Cmd+K, fuzzy search across patients/doctors/appointments/medicines)
• Notification center (bell icon, dropdown, badge count, real-time updates)

*Backend Changes Needed:*
• /api/v1/users/photo (upload endpoint)
• /api/v1/patients/{id}/vitals/history (vitals trends)
• /api/v1/notifications (notification list)
• /api/v1/stats/trends (dashboard chart data)

*Files to Create:*
• frontend/src/components/profile/photo-upload.tsx
• frontend/src/components/patient/vitals-display.tsx
• frontend/src/components/charts/bar-chart.tsx
• frontend/src/components/charts/line-chart.tsx
• frontend/src/components/ui/global-search.tsx
• frontend/src/components/layout/notification-center.tsx

*Status:* 🔜 Pending""",
        "labels": ["dreams-emr-ui", "phase-5", "advanced-features"]
    }
]

def create_ticket(summary, description, labels):
    """Create a Jira ticket"""
    url = f"{BASE_URL}/rest/api/3/issue"

    payload = {
        "fields": {
            "project": {
                "key": PROJECT_KEY
            },
            "summary": summary,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": description
                            }
                        ]
                    }
                ]
            },
            "issuetype": {
                "name": "Task"
            },
            "labels": labels
        }
    }

    response = requests.post(url, json=payload, auth=auth, headers=headers)

    if response.status_code == 201:
        ticket_key = response.json()['key']
        print(f"✅ Created: {ticket_key} - {summary}")
        return ticket_key
    else:
        print(f"❌ Failed to create: {summary}")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text}")
        return None

print("Creating Dreams EMR UI Transformation tickets...\n")

created_tickets = []
for ticket in tickets:
    ticket_key = create_ticket(ticket["summary"], ticket["description"], ticket["labels"])
    if ticket_key:
        created_tickets.append(ticket_key)

print(f"\n✅ Created {len(created_tickets)} tickets: {', '.join(created_tickets)}")
