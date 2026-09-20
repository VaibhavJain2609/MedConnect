"""PHI read-access audit middleware (DPDP / healthcare-grade audit trail).

Writes on clinical data are already captured by
``app.services.audit_service.log_change`` inside services/routers, but
reads were not. This middleware closes the gap: any ``GET`` to a
PHI-bearing path that completes with ``200`` produces an ``audit_logs``
row with ``action="READ"``.

Design constraints honored here:

- **User context**: auth dependencies call ``set_audit_user()`` on a
  ContextVar deep inside the request. That is only observable from a
  middleware that awaits the downstream app *inline in the same task*.
  ``BaseHTTPMiddleware`` would hide it (``call_next`` runs the app in a
  spawned task with a copied context — sets do not propagate back), so
  this is a pure-ASGI middleware and it MUST be registered first in
  ``main.py`` (``add_middleware`` prepends, so the first registration is
  innermost — directly above ExceptionMiddleware/router).
- **No PHI in the log**: only method, path (``scope["path"]`` never
  includes the query string), status code, resolved user id, client IP
  and request_id are stored — never the response body or query params.
- **Off the request path**: the DB insert runs in a detached
  ``asyncio.Task`` after the response has been sent, so audit latency
  is never added to the client-visible request time.
- Only ``200`` responses are logged; 401/403 denials and error paths
  leave no PHI-access record (there was no access).
"""
import asyncio
import logging
import re
import uuid

import structlog

from app.database import async_session
from app.middleware.rate_limit import _TRUSTED_PROXIES
from app.services import audit_service

_logger = logging.getLogger(__name__)

_UUID_RE = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"

# Never audit these (probes, docs, auth flows, metrics).
_SKIP_PREFIXES = ("/health", "/livez", "/metrics", "/docs", "/redoc", "/openapi.json", "/api/v1/auth")

# Ordered (path_regex, entity_type) rules. An optional first capture
# group supplies the entity id; rules without one log a collection read
# (record_id = NIL sentinel). More specific rules must precede broader
# prefixes for the same path space.
_PHI_READ_RULES: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pattern), entity_type)
    for pattern, entity_type in (
        # ---- Doctor portal: patient PHI -------------------------------
        (rf"^/api/v1/doctors/patients/({_UUID_RE})/records", "medical_records"),
        (rf"^/api/v1/doctors/patients/({_UUID_RE})/prescriptions", "prescriptions"),
        (rf"^/api/v1/doctors/patients/({_UUID_RE})/vitals", "vitals"),
        (rf"^/api/v1/doctors/patients/({_UUID_RE})/record-access", "record_access"),
        (rf"^/api/v1/doctors/patients/({_UUID_RE})(?:/|$)", "patients"),
        (r"^/api/v1/doctors/patients(?:/|$)", "patients"),  # list + search
        (rf"^/api/v1/doctors/records/({_UUID_RE})(?:/|$)", "medical_records"),  # amendments
        (rf"^/api/v1/doctors/prescriptions/({_UUID_RE})(?:/|$)", "prescriptions"),
        (r"^/api/v1/doctors/prescriptions$", "prescriptions"),
        # ---- Patient portal: own PHI ----------------------------------
        (rf"^/api/v1/patients/records/({_UUID_RE})(?:/|$)", "medical_records"),
        (r"^/api/v1/patients/records$", "medical_records"),
        (r"^/api/v1/patients/prescriptions(?:/|$)", "prescriptions"),
        (r"^/api/v1/patients/vitals(?:/|$)", "vitals"),
        (r"^/api/v1/patients/medical-history(?:/|$)", "medical_records"),
        (r"^/api/v1/patients/timeline(?:/|$)", "patient_timeline"),
        (r"^/api/v1/patients/profile(?:/|$)", "patients"),
        (r"^/api/v1/patients/record-access-requests(?:/|$)", "record_access"),
        (r"^/api/v1/patients/clinic-links(?:/|$)", "patient_clinic_links"),
        (r"^/api/v1/patients/link-code(?:/|$)", "patient_link_codes"),
        # ---- Encounters (SOAP notes — highest-density PHI) ------------
        (rf"^/api/v1/encounters/({_UUID_RE})(?:/|$)", "encounters"),
        (r"^/api/v1/encounters$", "encounters"),
        # ---- Patient lab results (PHI) --------------------------------
        (rf"^/api/v1/patients/lab-results/({_UUID_RE})(?:/|$)", "lab_results"),
        (r"^/api/v1/patients/lab-results(?:/|$)", "lab_results"),
        # ---- Global search returns patient/record matches -------------
        (r"^/api/v1/search(?:/|$)", "search"),
        # ---- Prescription PDFs / uploaded documents -------------------
        (rf"^/api/v1/prescriptions/({_UUID_RE})(?:/|$)", "prescriptions"),
        (r"^/api/v1/uploads/", "uploads"),  # object key is opaque — collection read
        # ---- Appointments / queue / billing / revenue -----------------
        (rf"^/api/v1/appointments/({_UUID_RE})(?:/|$)", "appointments"),
        (r"^/api/v1/appointments$", "appointments"),
        (r"^/api/v1/queue(?:/|$)", "queue_entries"),
        (rf"^/api/v1/billing/({_UUID_RE})(?:/|$)", "billing"),
        (r"^/api/v1/billing$", "billing"),
        (r"^/api/v1/revenue(?:/|$)", "billing"),
        # ---- Notifications (bodies may embed PHI) ---------------------
        (r"^/api/v1/notifications(?:/|$)", "notifications"),
        # ---- Clinic rosters / patient link surfaces -------------------
        (rf"^/api/v1/clinics/({_UUID_RE})/patients(?:/|$)", "patients"),
        (rf"^/api/v1/clinics/({_UUID_RE})/join-requests(?:/|$)", "patient_link_requests"),
        (rf"^/api/v1/clinics/({_UUID_RE})/invites(?:/|$)", "clinic_invites"),
        (rf"^/api/v1/clinics/({_UUID_RE})/members(?:/|$)", "clinic_members"),
        # ---- Admin PHI surfaces ---------------------------------------
        (r"^/api/v1/admin/audit(?:/|$)", "audit_logs"),
        (rf"^/api/v1/admin/lab-results/({_UUID_RE})(?:/|$)", "lab_results"),
        (r"^/api/v1/admin/lab-results(?:/|$)", "lab_results"),
        (rf"^/api/v1/admin/users/({_UUID_RE})(?:/|$)", "users"),
        (r"^/api/v1/admin/users$", "users"),
        (r"^/api/v1/admin/patients(?:/|$)", "patients"),
        (r"^/api/v1/admin/appointment", "appointments"),  # incl. appointment-requests
        (r"^/api/v1/admin/visits(?:/|$)", "visits"),
    )
)

