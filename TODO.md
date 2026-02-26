# Dreams EMR UI Transformation - TODO

**Project:** Transform MedConnect UI to match Dreams EMR design system
**Status:** Phase 3 Complete (3/10)
**Started:** 2026-02-26

---

## ✅ Completed Phases

### Phase 1: Design System Foundation (MD-171) ✅
**Branch:** `dreams-emr-ui-phase1-2`
**Jira:** MD-171 ✅ Done

- [x] Updated `tailwind.config.ts` with Dreams colors
  - Royal blue primary (#4169E1)
  - Dark sidebar (#1A1D1F)
  - Light background (#F5F7FA)
  - 5 status colors (inProgress, completed, pending, overdue, upcoming)
- [x] Updated `globals.css` with CSS variables for light/dark modes
- [x] Added dependencies: recharts, @tanstack/react-table
- [x] Created test page at `/test-design-system`

### Phase 2: Core Component Library (MD-172) ✅
**Branch:** `dreams-emr-ui-phase1-2`
**Jira:** MD-172 ✅ Done

**Components Created:**
- [x] Avatar component (`ui/avatar.tsx`)
  - Circular profile images with fallback initials
  - Sizes: sm, md, lg, xl, 2xl
  - Status indicators (online/offline/busy/away)
  - AvatarGroup for stacked avatars
- [x] Enhanced Badge component (`ui/badge.tsx`)
  - 5 status variants with proper colors
- [x] StatCard component (`dashboard/stat-card.tsx`)
  - Icon, metric, trend indicator
  - Mini sparkline chart support
- [x] Sparkline chart component (`charts/sparkline.tsx`)
  - Mini line charts for stat cards
- [x] ProfileCard component (`cards/profile-card.tsx`)
  - Large circular avatar
  - Status badge, info grid, CTA button
- [x] Rich DataTable component (`ui/data-table.tsx`)
  - Sortable columns with TanStack Table
  - Pagination, search, filters
  - Avatar and badge support in cells
- [x] Icon sets
  - Vital icons (9): Blood pressure, heart rate, SPO2, temperature, etc.
  - Meal icons (6): Breakfast, lunch, tea, dinner, bedtime, water
  - Department icons: Colored badges for medical departments

### Phase 3: Navigation & Layout (MD-173) ✅
**Branch:** `md-173-dreams-emr-ui-phase-3-navigation-layout`
**Jira:** MD-173 ✅ Done

- [x] Dark sidebar (`admin/admin-sidebar.tsx`)
  - Background: #1A1D1F
  - 4 grouped sections: MAIN, HEALTH CARE, MANAGEMENT, PAGES
  - Expandable submenus (Appointments, Laboratory)
  - Blue active state (#4169E1)
  - Mobile: Full-width overlay
- [x] Enhanced top bar (`admin/admin-layout.tsx`)
  - Global search bar
  - Utility icons: Grid, Language, Notifications (with badge), Settings
  - User avatar dropdown
- [x] Breadcrumb component (`ui/breadcrumb.tsx`)
  - Home > Section > Page navigation
- [x] ViewToggle component (`ui/view-toggle.tsx`)
  - Grid/Table/List switcher
  - localStorage persistence with `useViewMode` hook

---

## 🔜 Phase 4: Page Redesigns (6 tasks)

### Phase 4.1: Redesign Admin Dashboard (MD-174) 🔄 NEXT
**Jira:** MD-174
**Estimated:** 2-3 hours
**Priority:** High

**Features:**
- [ ] 4 stat cards with sparklines
  - All Patients (count, trend, sparkline)
  - Appointments (today/week)
  - Total Doctors (count, trend)
  - Transactions (revenue/count)
- [ ] Appointment Request widget
  - List of pending appointment requests
  - Patient name, doctor, department, date/time
  - Accept/Reject actions
- [ ] Patient Statistics chart
  - Bar chart: New patients vs Existing patients
  - Monthly breakdown
  - Using Recharts library
- [ ] Date range selector (top-right)
  - Last 7 days, 30 days, 90 days, Custom
- [ ] Grid layout
  - 4 columns for stat cards
  - 2 columns below for widgets

**Backend Endpoints Needed:**
- [ ] `/api/v1/admin/stats` - Dashboard metrics with trends
- [ ] `/api/v1/admin/appointment-requests` - Pending appointment list
- [ ] `/api/v1/admin/stats/patient-trends` - New vs existing patient data

**Files:**
- [ ] `frontend/src/app/admin/dashboard/page.tsx` (modify)
- [ ] `frontend/src/components/charts/bar-chart.tsx` (new)
- [ ] `frontend/src/components/dashboard/appointment-request-widget.tsx` (new)

---

### Phase 4.2: Redesign Patients Page (MD-175) 🔜
**Jira:** MD-175
**Estimated:** 2-3 hours
**Priority:** High

**Features:**
- [ ] View toggle (grid/table) - top-right
- [ ] Grid view
  - 2x3 ProfileCard layout
  - Large circular photos
  - "In Patient" / "Out Patient" status badges
  - Info grid: Last Visit, Gender, Location
- [ ] Table view
  - Rich DataTable with avatars
  - Sortable columns: ID, Name, Status, Last Visit, Doctor, Department
  - Status badges
  - Search by name/ID
- [ ] Search + filter controls
  - Search input (global)
  - Filter by: Status, Gender, Department
- [ ] "New Patient" button (blue, top-right)
- [ ] Pagination

**Files:**
- [ ] `frontend/src/app/admin/patients/page.tsx` (new or modify)
- [ ] `frontend/src/app/doctor/patients/page.tsx` (new)

---

### Phase 4.3: Create Patient Details Page (MD-176) 🔜
**Jira:** MD-176
**Estimated:** 4-5 hours
**Priority:** High

**Features:**
- [ ] Horizontal tab navigation (9 tabs)
  1. Patient Profile
  2. Appointments
  3. Vital Signs
  4. Visit History
  5. Lab Results
  6. Prescription
  7. Medical History
  8. Billings
  9. Documents
- [ ] Left sidebar: Patient profile card
  - Large photo
  - Basic info (name, ID, age, gender)
  - Contact info
  - Address
- [ ] Right content area: Tab content
- [ ] "Back to Patients" button (top-right)

**Vital Signs Tab:**
- [ ] 2x3 grid of vital cards
  - Blood Pressure (droplet icon)
  - Heart Rate (heart icon)
  - SPO2 (lungs icon)
  - Temperature (thermometer)
  - Respiratory Rate (breath icon)
  - Weight (scale icon)
- [ ] "View Past Data" link (trends chart modal)

**Appointments Tab:**
- [ ] 2-column card layout
- [ ] Status badges (Upcoming/Completed/Cancelled)
- [ ] Department + Doctor info with avatars
- [ ] Date & Time
- [ ] Action buttons (View Details, Reschedule)

**Files:**
- [ ] `frontend/src/app/patient/[id]/page.tsx` (new)
- [ ] `frontend/src/components/patient/patient-sidebar.tsx` (new)
- [ ] `frontend/src/components/patient/vitals-grid.tsx` (new)
- [ ] `frontend/src/components/patient/appointments-tab.tsx` (new)

---

### Phase 4.4: Redesign Doctors & Appointments Pages (MD-177) 🔜
**Jira:** MD-177
**Estimated:** 3-4 hours
**Priority:** Medium

**Doctors Page:**
- [ ] Grid view (2x4 cards)
- [ ] Large circular doctor photos
- [ ] Info display:
  - ID number (blue link)
  - Specialty
  - Experience + Appointments count
  - Email + Phone
- [ ] No action buttons (display only)

**Appointments Page:**
- [ ] Rich data table
- [ ] Columns:
  - Patient ID
  - Patient Name (with avatar)
  - Doctor Name (with avatar)
  - Department (colored badge)
  - Appointment Date (with time)
  - Status (badge)
- [ ] Sortable columns
- [ ] Submenu in sidebar:
  - All Appointments
  - Consultation

**Files:**
- [ ] `frontend/src/app/admin/doctors/page.tsx` (modify)
- [ ] `frontend/src/app/admin/appointments/page.tsx` (modify)

---

### Phase 4.5: Create Visits & Lab Results Pages (MD-178) 🔜
**Jira:** MD-178
**Estimated:** 3-4 hours
**Priority:** Medium

**Visits Page:**
- [ ] Rich data table
- [ ] Columns:
  - Visit ID
  - Patient Name (avatar)
  - Department (colored badge)
  - Doctor Name (avatar)
  - Visit Date
  - Status (badge)
- [ ] Badge count (orange) showing total
- [ ] Search + sort controls

**Lab Results Page:**
- [ ] Rich data table
- [ ] Columns:
  - Test ID
  - Patient Name (avatar)
  - Gender
  - Appointment Date
  - Referred By (doctor avatar)
  - Test Name
  - Status (Received/In Progress/Pending)
- [ ] Status colors:
  - Received (green)
  - In Progress (purple)
  - Pending (orange)

**Files:**
- [ ] `frontend/src/app/admin/visits/page.tsx` (new)
- [ ] `frontend/src/app/admin/lab-results/page.tsx` (new)

---

### Phase 4.6: Update Pharmacy/Medicines Page (MD-178) 🔜
**Jira:** MD-178 (included)
**Estimated:** 1-2 hours
**Priority:** Low

**Features:**
- [ ] Product inventory table
- [ ] Columns:
  - ID
  - Product Name
  - Price
  - Offer Price
  - Purchase Date
  - Expire Date
  - Stock
  - Description (truncated)
  - Unit (ml/mg)
- [ ] "New Product" button
- [ ] Search + sort controls

**Files:**
- [ ] `frontend/src/app/admin/pharmacy/page.tsx` (modify from medicines)

---

## 🚀 Phase 5: Advanced Features (MD-179) 🔮

**Jira:** MD-179
**Estimated:** 6-8 hours
**Priority:** Medium

### 5.1: Profile Photo Upload
- [ ] Photo upload component (`profile/photo-upload.tsx`)
  - Drag-and-drop
  - Image cropping (1:1 aspect ratio)
  - Preview before upload
- [ ] Backend endpoint: `/api/v1/users/photo`
  - Store in `uploads/` folder (Option A) or S3 (Option B)
  - Return photo URL
- [ ] Display in Avatar component

### 5.2: Enhanced Vital Signs
- [ ] Interactive vital cards with hover states
- [ ] Click to view historical trends (line chart modal)
- [ ] Color-coded values (red for out-of-range, green for normal)
- [ ] Unit conversion support (imperial/metric)
- [ ] Backend: `/api/v1/patients/{id}/vitals/history`

### 5.3: Charts & Data Visualization
- [ ] Additional chart components
  - Bar chart (`charts/bar-chart.tsx`)
  - Line chart (`charts/line-chart.tsx`)
  - Pie/donut chart (optional)
- [ ] Backend: `/api/v1/stats/trends` (dashboard chart data)

### 5.4: Global Search (Cmd+K)
- [ ] Global search component (`ui/global-search.tsx`)
- [ ] Keyboard shortcut: Cmd+K
- [ ] Search across: Patients, Doctors, Appointments, Medicines
- [ ] Recent searches
- [ ] Quick actions
- [ ] Fuzzy search with highlighting

### 5.5: Notification System
- [ ] Notification center component (`layout/notification-center.tsx`)
- [ ] Bell icon with badge count
- [ ] Dropdown panel with notification list
- [ ] Mark as read/unread
- [ ] Categories: Appointments, Lab Results, System
- [ ] Real-time updates (WebSocket or polling)
- [ ] Backend: `/api/v1/notifications`

---

## 📋 Backend API Endpoints to Add

**Dashboard:**
- [ ] `GET /api/v1/admin/stats` - Dashboard metrics with trends
- [ ] `GET /api/v1/admin/appointment-requests` - Pending appointments
- [ ] `GET /api/v1/admin/stats/patient-trends` - Patient statistics for charts

**Advanced Features:**
- [ ] `POST /api/v1/users/photo` - Upload profile photo
- [ ] `GET /api/v1/patients/{id}/vitals/history` - Historical vital signs
- [ ] `GET /api/v1/notifications` - User notifications list
- [ ] `PUT /api/v1/notifications/{id}/read` - Mark notification as read
- [ ] `GET /api/v1/stats/trends` - Dashboard chart data

---

## 🧪 Testing Checklist

**Per Page:**
- [ ] Desktop (Chrome, Firefox, Safari)
- [ ] Tablet (iPad)
- [ ] Mobile (iPhone, Android)
- [ ] Keyboard navigation
- [ ] Screen reader compatibility
- [ ] All data loads from API correctly
- [ ] Tables sortable and paginated
- [ ] Search/filter functional
- [ ] No console errors
- [ ] Loading states show spinner

**Performance:**
- [ ] Lighthouse score: 90+ (Performance, Accessibility)
- [ ] Charts render with real data
- [ ] Images optimized
- [ ] Lazy loading implemented

---

## 📦 Dependencies to Add (If Needed)

```json
{
  "dependencies": {
    "react-dropzone": "^14.2.0",      // Phase 5: Photo upload
    "react-image-crop": "^11.0.0",     // Phase 5: Photo cropping
    "react-hot-toast": "^2.4.1"        // Phase 5: Notifications
  }
}
```

---

## 🔄 Git Workflow

**Branch Naming:**
- Format: `md-{ticket-number}-{description}`
- Example: `md-174-admin-dashboard-redesign`

**Commit Message Format:**
```
[MD-XXX] Brief description

Detailed changes:
- Point 1
- Point 2

Jira: MD-XXX
Status: {In Progress|Complete}

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

---

## 📊 Progress Tracking

**Overall Progress:** 3/10 phases complete (30%)

- ✅ Phase 1: Design System Foundation
- ✅ Phase 2: Core Component Library
- ✅ Phase 3: Navigation & Layout
- 🔄 Phase 4.1: Admin Dashboard (NEXT)
- 🔜 Phase 4.2: Patients Page
- 🔜 Phase 4.3: Patient Details Page
- 🔜 Phase 4.4: Doctors & Appointments
- 🔜 Phase 4.5: Visits & Lab Results
- 🔜 Phase 4.6: Pharmacy
- 🔮 Phase 5: Advanced Features

**Estimated Total Time Remaining:** 25-35 hours

---

## 🎯 Success Criteria

- [ ] All pages match Dreams EMR visual design
- [ ] No existing functionality broken
- [ ] All tests passing
- [ ] No TypeScript errors
- [ ] Lighthouse score: 90+ (Performance, Accessibility)
- [ ] Mobile responsive (all pages)
- [ ] User acceptance testing passes

---

**Last Updated:** 2026-02-26
**Next Task:** Phase 4.1 - Admin Dashboard Redesign (MD-174)
