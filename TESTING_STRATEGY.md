# Testing Strategy Document
# MedConnect Healthcare Platform

**Version:** 1.0
**Date:** 2026-02-25
**Status:** Active Development

---

## Table of Contents

1. [Testing Philosophy](#1-testing-philosophy)
2. [Testing Pyramid](#2-testing-pyramid)
3. [Test Types](#3-test-types)
4. [Backend Testing](#4-backend-testing)
5. [Frontend Testing](#5-frontend-testing)
6. [Integration Testing](#6-integration-testing)
7. [End-to-End Testing](#7-end-to-end-testing)
8. [Performance Testing](#8-performance-testing)
9. [Security Testing](#9-security-testing)
10. [Test Data Management](#10-test-data-management)
11. [CI/CD Integration](#11-cicd-integration)
12. [Test Metrics and Coverage](#12-test-metrics-and-coverage)

---

## 1. Testing Philosophy

### 1.1 Core Principles

1. **Test-Driven Development (TDD):** Write tests before implementation code
2. **Confidence over Coverage:** Tests should provide confidence, not just coverage percentages
3. **Fast Feedback:** Tests should run quickly to enable rapid iteration
4. **Isolation:** Each test should be independent and not affect others
5. **Maintainability:** Tests should be easy to understand and maintain
6. **Realistic Data:** Use realistic test data that mirrors production

### 1.2 Testing Goals

- **Code Coverage:** Maintain > 80% coverage for backend, > 70% for frontend
- **Bug Detection:** Catch bugs before production deployment
- **Regression Prevention:** Ensure new changes don't break existing functionality
- **Documentation:** Tests serve as living documentation of system behavior
- **Confidence:** Enable safe refactoring and feature additions

### 1.3 When to Write Tests

**Always Test:**
- Critical business logic (prescription creation, drug interactions)
- Security-sensitive code (authentication, authorization)
- Data validation and transformations
- Complex algorithms (FHIR bundle generation)
- API endpoints
- Database queries

**Optional Testing:**
- Simple CRUD operations (low business logic)
- Trivial getters/setters
- UI component styling (visual regression tests instead)

---

## 2. Testing Pyramid

```
          ┌─────────────┐
          │     E2E     │  10%  - Full user workflows
          │   (Slow)    │        - Critical paths only
          └─────────────┘
         ┌───────────────┐
         │  Integration  │  20%  - API + DB interactions
         │   (Medium)    │        - Service layer tests
         └───────────────┘
        ┌─────────────────┐
        │      Unit       │  70%  - Functions, methods, utils
        │     (Fast)      │        - Business logic
        └─────────────────┘
```

**Distribution:**
- **Unit Tests:** 70% - Fast, isolated, test individual functions/methods
- **Integration Tests:** 20% - Medium speed, test component interactions
- **E2E Tests:** 10% - Slow, test complete user workflows

---

## 3. Test Types

### 3.1 Unit Tests

**Purpose:** Test individual functions/methods in isolation

**Characteristics:**
- Fast (< 1ms per test)
- No external dependencies (mock databases, APIs)
- Test single responsibility
- High code coverage

**Example:**
```python
def test_hash_password():
    password = "SecurePassword123"
    hashed = hash_password(password)
    assert verify_password(password, hashed)
    assert not verify_password("WrongPassword", hashed)
```

### 3.2 Integration Tests

**Purpose:** Test interaction between components

**Characteristics:**
- Medium speed (< 100ms per test)
- Real database (test database)
- Real Redis (or mock)
- Test service layer + database

**Example:**
```python
def test_create_prescription_service(db_session):
    # Real database interaction
    prescription = prescription_service.create(
        patient_id=patient.id,
        doctor_id=doctor.id,
        medicines=[...]
    )
    assert prescription.id is not None
    assert db_session.query(Prescription).count() == 1
```

### 3.3 End-to-End (E2E) Tests

**Purpose:** Test complete user workflows

**Characteristics:**
- Slow (1-10 seconds per test)
- Full stack (frontend + backend + database)
- Simulate real user interactions
- Test critical paths only

**Example:**
```typescript
test('Doctor creates prescription for patient', async () => {
  await login('doctor@example.com', 'password');
  await navigateTo('/doctor/prescriptions/new');
  await searchMedicine('Paracetamol');
  await selectMedicine('Crocin 500mg');
  await fillDosage('1 tablet, TID, 5 days');
  await submitPrescription();
  await expect(page).toHaveURL('/prescriptions/success');
});
```

### 3.4 Performance Tests

**Purpose:** Validate system performance under load

**Characteristics:**
- Slow (minutes to hours)
- Test load, stress, spike scenarios
- Measure response times, throughput, resource usage

### 3.5 Security Tests

**Purpose:** Identify security vulnerabilities

**Characteristics:**
- Automated (dependency scanning, SAST)
- Manual (penetration testing)
- Continuous (on every commit)

---

## 4. Backend Testing

### 4.1 Test Framework

**Stack:**
- **pytest:** Test framework
- **pytest-asyncio:** Async test support
- **httpx:** HTTP client for API testing
- **faker:** Generate realistic test data
- **factory_boy:** Model factories

**Setup:**
```python
# conftest.py
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from app.database import Base
from app.main import app

@pytest.fixture
async def db_session():
    # Create test database
    engine = create_async_engine("postgresql+asyncpg://...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSession(engine) as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
def client():
    return TestClient(app)
```

### 4.2 Unit Test Examples

#### 4.2.1 Utility Functions

```python
# tests/test_security.py
from app.utils.security import hash_password, verify_password, create_access_token

def test_hash_password():
    password = "SecurePassword123"
    hashed = hash_password(password)

    assert hashed != password
    assert len(hashed) > 0
    assert verify_password(password, hashed)

def test_verify_password_wrong():
    password = "SecurePassword123"
    hashed = hash_password(password)

    assert not verify_password("WrongPassword", hashed)

def test_create_access_token():
    data = {"sub": "user-uuid", "role": "patient"}
    token = create_access_token(data)

    assert token is not None
    assert isinstance(token, str)

    # Decode and verify
    payload = decode_access_token(token)
    assert payload["sub"] == "user-uuid"
    assert payload["role"] == "patient"
```

#### 4.2.2 FHIR Bundle Generation

```python
# tests/test_fhir.py
from app.utils.fhir import create_medication_request_bundle

def test_create_medication_request_bundle():
    medicines = [
        {
            "name": "Paracetamol 500mg",
            "dosage": "1 tablet",
            "frequency": "TID",
            "duration": "5 days"
        }
    ]

    bundle = create_medication_request_bundle(
        patient_id="patient-uuid",
        doctor_id="doctor-uuid",
        medicines=medicines
    )

    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "collection"
    assert len(bundle["entry"]) == 1
    assert bundle["entry"][0]["resource"]["resourceType"] == "MedicationRequest"
```

### 4.3 Integration Test Examples

#### 4.3.1 Authentication Flow

```python
# tests/test_auth.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_signup_success(client: AsyncClient):
    response = await client.post("/api/v1/auth/signup", json={
        "email": "newuser@example.com",
        "password": "SecurePassword123",
        "full_name": "Test User",
        "role": "patient"
    })

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["user"]["email"] == "newuser@example.com"
    assert "access_token" in data
    assert "refresh_token" in data

@pytest.mark.asyncio
async def test_signup_duplicate_email(client: AsyncClient, db_session):
    # Create user first
    await create_user(db_session, email="existing@example.com")

    # Try to signup with same email
    response = await client.post("/api/v1/auth/signup", json={
        "email": "existing@example.com",
        "password": "Password123",
        "full_name": "Duplicate User",
        "role": "patient"
    })

    assert response.status_code == 400
    assert "already exists" in response.json()["error"]["message"]

@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, db_session):
    # Create user
    user = await create_user(
        db_session,
        email="user@example.com",
        password="Password123"
    )

    # Login
    response = await client.post("/api/v1/auth/login", json={
        "email": "user@example.com",
        "password": "Password123"
    })

    assert response.status_code == 200
    data = response.json()["data"]
    assert "access_token" in data
    assert data["user"]["id"] == str(user.id)

@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, db_session):
    await create_user(
        db_session,
        email="user@example.com",
        password="CorrectPassword"
    )

    response = await client.post("/api/v1/auth/login", json={
        "email": "user@example.com",
        "password": "WrongPassword"
    })

    assert response.status_code == 401
    assert "Invalid credentials" in response.json()["error"]["message"]
```

#### 4.3.2 Prescription Creation

```python
# tests/test_prescriptions.py
@pytest.mark.asyncio
async def test_create_prescription(
    client: AsyncClient,
    db_session,
    doctor_token,
    patient
):
    response = await client.post(
        "/api/v1/doctors/prescriptions",
        headers={"Authorization": f"Bearer {doctor_token}"},
        json={
            "patient_id": str(patient.id),
            "medicines": [
                {
                    "name": "Paracetamol 500mg",
                    "dosage": "1 tablet",
                    "frequency": "TID",
                    "duration": "5 days",
                    "instructions": "Take after meals"
                }
            ],
            "diagnosis": "Fever",
            "notes": "Avoid cold foods"
        }
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["patient_id"] == str(patient.id)
    assert len(data["medicines"]) == 1
    assert data["record_id"] is not None  # Auto-created record

@pytest.mark.asyncio
async def test_create_prescription_unauthorized(client: AsyncClient, patient_token):
    # Patient tries to create prescription (should fail)
    response = await client.post(
        "/api/v1/doctors/prescriptions",
        headers={"Authorization": f"Bearer {patient_token}"},
        json={
            "patient_id": "some-uuid",
            "medicines": [...]
        }
    )

    assert response.status_code == 403
```

#### 4.3.3 Drug Interaction Checking

```python
# tests/test_interactions.py
@pytest.mark.asyncio
async def test_check_drug_interactions(client: AsyncClient, db_session):
    # Create salts and interaction
    salt1 = await create_salt(db_session, name="Aspirin")
    salt2 = await create_salt(db_session, name="Warfarin")
    await create_interaction(
        db_session,
        salt1.id,
        salt2.id,
        severity="major",
        effect="Increased bleeding risk"
    )

    # Check interactions
    response = await client.post("/api/v1/interactions/check", json={
        "salt_ids": [str(salt1.id), str(salt2.id)]
    })

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["severity"] == "major"
    assert "bleeding" in data[0]["effect"].lower()

@pytest.mark.asyncio
async def test_no_interactions(client: AsyncClient, db_session):
    salt1 = await create_salt(db_session, name="Paracetamol")
    salt2 = await create_salt(db_session, name="Vitamin C")
    # No interaction created

    response = await client.post("/api/v1/interactions/check", json={
        "salt_ids": [str(salt1.id), str(salt2.id)]
    })

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 0
```

### 4.4 Test Fixtures and Factories

```python
# tests/factories.py
import factory
from factory.alchemy import SQLAlchemyModelFactory
from app.models import User, Doctor, Prescription

class UserFactory(SQLAlchemyModelFactory):
    class Meta:
        model = User
        sqlalchemy_session_persistence = "commit"

    email = factory.Faker("email")
    phone = factory.Faker("phone_number")
    full_name = factory.Faker("name")
    role = "patient"

class DoctorFactory(SQLAlchemyModelFactory):
    class Meta:
        model = Doctor
        sqlalchemy_session_persistence = "commit"

    user = factory.SubFactory(UserFactory, role="doctor")
    specialization = "General Medicine"
    license_number = factory.Faker("bothify", text="MCI-####-####")
    years_of_experience = factory.Faker("random_int", min=1, max=30)

# Usage in tests
@pytest.mark.asyncio
async def test_with_factory(db_session):
    doctor = DoctorFactory.create(specialization="Cardiology")
    assert doctor.specialization == "Cardiology"
    assert doctor.user.role == "doctor"
```

---

## 5. Frontend Testing

### 5.1 Test Framework

**Stack:**
- **Vitest:** Fast unit test runner (Vite-based)
- **React Testing Library:** Component testing
- **MSW (Mock Service Worker):** API mocking
- **Playwright:** E2E testing

**Setup:**
```typescript
// vitest.config.ts
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: ['node_modules/', 'src/test/'],
    },
  },
});
```

### 5.2 Component Testing

#### 5.2.1 Simple Component

```typescript
// components/ui/button.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { Button } from './button';

describe('Button', () => {
  it('renders with text', () => {
    render(<Button>Click me</Button>);
    expect(screen.getByText('Click me')).toBeInTheDocument();
  });

  it('calls onClick when clicked', () => {
    const handleClick = vi.fn();
    render(<Button onClick={handleClick}>Click</Button>);

    fireEvent.click(screen.getByText('Click'));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('is disabled when disabled prop is true', () => {
    render(<Button disabled>Disabled</Button>);
    expect(screen.getByText('Disabled')).toBeDisabled();
  });
});
```

#### 5.2.2 Complex Component with API

```typescript
// components/medicine/DrugInteractionWarning.test.tsx
import { render, screen, waitFor } from '@testing-library/react';
import { DrugInteractionWarning } from './DrugInteractionWarning';
import { rest } from 'msw';
import { setupServer } from 'msw/node';

const server = setupServer(
  rest.post('/api/v1/interactions/check', (req, res, ctx) => {
    return res(ctx.json({
      data: [
        {
          interaction_id: 'uuid',
          salt_1: { name: 'Aspirin' },
          salt_2: { name: 'Warfarin' },
          severity: 'major',
          effect: 'Increased bleeding risk',
        },
      ],
    }));
  })
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('DrugInteractionWarning', () => {
  it('displays interaction warning', async () => {
    const interactions = [
      {
        severity: 'major',
        salt_1: { name: 'Aspirin' },
        salt_2: { name: 'Warfarin' },
        effect: 'Increased bleeding risk',
      },
    ];

    render(<DrugInteractionWarning interactions={interactions} />);

    expect(screen.getByText(/major interaction/i)).toBeInTheDocument();
    expect(screen.getByText(/Aspirin/)).toBeInTheDocument();
    expect(screen.getByText(/Warfarin/)).toBeInTheDocument();
    expect(screen.getByText(/bleeding risk/i)).toBeInTheDocument();
  });

  it('uses correct color for severity', () => {
    const interactions = [
      { severity: 'contraindicated', salt_1: { name: 'A' }, salt_2: { name: 'B' }, effect: 'Test' },
    ];

    render(<DrugInteractionWarning interactions={interactions} />);

    const warning = screen.getByRole('alert');
    expect(warning).toHaveClass('border-red-200'); // Contraindicated = red
  });
});
```

### 5.3 Custom Hook Testing

```typescript
// hooks/useDrugInteractions.test.ts
import { renderHook, waitFor } from '@testing-library/react';
import { useDrugInteractions } from './useDrugInteractions';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

describe('useDrugInteractions', () => {
  it('fetches interactions on mount', async () => {
    const { result } = renderHook(
      () => useDrugInteractions(['salt-1', 'salt-2']),
      { wrapper: createWrapper() }
    );

    expect(result.current.loading).toBe(true);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.interactions).toBeDefined();
  });

  it('sets hasContraindicated flag', async () => {
    // Mock API to return contraindicated interaction
    const { result } = renderHook(
      () => useDrugInteractions(['aspirin', 'warfarin']),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.hasContraindicated).toBe(true);
    });
  });
});
```

---

## 6. Integration Testing

### 6.1 API + Database Integration

```python
# tests/integration/test_patient_timeline.py
@pytest.mark.asyncio
async def test_patient_timeline_flow(client: AsyncClient, db_session):
    # Create patient
    patient = await UserFactory.create(role="patient")
    doctor = await DoctorFactory.create()

    # Create access token
    token = create_access_token({"sub": str(patient.id), "role": "patient"})

    # Initially empty timeline
    response = await client.get(
        "/api/v1/patients/timeline",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert len(response.json()["data"]) == 0

    # Doctor creates medical record
    doctor_token = create_access_token({"sub": str(doctor.user_id), "role": "doctor"})
    await client.post(
        "/api/v1/doctors/records",
        headers={"Authorization": f"Bearer {doctor_token}"},
        json={
            "patient_id": str(patient.id),
            "record_type": "consultation",
            "chief_complaint": "Fever",
            "diagnosis": "Viral infection"
        }
    )

    # Timeline now has one record
    response = await client.get(
        "/api/v1/patients/timeline",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert len(response.json()["data"]) == 1
    assert response.json()["data"][0]["chief_complaint"] == "Fever"
```

### 6.2 Medicine Search Integration

```python
# tests/integration/test_medicine_search.py
@pytest.mark.asyncio
async def test_medicine_search_with_cache(client: AsyncClient, redis_client):
    # First request (cache miss)
    response1 = await client.get("/api/v1/medicines/search?q=paracetamol")
    assert response1.status_code == 200
    results1 = response1.json()["data"]

    # Check cache populated
    cache_key = "medicine:search:paracetamol"
    cached = await redis_client.get(cache_key)
    assert cached is not None

    # Second request (cache hit)
    response2 = await client.get("/api/v1/medicines/search?q=paracetamol")
    results2 = response2.json()["data"]

    # Results should match
    assert results1 == results2
```

---

## 7. End-to-End Testing

### 7.1 Playwright Setup

```typescript
// playwright.config.ts
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
    { name: 'webkit', use: { ...devices['Desktop Safari'] } },
  ],
});
```

### 7.2 E2E Test Examples

#### 7.2.1 User Authentication Flow

```typescript
// e2e/auth.spec.ts
import { test, expect } from '@playwright/test';

test.describe('Authentication', () => {
  test('user can sign up and login', async ({ page }) => {
    // Navigate to signup
    await page.goto('/signup');

    // Fill signup form
    await page.fill('[name="email"]', 'newuser@example.com');
    await page.fill('[name="password"]', 'SecurePassword123');
    await page.fill('[name="full_name"]', 'Test User');
    await page.selectOption('[name="role"]', 'patient');

    // Submit
    await page.click('button[type="submit"]');

    // Should redirect to patient timeline
    await expect(page).toHaveURL('/patient/timeline');
    await expect(page.locator('text=Welcome, Test User')).toBeVisible();

    // Logout
    await page.click('[data-testid="logout-button"]');
    await expect(page).toHaveURL('/');

    // Login again
    await page.goto('/login');
    await page.fill('[name="email"]', 'newuser@example.com');
    await page.fill('[name="password"]', 'SecurePassword123');
    await page.click('button[type="submit"]');

    await expect(page).toHaveURL('/patient/timeline');
  });

  test('shows error on invalid login', async ({ page }) => {
    await page.goto('/login');
    await page.fill('[name="email"]', 'wrong@example.com');
    await page.fill('[name="password"]', 'WrongPassword');
    await page.click('button[type="submit"]');

    await expect(page.locator('text=Invalid credentials')).toBeVisible();
  });
});
```

#### 7.2.2 Doctor Creates Prescription

```typescript
// e2e/prescription.spec.ts
import { test, expect } from '@playwright/test';

test.describe('Prescription Creation', () => {
  test.beforeEach(async ({ page }) => {
    // Login as doctor
    await page.goto('/login');
    await page.fill('[name="email"]', 'doctor@example.com');
    await page.fill('[name="password"]', 'DoctorPassword123');
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL('/doctor/dashboard');
  });

  test('doctor creates prescription with drug interaction warning', async ({ page }) => {
    // Navigate to new prescription
    await page.goto('/doctor/prescriptions/new');

    // Select patient
    await page.fill('[data-testid="patient-search"]', 'John Doe');
    await page.click('text=John Doe');

    // Add first medicine (Aspirin)
    await page.fill('[data-testid="medicine-search"]', 'Aspirin');
    await page.click('text=Aspirin 100mg');
    await page.fill('[name="dosage"]', '1 tablet');
    await page.fill('[name="frequency"]', 'OD');
    await page.fill('[name="duration"]', '30 days');
    await page.click('[data-testid="add-medicine"]');

    // Add second medicine (Warfarin) - triggers interaction
    await page.fill('[data-testid="medicine-search"]', 'Warfarin');
    await page.click('text=Warfarin 5mg');
    await page.fill('[name="dosage"]', '1 tablet');
    await page.fill('[name="frequency"]', 'OD');
    await page.click('[data-testid="add-medicine"]');

    // Should show interaction warning
    await expect(page.locator('[data-testid="interaction-warning"]')).toBeVisible();
    await expect(page.locator('text=Major Interaction')).toBeVisible();
    await expect(page.locator('text=bleeding risk')).toBeVisible();

    // Fill other fields
    await page.fill('[name="diagnosis"]', 'Atrial fibrillation');
    await page.fill('[name="notes"]', 'Monitor INR regularly');

    // Submit prescription
    await page.click('button[type="submit"]');

    // Should confirm despite warning
    await page.click('text=I understand the risks');
    await page.click('button:has-text("Confirm")');

    // Success
    await expect(page).toHaveURL(/\/prescriptions\/\w+/);
    await expect(page.locator('text=Prescription created successfully')).toBeVisible();
  });
});
```

---

## 8. Performance Testing

### 8.1 Load Testing with Locust

```python
# locustfile.py
from locust import HttpUser, task, between

class MedConnectUser(HttpUser):
    wait_time = between(1, 3)
    host = "http://localhost:8000"

    def on_start(self):
        # Login
        response = self.client.post("/api/v1/auth/login", json={
            "email": "testuser@example.com",
            "password": "Password123"
        })
        self.token = response.json()["data"]["access_token"]

    @task(3)
    def view_timeline(self):
        self.client.get(
            "/api/v1/patients/timeline",
            headers={"Authorization": f"Bearer {self.token}"}
        )

    @task(2)
    def search_medicine(self):
        self.client.get("/api/v1/medicines/search?q=paracetamol")

    @task(1)
    def check_interactions(self):
        self.client.post("/api/v1/interactions/check", json={
            "salt_ids": ["uuid-1", "uuid-2"]
        })
```

**Run:**
```bash
# Test with 100 users, spawn rate 10/second
locust -f locustfile.py --users 100 --spawn-rate 10 --run-time 5m
```

**Metrics to Monitor:**
- Request rate (req/s)
- Response time (p50, p95, p99)
- Error rate (%)
- Database connections
- Memory usage

### 8.2 Database Performance Testing

```python
# tests/performance/test_query_performance.py
import pytest
import time

@pytest.mark.asyncio
async def test_patient_timeline_performance(db_session):
    # Create 1000 records
    patient = await UserFactory.create(role="patient")
    for _ in range(1000):
        await MedicalRecordFactory.create(patient_id=patient.id)

    # Measure query time
    start = time.time()
    records = await record_service.get_patient_timeline(
        patient_id=patient.id,
        limit=20
    )
    elapsed = time.time() - start

    assert len(records) == 20
    assert elapsed < 0.2  # Should be < 200ms
```

---

## 9. Security Testing

### 9.1 Automated Security Scanning

**Dependency Scanning:**
```bash
# Python dependencies
pip-audit

# JavaScript dependencies
npm audit

# Fix vulnerabilities
npm audit fix
```

**SAST (Static Application Security Testing):**
```bash
# Bandit for Python
bandit -r backend/app

# ESLint security plugin
npm run lint:security
```

### 9.2 Security Test Cases

```python
# tests/security/test_auth_security.py
@pytest.mark.asyncio
async def test_cannot_access_other_patient_records(client, patient1_token, patient2):
    # Patient 1 tries to access Patient 2's records
    response = await client.get(
        f"/api/v1/patients/records/{patient2.id}",
        headers={"Authorization": f"Bearer {patient1_token}"}
    )

    assert response.status_code == 403

@pytest.mark.asyncio
async def test_sql_injection_prevention(client):
    # Attempt SQL injection in search
    response = await client.get(
        "/api/v1/medicines/search?q=' OR '1'='1"
    )

    # Should not return all medicines, should be sanitized
    assert response.status_code == 200
    results = response.json()["data"]
    assert len(results["brands"]) < 100  # Not all 250K brands

@pytest.mark.asyncio
async def test_rate_limiting(client):
    # Make 20 requests rapidly
    for i in range(20):
        response = await client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "password"
        })

    # 11th request should be rate limited
    assert response.status_code == 429
```

---

## 10. Test Data Management

### 10.1 Test Database

**Setup:**
```python
# conftest.py
@pytest.fixture(scope="session")
async def test_db():
    # Create test database
    engine = create_async_engine(
        "postgresql+asyncpg://test:test@localhost/medconnect_test"
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Drop test database
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
```

### 10.2 Seed Data

```python
# tests/seed_data.py
async def create_test_users(session):
    # Create standard test users
    patient = await UserFactory.create(
        email="patient@test.com",
        role="patient",
        full_name="Test Patient"
    )

    doctor = await DoctorFactory.create(
        user__email="doctor@test.com",
        user__full_name="Dr. Test",
        specialization="General Medicine"
    )

    admin = await UserFactory.create(
        email="admin@test.com",
        role="admin",
        full_name="Admin User"
    )

    return patient, doctor, admin
```

### 10.3 Test Data Cleanup

```python
@pytest.fixture(autouse=True)
async def cleanup(db_session):
    yield
    # Cleanup after each test
    await db_session.execute(delete(Prescription))
    await db_session.execute(delete(MedicalRecord))
    await db_session.commit()
```

---

## 11. CI/CD Integration

### 11.1 GitHub Actions Workflow

```yaml
# .github/workflows/test.yml
name: Test Suite

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  backend-tests:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
          pip install pytest pytest-asyncio pytest-cov

      - name: Run migrations
        run: |
          cd backend
          alembic upgrade head

      - name: Run tests
        run: |
          cd backend
          pytest --cov=app --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./backend/coverage.xml

  frontend-tests:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'

      - name: Install dependencies
        run: |
          cd frontend
          npm ci

      - name: Run tests
        run: |
          cd frontend
          npm run test:coverage

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./frontend/coverage/coverage-final.json

  e2e-tests:
    runs-on: ubuntu-latest
    needs: [backend-tests, frontend-tests]

    steps:
      - uses: actions/checkout@v3

      - name: Start services
        run: docker-compose up -d

      - name: Wait for services
        run: ./scripts/wait-for-services.sh

      - name: Run E2E tests
        run: npx playwright test

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: playwright-report
          path: playwright-report/
```

### 11.2 Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files

  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
        language_version: python3.12

  - repo: https://github.com/PyCQA/flake8
    rev: 6.0.0
    hooks:
      - id: flake8

  - repo: local
    hooks:
      - id: pytest-check
        name: pytest-check
        entry: bash -c 'cd backend && pytest tests/unit'
        language: system
        pass_filenames: false
        always_run: true
```

---

## 12. Test Metrics and Coverage

### 12.1 Coverage Goals

| Component | Target | Current | Status |
|-----------|--------|---------|--------|
| Backend Services | 90% | 85% | 🟡 In Progress |
| Backend Routes | 80% | 75% | 🟡 In Progress |
| Backend Models | 70% | 80% | ✅ Met |
| Frontend Components | 70% | 60% | 🟡 In Progress |
| Frontend Hooks | 80% | 65% | 🟡 In Progress |
| **Overall** | **80%** | **72%** | 🟡 In Progress |

### 12.2 Test Metrics

**Tracked Metrics:**
- **Coverage:** Line, branch, function coverage percentages
- **Test Count:** Total tests, passing, failing, skipped
- **Duration:** Total test suite runtime
- **Flakiness:** Tests that fail intermittently
- **Performance:** Test execution time trends

**Dashboard:** Codecov.io or SonarQube

### 12.3 Quality Gates

**Merge Requirements:**
- All tests passing
- Coverage > 80% (or no decrease)
- No critical security vulnerabilities
- Code review approval
- No linting errors

---

**End of Document**

**Last Updated:** 2026-02-25
**Maintained By:** MedConnect QA Team