# Keep strong references to in-flight audit writes so the event loop
# doesn't garbage-collect them mid-insert.
_background_tasks: set[asyncio.Task] = set()


def _match_phi_read(path: str) -> tuple[str, uuid.UUID] | None:
    """Return (entity_type, entity_id) for PHI-bearing GET paths, else None."""
    for pattern, entity_type in _PHI_READ_RULES:
        m = pattern.match(path)
        if m:
            entity_id = audit_service.NIL_ENTITY_ID
            if m.groups():
                try:
                    entity_id = uuid.UUID(m.group(1))
                except (ValueError, AttributeError):
                    pass
            return entity_type, entity_id
    return None


def _client_ip(scope) -> str | None:
    """Direct peer IP; honor X-Forwarded-For only from trusted proxies
    (same policy as the rate limiter — the header is spoofable otherwise)."""
    client = scope.get("client")
    host = client[0] if client else None
    if host and host in _TRUSTED_PROXIES:
        for name, value in scope.get("headers") or []:
            if name.lower() == b"x-forwarded-for":
                return value.decode("latin-1").split(",")[0].strip()
    return host


async def _persist_read_audit(
    entity_type: str,
    entity_id: uuid.UUID,
    changed_by: uuid.UUID | None,
    path: str,
    status_code: int,
    ip_address: str | None,
    request_id: str | None,
) -> None:
    """Write the audit row on a short-lived session, off the request path."""
    try:
        async with async_session() as session:
            await audit_service.log_read(
                session,
                entity_type=entity_type,
                entity_id=entity_id,
                changed_by=changed_by,
                method="GET",
                path=path,
                status_code=status_code,
                ip_address=ip_address,
                request_id=request_id,
            )
            await session.commit()
    except Exception as exc:
        # Audit failure must never surface to the request — but it must be
        # visible in ops logs because a silent gap breaks the compliance trail.
        _logger.error(
            "audit_read_persist_failed path=%s error=%s", path, exc, exc_info=True
        )


class AuditReadMiddleware:
    """Pure-ASGI middleware — see module docstring for ordering/context
    requirements. Wraps ``send`` only to observe the response status; it
    never touches the body."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") != "GET":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path.startswith(_SKIP_PREFIXES):
            await self.app(scope, receive, send)
            return

        matched = _match_phi_read(path)
        if matched is None:
            await self.app(scope, receive, send)
            return

        status_code: int | None = None

        async def send_with_status_capture(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status")
            await send(message)

        try:
            await self.app(scope, receive, send_with_status_capture)
        finally:
            if status_code == 200:
                entity_type, entity_id = matched
                # set_audit_user() ran downstream in this same context, so
                # the resolved user is visible here without re-running auth.
                changed_by = audit_service.get_audit_user()
                request_id = structlog.contextvars.get_contextvars().get("request_id")
                task = asyncio.create_task(
                    _persist_read_audit(
                        entity_type=entity_type,
                        entity_id=entity_id,
                        changed_by=changed_by,
                        path=path,
                        status_code=status_code,
                        ip_address=_client_ip(scope),
                        request_id=request_id,
                    )
                )
                _background_tasks.add(task)
                task.add_done_callback(_background_tasks.discard)
