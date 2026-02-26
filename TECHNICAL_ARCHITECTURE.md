# Technical Architecture Document
# MedConnect Healthcare Platform

**Version:** 1.0
**Date:** 2026-02-25
**Status:** Active Development

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture Diagrams](#2-architecture-diagrams)
3. [Component Design](#3-component-design)
4. [Data Flow](#4-data-flow)
5. [Technology Stack Deep Dive](#5-technology-stack-deep-dive)
6. [Infrastructure Architecture](#6-infrastructure-architecture)
7. [Security Architecture](#7-security-architecture)
8. [Scalability and Performance](#8-scalability-and-performance)
9. [Deployment Architecture](#9-deployment-architecture)
10. [Monitoring and Observability](#10-monitoring-and-observability)

---

## 1. System Overview

### 1.1 Architecture Style

MedConnect follows a **three-tier layered architecture** with clear separation of concerns:

```
┌─────────────────────────────────────────┐
│         Presentation Layer              │
│  (Next.js Frontend + Mobile App)        │
└────────────────┬────────────────────────┘
                 │ HTTPS/REST
┌────────────────▼────────────────────────┐
│          Application Layer              │
│  (FastAPI Backend + Business Logic)     │
└────────────────┬────────────────────────┘
                 │ SQL/Redis
┌────────────────▼────────────────────────┐
│            Data Layer                   │
│  (PostgreSQL + Redis + File Storage)    │
└─────────────────────────────────────────┘
```

### 1.2 Key Architectural Principles

1. **Separation of Concerns:** Clear boundaries between layers
2. **Single Responsibility:** Each component has one primary purpose
3. **DRY (Don't Repeat Yourself):** Reusable services and utilities
4. **SOLID Principles:** Applied to service and model design
5. **API-First Design:** Frontend consumes well-defined REST APIs
6. **Database per Service:** Separate databases for EMR and Medicine data
7. **Stateless Backend:** Enables horizontal scaling
8. **Eventual Consistency:** For non-critical operations

### 1.3 Design Patterns

**Backend Patterns:**
- **Repository Pattern:** Service layer abstracts database access
- **Dependency Injection:** FastAPI's built-in DI container
- **Factory Pattern:** Model creation and FHIR bundle generation
- **Strategy Pattern:** Different authentication strategies (email, phone, OTP)
- **Observer Pattern:** Event-driven notifications (future)

**Frontend Patterns:**
- **Component Composition:** Reusable React components
- **Container/Presentational:** Smart containers manage state, dumb components render
- **Higher-Order Components:** Authentication guards, error boundaries
- **Custom Hooks:** Reusable stateful logic
- **Render Props:** Flexible component composition

---

## 2. Architecture Diagrams

### 2.1 High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Internet                             │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│                    Nginx (Reverse Proxy)                     │
│  - TLS Termination   - Rate Limiting   - Load Balancing     │
└─────────┬──────────────────────────────────┬────────────────┘
          │                                  │
┌─────────▼──────────┐            ┌─────────▼──────────────┐
│   Frontend (Next)  │            │   Backend (FastAPI)    │
│  Port 3000         │            │   Port 8000            │
│  - React Pages     │            │   - REST API           │
│  - shadcn/ui       │            │   - Business Logic     │
│  - TanStack Query  │            │   - Auth Service       │
└────────────────────┘            └─────────┬──────────────┘
                                            │
                    ┌───────────────────────┼───────────────────┐
                    │                       │                   │
          ┌─────────▼─────────┐  ┌─────────▼────────┐  ┌──────▼──────┐
          │  PostgreSQL (Main)│  │ PostgreSQL (Med) │  │    Redis    │
          │  - Users          │  │ - Salts          │  │  - Cache    │
          │  - Records        │  │ - Brands         │  │  - Sessions │
          │  - Prescriptions  │  │ - Interactions   │  └─────────────┘
          └───────────────────┘  └──────────────────┘
                    │
          ┌─────────▼─────────┐
          │     Keycloak      │
          │  - SSO            │
          │  - User Federation│
          └───────────────────┘
```

### 2.2 Backend Component Architecture

```
backend/
├── app/
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Configuration management
│   ├── database.py          # Database connections
│   │
│   ├── dependencies.py      # Dependency injection
│   │   ├── get_db()
│   │   ├── get_current_user()
│   │   ├── require_role()
│   │
│   ├── routers/             # API endpoints (controllers)
│   │   ├── auth.py
│   │   ├── patients.py
│   │   ├── doctors.py
│   │   ├── medicines_emr.py
│   │   ├── interactions.py
│   │   └── admin/
│   │
│   ├── services/            # Business logic
│   │   ├── auth_service.py
│   │   ├── record_service.py
│   │   ├── prescription_service.py
│   │   ├── salt_service.py
│   │   ├── brand_service.py
│   │   └── medicine_search_service.py
│   │
│   ├── models/              # SQLAlchemy ORM models
│   │   ├── user.py
│   │   ├── doctor.py
│   │   ├── medical_record.py
│   │   ├── prescription.py
│   │   └── medicine/        # Separate medicine models
│   │
│   ├── schemas/             # Pydantic schemas (DTOs)
│   │   ├── auth.py
│   │   ├── user.py
│   │   ├── record.py
│   │   ├── prescription.py
│   │   └── medicine_emr.py
│   │
│   └── utils/               # Utilities
│       ├── security.py      # JWT, bcrypt
│       ├── fhir.py          # FHIR bundle generation
│       └── validators.py
│
├── alembic/                 # Main DB migrations
├── alembic_medicine/        # Medicine DB migrations
└── tests/                   # Test suite
```

### 2.3 Frontend Component Architecture

```
frontend/src/
├── app/                     # Next.js App Router
│   ├── layout.tsx           # Root layout
│   ├── page.tsx             # Landing page
│   ├── login/
│   ├── signup/
│   ├── patient/
│   │   ├── timeline/
│   │   └── records/[id]/
│   └── doctor/
│       ├── dashboard/
│       ├── records/new/
│       └── prescriptions/new/
│
├── components/              # React components
│   ├── ui/                  # shadcn/ui components
│   │   ├── button.tsx
│   │   ├── input.tsx
│   │   ├── card.tsx
│   │   └── ...
│   ├── layout/
│   │   ├── navbar.tsx
│   │   ├── sidebar.tsx
│   │   └── auth-guard.tsx
│   ├── medicine/
│   │   ├── DrugInteractionWarning.tsx
│   │   ├── AlternativeMedicines.tsx
│   │   └── PrescriptionFormExample.tsx
│   └── forms/
│
├── hooks/                   # Custom React hooks
│   ├── useDrugInteractions.ts
│   └── useAuth.ts
│
├── lib/                     # Utilities
│   ├── api.ts               # Axios client
│   ├── auth.ts              # Auth helpers
│   └── utils.ts             # General utilities
│
└── stores/                  # State management
    └── auth-store.ts        # Zustand store
```

### 2.4 Database Architecture

```
┌─────────────────────────────────────────────────────┐
│              PostgreSQL Instance                     │
│                                                      │
│  ┌──────────────────┐      ┌────────────────────┐  │
│  │  medconnect DB   │      │  medconnect_emr DB │  │
│  │  (Main Schema)   │      │  (Medicine Schema) │  │
│  │                  │      │                    │  │
│  │  - users         │      │  - salts           │  │
│  │  - doctors       │      │  - salt_strengths  │  │
│  │  - medical_rec.. │      │  - brands          │  │
│  │  - prescriptions │      │  - manufacturers   │  │
│  │  - ...           │      │  - interactions    │  │
│  │                  │      │  - ...             │  │
│  └──────────────────┘      └────────────────────┘  │
│                                                      │
│  Extensions:                                         │
│  - pgvector (vector embeddings)                     │
│  - pg_trgm (fuzzy search)                           │
│  - uuid-ossp (UUID generation)                      │
└─────────────────────────────────────────────────────┘
```

---

## 3. Component Design

### 3.1 Authentication Flow

```
┌────────┐                ┌─────────┐              ┌──────────┐
│ Client │                │ FastAPI │              │ Keycloak │
└───┬────┘                └────┬────┘              └────┬─────┘
    │                          │                        │
    │  POST /auth/login        │                        │
    ├─────────────────────────>│                        │
    │  {email, password}       │                        │
    │                          │                        │
    │                          │  Verify with Keycloak  │
    │                          ├───────────────────────>│
    │                          │                        │
    │                          │<───────────────────────┤
    │                          │  User verified         │
    │                          │                        │
    │                          │  Query user from DB    │
    │                          ├───────────┐            │
    │                          │           │            │
    │                          │<──────────┘            │
    │                          │                        │
    │                          │  Generate JWT tokens   │
    │                          ├───────────┐            │
    │                          │           │            │
    │                          │<──────────┘            │
    │                          │                        │
    │<─────────────────────────┤                        │
    │  {access_token,          │                        │
    │   refresh_token}         │                        │
    │                          │                        │
    │  Subsequent requests     │                        │
    │  Authorization: Bearer   │                        │
    ├─────────────────────────>│                        │
    │                          │                        │
    │                          │  Verify JWT signature  │
    │                          ├───────────┐            │
    │                          │           │            │
    │                          │<──────────┘            │
    │                          │                        │
    │<─────────────────────────┤                        │
    │  Response                │                        │
```

### 3.2 Prescription Creation Flow

```
┌────────┐         ┌─────────┐         ┌──────────┐         ┌─────────┐
│ Doctor │         │ FastAPI │         │   DB     │         │  Redis  │
└───┬────┘         └────┬────┘         └────┬─────┘         └────┬────┘
    │                   │                   │                    │
    │  POST /prescr..   │                   │                    │
    ├──────────────────>│                   │                    │
    │  {medicines[]}    │                   │                    │
    │                   │                   │                    │
    │                   │  Check interactions                    │
    │                   ├───────────────────┤                    │
    │                   │                   │                    │
    │                   │<──────────────────┤                    │
    │                   │  Interactions     │                    │
    │                   │                   │                    │
    │                   │  If major/contra: │                    │
    │                   │  Warn doctor      │                    │
    │                   │                   │                    │
    │                   │  Create medical   │                    │
    │                   │  record (auto)    │                    │
    │                   ├──────────────────>│                    │
    │                   │                   │                    │
    │                   │  Create prescription                   │
    │                   ├──────────────────>│                    │
    │                   │                   │                    │
    │                   │  Generate FHIR    │                    │
    │                   │  bundle           │                    │
    │                   ├───────┐           │                    │
    │                   │       │           │                    │
    │                   │<──────┘           │                    │
    │                   │                   │                    │
    │                   │  Cache for patient│                    │
    │                   ├───────────────────────────────────────>│
    │                   │                   │                    │
    │<──────────────────┤                   │                    │
    │  Prescription     │                   │                    │
    │  created          │                   │                    │
```

### 3.3 Medicine Search Flow (with Caching)

```
┌────────┐         ┌─────────┐         ┌─────────┐         ┌──────────┐
│ Client │         │ FastAPI │         │  Redis  │         │ Medicine │
│        │         │         │         │  Cache  │         │    DB    │
└───┬────┘         └────┬────┘         └────┬────┘         └────┬─────┘
    │                   │                   │                   │
    │  GET /medicines/  │                   │                   │
    │  search?q=para..  │                   │                   │
    ├──────────────────>│                   │                   │
    │                   │                   │                   │
    │                   │  Check cache      │                   │
    │                   ├──────────────────>│                   │
    │                   │                   │                   │
    │                   │<──────────────────┤                   │
    │                   │  MISS             │                   │
    │                   │                   │                   │
    │                   │  Query medicine DB                    │
    │                   ├───────────────────────────────────────>│
    │                   │  Full-text search │                   │
    │                   │                   │                   │
    │                   │<───────────────────────────────────────┤
    │                   │  Results          │                   │
    │                   │                   │                   │
    │                   │  Store in cache (TTL: 5min)           │
    │                   ├──────────────────>│                   │
    │                   │                   │                   │
    │<──────────────────┤                   │                   │
    │  Search results   │                   │                   │
    │                   │                   │                   │
    │  (Subsequent req) │                   │                   │
    ├──────────────────>│                   │                   │
    │                   │                   │                   │
    │                   │  Check cache      │                   │
    │                   ├──────────────────>│                   │
    │                   │                   │                   │
    │                   │<──────────────────┤                   │
    │                   │  HIT              │                   │
    │                   │                   │                   │
    │<──────────────────┤                   │                   │
    │  Cached results   │                   │                   │
```

---

## 4. Data Flow

### 4.1 Patient Timeline Request

```
1. Patient navigates to /patient/timeline
2. Frontend: AuthGuard checks authentication
3. Frontend: TanStack Query initiates request
4. API: GET /api/v1/patients/timeline?search=fever&limit=20
5. Backend: Verify JWT, extract patient_id
6. Backend: RecordService.get_patient_timeline()
7. Database: SELECT with full-text search, pagination
8. Backend: Transform to response schema
9. Frontend: Display timeline with records
10. Frontend: Cache response (stale-while-revalidate)
```

### 4.2 Create Prescription Workflow

```
1. Doctor fills prescription form
2. Frontend: Auto-checks drug interactions (useDrugInteractions hook)
3. Frontend: Displays warnings if interactions found
4. Doctor: Reviews warnings, proceeds
5. API: POST /api/v1/doctors/prescriptions
6. Backend: Verify doctor authorization
7. Backend: Validate patient exists
8. Backend: Check drug interactions (severity validation)
9. Backend: Create MedicalRecord automatically
10. Backend: Create Prescription linked to record
11. Backend: Generate FHIR MedicationRequest bundle
12. Database: Insert record and prescription (transaction)
13. Backend: Invalidate patient cache in Redis
14. Frontend: Redirect to prescription detail
15. Frontend: Refetch patient timeline
```

### 4.3 Medicine Autocomplete

```
1. User types "para" in medicine search
2. Frontend: Debounce input (500ms)
3. API: GET /api/v1/medicines/search?q=para&limit=20
4. Backend: Check Redis cache (key: "medicine:search:para")
5. If CACHE HIT: Return cached results (< 10ms)
6. If CACHE MISS:
   a. Query medicine DB with full-text search
   b. Sort by relevance
   c. Limit to 20 results
   d. Store in Redis (TTL: 5 minutes)
   e. Return results (< 100ms)
7. Frontend: Display dropdown with results
8. User selects medicine
9. Frontend: Add to prescription form
```

---

## 5. Technology Stack Deep Dive

### 5.1 Backend Stack

#### FastAPI
- **Version:** 0.115+
- **Purpose:** Modern, fast web framework for building APIs
- **Key Features:**
  - Automatic OpenAPI documentation
  - Built-in request validation (Pydantic)
  - Dependency injection
  - Async support (ASGI)
  - Type hints for IDE support

**Configuration:**
```python
app = FastAPI(
    title="MedConnect API",
    description="EMR + Patient Portal",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)
```

#### SQLAlchemy
- **Version:** 2.0
- **Purpose:** ORM and database toolkit
- **Features Used:**
  - Async engine (asyncpg driver)
  - Declarative base
  - Relationships (lazy/eager loading)
  - Connection pooling

**Connection Pool:**
```python
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True
)
```

#### Alembic
- **Purpose:** Database migrations
- **Features:**
  - Reversible migrations
  - Auto-generation from models
  - Multi-database support (main + medicine)

**Migration Structure:**
```
alembic/versions/
├── 001_initial_schema.py
├── 002_add_vitals.py
└── ...

alembic_medicine/versions/
├── 8e7b05567dfb_create_emr_medicine_schema_v2.py
└── ...
```

### 5.2 Frontend Stack

#### Next.js
- **Version:** 14
- **Purpose:** React framework with SSR, routing
- **Features Used:**
  - App Router (file-based routing)
  - Server Components (future)
  - Image optimization
  - Code splitting

**Routing:**
```
app/
├── page.tsx              → /
├── login/page.tsx        → /login
├── patient/
│   └── timeline/page.tsx → /patient/timeline
└── doctor/
    └── dashboard/page.tsx → /doctor/dashboard
```

#### TanStack Query
- **Version:** 5.x
- **Purpose:** Server state management, caching
- **Features:**
  - Automatic background refetching
  - Cache invalidation
  - Optimistic updates
  - Stale-while-revalidate

**Configuration:**
```typescript
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30000, // 30 seconds
      cacheTime: 300000, // 5 minutes
      refetchOnWindowFocus: false,
    },
  },
});
```

#### Zustand
- **Version:** 4.x
- **Purpose:** Lightweight state management
- **Use Cases:**
  - Auth state (user, tokens)
  - UI state (modals, sidebars)

**Store Example:**
```typescript
const useAuthStore = create<AuthState>((set) => ({
  user: null,
  accessToken: null,
  setUser: (user) => set({ user }),
  logout: () => set({ user: null, accessToken: null }),
}));
```

### 5.3 Database Stack

#### PostgreSQL
- **Version:** 16
- **Extensions:**
  - **pgvector:** Vector similarity search (medicine embeddings)
  - **pg_trgm:** Fuzzy text search
  - **uuid-ossp:** UUID generation

**Performance Tuning:**
```sql
-- Shared buffers (25% of RAM)
shared_buffers = 4GB

-- Effective cache (50-75% of RAM)
effective_cache_size = 12GB

-- Work mem (per connection)
work_mem = 50MB

-- Maintenance work mem
maintenance_work_mem = 1GB

-- Max connections
max_connections = 200
```

#### Redis
- **Version:** 7
- **Use Cases:**
  - Session storage
  - API response caching
  - Rate limiting counters
  - Medicine search cache

**Cache Strategy:**
```
Medicine Search: TTL 5 minutes
Patient Timeline: TTL 1 minute (invalidate on new record)
User Profile: TTL 10 minutes (invalidate on update)
```

---

## 6. Infrastructure Architecture

### 6.1 Docker Compose Setup

```yaml
services:
  postgres:
    image: postgres:16
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      POSTGRES_USER: medconnect
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: medconnect
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U medconnect"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s

  keycloak:
    image: quay.io/keycloak/keycloak:latest
    environment:
      KC_DB: postgres
      KC_DB_URL: jdbc:postgresql://postgres:5432/medconnect
      KC_DB_SCHEMA: keycloak
    command: start-dev --import-realm --health-enabled=true
    depends_on:
      - postgres

  backend:
    build: ./backend
    volumes:
      - ./backend:/app
    environment:
      DATABASE_URL: ${DATABASE_URL}
      REDIS_URL: ${REDIS_URL}
    command: >
      sh -c "alembic upgrade head &&
             uvicorn app.main:app --host 0.0.0.0 --reload"
    depends_on:
      - postgres
      - redis
      - keycloak

  frontend:
    build: ./frontend
    volumes:
      - ./frontend:/app
      - /app/node_modules
    environment:
      NEXT_PUBLIC_API_URL: ${API_URL}
    depends_on:
      - backend

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
    depends_on:
      - backend
      - frontend
```

### 6.2 Production Deployment (VPS/Cloud)

```
┌─────────────────────────────────────────────────────────┐
│                   Load Balancer (Nginx)                 │
│                 SSL Termination (Let's Encrypt)         │
└────────────┬───────────────────────────┬────────────────┘
             │                           │
┌────────────▼──────────┐   ┌───────────▼─────────────┐
│  Backend Instance 1   │   │  Backend Instance 2     │
│  (Docker Container)   │   │  (Docker Container)     │
└───────────────────────┘   └─────────────────────────┘
             │                           │
             └──────────┬────────────────┘
                        │
        ┌───────────────┼───────────────────┐
        │               │                   │
┌───────▼──────┐  ┌─────▼──────┐  ┌────────▼────────┐
│  PostgreSQL  │  │   Redis    │  │  File Storage   │
│  (Primary)   │  │  (Cluster) │  │  (S3/CloudFlare)│
└──────────────┘  └────────────┘  └─────────────────┘
        │
┌───────▼──────┐
│  PostgreSQL  │
│  (Replica)   │
│  (Read-only) │
└──────────────┘
```

### 6.3 Scaling Strategy

**Horizontal Scaling:**
- **Backend:** Multiple FastAPI instances behind load balancer
- **Database:** Read replicas for read-heavy operations
- **Redis:** Redis Cluster for high availability

**Vertical Scaling:**
- **Database:** Increase RAM for larger shared_buffers
- **Redis:** Increase maxmemory for larger cache

**Auto-Scaling Triggers:**
- CPU > 70% for 5 minutes
- Memory > 80% for 5 minutes
- Request queue length > 100

---

## 7. Security Architecture

### 7.1 Defense in Depth

```
Layer 1: Network Security
  - Firewall rules (allow only 80, 443)
  - DDoS protection (Cloudflare/AWS Shield)

Layer 2: Application Gateway
  - Nginx rate limiting
  - Request size limits (10MB)
  - Security headers

Layer 3: Authentication
  - JWT with short expiry (15 minutes)
  - Refresh token rotation
  - Keycloak integration

Layer 4: Authorization
  - Role-based access control (RBAC)
  - Resource-level permissions
  - Dependency injection guards

Layer 5: Data Protection
  - TLS 1.3 encryption in transit
  - Database encryption at rest
  - Field-level encryption (sensitive data)

Layer 6: Audit and Monitoring
  - Access logs
  - Audit trail (all patient record access)
  - Sentry error tracking
```

### 7.2 Security Headers (Nginx)

```nginx
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "DENY" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';" always;
add_header Referrer-Policy "no-referrer-when-downgrade" always;
add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;
```

### 7.3 JWT Token Structure

```json
{
  "header": {
    "alg": "RS256",
    "typ": "JWT"
  },
  "payload": {
    "sub": "user-uuid",
    "email": "user@example.com",
    "role": "patient",
    "exp": 1709123456,
    "iat": 1709122556,
    "jti": "token-uuid"
  },
  "signature": "..."
}
```

**Token Lifecycle:**
1. User logs in
2. Backend generates access token (15 min) + refresh token (7 days)
3. Frontend stores in memory (access) + httpOnly cookie (refresh)
4. Access token used for API requests
5. On expiry, use refresh token to get new access token
6. Refresh token rotated on each use (prevent replay)
7. On logout, blacklist refresh token (Redis)

---

## 8. Scalability and Performance

### 8.1 Database Optimization

**Indexing Strategy:**
```sql
-- Composite index for patient timeline
CREATE INDEX idx_records_patient_date
ON medical_records(patient_id, created_at DESC)
WHERE deleted_at IS NULL;

-- GIN index for JSONB full-text search
CREATE INDEX idx_records_fhir
ON medical_records USING GIN(fhir_bundle);

-- Full-text search index
CREATE INDEX idx_records_search
ON medical_records USING GIN(
  to_tsvector('english',
    coalesce(chief_complaint, '') || ' ' ||
    coalesce(diagnosis, '') || ' ' ||
    coalesce(notes, '')
  )
);
```

**Query Optimization:**
```python
# Bad: N+1 queries
records = session.query(MedicalRecord).all()
for record in records:
    print(record.doctor.full_name)  # Lazy load for each!

# Good: Eager loading
records = session.query(MedicalRecord)\
    .options(selectinload(MedicalRecord.doctor))\
    .all()
for record in records:
    print(record.doctor.full_name)  # Already loaded!
```

**Connection Pooling:**
```python
# SQLAlchemy pool configuration
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,          # Min connections
    max_overflow=10,       # Extra connections under load
    pool_timeout=30,       # Wait 30s for connection
    pool_recycle=3600,     # Recycle connections every hour
    pool_pre_ping=True     # Check connection before use
)
```

### 8.2 Caching Strategy

**Multi-Level Caching:**

```
Level 1: Browser Cache (Static Assets)
  - JS/CSS bundles: 1 year
  - Images: 1 year
  - HTML: no-cache

Level 2: CDN Cache (Cloudflare)
  - Static assets: 1 month
  - API responses: no-cache

Level 3: Redis Cache (Application)
  - Medicine search: 5 minutes
  - User profile: 10 minutes
  - Patient timeline: 1 minute (invalidate on update)

Level 4: Database Query Cache (PostgreSQL)
  - Materialized views (future)
  - Prepared statements
```

**Cache Invalidation:**
```python
# Create prescription -> Invalidate patient timeline cache
@router.post("/prescriptions")
async def create_prescription(prescription: PrescriptionCreate, redis: Redis):
    # Create prescription
    new_prescription = await prescription_service.create(prescription)

    # Invalidate cache
    await redis.delete(f"patient:timeline:{prescription.patient_id}")

    return new_prescription
```

### 8.3 Performance Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| API Response Time (p95) | < 500ms | Sentry APM |
| Medicine Search | < 100ms | Custom logging |
| Page Load (TTI) | < 3s on 3G | Lighthouse |
| Database Query | < 200ms | pg_stat_statements |
| Cache Hit Rate | > 80% | Redis INFO |
| Concurrent Users | 1,000 | Load testing (Locust) |

---

## 9. Deployment Architecture

### 9.1 CI/CD Pipeline

```
┌─────────────┐
│  Git Push   │
│  to main    │
└──────┬──────┘
       │
┌──────▼──────────┐
│  GitHub Actions │
│  - Lint         │
│  - Type check   │
│  - Unit tests   │
└──────┬──────────┘
       │
┌──────▼──────────┐
│  Build Docker   │
│  Images         │
│  - Backend      │
│  - Frontend     │
└──────┬──────────┘
       │
┌──────▼──────────┐
│  Push to        │
│  Registry       │
│  (Docker Hub)   │
└──────┬──────────┘
       │
┌──────▼──────────┐
│  Deploy to      │
│  Staging        │
│  - Run migrations
│  - Health check │
└──────┬──────────┘
       │
┌──────▼──────────┐
│  Integration    │
│  Tests          │
│  (Staging)      │
└──────┬──────────┘
       │
┌──────▼──────────┐
│  Manual         │
│  Approval       │
│  (Production)   │
└──────┬──────────┘
       │
┌──────▼──────────┐
│  Deploy to      │
│  Production     │
│  - Blue/Green   │
│  - Health check │
│  - Auto-rollback│
└─────────────────┘
```

### 9.2 Database Migration Strategy

```bash
# Pre-deployment
1. Backup production database
2. Test migration on staging
3. Verify rollback procedure

# Deployment
1. Stop writes (maintenance mode) - optional for breaking changes
2. Run migration: alembic upgrade head
3. Verify migration success
4. Restart backend
5. Health check
6. Resume writes

# Rollback (if needed)
1. alembic downgrade -1
2. Restore from backup (last resort)
```

### 9.3 Zero-Downtime Deployment

**Blue-Green Deployment:**
```
1. Current (Blue): Serving traffic
2. Deploy new version to Green environment
3. Run health checks on Green
4. Switch traffic to Green (Nginx upstream)
5. Monitor for errors
6. If errors: Switch back to Blue
7. If stable: Decommission Blue
```

---

## 10. Monitoring and Observability

### 10.1 Three Pillars of Observability

**1. Metrics (What is happening?)**
- Request rate, error rate, duration (RED metrics)
- Database connections, query performance
- Cache hit/miss rates
- Memory and CPU usage

**2. Logs (Why is it happening?)**
- Structured JSON logs (structlog)
- Request/response logs
- Error logs with stack traces
- Audit logs (patient record access)

**3. Traces (Where is it happening?)**
- Distributed tracing (future: OpenTelemetry)
- Request flow across services
- Database query traces
- External API call traces

### 10.2 Monitoring Stack

```
┌─────────────────────────────────────────┐
│         Application (FastAPI)           │
│  - structlog (JSON logs)                │
│  - Sentry SDK (errors + APM)            │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│            Sentry.io                    │
│  - Error tracking                       │
│  - Performance monitoring (APM)         │
│  - Release tracking                     │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│        System Logs (stdout)             │
│  → Docker logs                          │
│  → CloudWatch / Datadog                 │
└─────────────────────────────────────────┘
```

### 10.3 Health Checks

**Endpoint:** `GET /health`

**Checks:**
```python
async def health():
    status = {
        "status": "ok",
        "db": await check_database(),
        "medicine_db": await check_medicine_db(),
        "redis": await check_redis(),
        "version": "0.1.0"
    }

    all_ok = all(v == "ok" for k, v in status.items() if k != "version")

    return JSONResponse(
        status_code=200 if all_ok else 503,
        content=status
    )
```

**Monitoring:**
- Uptime monitoring (Pingdom, UptimeRobot)
- Alert if health check fails 3 consecutive times
- Auto-restart container on failure

### 10.4 Alerting

**Critical Alerts (PagerDuty):**
- Database connection failures
- Error rate > 5%
- Response time p95 > 2 seconds
- Health check failures

**Warning Alerts (Email/Slack):**
- Error rate > 1%
- Cache hit rate < 70%
- Disk space < 20%
- Certificate expiring < 30 days

---

**End of Document**

**Last Updated:** 2026-02-25
**Maintained By:** MedConnect Development Team
