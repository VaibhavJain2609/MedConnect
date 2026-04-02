# MedConnect Multi-Tenancy & Doctor Onboarding Plan

## Context

MedConnect currently has no formal Clinic/Organization entity — doctor facility scoping uses string-matching on `facility_name`/`facility_city` fields. This plan introduces proper clinic multi-tenancy, bank-style doctor onboarding with license verification, clinic invite/join workflows, and patient linking with record isolation. Aadhaar KYC and cross-clinic record sharing are designed for but deferred.

---

## Sprint 1: Clinic Foundation (Build First)

Everything depends on the Clinic model existing.

### New Models (`backend/app/models/clinic.py`)

**Clinic** — `clinics` table
- `id` (UUID PK), `name`, `address`, `city`, `state`, `phone`, `email`, `logo_url`
- `is_active` (bool), `record_sharing_mode` (string: `"per_clinic"` | `"per_doctor"`, default `"per_clinic"`)
- `created_by` (FK→users), standard timestamps + soft delete

**ClinicBranch** — `clinic_branches` table
- `id`, `clinic_id` (FK→clinics), `name`, `address`, `city`, `state`, `phone`, `is_active`
- Standard timestamps + soft delete

**ClinicMembership** — `clinic_memberships` table
- `id`, `clinic_id` (FK→clinics), `user_id` (FK→users), `role` (`"owner"` | `"admin"` | `"doctor"`)
- `branch_id` (nullable FK→clinic_branches), `is_active`, `joined_at`
- Unique index on `(user_id, clinic_id)` where `deleted_at IS NULL`

### Modified Models

**Doctor** (`backend/app/models/doctor.py`) — Add fields:
- `license_council` (String), `license_year` (Integer)
- `nhr_verification_status` (String: `"pending"` | `"verified"` | `"failed"` | `"not_checked"`)
- `verification_notes` (Text)
- `onboarding_step` (String: `"pending"` | `"profile"` | `"license"` | `"clinic"` | `"completed"`, default `"pending"`)
- Keep `facility_name`/`facility_city` temporarily

**MedicalRecord** (`backend/app/models/medical_record.py`) — Add:
- `clinic_id` (nullable FK→clinics)

**Prescription** (`backend/app/models/prescription.py`) — Add:
- `clinic_id` (nullable FK→clinics)

### Migration Strategy
1. **Migration 1**: Create tables + add new columns (all nullable/defaulted)
2. **Migration 2** (data): Create Clinic rows from distinct `(facility_name, facility_city)` pairs, create ClinicMembership rows for each doctor, backfill `clinic_id` on records. Set `onboarding_step="completed"` for existing verified doctors.

### Backend
- New schemas: `backend/app/schemas/clinic.py`
- New service: `backend/app/services/clinic_service.py`
- New routers: `backend/app/routers/clinics.py`, `backend/app/routers/admin/clinics.py`
- Register in `backend/app/main.py`

**Clinic endpoints** (doctor-facing):
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/clinics` | verified doctor | Create clinic (becomes owner) |
| GET | `/api/v1/clinics/my` | any auth user | List my clinics |
| GET | `/api/v1/clinics/{id}` | clinic member | Clinic detail |
| PUT | `/api/v1/clinics/{id}` | clinic owner/admin | Update clinic |
| GET | `/api/v1/clinics/{id}/members` | clinic member | List members |
| PUT | `/api/v1/clinics/{id}/settings` | clinic owner/admin | Update record_sharing_mode |
| POST | `/api/v1/clinics/{id}/branches` | clinic owner/admin | Create branch |

**Admin clinic endpoints**:
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/admin/clinics` | List all clinics |
| GET | `/api/v1/admin/clinics/{id}` | Clinic detail + stats |
| PUT | `/api/v1/admin/clinics/{id}` | Update any clinic |
| DELETE | `/api/v1/admin/clinics/{id}` | Soft delete |

