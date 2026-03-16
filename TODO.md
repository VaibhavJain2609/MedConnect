# MedConnect — Security & Quality Backlog

Generated from codebase audit. Critical issues (MD-290–293) have been fixed.
Remaining items are tracked below by priority.

---

## HIGH Priority

✅ All HIGH priority tickets (MD-294–MD-297) have been resolved.

---

## MEDIUM Priority

✅ All MEDIUM priority tickets (MD-298–MD-307) have been resolved.

**Notes:**
- MD-302: Already batch-loading clinic names before serialization loop — no change needed.
- MD-305: `JSON.parse` already wrapped in try/catch in `api.ts` — no change needed.
- MD-307: Audit of all admin routers confirmed `deleted_at.is_(None)` filtering is consistently applied — no change needed.

---

## Reference

| Ticket | Summary | Priority |
|--------|---------|----------|
| MD-290 | ✅ Vitals endpoint missing doctor-patient auth check | Critical |
| MD-291 | ✅ Mass-assignment via setattr loop | High |
| MD-292 | ✅ No vital value range validation | Critical |
| MD-293 | ✅ JWT token in WebSocket URL | High |
| MD-294 | ✅ Rate-limit JWT decoded without signature verification | High |
| MD-295 | ✅ Prescription medicines unvalidated JSONB | High |
| MD-296 | ✅ User provisioning race condition | High |
| MD-297 | ✅ Doctor prescriptions without relationship check | High |
| MD-298 | ✅ Rate limiter fails open when Redis down | Medium |
| MD-299 | ✅ File upload MIME type not validated | Medium |
| MD-300 | ✅ datetime.utcnow() deprecation | Medium |
| MD-301 | ✅ No cursor pagination on doctor vitals | Medium |
| MD-302 | ✅ N+1 clinic queries in appointments (already fixed) | Medium |
| MD-303 | ✅ Tokens in localStorage (XSS risk) | Medium |
| MD-304 | ✅ JWKS cache never expires | Medium |
| MD-305 | ✅ JSON.parse without try-catch (already fixed) | Medium |
| MD-306 | ✅ No prod env var validation at startup | Medium |
| MD-307 | ✅ Soft-delete filtering inconsistent (audit: all OK) | Medium |
