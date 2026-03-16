# MedConnect — Security & Quality Backlog

Generated from codebase audit. Critical issues (MD-290–293) have been fixed.
Remaining items are tracked below by priority.

---

## HIGH Priority

### MD-294 — Rate-limit JWT decoded without signature verification
**File:** `backend/app/middleware/rate_limit.py:54-55`
**Issue:** `jwt.decode(token, options={"verify_signature": False})` is used to extract a user ID for rate-limit keying. An attacker can forge any user ID to bypass per-user limits or target specific users.
**Fix:** Use HMAC hash of the raw token bytes as the rate-limit key — no decoding needed.

### MD-295 — Prescription medicines stored as unvalidated JSONB
**File:** `backend/app/models/prescription.py:21`, `backend/app/services/prescription_service.py:59`
**Issue:** `medicines` column is raw JSONB. No schema enforced on write — malformed dosage, missing medicine IDs, or impossible quantities are stored silently.
**Fix:** Define a `PrescriptionMedicineItem` Pydantic schema and validate each item before persistence. Consider adding a DB check constraint on the JSONB structure.

### MD-296 — User auto-provisioning race condition
**File:** `backend/app/dependencies.py:64-102`
**Issue:** Two concurrent first-time requests for the same Keycloak user can both pass `if not user` and both attempt to INSERT a User row. Depending on DB isolation level, this either fails with an integrity error or creates duplicate rows.
**Fix:** Replace the SELECT + INSERT pattern with PostgreSQL `INSERT ... ON CONFLICT (keycloak_sub) DO NOTHING` (upsert).

### MD-297 — Doctor can view patient prescriptions without relationship verification
**File:** `backend/app/routers/doctors.py:264-350`
**Issue:** `get_patient_prescriptions` checks doctor relationship only via `doctor_id` filter on records. Without an explicit call to `_check_doctor_patient_relationship()`, a doctor with any record for the patient can see all their prescriptions across clinics.
**Fix:** Add `_check_doctor_patient_relationship()` call at the top of the endpoint, same pattern as `get_patient_profile`.

---

## MEDIUM Priority

### MD-298 — Rate limiter fails open silently when Redis is unavailable
**File:** `backend/app/middleware/rate_limit.py:90-92`
**Issue:** `except Exception: return True, 0` — all requests allowed through with no log or alert when Redis is down.
**Fix:** Log the Redis failure with `logger.error(...)`. Emit an observable metric. Consider a simple in-process token bucket as a degraded fallback.

### MD-299 — File uploads validated by extension only, not MIME type
**File:** `backend/app/routers/uploads.py:39-50`
**Issue:** Only the file extension is checked. An attacker renames `.exe` → `.pdf` and the upload is accepted.
**Fix:** Use `python-magic` to check actual MIME type from file magic bytes. Reject if MIME doesn't match the extension whitelist.

### MD-300 — `datetime.utcnow()` deprecation — inconsistent timezone handling
**Files:** `backend/app/services/clinic_service.py:53`, `backend/app/services/clinic_service.py:116`
**Issue:** `datetime.utcnow()` is deprecated in Python 3.12. Other files correctly use `datetime.now(timezone.utc)`.
**Fix:** Global search-replace `datetime.utcnow()` → `datetime.now(timezone.utc)` across all backend files.

### MD-301 — No cursor pagination on doctor-facing vitals endpoint
**File:** `backend/app/routers/vitals.py:315-320`
**Issue:** Hard-coded `LIMIT 200` with no offset/cursor. The patient-facing endpoint already has `limit` and `days` params — add the same to the doctor-facing endpoint and remove the hard-coded 200.
**Fix:** Add `limit: int = Query(200, ge=1, le=500)` parameter consistent with the patient endpoint.

### MD-302 — N+1 clinic queries in appointments list
**File:** `backend/app/routers/appointments.py:392-431`
**Issue:** Patient and doctor names are batch-loaded, but clinic names are still fetched individually per appointment row.
**Fix:** Add `clinic_ids = list({a.clinic_id for a in appointments if a.clinic_id})` and batch-load clinic names before the serialization loop.

### MD-303 — JWT tokens stored in localStorage — XSS-readable
**File:** `frontend/src/lib/api/notifications.ts:132`, `frontend/src/lib/api.ts`
**Issue:** `localStorage.getItem("access_token")` is used throughout. Any XSS payload can read and exfiltrate the token.
**Fix (preferred):** Migrate token storage to HttpOnly, Secure, SameSite=Strict cookies managed server-side.
**Fix (interim):** Document the risk, ensure strict CSP headers, and sanitize all user-rendered content.

### MD-304 — JWKS client cache never expires — breaks on Keycloak key rotation
**File:** `backend/app/utils/security.py:13-19`
**Issue:** `_jwks_client` is a module-level singleton with `cache_keys=True` but no TTL. After Keycloak key rotation, all token verifications fail until the process restarts.
**Fix:** Set a reasonable cache lifetime (`cache_jwk_set_duration=300`) or catch `PyJWKClientError` and force a cache refresh on failure.

### MD-305 — `JSON.parse` on localStorage without try-catch
**File:** `frontend/src/lib/api.ts:25-31`
**Issue:** `JSON.parse(localStorage.getItem("clinic-store"))` will throw if the stored value is corrupted, crashing the Axios interceptor for all requests.
**Fix:** Wrap in `try { ... } catch { /* clear corrupted entry */ localStorage.removeItem("clinic-store") }`.

### MD-306 — No startup validation for required environment variables
**File:** `backend/app/config.py`
**Issue:** Critical vars like `DATABASE_URL` and `KEYCLOAK_URL` have hardcoded dev defaults. A production deploy with a missing `.env` silently connects to dev infrastructure.
**Fix:** Add a Pydantic validator that raises `ValueError` if `APP_ENV == "production"` and any critical var is still the default value.

### MD-307 — Inconsistent soft-delete filtering in admin endpoints
**Files:** Various files in `backend/app/routers/admin/`
**Issue:** Some admin list endpoints return soft-deleted records because `deleted_at.is_(None)` is missing from their queries.
**Fix:** Audit every `select()` in admin routers and ensure `.where(Model.deleted_at.is_(None))` is always present for user-facing data.

---

## Reference

| Ticket | Summary | Priority |
|--------|---------|----------|
| MD-290 | ✅ Vitals endpoint missing doctor-patient auth check | Critical |
| MD-291 | ✅ Mass-assignment via setattr loop | High |
| MD-292 | ✅ No vital value range validation | Critical |
| MD-293 | ✅ JWT token in WebSocket URL | High |
| MD-294 | Rate-limit JWT decoded without signature verification | High |
| MD-295 | Prescription medicines unvalidated JSONB | High |
| MD-296 | User provisioning race condition | High |
| MD-297 | Doctor prescriptions without relationship check | High |
| MD-298 | Rate limiter fails open when Redis down | Medium |
| MD-299 | File upload MIME type not validated | Medium |
| MD-300 | datetime.utcnow() deprecation | Medium |
| MD-301 | No cursor pagination on doctor vitals | Medium |
| MD-302 | N+1 clinic queries in appointments | Medium |
| MD-303 | Tokens in localStorage (XSS risk) | Medium |
| MD-304 | JWKS cache never expires | Medium |
| MD-305 | JSON.parse without try-catch | Medium |
| MD-306 | No prod env var validation at startup | Medium |
| MD-307 | Soft-delete filtering inconsistent | Medium |
