# Software Requirements Specification (SRS)
# MedConnect - Healthcare Platform

**Version:** 1.0
**Date:** 2026-02-25
**Status:** Active Development
**Document Owner:** MedConnect Development Team

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Overall Description](#2-overall-description)
3. [System Architecture](#3-system-architecture)
4. [Functional Requirements](#4-functional-requirements)
5. [Non-Functional Requirements](#5-non-functional-requirements)
6. [Database Schema](#6-database-schema)
7. [API Specifications](#7-api-specifications)
8. [User Interface Requirements](#8-user-interface-requirements)
9. [Integration Requirements](#9-integration-requirements)
10. [Security Requirements](#10-security-requirements)
11. [Future Enhancements](#11-future-enhancements)
12. [Appendices](#12-appendices)

---

## 1. Introduction

### 1.1 Purpose

MedConnect is a comprehensive healthcare platform designed for India's Digital Health Ecosystem, integrating Electronic Medical Records (EMR), patient portals, doctor interfaces, and ABDM (Ayushman Bharat Digital Mission) compliance.

### 1.2 Scope

The system provides:
- **Patient Management:** Complete health timeline, medical records, prescriptions
- **Doctor Portal:** Patient management, prescription writing, clinical decision support
- **Admin Panel:** User management, medicine database management, system configuration
- **Medicine Database:** Comprehensive pharmaceutical database with 250,797+ brands
- **ABDM Integration:** ABHA ID support, Health Information Exchange
- **Clinical Decision Support:** Drug interactions, contraindications, alternatives

### 1.3 Definitions and Acronyms

| Term | Definition |
|------|------------|
| ABDM | Ayushman Bharat Digital Mission |
| ABHA | Ayushman Bharat Health Account |
| EMR | Electronic Medical Record |
| FHIR | Fast Healthcare Interoperability Resources (R4) |
| HIP | Health Information Provider |
| HIU | Health Information User |
| API | Active Pharmaceutical Ingredient (Salt) |
| TDD | Test-Driven Development |
| RBAC | Role-Based Access Control |

### 1.4 References

- FHIR R4 Specification: https://hl7.org/fhir/R4/
- ABDM Documentation: https://abdm.gov.in
- Project CLAUDE.md: `/Users/vaibhavjain/projects/MedConnect/CLAUDE.md`
- Medicine Schema: `backend/docs/medicine_schema_v2.md`

---

## 2. Overall Description

### 2.1 Product Perspective

MedConnect operates as a comprehensive healthcare platform with the following system components:

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend Layer                        │
│  Next.js 14 + Tailwind CSS + shadcn/ui                 │
│  - Patient Portal   - Doctor Portal   - Admin Panel     │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│                   API Gateway Layer                      │
│                Nginx + Rate Limiting                     │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│                  Backend Layer                           │
│  FastAPI + SQLAlchemy + Alembic                         │
│  - Auth Service    - Record Service                     │
│  - Medicine Service - Prescription Service              │
│  - ABDM Service (Future)                                │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│                  Data Layer                              │
│  PostgreSQL 16 + pgvector + Redis 7                     │
│  - Main DB (EMR)   - Medicine DB (Separate)             │
└─────────────────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│              External Integrations                       │
│  - Keycloak (Auth)  - ABDM APIs  - Sentry (Monitoring)  │
└─────────────────────────────────────────────────────────┘
```

### 2.2 Product Functions

**Phase 1: Core EMR + Patient Portal (IMPLEMENTED)**
- User registration and authentication (Email/Phone)
- JWT-based authorization with role-based access control
- Medical record creation and management
- Prescription management with FHIR R4 compliance
- Patient health timeline with search and filtering
- Medicine database with 250,797+ brands

**Phase 2: Enhanced Medicine Management (IN PROGRESS)**
- Medicine autocomplete API
- Drug interaction warnings
- Alternative medicine suggestions
- Bulk medicine import/export
- Admin CRUD for medicines, salts, manufacturers

**Phase 3: Advanced Features (PLANNED)**
- Doctor verification workflow
- Patient profile editing with document upload
- Appointment management
- Clinical templates
- Vitals tracking

**Phase 4: ABDM Integration (PLANNED)**
- ABHA ID creation and linking
- Health Information Provider (HIP) module
- Health Information User (HIU) module
- Consent management
- QR-based record sharing

### 2.3 User Classes and Characteristics

| User Role | Technical Expertise | System Usage |
|-----------|---------------------|--------------|
| **Patient** | Low | View health records, prescriptions, upload documents |
| **Doctor** | Medium | Create records, write prescriptions, manage patients |
| **Admin** | High | Manage users, medicines, system configuration |
| **System Admin** | Very High | Database management, server configuration, monitoring |

### 2.4 Operating Environment

- **Server:** Linux (Docker Compose orchestration)
- **Database:** PostgreSQL 16 with pgvector extension
- **Cache:** Redis 7
- **Runtime:** Python 3.12, Node.js 18+
- **Reverse Proxy:** Nginx
- **Auth:** Keycloak
- **Deployment:** Docker containers on VPS/Cloud

### 2.5 Design and Implementation Constraints

- Must comply with ABDM standards for health data exchange
- FHIR R4 compliance for all medical records
- Data encryption at rest and in transit
- HIPAA/Indian healthcare data privacy standards
- Support for Indian medicine schedules (H, H1, X)
- Multi-language support (English + regional languages)

---

## 3. System Architecture

### 3.1 Technology Stack

| Layer | Technology | Version | Purpose |
|-------|------------|---------|---------|
| **Frontend** | Next.js | 14 | React framework with SSR |
| | Tailwind CSS | 3.x | Utility-first CSS |
| | shadcn/ui | Latest | UI component library |
| | TanStack Query | 5.x | Server state management |
| | Zustand | 4.x | Client state management |
| **Backend** | FastAPI | 0.115+ | REST API framework |
| | SQLAlchemy | 2.0 | ORM and database toolkit |
| | Alembic | Latest | Database migrations |
| | Uvicorn | Latest | ASGI server |
| | Pydantic | 2.x | Data validation |
| **Database** | PostgreSQL | 16 | Primary database |
| | pgvector | Latest | Vector embeddings |
| | Redis | 7 | Caching and sessions |
| **Infrastructure** | Docker | Latest | Containerization |
| | Docker Compose | Latest | Multi-container orchestration |
| | Nginx | Alpine | Reverse proxy + load balancer |
| **Authentication** | Keycloak | Latest | Identity and access management |
| **Monitoring** | Sentry | Latest | Error tracking |
| | structlog | Latest | Structured logging |

### 3.2 Architectural Patterns

**Backend Architecture:**
- **Layered Architecture:** Routers → Services → Models
- **Repository Pattern:** Service layer abstracts database access
- **Dependency Injection:** FastAPI's built-in DI for database sessions
- **CQRS (Future):** Separate read and write models for complex queries

**Frontend Architecture:**
- **Component-Based:** Reusable React components
- **Container/Presentational:** Smart containers + dumb components
- **API Layer Abstraction:** Centralized axios instance with interceptors
- **State Management:** Zustand for global state, TanStack Query for server state

**Database Architecture:**
- **Schema Separation:** Main EMR database + separate Medicine database
- **Soft Delete Pattern:** All records have `deleted_at` column
- **Audit Trail:** `created_at`, `updated_at` on all tables
- **JSONB for Flexibility:** FHIR bundles, prescription medicines, metadata

### 3.3 Communication Protocols

- **Client-Frontend:** HTTPS
- **Frontend-Backend:** REST API over HTTPS
- **Backend-Database:** PostgreSQL wire protocol (asyncpg)
- **Backend-Cache:** Redis protocol
- **Backend-Auth:** OIDC/OAuth2 with Keycloak
- **Future:** WebSocket for real-time notifications

---

## 4. Functional Requirements

### 4.1 User Management

#### 4.1.1 User Registration (FR-AUTH-001)

**Priority:** P0 (Critical)
**Status:** Implemented

**Description:** Users can register with email or phone number.

**Inputs:**
- Email or Phone (unique)
- Password (minimum 8 characters)
- Full Name
- Role (patient, doctor, admin)
- Language preference (default: en)

**Processing:**
- Validate input format
- Check uniqueness of email/phone
- Hash password using bcrypt
- Create user in database with Keycloak synchronization
- Generate Keycloak subject ID

**Outputs:**
- User profile object
- Access token (JWT, 15-minute expiry)
- Refresh token (JWT, 7-day expiry)

**Business Rules:**
- Email must be valid format
- Phone must be Indian format (+91)
- Password minimum 8 characters
- Duplicate email/phone rejected
- Default role is 'patient' if not specified

#### 4.1.2 User Authentication (FR-AUTH-002)

**Priority:** P0 (Critical)
**Status:** Implemented

**Description:** Users can log in with email/phone and password.

**Inputs:**
- Email or Phone
- Password

**Processing:**
- Look up user by email/phone
- Verify password against bcrypt hash
- Check if user is active
- Generate JWT tokens

**Outputs:**
- Access token (JWT)
- Refresh token (JWT)
- User profile

**Business Rules:**
- Account must be active
- Maximum 5 failed login attempts before lockout
- Tokens include user_id, role, permissions

#### 4.1.3 Token Refresh (FR-AUTH-003)

**Priority:** P0 (Critical)
**Status:** Implemented

**Description:** Refresh access token using refresh token.

**Inputs:**
- Valid refresh token

**Processing:**
- Validate refresh token signature
- Check token expiry
- Verify user still exists and active
- Generate new access token

**Outputs:**
- New access token

**Business Rules:**
- Refresh token must not be expired
- User must still be active
- Refresh token can only be used once (rotation)

#### 4.1.4 User Profile Management (FR-USER-001)

**Priority:** P1 (High)
**Status:** Partially Implemented

**Current:**
- Get current user profile (Implemented)
- Get doctor profile (Implemented)
- Update doctor profile (Implemented)

**Future:**
- Patient profile editing
- Profile picture upload
- Document upload (ID, medical history)

### 4.2 Medical Records Management

#### 4.2.1 Create Medical Record (FR-RECORD-001)

**Priority:** P0 (Critical)
**Status:** Implemented

**Description:** Doctors can create medical records for patients.

**Inputs:**
- Patient ID (UUID)
- Record Type (consultation, lab_report, imaging, etc.)
- FHIR Bundle (JSONB)
- Chief Complaint (text)
- Diagnosis (text)
- Notes (text)

**Processing:**
- Validate doctor has permission
- Validate patient exists
- Create FHIR R4 compliant bundle
- Store record with metadata
- Index for full-text search

**Outputs:**
- Medical record object with ID
- FHIR bundle

**Business Rules:**
- Only doctors can create records
- Patient must exist
- FHIR bundle must be valid R4
- Record cannot be deleted (soft delete only)

#### 4.2.2 View Medical Records (FR-RECORD-002)

**Priority:** P0 (Critical)
**Status:** Implemented

**Description:** View medical records with access control.

**Roles:**
- **Patient:** Can view only their own records
- **Doctor:** Can view records they created
- **Admin:** Can view all records (audit purposes)

**Features:**
- Pagination (cursor-based)
- Search by keywords (full-text)
- Filter by record type
- Sort by date (descending)

**Outputs:**
- Paginated list of records
- Record details (FHIR bundle)

#### 4.2.3 Patient Health Timeline (FR-RECORD-003)

**Priority:** P0 (Critical)
**Status:** Implemented

**Description:** Chronological view of patient's health records.

**Features:**
- Timeline view (date descending)
- Search by keywords
- Filter by record type
- Cursor-based pagination
- Mobile-responsive

**Query Parameters:**
- `search` (optional): Full-text search
- `record_type` (optional): Filter by type
- `cursor` (optional): Pagination cursor
- `limit` (optional): Results per page (default 20)

### 4.3 Prescription Management

#### 4.3.1 Create Prescription (FR-PRESCRIPTION-001)

**Priority:** P0 (Critical)
**Status:** Implemented

**Description:** Doctors can create prescriptions for patients.

**Inputs:**
- Patient ID
- Doctor ID (from auth context)
- Medicines (array of medicine objects)
  - Medicine ID or Name
  - Dosage
  - Frequency
  - Duration
  - Instructions
- Diagnosis (text)
- Notes (text)
- Valid Until (date)

**Processing:**
- Validate doctor authorization
- Validate patient exists
- Create linked medical record automatically
- Store medicines as JSONB array
- Generate FHIR MedicationRequest bundle

**Outputs:**
- Prescription object
- Linked medical record ID
- FHIR bundle

**Business Rules:**
- Only doctors can prescribe
- Patient must exist
- At least one medicine required
- Valid until date must be future
- Prescription links to medical record

#### 4.3.2 View Prescriptions (FR-PRESCRIPTION-002)

**Priority:** P0 (Critical)
**Status:** Implemented

**Description:** Patients can view their prescriptions.

**Features:**
- List all prescriptions for patient
- Pagination
- Filter by date range
- Filter by validity (active/expired)
- View prescription details with medicine list

**Outputs:**
- Paginated prescription list
- Prescription details with medicines

#### 4.3.3 Medicine Autocomplete (FR-PRESCRIPTION-003)

**Priority:** P1 (High)
**Status:** Implemented

**Description:** Autocomplete medicine search for prescription forms.

**Features:**
- Real-time search as user types
- Search by brand name or salt name
- Fuzzy matching
- Results sorted by relevance
- Caching for performance (Redis)

**API Endpoint:** `GET /api/v1/medicines/search?q={query}`

**Outputs:**
- Array of medicine suggestions (max 20)
- Each result includes: brand_id, brand_name, salt_composition, manufacturer

#### 4.3.4 Drug Interaction Checking (FR-PRESCRIPTION-004)

**Priority:** P1 (High)
**Status:** Implemented

**Description:** Automatic checking for drug-drug interactions.

**Features:**
- Check interactions when medicines added to prescription
- Severity levels: Contraindicated, Major, Moderate, Minor
- Visual warnings with color coding
- Effect description and management suggestions
- Block prescription if contraindicated

**API Endpoint:** `POST /api/v1/interactions/check`

**Input:**
- Array of salt IDs

**Output:**
- Array of interactions with severity, effect, mechanism, management

**Business Rules:**
- Always check before finalizing prescription
- Contraindicated interactions must be acknowledged by doctor
- Log all interaction warnings in audit trail

#### 4.3.5 Alternative Medicines (FR-PRESCRIPTION-005)

**Priority:** P1 (High)
**Status:** Implemented

**Description:** Suggest alternative brands with same composition.

**Features:**
- Find brands with identical salt composition
- Display alternatives with pricing
- Highlight discontinued medicines
- Allow replacement in prescription

**API Endpoint:** `GET /api/v1/brands/{brand_id}/alternatives`

**Output:**
- Array of alternative brands
- Same composition as original
- Includes manufacturer, price, availability

### 4.4 Medicine Database Management

#### 4.4.1 Medicine Database Schema (FR-MEDICINE-001)

**Priority:** P0 (Critical)
**Status:** Implemented

**Description:** Comprehensive pharmaceutical database with 21 tables.

**Core Tables:**
- **Salts:** 1,532 active pharmaceutical ingredients
- **Salt Strengths:** 5,984 strength variations
- **Brands:** 250,797 commercial products
- **Manufacturers:** 7,648 pharmaceutical companies
- **Brand Compositions:** 331,442 brand→salt_strength links

**Clinical Safety Tables:**
- Drug Interactions
- Contraindications
- Side Effects
- Indications (Uses)
- Dosing Guidelines

**Classification Tables:**
- Chemical Classes (871)
- Therapeutic Classes (22)
- Action Classes (431)

#### 4.4.2 Medicine Search API (FR-MEDICINE-002)

**Priority:** P1 (High)
**Status:** Implemented

**Description:** Unified search across salts and brands.

**API Endpoint:** `GET /api/v1/medicines/search`

**Query Parameters:**
- `q` (required): Search query
- `type` (optional): salt, brand, all (default)
- `limit` (optional): Results limit (default 20)

**Features:**
- Full-text search on names
- Fuzzy matching
- Autocomplete support
- Separate salt and brand results
- Performance: < 100ms

#### 4.4.3 Admin Medicine Management (FR-ADMIN-001)

**Priority:** P1 (High)
**Status:** Partially Implemented

**Current:**
- List manufacturers (Implemented)
- Create manufacturer (Implemented)
- Update manufacturer (Implemented)
- Delete manufacturer (Implemented)
- List salts (Implemented)
- Create salt (Implemented)
- Update salt (Implemented)
- Delete salt (Implemented)
- List brands (Implemented)

**Future:**
- Create brand with composition
- Update brand composition
- Delete brand
- Bulk import CSV
- Bulk export CSV
- Validate data integrity

#### 4.4.4 Bulk Medicine Import (FR-ADMIN-002)

**Priority:** P2 (Medium)
**Status:** Planned

**Description:** Upload CSV to bulk add/update medicines.

**Features:**
- CSV template download
- Upload CSV file
- Data validation
- Preview changes
- Confirm and import
- Error reporting

**Validation:**
- Manufacturer exists or create new
- Salt exists or create new
- Strength format valid
- Composition format valid
- No duplicate brands

### 4.5 Doctor Portal

#### 4.5.1 Doctor Dashboard (FR-DOCTOR-001)

**Priority:** P0 (Critical)
**Status:** Implemented

**Features:**
- Patient list (patients with records created by doctor)
- Quick access to create record/prescription
- Recent activity
- Statistics (total patients, records, prescriptions)

#### 4.5.2 Patient Search (FR-DOCTOR-002)

**Priority:** P1 (High)
**Status:** Planned

**Description:** Search for patients across system.

**Features:**
- Search by name, phone, email, ABHA ID
- Fuzzy matching
- Pagination
- Access patient records with consent

#### 4.5.3 Appointment Management (FR-DOCTOR-003)

**Priority:** P2 (Medium)
**Status:** Planned

**Features:**
- View appointment calendar
- Schedule appointments
- Mark appointment status (scheduled, completed, cancelled)
- Send reminders (SMS/email)

#### 4.5.4 Clinical Templates (FR-DOCTOR-004)

**Priority:** P2 (Medium)
**Status:** Planned

**Description:** Pre-defined templates for common conditions.

**Features:**
- Create custom templates
- Use templates for records
- Template library (diabetes, hypertension, etc.)
- Share templates with other doctors

#### 4.5.5 Doctor Verification (FR-DOCTOR-005)

**Priority:** P1 (High)
**Status:** Planned

**Description:** Verify doctor credentials before granting privileges.

**Features:**
- Upload medical license
- Upload ID proof
- Upload certificates
- Admin review workflow
- Approval/rejection with comments
- Email notifications

**Workflow:**
1. Doctor registers → status: pending_verification
2. Doctor uploads documents
3. Admin reviews documents
4. Admin approves/rejects
5. Doctor receives email notification
6. If approved, doctor can create records

### 4.6 Patient Portal

#### 4.6.1 Patient Timeline (FR-PATIENT-001)

**Priority:** P0 (Critical)
**Status:** Implemented

**Features:**
- Chronological health timeline
- View all records and prescriptions
- Search and filter
- Mobile-responsive
- FHIR-compliant data display

#### 4.6.2 Patient Profile Editing (FR-PATIENT-002)

**Priority:** P1 (High)
**Status:** Planned

**Features:**
- Edit personal information
- Update contact details
- Upload profile picture
- Manage language preferences
- Link ABHA ID

#### 4.6.3 Document Upload (FR-PATIENT-003)

**Priority:** P1 (High)
**Status:** Planned

**Description:** Upload medical documents and images.

**Features:**
- Upload files (PDF, JPG, PNG)
- OCR for prescription images
- Categorize documents
- Tag with date and type
- Download original file

**Supported Types:**
- Lab reports
- Imaging (X-ray, MRI, CT scan)
- Prescriptions
- Medical certificates
- Vaccination records

#### 4.6.4 Vitals Tracking (FR-PATIENT-004)

**Priority:** P2 (Medium)
**Status:** Planned

**Description:** Track vital signs over time.

**Vitals:**
- Blood pressure
- Heart rate
- Blood glucose
- Weight
- Temperature
- SpO2

**Features:**
- Manual entry
- Graph visualization
- Trend analysis
- Export to CSV
- Share with doctor

### 4.7 Admin Panel

#### 4.7.1 User Management (FR-ADMIN-USER-001)

**Priority:** P1 (High)
**Status:** Planned

**Features:**
- List all users (pagination, search)
- View user details
- Activate/deactivate user
- Change user role
- Reset password
- Audit log of user actions

#### 4.7.2 System Dashboard (FR-ADMIN-DASHBOARD-001)

**Priority:** P2 (Medium)
**Status:** Planned

**Features:**
- Total users by role
- Active users (last 30 days)
- Records created (last 30 days)
- Prescriptions created
- System health (DB, Redis, API status)
- Error rate (Sentry integration)

#### 4.7.3 Audit Logging (FR-ADMIN-AUDIT-001)

**Priority:** P1 (High)
**Status:** Planned

**Description:** Track all critical system actions.

**Logged Events:**
- User login/logout
- Record creation/modification
- Prescription creation
- Medicine changes
- User role changes
- Failed login attempts

**Features:**
- Search by user, action, date
- Export audit log
- Retention: 7 years (compliance)

---

## 5. Non-Functional Requirements

### 5.1 Performance Requirements

#### NFR-PERF-001: API Response Time
- **Requirement:** 95th percentile response time < 500ms
- **Measurement:** All API endpoints under normal load
- **Current Status:** Medicine search < 100ms (Achieved)

#### NFR-PERF-002: Database Query Performance
- **Requirement:** All database queries < 200ms
- **Implementation:** Strategic indexes, query optimization, connection pooling
- **Current Status:** Achieved with pgvector and GIN indexes

#### NFR-PERF-003: Frontend Load Time
- **Requirement:** Time to Interactive < 3 seconds on 3G
- **Implementation:** Next.js SSR, code splitting, image optimization
- **Current Status:** To be measured

#### NFR-PERF-004: Concurrent Users
- **Requirement:** Support 1,000 concurrent users
- **Implementation:** Horizontal scaling, load balancing, caching
- **Current Status:** Target for production

### 5.2 Scalability Requirements

#### NFR-SCALE-001: Database Scalability
- **Requirement:** Support 1 million patient records
- **Implementation:** Partitioning, archival strategy, read replicas
- **Current Status:** Schema designed for scale

#### NFR-SCALE-002: Horizontal Scaling
- **Requirement:** Add backend instances without code changes
- **Implementation:** Stateless API design, Redis for sessions
- **Current Status:** Architected for scaling

#### NFR-SCALE-003: Medicine Database Growth
- **Requirement:** Support 500K+ medicines
- **Implementation:** Separate database, optimized indexes, caching
- **Current Status:** 250,797 medicines loaded, schema supports growth

### 5.3 Availability Requirements

#### NFR-AVAIL-001: System Uptime
- **Requirement:** 99.5% uptime (43.8 hours downtime/year)
- **Implementation:** Health checks, auto-restart, monitoring
- **Monitoring:** `/health` endpoint, Sentry alerts

#### NFR-AVAIL-002: Database Backup
- **Requirement:** Daily backups with 30-day retention
- **Implementation:** PostgreSQL pg_dump, point-in-time recovery
- **Recovery Time Objective (RTO):** 4 hours
- **Recovery Point Objective (RPO):** 24 hours

#### NFR-AVAIL-003: Disaster Recovery
- **Requirement:** Documented DR plan with tested procedures
- **Implementation:** Backup verification, restore testing quarterly

### 5.4 Security Requirements

#### NFR-SEC-001: Authentication
- **Requirement:** Secure authentication with JWT tokens
- **Implementation:**
  - bcrypt password hashing (cost factor 12)
  - Access token: 15 minutes expiry
  - Refresh token: 7 days expiry, rotation
  - Token signing with RS256

#### NFR-SEC-002: Authorization
- **Requirement:** Role-based access control (RBAC)
- **Roles:** Patient, Doctor, Admin
- **Implementation:** Dependency injection guards, Keycloak integration

#### NFR-SEC-003: Data Encryption
- **Requirement:**
  - Data at rest: Database encryption
  - Data in transit: TLS 1.3
- **Implementation:** PostgreSQL encryption, Nginx HTTPS

#### NFR-SEC-004: API Security
- **Requirement:** Protection against common attacks
- **Implementation:**
  - Rate limiting (100 req/min API, 10 req/min auth)
  - CORS policy (whitelist frontend origin)
  - XSS protection headers
  - CSRF protection
  - SQL injection prevention (parameterized queries)

#### NFR-SEC-005: Sensitive Data
- **Requirement:** No sensitive data in logs or error messages
- **Implementation:** Structured logging with field masking, Sentry scrubbing

#### NFR-SEC-006: Session Management
- **Requirement:** Secure session handling
- **Implementation:**
  - HTTPOnly cookies
  - Secure flag in production
  - Session timeout: 15 minutes idle
  - Logout clears all tokens

### 5.5 Compliance Requirements

#### NFR-COMP-001: ABDM Compliance
- **Requirement:** Compliance with ABDM standards
- **Implementation:**
  - FHIR R4 for all health records
  - ABHA ID integration
  - Consent management framework
  - M1, M2, M3 APIs (planned)

#### NFR-COMP-002: Data Privacy
- **Requirement:** Compliance with Indian data privacy laws
- **Implementation:**
  - Patient data consent
  - Right to access data
  - Right to deletion (soft delete, anonymization)
  - Data retention policies

#### NFR-COMP-003: Audit Trail
- **Requirement:** Comprehensive audit logging
- **Implementation:** All access to patient records logged
- **Retention:** 7 years

#### NFR-COMP-004: Medical Data Standards
- **Requirement:** FHIR R4 compliance for interoperability
- **Implementation:**
  - All records stored as FHIR bundles
  - Validation against FHIR schemas
  - SNOMED CT codes (future)
  - ICD-10 codes (future)

### 5.6 Usability Requirements

#### NFR-USE-001: Mobile Responsiveness
- **Requirement:** Full functionality on mobile devices
- **Implementation:** Tailwind CSS responsive design
- **Testing:** Chrome DevTools, real devices

#### NFR-USE-002: Accessibility
- **Requirement:** WCAG 2.1 Level AA compliance
- **Implementation:**
  - Semantic HTML
  - Keyboard navigation
  - Screen reader support
  - Color contrast ratios
  - Alt text for images

#### NFR-USE-003: Multi-language Support
- **Requirement:** Support for English and regional Indian languages
- **Implementation:** i18n framework (future)
- **Languages:** English, Hindi, Bengali, Tamil, Telugu, Marathi

#### NFR-USE-004: User Experience
- **Requirement:** Intuitive interface with minimal training
- **Implementation:**
  - Consistent UI patterns
  - Clear error messages
  - Loading states
  - Success confirmations
  - Help tooltips

### 5.7 Maintainability Requirements

#### NFR-MAINT-001: Code Quality
- **Requirement:** High code quality standards
- **Implementation:**
  - Type hints (Python)
  - TypeScript (Frontend)
  - Linting (pylint, ESLint)
  - Code reviews
  - Test coverage > 80%

#### NFR-MAINT-002: Documentation
- **Requirement:** Comprehensive documentation
- **Documentation:**
  - API documentation (Swagger/OpenAPI)
  - Database schema documentation
  - README files
  - Inline code comments
  - Architecture diagrams

#### NFR-MAINT-003: Version Control
- **Requirement:** Git-based version control
- **Branch Strategy:** Feature branches, main branch protection
- **Commit Messages:** Conventional commits with Jira ticket references

#### NFR-MAINT-004: Database Migrations
- **Requirement:** Reversible database migrations
- **Implementation:** Alembic with upgrade/downgrade
- **Testing:** Migration testing in staging

### 5.8 Monitoring and Logging Requirements

#### NFR-MON-001: Application Monitoring
- **Requirement:** Real-time application monitoring
- **Implementation:** Sentry for error tracking
- **Metrics:** Error rate, response time, request volume

#### NFR-MON-002: Structured Logging
- **Requirement:** Structured JSON logs
- **Implementation:** structlog library
- **Fields:** timestamp, level, message, context, user_id, request_id

#### NFR-MON-003: Health Checks
- **Requirement:** Automated health monitoring
- **Endpoint:** `GET /health`
- **Checks:** Database, Redis, external services
- **Monitoring:** Uptime monitoring service

#### NFR-MON-004: Alerts
- **Requirement:** Automated alerts for critical issues
- **Alerts:**
  - Error rate > 5%
  - Response time > 2 seconds (95th percentile)
  - Database connection failures
  - Redis connection failures
  - Disk space < 20%

---

## 6. Database Schema

### 6.1 Main EMR Database Schema

#### 6.1.1 Users Table

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE,
    phone VARCHAR(15) UNIQUE,
    keycloak_sub VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL, -- patient, doctor, admin
    language_pref VARCHAR(10) DEFAULT 'en',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    deleted_at TIMESTAMP WITH TIME ZONE,

    INDEX idx_users_email (email) WHERE deleted_at IS NULL,
    INDEX idx_users_phone (phone) WHERE deleted_at IS NULL,
    INDEX idx_users_role (role) WHERE deleted_at IS NULL
);
```

#### 6.1.2 Doctors Table

```sql
CREATE TABLE doctors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) UNIQUE,
    specialization VARCHAR(255),
    license_number VARCHAR(100) UNIQUE,
    years_of_experience INTEGER,
    facility_name VARCHAR(255),
    facility_address TEXT,
    consultation_fee NUMERIC(10, 2),

    verification_status VARCHAR(20) DEFAULT 'pending', -- pending, verified, rejected
    verification_documents JSONB,
    verified_at TIMESTAMP WITH TIME ZONE,
    verified_by UUID REFERENCES users(id),

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    INDEX idx_doctors_user (user_id),
    INDEX idx_doctors_verification (verification_status)
);
```

#### 6.1.3 Medical Records Table

```sql
CREATE TABLE medical_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID NOT NULL REFERENCES users(id),
    doctor_id UUID NOT NULL REFERENCES doctors(id),

    record_type VARCHAR(50) NOT NULL, -- consultation, lab_report, imaging, vitals, etc.
    fhir_bundle JSONB NOT NULL,

    chief_complaint TEXT,
    diagnosis TEXT,
    notes TEXT,

    abha_address VARCHAR(255),

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    deleted_at TIMESTAMP WITH TIME ZONE,

    INDEX idx_records_patient_date (patient_id, created_at DESC) WHERE deleted_at IS NULL,
    INDEX idx_records_doctor (doctor_id) WHERE deleted_at IS NULL,
    INDEX idx_records_type (record_type) WHERE deleted_at IS NULL,
    GIN INDEX idx_records_fhir (fhir_bundle),
    FULLTEXT INDEX idx_records_search (chief_complaint, diagnosis, notes)
);
```

#### 6.1.4 Prescriptions Table

```sql
CREATE TABLE prescriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    record_id UUID NOT NULL REFERENCES medical_records(id),
    doctor_id UUID NOT NULL REFERENCES doctors(id),
    patient_id UUID NOT NULL REFERENCES users(id),

    medicines JSONB NOT NULL, -- Array of medicine objects
    diagnosis TEXT,
    notes TEXT,

    translated JSONB, -- Translations in regional languages
    valid_until DATE,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    deleted_at TIMESTAMP WITH TIME ZONE,

    INDEX idx_rx_patient_date (patient_id, created_at DESC) WHERE deleted_at IS NULL,
    INDEX idx_rx_doctor (doctor_id) WHERE deleted_at IS NULL
);
```

### 6.2 Medicine Database Schema (Separate Database)

**See:** `backend/docs/medicine_schema_v2.md` for complete 21-table schema

**Key Tables:**
- **salts** (1,532 records): Active pharmaceutical ingredients
- **salt_strengths** (5,984 records): Available strengths
- **brands** (250,797 records): Commercial products
- **manufacturers** (7,648 records): Pharmaceutical companies
- **brand_compositions** (331,442 records): Brand→Salt links
- **drug_interactions**: Drug-drug interactions
- **contraindications**: Conditions where drug should not be used
- **side_effects**: Adverse effects
- **uses**: Indications
- **dosing_guidelines**: Standard dosing recommendations

### 6.3 Database Indexes Strategy

**Performance Optimization:**
- B-tree indexes on foreign keys
- Composite indexes on frequently queried columns (patient_id + created_at)
- GIN indexes on JSONB columns (FHIR bundles)
- Full-text search indexes on text columns
- Partial indexes with WHERE clauses (soft delete filtering)

**Index Maintenance:**
- Regular VACUUM ANALYZE
- Index usage monitoring
- Remove unused indexes

---

## 7. API Specifications

### 7.1 API Design Principles

- **RESTful:** Resource-oriented URLs
- **Versioned:** `/api/v1/` prefix
- **Consistent:** Standardized request/response formats
- **Documented:** OpenAPI/Swagger at `/docs`
- **Paginated:** Cursor-based pagination for lists
- **Filtered:** Query parameters for filtering
- **Secure:** JWT authentication required (except public endpoints)

### 7.2 API Base URL

- **Development:** `http://localhost:8000`
- **Production:** `https://api.medconnect.in`

### 7.3 Common Response Formats

#### Success Response

```json
{
  "data": { ... }
}
```

#### Error Response

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": [
      {
        "field": "email",
        "message": "Invalid email format"
      }
    ]
  }
}
```

#### Paginated Response

```json
{
  "data": [ ... ],
  "pagination": {
    "next_cursor": "uuid-of-last-item",
    "has_more": true,
    "limit": 20
  }
}
```

### 7.4 Authentication Endpoints

#### POST /api/v1/auth/signup

**Request:**
```json
{
  "email": "user@example.com",
  "phone": "+919876543210",
  "password": "SecurePassword123",
  "full_name": "John Doe",
  "role": "patient",
  "language_pref": "en"
}
```

**Response:**
```json
{
  "data": {
    "user": {
      "id": "uuid",
      "email": "user@example.com",
      "full_name": "John Doe",
      "role": "patient"
    },
    "access_token": "eyJ...",
    "refresh_token": "eyJ...",
    "token_type": "bearer"
  }
}
```

#### POST /api/v1/auth/login

**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123"
}
```

**Response:**
```json
{
  "data": {
    "access_token": "eyJ...",
    "refresh_token": "eyJ...",
    "token_type": "bearer",
    "user": { ... }
  }
}
```

#### POST /api/v1/auth/refresh

**Request:**
```json
{
  "refresh_token": "eyJ..."
}
```

**Response:**
```json
{
  "data": {
    "access_token": "eyJ..."
  }
}
```

#### GET /api/v1/auth/me

**Headers:** `Authorization: Bearer {access_token}`

**Response:**
```json
{
  "data": {
    "id": "uuid",
    "email": "user@example.com",
    "full_name": "John Doe",
    "role": "patient"
  }
}
```

### 7.5 Medical Records Endpoints

#### GET /api/v1/patients/timeline

**Authorization:** Patient role

**Query Parameters:**
- `search` (optional): Full-text search
- `record_type` (optional): Filter by type
- `cursor` (optional): Pagination cursor
- `limit` (optional): Results per page (default 20)

**Response:**
```json
{
  "data": [
    {
      "id": "uuid",
      "record_type": "consultation",
      "chief_complaint": "Fever and cough",
      "diagnosis": "Upper respiratory tract infection",
      "doctor": {
        "id": "uuid",
        "full_name": "Dr. Smith",
        "specialization": "General Medicine"
      },
      "created_at": "2026-02-25T10:30:00Z"
    }
  ],
  "pagination": { ... }
}
```

#### GET /api/v1/patients/records/{id}

**Authorization:** Patient (own records) or Doctor (created records)

**Response:**
```json
{
  "data": {
    "id": "uuid",
    "record_type": "consultation",
    "fhir_bundle": { ... },
    "chief_complaint": "Fever and cough",
    "diagnosis": "Upper respiratory tract infection",
    "notes": "Prescribed rest and fluids",
    "doctor": { ... },
    "created_at": "2026-02-25T10:30:00Z"
  }
}
```

#### POST /api/v1/doctors/records

**Authorization:** Doctor role

**Request:**
```json
{
  "patient_id": "uuid",
  "record_type": "consultation",
  "chief_complaint": "Fever and cough",
  "diagnosis": "Upper respiratory tract infection",
  "notes": "Prescribed rest and fluids",
  "fhir_bundle": { ... }
}
```

**Response:**
```json
{
  "data": {
    "id": "uuid",
    "record_type": "consultation",
    "patient_id": "uuid",
    "doctor_id": "uuid",
    "created_at": "2026-02-25T10:30:00Z"
  }
}
```

### 7.6 Prescription Endpoints

#### GET /api/v1/patients/prescriptions

**Authorization:** Patient role

**Response:**
```json
{
  "data": [
    {
      "id": "uuid",
      "doctor": {
        "full_name": "Dr. Smith",
        "specialization": "General Medicine"
      },
      "medicines": [
        {
          "name": "Paracetamol 500mg",
          "dosage": "1 tablet",
          "frequency": "Three times daily",
          "duration": "5 days"
        }
      ],
      "diagnosis": "Fever",
      "created_at": "2026-02-25T10:30:00Z",
      "valid_until": "2026-03-25"
    }
  ]
}
```

#### POST /api/v1/doctors/prescriptions

**Authorization:** Doctor role

**Request:**
```json
{
  "patient_id": "uuid",
  "medicines": [
    {
      "medicine_id": "uuid",
      "dosage": "1 tablet",
      "frequency": "TID",
      "duration": "5 days",
      "instructions": "Take after meals"
    }
  ],
  "diagnosis": "Upper respiratory tract infection",
  "notes": "Avoid cold foods",
  "valid_until": "2026-03-25"
}
```

**Response:**
```json
{
  "data": {
    "id": "uuid",
    "record_id": "uuid",
    "patient_id": "uuid",
    "doctor_id": "uuid",
    "medicines": [ ... ],
    "created_at": "2026-02-25T10:30:00Z"
  }
}
```

### 7.7 Medicine Endpoints

#### GET /api/v1/medicines/search

**Authorization:** Optional (public endpoint)

**Query Parameters:**
- `q` (required): Search query
- `type` (optional): salt, brand, all (default)
- `limit` (optional): Max results (default 20)

**Response:**
```json
{
  "data": {
    "salts": [
      {
        "salt_id": "uuid",
        "salt_name": "Paracetamol",
        "chemical_class": "Analgesic",
        "therapeutic_class": "Pain relief"
      }
    ],
    "brands": [
      {
        "brand_id": "uuid",
        "brand_name": "Crocin",
        "manufacturer": "GlaxoSmithKline",
        "salt_composition": "Paracetamol (500mg)"
      }
    ]
  }
}
```

#### GET /api/v1/salts/{salt_id}/strengths

**Authorization:** Optional

**Response:**
```json
{
  "data": [
    {
      "salt_strength_id": "uuid",
      "strength_value": 500,
      "strength_unit": "mg",
      "is_standard_strength": true
    },
    {
      "salt_strength_id": "uuid",
      "strength_value": 650,
      "strength_unit": "mg",
      "is_standard_strength": true
    }
  ]
}
```

#### GET /api/v1/salts/{salt_id}/brands

**Authorization:** Optional

**Query Parameters:**
- `strength_value` (optional): Filter by strength value
- `strength_unit` (optional): Filter by strength unit

**Response:**
```json
{
  "data": [
    {
      "brand_id": "uuid",
      "brand_name": "Crocin",
      "manufacturer": {
        "manufacturer_id": "uuid",
        "manufacturer_name": "GlaxoSmithKline"
      },
      "compositions": [
        {
          "salt_name": "Paracetamol",
          "strength_value": 500,
          "strength_unit": "mg"
        }
      ],
      "is_discontinued": false
    }
  ]
}
```

#### GET /api/v1/brands/{brand_id}

**Authorization:** Optional

**Response:**
```json
{
  "data": {
    "brand_id": "uuid",
    "brand_name": "Crocin",
    "manufacturer": { ... },
    "compositions": [
      {
        "salt_name": "Paracetamol",
        "strength_value": 500,
        "strength_unit": "mg",
        "sequence": 1
      }
    ],
    "salt_composition": "Paracetamol (500mg)",
    "is_discontinued": false,
    "created_at": "2025-01-01T00:00:00Z"
  }
}
```

#### GET /api/v1/brands/{brand_id}/alternatives

**Authorization:** Optional

**Response:**
```json
{
  "data": [
    {
      "brand_id": "uuid",
      "brand_name": "Dolo 650",
      "manufacturer": { ... },
      "compositions": [ ... ],
      "salt_composition": "Paracetamol (650mg)",
      "is_discontinued": false
    }
  ]
}
```

### 7.8 Drug Interaction Endpoints

#### POST /api/v1/interactions/check

**Authorization:** Doctor role recommended

**Request:**
```json
{
  "salt_ids": [
    "uuid-salt-1",
    "uuid-salt-2",
    "uuid-salt-3"
  ]
}
```

**Response:**
```json
{
  "data": [
    {
      "interaction_id": "uuid",
      "salt_1": {
        "id": "uuid",
        "name": "Aspirin"
      },
      "salt_2": {
        "id": "uuid",
        "name": "Warfarin"
      },
      "severity": "major",
      "effect": "Increased risk of bleeding",
      "mechanism": "Both inhibit platelet aggregation",
      "management": "Monitor INR closely. Consider alternative."
    }
  ]
}
```

#### GET /api/v1/salts/{salt_id}/interactions

**Authorization:** Optional

**Query Parameters:**
- `severity` (optional): Filter by severity

**Response:**
```json
{
  "data": [
    {
      "interaction_id": "uuid",
      "interacting_salt": {
        "id": "uuid",
        "name": "Warfarin"
      },
      "severity": "major",
      "effect": "Increased bleeding risk"
    }
  ]
}
```

### 7.9 Admin Endpoints

#### GET /api/v1/admin/manufacturers

**Authorization:** Admin role

**Response:**
```json
{
  "data": [
    {
      "manufacturer_id": "uuid",
      "manufacturer_name": "GlaxoSmithKline",
      "country": "India",
      "is_active": true
    }
  ]
}
```

#### POST /api/v1/admin/manufacturers

**Authorization:** Admin role

**Request:**
```json
{
  "manufacturer_name": "New Pharma Ltd",
  "country": "India",
  "license_number": "MH-123456"
}
```

#### GET /api/v1/admin/salts

**Authorization:** Admin role

**Response:**
```json
{
  "data": [
    {
      "salt_id": "uuid",
      "salt_name": "Paracetamol",
      "chemical_class": "Analgesic",
      "therapeutic_class": "Pain relief",
      "habit_forming": false,
      "schedule": "H"
    }
  ]
}
```

#### POST /api/v1/admin/salts

**Authorization:** Admin role

**Request:**
```json
{
  "salt_name": "New Active Ingredient",
  "description": "Description",
  "chemical_class_id": "uuid",
  "therapeutic_class_id": "uuid",
  "habit_forming": false,
  "schedule": "H"
}
```

### 7.10 Health Check Endpoint

#### GET /health

**Authorization:** None (public)

**Response:**
```json
{
  "status": "ok",
  "db": "ok",
  "medicine_db": "ok",
  "redis": "ok",
  "version": "0.1.0"
}
```

**Status Codes:**
- 200: All services healthy
- 503: One or more services degraded

---

## 8. User Interface Requirements

### 8.1 Design System

**Component Library:** shadcn/ui based on Radix UI primitives

**Styling:** Tailwind CSS utility-first framework

**Color Palette:**
- Primary: Blue (#3B82F6)
- Success: Green (#10B981)
- Warning: Yellow (#F59E0B)
- Error: Red (#EF4444)
- Neutral: Gray shades

**Typography:**
- Font: Inter (sans-serif)
- Headings: 24px, 20px, 18px, 16px
- Body: 14px
- Small: 12px

**Spacing:** 4px base unit (Tailwind default)

### 8.2 Responsive Design

**Breakpoints:**
- Mobile: < 640px
- Tablet: 640px - 1024px
- Desktop: > 1024px

**Requirements:**
- All pages must be fully functional on mobile
- Touch-friendly tap targets (min 44x44px)
- Readable text without zooming
- Proper viewport meta tag

### 8.3 Page Layouts

#### 8.3.1 Patient Timeline
- Header with search bar and filters
- Timeline view with card-based records
- Infinite scroll or load more pagination
- Empty state when no records
- Loading skeleton

#### 8.3.2 Prescription Form
- Medicine search with autocomplete
- Dynamic medicine list (add/remove)
- Drug interaction warnings (real-time)
- Alternative suggestions
- Save draft functionality
- Preview before submit

#### 8.3.3 Admin Dashboard
- Statistics cards (users, records, prescriptions)
- Recent activity feed
- Quick actions
- System health indicators
- Navigation sidebar

#### 8.3.4 Doctor Dashboard
- Patient list with search
- Appointment calendar
- Quick create buttons (record, prescription)
- Recent activity
- Verification status banner (if pending)

### 8.4 Forms and Validation

**Form Design:**
- Clear labels above inputs
- Placeholder text for hints
- Required field indicators (*)
- Inline validation on blur
- Error messages below fields
- Submit button disabled until valid
- Loading state on submit

**Validation Rules:**
- Client-side validation (instant feedback)
- Server-side validation (security)
- Clear error messages
- Field-specific validation

### 8.5 Loading States

**Patterns:**
- Skeleton loaders for content
- Spinner for actions (buttons)
- Progress bars for file uploads
- Optimistic UI updates where appropriate

### 8.6 Error Handling

**User-Friendly Errors:**
- Clear error messages
- Suggest corrective actions
- Avoid technical jargon
- Toast notifications for transient errors
- Error pages for critical failures

---

## 9. Integration Requirements

### 9.1 ABDM Integration (Planned)

#### 9.1.1 ABHA ID Creation and Linking

**Features:**
- Create ABHA ID via Aadhaar OTP
- Create ABHA ID via mobile OTP
- Link existing ABHA ID to MedConnect account
- Verify ABHA ID

**APIs:**
- ABDM M1 API: ABHA creation
- ABDM M2 API: ABHA verification
- ABDM M3 API: ABHA linking

#### 9.1.2 Health Information Provider (HIP)

**Features:**
- Register as HIP with ABDM
- Patient discovery
- Care context linking
- Consent request handling
- Health information push on consent

**Workflow:**
1. Patient links ABHA ID in MedConnect
2. MedConnect registers as HIP for patient
3. HIU requests patient data via ABDM
4. Patient grants consent in ABDM app
5. MedConnect receives consent notification
6. MedConnect pushes health records to ABDM
7. HIU fetches records from ABDM

#### 9.1.3 Health Information User (HIU)

**Features:**
- Discover patient records at other HIPs
- Request consent from patient
- Fetch health records on consent
- Display fetched records in timeline

**Workflow:**
1. Patient wants to share external records
2. Doctor initiates HIU discovery
3. ABDM returns available HIPs for patient
4. Doctor requests consent for specific HIPs
5. Patient approves in ABDM app
6. MedConnect fetches records from HIPs via ABDM
7. Records imported into patient timeline

#### 9.1.4 Consent Management

**Features:**
- View active consents
- Revoke consent
- Consent expiry handling
- Consent purpose tracking (healthcare, insurance, research)

**Consent Types:**
- One-time consent
- Time-bound consent (validity period)
- Purpose-specific consent

### 9.2 Keycloak Integration (Implemented)

**Features:**
- Single Sign-On (SSO)
- User federation
- Social login (future: Google, Facebook)
- Multi-factor authentication (future)

**Configuration:**
- Realm: medconnect
- Client ID: medconnect-backend (backend), medconnect-frontend (frontend)
- Protocol: OpenID Connect
- Token: JWT

### 9.3 Sentry Integration (Implemented)

**Features:**
- Error tracking
- Performance monitoring
- Release tracking
- User feedback

**Configuration:**
- Sample rate: 10% for transactions
- Environment: development, staging, production
- Scrubbing: Remove sensitive data (passwords, tokens)

### 9.4 SMS/Email Gateway (Planned)

**Use Cases:**
- OTP for phone verification
- Password reset emails
- Appointment reminders
- Prescription notifications

**Providers (Options):**
- SMS: Twilio, MSG91, Exotel
- Email: SendGrid, AWS SES

### 9.5 Payment Gateway (Future)

**Use Cases:**
- Patient premium subscription (₹49/month)
- Doctor consultation fees
- Report download fees

**Providers (Options):**
- Razorpay
- Paytm
- Stripe

### 9.6 Cloud Storage (Planned)

**Use Cases:**
- Document uploads (prescriptions, reports)
- Profile pictures
- Medical images

**Providers (Options):**
- AWS S3
- Google Cloud Storage
- Cloudflare R2

---

## 10. Security Requirements

### 10.1 Authentication and Authorization

**Authentication Mechanisms:**
- Email/Password (bcrypt hashed)
- Phone/Password (future)
- Social login (future: Google, Facebook)
- OTP-based login (future)

**Authorization:**
- Role-Based Access Control (RBAC)
- Roles: patient, doctor, admin
- Permissions enforced at API level
- Frontend guards for UI elements

### 10.2 Data Protection

**Encryption:**
- TLS 1.3 for data in transit
- Database-level encryption at rest
- Sensitive fields encrypted (future: field-level encryption for Aadhaar, etc.)

**Password Security:**
- bcrypt with cost factor 12
- Minimum 8 characters
- No password in logs or error messages
- Password reset via email/SMS OTP

**Session Management:**
- JWT tokens with short expiry
- Refresh token rotation
- Logout clears all tokens
- Session timeout: 15 minutes idle

### 10.3 API Security

**Rate Limiting:**
- Global: 100 requests/minute
- Auth endpoints: 10 requests/minute
- IP-based limiting

**CORS Policy:**
- Whitelist frontend origin
- Credentials allowed
- No wildcards in production

**Request Validation:**
- Input sanitization
- SQL injection prevention (parameterized queries)
- XSS prevention (escape output)
- CSRF tokens (future for cookie-based sessions)

**Security Headers:**
```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
Content-Security-Policy: default-src 'self'
```

### 10.4 Compliance and Audit

**Audit Logging:**
- All access to patient records logged
- User actions logged (login, logout, record creation)
- Failed login attempts logged
- Logs retained for 7 years

**Data Privacy:**
- Patient consent for data access
- Right to access data (export)
- Right to deletion (soft delete + anonymization)
- Data minimization principle

**Vulnerability Management:**
- Regular dependency updates
- Security scanning (Snyk, Dependabot)
- Penetration testing (annual)
- Bug bounty program (future)

---

## 11. Future Enhancements

### 11.1 Phase 2: AI Layer (Months 2-3)

#### 11.1.1 OCR for Prescription Images
- Upload prescription image
- Extract medicine names, dosages, instructions
- Verify extracted data
- Import to medicine list

**Technology:** Google Cloud Vision API

#### 11.1.2 Prescription Parser (LLM)
- Natural language prescription input
- Extract structured data (medicine, dosage, frequency)
- Suggest corrections

**Technology:** Groq LLM API

#### 11.1.3 Multi-Language Translation
- Translate prescriptions to regional languages
- Support for Hindi, Bengali, Tamil, Telugu, Marathi
- Display translated prescriptions

**Technology:** IndicTrans2 model

#### 11.1.4 Medicine Semantic Search
- Vector embeddings for medicines (pgvector)
- Semantic search (find similar medicines by indication)
- Improve autocomplete relevance

**Technology:** Sentence transformers, pgvector

### 11.2 Phase 3: ABDM Integration (Months 3-5)

**See Section 9.1 for detailed ABDM requirements**

**Key Features:**
- ABHA ID creation and linking
- Health Information Provider (HIP) module
- Health Information User (HIU) module
- Consent management
- QR-based record sharing
- M1, M2, M3 API integration

### 11.3 Phase 4: Scale and Mobile (Months 5+)

#### 11.3.1 Clinic Portal
- Multi-doctor clinics
- Shared patient pool
- Appointment scheduling
- Queue management
- Billing integration

#### 11.3.2 Family Vault
- Link family members
- View family health records
- Manage elderly/children health
- Emergency access

#### 11.3.3 Native Mobile App
- React Native (Expo)
- Push notifications
- Offline mode
- Camera integration (document upload)
- Biometric authentication

#### 11.3.4 Analytics and Insights
- Patient health trends
- Medication adherence tracking
- Personalized health tips
- Predictive analytics (risk scoring)

#### 11.3.5 Telemedicine
- Video consultation
- In-app chat
- Screen sharing (for reports)
- Prescription writing during call

**Technology:** WebRTC, Socket.io

---

## 12. Appendices

### 12.1 Glossary

| Term | Definition |
|------|------------|
| ABHA | Ayushman Bharat Health Account - unique health ID for Indian citizens |
| ABDM | Ayushman Bharat Digital Mission - national digital health ecosystem |
| FHIR | Fast Healthcare Interoperability Resources - standard for health data exchange |
| HIP | Health Information Provider - entity that stores health records |
| HIU | Health Information User - entity that requests health records |
| EMR | Electronic Medical Record - digital version of patient chart |
| API | Application Programming Interface (also Active Pharmaceutical Ingredient in pharma context) |
| Salt | Active pharmaceutical ingredient (API) |
| Brand | Commercial product name |
| Composition | Combination of salts with specific strengths |

### 12.2 Abbreviations

| Abbreviation | Full Form |
|--------------|-----------|
| TDD | Test-Driven Development |
| RBAC | Role-Based Access Control |
| CORS | Cross-Origin Resource Sharing |
| JWT | JSON Web Token |
| OTP | One-Time Password |
| SMS | Short Message Service |
| API | Application Programming Interface |
| REST | Representational State Transfer |
| CRUD | Create, Read, Update, Delete |
| UI | User Interface |
| UX | User Experience |
| SSO | Single Sign-On |
| MFA | Multi-Factor Authentication |

### 12.3 References

1. **FHIR R4 Specification:** https://hl7.org/fhir/R4/
2. **ABDM Documentation:** https://abdm.gov.in
3. **FastAPI Documentation:** https://fastapi.tiangolo.com
4. **Next.js Documentation:** https://nextjs.org/docs
5. **PostgreSQL Documentation:** https://www.postgresql.org/docs/
6. **Keycloak Documentation:** https://www.keycloak.org/documentation

### 12.4 Document Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-02-25 | MedConnect Team | Initial comprehensive SRS |

### 12.5 Jira Epic Summary

**Highest Priority:**
1. Medicine Database & Dataset (MD)
2. Admin Panel - Core Infrastructure (MD)

**High Priority:**
3. Admin Panel - Medicine Management (MD)
4. Admin Panel - User Management (MD)
5. Admin Panel - Doctor Verification (MD)
6. Prescription Enhancement (MD)

**Medium Priority:**
7. Patient Portal Enhancement (MD)
8. Doctor Portal Enhancement (MD)
9. ABDM Integration (MD)

**Detailed Jira Tickets:** See JIRA project MED

---

**End of Document**

**Document Status:** Active Development
**Next Review Date:** 2026-03-25
**Contact:** MedConnect Development Team
