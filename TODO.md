# MedConnect — Open TODO Items

Last updated: 2026-03-20

All items below are tracked as Jira tickets in the MD project.

---

## Critical

| Ticket | File | Description |
|--------|------|-------------|
| MD-345 | `backend/app/routers/appointments.py:149-189` | **N+1 query pattern** in `_load_appointment_with_names()` — 4 separate DB queries per appointment; batch with JOINs |
| MD-346 | `frontend/src/app/patient/records/page.tsx` | **Missing page** — patient sidebar links to `/patient/records` which 404s; create a records list page |
| MD-347 | `frontend/src/app/patient/[id]/page.tsx:99,123,187` | **Hardcoded mock data** — 3 TODO comments; replace with real API calls to `/api/v1/patients/{id}`, `/vitals`, `/appointments` |

---

## High

| Ticket | File | Description |
|--------|------|-------------|
| MD-315 | `frontend/src/lib/api/users.ts:37-42` | **Missing backend endpoint** `PUT /api/v1/users/me` — profile update always 404s |
| MD-316 | `frontend/src/lib/api/users.ts:49-64` | **Missing backend endpoints** `POST/DELETE /api/v1/users/photo` — photo upload always 404s |
| MD-317 | `frontend/src/lib/api/patients.ts` | **Missing backend endpoints** `GET /api/v1/patients/{id}/vitals`, `/vitals/history`, `/appointments` |
| MD-319 | `frontend/src/lib/api/` | **Missing backend endpoint** `POST /api/v1/doctors/patients/{id}/vital-alerts` |
| MD-353 | `frontend/src/app/admin/dashboard/page.tsx:65-93` | **No error handling** for secondary stats queries (`patientTrend`, `recordTrend`, etc.) — silent failures |
| MD-367 | `frontend/src/app/patient/[id]/page.tsx:569-621` | **6 placeholder tabs** — Visits, Lab Results, Prescriptions, Medical History, Billings, Documents show "will be displayed here" |

---

## Medium

| Ticket | File | Description |
|--------|------|-------------|
| MD-323 | `backend/app/middleware/rate_limit.py` | **Rate limiter fails open** — exceptions logged but requests proceed; consider stricter fail behaviour |
| MD-326 | `backend/app/utils/security.py` | **Broad `except Exception`** in JWKS decode — masks unexpected errors |
| MD-329 | `frontend/src/lib/api/` | **Pagination mismatch** — some endpoints use cursor, others use page-based; standardise |
| MD-358 | `backend/app/routers/admin/stats.py:654` | **Visits departments always returns `[]`** — hardcoded empty list; implement real data or remove endpoint |
| MD-363 | `frontend/src/lib/keycloak.ts:4,14` | **Keycloak export type mismatch** — `null` exported as `Keycloak`; update to `Keycloak \| null` |
| MD-364 | `frontend/src/app/patient/appointments/page.tsx:488` | **`as any` on Badge variant** — hides type mismatch; use typed map |
| MD-334 | `frontend/src/app/` (multiple) | **Multiple `as any` casts** across pages — replace with proper type guards |

---

## Low

| Ticket | File | Description |
|--------|------|-------------|
| MD-337 | `frontend/src/lib/api/clinics.ts` | **`getMyClinicss()` double-s typo** in function name |
| MD-338 | `frontend/` | **Missing `.env.example`** — document all `NEXT_PUBLIC_*` variables |
| MD-339 | `backend/app/routers/vitals.py` | **Vitals router uses full paths** in decorators (`/api/v1/patients/vitals`) instead of relative paths |
| MD-365 | `backend/app/routers/` (multiple) | **No max-length validation** on string fields in Pydantic schemas (full_name, phone, etc.) |
| MD-366 | `backend/app/utils/security.py` | **JWKS client reset without lock** — concurrent failures can reinitialise simultaneously |

---

## Recently Completed

### Round 3 (2026-03-20)

| Ticket | Description |
|--------|-------------|
| MD-348 | Fixed NameError `uuid.uuid4()` in onboarding.py (imported as `_uuid_mod`) |
| MD-349 | Added `deleted_at` filter to both NotificationPreferences queries |
| MD-351 | Dead admin buttons: New Doctor navigates to pending; New Visit/Test disabled with tooltip |
| MD-352 | Load More buttons now functional in patient timeline + doctor prescriptions |
| MD-354 | Replaced loading spinner with skeleton card grid in admin doctors page |
| MD-355 | Replaced deprecated `utcnow()` with `datetime.now(timezone.utc)` in onboarding.py |
| MD-356 | Enforced status transitions in `DELETE /appointments/{id}` (blocks terminal states) |
| MD-357 | Added `db.commit()` after vital flush so record persists before notifications fire |
| MD-359 | Added UUID validation for `clinic_id` in admin/users.py before DB query |
| MD-360 | Standardised HTTP status codes in patient_links.py (`status.HTTP_*` constants) |
| MD-361 | Captured `error` object in `useQuery` on doctor prescriptions page |
| MD-362 | Added `useEffect` cleanup for debounce timeout in DoctorSearchInput |
| MD-368 | Added Doctor profile existence check in patient_links role verification |

### Round 2 (2026-03-20)

| Ticket | Description |
|--------|-------------|
| MD-308 | Added `require_admin` to admin/medicines.py and admin/components.py |
| MD-309 | Fixed soft-delete join filters in lab_results `_list_query()` |
| MD-310 | Fixed `_next_test_id` count to exclude soft-deleted records |
| MD-311 | Replaced all `fetch()` calls in medicines.ts + medicines-emr.ts with axios api instance |
| MD-313 | Moved `DELETE /read` before `DELETE /{id}` in notifications.py (route shadowing fix) |
| MD-318 | Fixed `updatePatient`/`deletePatient` to call `/admin/users/` not `/admin/patients/` |
| MD-320 | Added null guards for keycloak in api.ts interceptor |
| MD-321 | Added auth page guard to 401 handler to prevent redirect loops |
| MD-322 | Moved inline setState into `useEffect` in patient profile page |
| MD-325 | Malformed date filter now raises HTTP 400 instead of silently passing |
| MD-330 | Replaced `n.metadata!.consent_id` with `n.metadata?.consent_id` |
| MD-340 | Added type hint to `doctor_info` parameter in doctors.py |
| MD-341 | Added `_uid` field to Medicine interface; replaced index-based React keys |
| MD-342 | Added `console.error` logging to template save catch block |
| MD-343 | Removed debug `console.log` from MedicineAutocomplete |
| MD-344 | Improved auth error message to extract actual error text |

### Round 1 (earlier)

| Ticket | Description |
|--------|-------------|
| MD-290 | Vitals endpoint missing doctor-patient auth check |
| MD-291 | Mass-assignment via setattr loop |
| MD-292 | No vital value range validation |
| MD-293 | JWT token in WebSocket URL |
| MD-294 | Rate-limit JWT decoded without signature verification |
| MD-295 | Prescription medicines unvalidated JSONB |
| MD-296 | User provisioning race condition |
| MD-297 | Doctor prescriptions without relationship check |
| MD-298–307 | Medium priority security + quality fixes (see git history) |