### Frontend
- New API module: `frontend/src/lib/api/clinics.ts`
- New store: `frontend/src/stores/clinic-store.ts` (active clinic ID, user's clinics)
- Admin pages: `/admin/clinics` (list), `/admin/clinics/[id]` (detail)
- Doctor pages: `/doctor/clinic` (dashboard)
- Clinic selector component in doctor header (for multi-clinic doctors)
- Add `X-Clinic-Id` header via axios interceptor from clinic store
- Update admin sidebar: add "Clinics" under MANAGEMENT

---

## Sprint 2: Record Scoping Migration

**Depends on:** Sprint 1

### Backend Changes
- New dependency: `get_active_clinic` — reads `X-Clinic-Id` header, verifies membership
- Update `record_service.py` and `prescription_service.py`: store `clinic_id` on creation
- Update `doctors.py` router: replace `facility_name`/`facility_city` matching with clinic membership queries
- Respect `Clinic.record_sharing_mode`: `"per_doctor"` = only own records, `"per_clinic"` = all clinic doctors' records

### Frontend Changes
- Clinic selector in doctor layout header
- Axios interceptor attaches `X-Clinic-Id`

---

## Sprint 3: Doctor Onboarding (Bank-Style)

**Depends on:** Sprint 1 (Clinic model needed for step 3)

### Flow
1. Doctor registers via Keycloak → auto-provisioned with `verified=false`, `onboarding_step="pending"`
2. Redirected to `/doctor/onboarding` (minimal layout, no sidebar)
3. **Step 1 — Profile**: Name, specialization, phone
4. **Step 2 — License**: License number, council, year → NHR verification (stub for now, mock response)
5. **Step 3 — Clinic**: Create new clinic OR enter invite code OR search & request to join
6. After completing all steps → `onboarding_step="completed"`, awaits verification
7. **Pending dashboard**: Shows "Awaiting verification" with status of each step
8. Platform admin reviews and approves/rejects → doctor.verified = true → full access

### Backend
- New router: `backend/app/routers/onboarding.py`
  - `GET /api/v1/onboarding/status` — current step + data
  - `PUT /api/v1/onboarding/profile` — step 1
  - `PUT /api/v1/onboarding/license` — step 2
  - `POST /api/v1/onboarding/clinic` — step 3 (create or join)
  - `POST /api/v1/onboarding/verify-nhr` — trigger NHR check (stubbed)
- New dependency: `get_verified_doctor` — checks `verified=True` AND `onboarding_step="completed"`. Use for clinical endpoints.
- New stub service: `backend/app/services/nhr_service.py` — returns mock response
- Update `doctors.py`: prescription/record creation uses `get_verified_doctor`

### Frontend
- New layout: `frontend/src/app/doctor/onboarding/layout.tsx` (minimal, no sidebar)
- New page: `frontend/src/app/doctor/onboarding/page.tsx` (wizard container)
- Step components: `step-profile.tsx`, `step-license.tsx`, `step-clinic.tsx`
- Progress indicator component
- Pending verification dashboard component
- Update doctor layout: redirect to `/doctor/onboarding` if `onboarding_step != "completed"`
- If completed but not verified: show pending verification view instead of full dashboard

---

## Sprint 4: Clinic Invite System

**Depends on:** Sprint 1 + Sprint 3

### New Models (`backend/app/models/clinic_invite.py`)

**ClinicInvite** — `clinic_invites` table
- `id`, `clinic_id`, `invite_type` (`"code"` | `"email"`), `code` (unique), `email` (nullable)
- `role` (default `"doctor"`), `expires_at`, `max_uses`, `use_count`, `created_by`

**ClinicJoinRequest** — `clinic_join_requests` table
- `id`, `clinic_id`, `user_id`, `message`, `status` (`"pending"` | `"approved"` | `"rejected"`)
- `reviewed_by`, `reviewed_at`

### Backend
- New router: `backend/app/routers/clinic_invites.py`
  - `POST /api/v1/clinics/{id}/invites` — generate code or email invite
  - `GET /api/v1/clinics/{id}/invites` — list active invites
  - `DELETE /api/v1/clinics/{id}/invites/{invite_id}` — revoke
  - `POST /api/v1/invites/redeem` — redeem invite code
  - `GET /api/v1/clinics/search` — search clinics to join
  - `POST /api/v1/clinics/{id}/join-request` — request to join
  - `GET /api/v1/clinics/{id}/join-requests` — list pending (clinic admin)
  - `PUT /api/v1/clinics/{id}/join-requests/{id}` — approve/reject

### Frontend
- Invite management page for clinic owners/admins
- Join request review page
- Clinic search + request modal (also used in onboarding step 3)

---

## Sprint 5: Patient Linking

**Depends on:** Sprint 1 + Sprint 2

### New Models (`backend/app/models/patient_link.py`)

**PatientClinicLink** — `patient_clinic_links` table
- `id`, `patient_id`, `clinic_id`, `linked_by` (doctor), `consent_status` (`"pending"` | `"approved"` | `"revoked"`)
- `consented_at`, unique index on `(patient_id, clinic_id)`

**PatientLinkCode** — `patient_link_codes` table
- `id`, `patient_id`, `code` (10-digit, unique), `expires_at` (weekly rotation)

### Backend
- New router: `backend/app/routers/patient_links.py`
  - `GET /api/v1/patients/link-code` — get/generate weekly code
  - `POST /api/v1/clinics/{id}/link-patient` — link by code (doctor)
  - `GET /api/v1/patients/clinic-links` — list linked clinics (patient)
  - `PUT /api/v1/patients/clinic-links/{id}/consent` — approve/revoke (patient)
  - `GET /api/v1/clinics/{id}/patients` — list linked patients (clinic member)
- Consent notification flow via existing notification system

### Frontend
- Patient portal: link code display page, linked clinics management page
- Doctor portal: patient linking page (enter code)
- Add "My Clinics" to patient sidebar

---

## Sprint 6: Cleanup

- Remove `facility_name`/`facility_city` from Doctor model
- Drop columns via migration
- Remove old facility-based scoping code
- Update all admin views to show clinic membership

---

## Key Architectural Decisions

1. **`X-Clinic-Id` header** for clinic context — avoids breaking existing endpoint paths
2. **Clinic admin vs Platform admin** — clinic admin is a ClinicMembership role (user still has `role="doctor"` in Keycloak), platform admin has `role="admin"`
3. **New dependency `require_clinic_admin(clinic_id)`** — checks ClinicMembership role
4. **Backwards compatible** — `clinic_id` nullable on records, old facility fields kept until Sprint 6

## Deferred (Design-Ready)
- **Aadhaar KYC**: Add as additional verification step in onboarding later
- **Cross-clinic record access**: PatientClinicLink + consent model supports future `CrossClinicAccessRequest`

## Verification

For each sprint:
1. Run `alembic upgrade head` — migrations apply cleanly
2. Run `pytest` — all existing tests pass, new tests pass
3. Run `npm run build` — frontend compiles
4. Manual test: doctor signup → onboarding → clinic creation → patient linking → record scoping
