import asyncio
import logging
import uuid
from contextlib import asynccontextmanager

import sentry_sdk
import structlog
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from starlette.datastructures import MutableHeaders
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.middleware.audit_middleware import AuditReadMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.routers import auth, doctors, patients, notifications
from app.routers import medicines_emr, interactions, search
from app.routers.admin import brands as admin_brands
from app.routers.admin import doctors as admin_doctors
from app.routers.admin import manufacturers as admin_manufacturers
from app.routers.admin import salts as admin_salts
from app.routers.admin import stats as admin_stats
from app.routers.admin import users as admin_users
from app.routers.admin import clinics as admin_clinics
from app.routers.admin import audit as admin_audit
from app.routers.admin import lab_results as admin_lab_results
from app.routers.admin import exports as admin_exports
from app.routers.admin import broadcast as admin_broadcast
from app.routers.admin import patients as admin_patients
from app.routers import clinics
from app.routers import clinic_webhooks
from app.routers import onboarding
from app.routers import clinic_invites
from app.routers import patient_links
from app.routers import record_access
from app.routers import appointments
from app.routers import uploads
from app.routers import vitals
from app.routers import prescriptions_pdf
from app.routers import billing, revenue, queue, push
from app.routers import availability
from app.routers import encounters
from app.routers import encounters_pdf
from app.routers import lab_results
from app.routers.admin import visits as admin_visits
from app.routers.admin import health as admin_health

# merge_contextvars first so request_id (bound by RequestIDMiddleware) shows
# up on every log line. wrap_for_formatter hands structlog events to the
# stdlib ProcessorFormatter below; foreign_pre_chain applies the same
# processors to stdlib-originated records so all logs render as JSON.
_shared_log_processors = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.processors.TimeStamper(fmt="iso"),
]

structlog.configure(
    processors=[
        *_shared_log_processors,
        structlog.processors.format_exc_info,
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

_stdlib_formatter = structlog.stdlib.ProcessorFormatter(
    foreign_pre_chain=_shared_log_processors,
    processors=[
        structlog.stdlib.ProcessorFormatter.remove_processors_meta,
        structlog.processors.JSONRenderer(),
    ],
)
_stdlib_handler = logging.StreamHandler()
_stdlib_handler.setFormatter(_stdlib_formatter)
_root_logger = logging.getLogger()
if not _root_logger.handlers:
    _root_logger.addHandler(_stdlib_handler)
_root_logger.setLevel(settings.LOG_LEVEL)

if settings.SENTRY_DSN:
    sentry_sdk.init(dsn=settings.SENTRY_DSN, traces_sample_rate=0.1)

_api_docs_enabled = settings.APP_ENV != "production"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: pre-warm the Keycloak JWKS cache so the first authenticated
    # request doesn't block on the certs fetch. PyJWKClient is synchronous —
    # run it in a worker thread (prewarm_jwks logs and swallows failures).
    from app.utils.security import prewarm_jwks

    await asyncio.to_thread(prewarm_jwks)

    yield

    # Shutdown: close the rate-limit Redis client, then dispose both engines.
    from app.database import engine, medicine_engine
    from app.middleware import rate_limit as _rate_limit

    redis_client = _rate_limit._redis_client
    if redis_client is not None:
        try:
            await redis_client.aclose()
        except Exception:
            pass
    await engine.dispose()
    await medicine_engine.dispose()


app = FastAPI(
    title="MedConnect API",
    description="EMR + Patient Portal for India's Digital Health Ecosystem",
    version="0.1.0",
    docs_url="/docs" if _api_docs_enabled else None,
    redoc_url="/redoc" if _api_docs_enabled else None,
    openapi_url="/openapi.json" if _api_docs_enabled else None,
    lifespan=lifespan,
)


# CORS Configuration - Allow frontend to access API
allowed_origins = [settings.FRONTEND_URL]

# In development, also allow localhost frontend variations (never add backend ports)
if settings.APP_ENV == "development":
    allowed_origins.extend([
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ])

# AuditReadMiddleware is registered FIRST so it ends up INNERMOST
# (add_middleware prepends; last registration is outermost). It must sit
# directly above the router because it is pure-ASGI and reads the
# audit-user contextvar set by auth dependencies — any BaseHTTPMiddleware
# between it and the router would run the endpoint in a copied context
# and hide that value.
app.add_middleware(AuditReadMiddleware)


class MaintenanceModeMiddleware:
    """Pure-ASGI gate honoring the `maintenance_mode` platform setting.

    When enabled, non-admin API traffic gets 503. Exempt: health/metrics/docs
    probes, auth (so admins can still log in), and /api/v1/admin/* (the router
    already enforces require_admin, so non-admins just 403 there anyway).
    The DB read is cached for 30s to keep the hot path cheap.
    """

    _EXEMPT_PREFIXES = (
        "/health", "/livez", "/metrics", "/docs", "/redoc", "/openapi.json",
        "/api/v1/auth", "/api/v1/admin",
    )
    _CACHE_TTL = 30.0

    def __init__(self, app):
        self.app = app
        self._cached_at = 0.0
        self._cached_value = False

    async def _maintenance_on(self) -> bool:
        import time as _time

        now = _time.monotonic()
        if now - self._cached_at < self._CACHE_TTL:
            return self._cached_value
        try:
            from app.database import async_session
            from app.services import platform_settings

            async with async_session() as db:
                self._cached_value = bool(await platform_settings.get_setting(db, "maintenance_mode"))
            self._cached_at = now
        except Exception:
            # Fail open — a settings-DB outage must not take the API down
            self._cached_at = now  # still cache to avoid hammering a down DB
        return self._cached_value

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope.get("path", "")
        if path.startswith("/api/v1") and not any(path.startswith(p) for p in self._EXEMPT_PREFIXES):
            if await self._maintenance_on():
                response = JSONResponse(
                    status_code=503,
                    content={"error": {"code": "MAINTENANCE_MODE", "message": "Platform is under maintenance — please try again shortly"}},
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


app.add_middleware(MaintenanceModeMiddleware)

# Prometheus metrics at /metrics — instrumented AFTER the add_middleware
# calls so it ends up outermost and still observes 429s/redirects from the
# rate-limiter and CORS layers. Scraped in-cluster only; the Ingress path
# rules never expose it externally.
Instrumentator().instrument(app).expose(app, include_in_schema=False)

app.add_middleware(RateLimitMiddleware)

# NOTE: the audit user is set by auth dependencies (set_audit_user(user.id)
# in app/dependencies.py). There is intentionally no middleware resetting it
# to None here — doing so would wipe the real user bound for the request.

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Clinic-Id", "X-Forwarded-For", "X-Request-Id"],
    expose_headers=["X-Total-Count", "X-Next-Cursor", "X-Request-Id"],
)


# Security headers (nosniff, X-Frame-Options, Referrer-Policy,
# Permissions-Policy, API CSP, prod-only HSTS, and Cache-Control: no-store
# on /api/v1/*) live in app/middleware/security_headers.py. Registered at
# this point in the stack — same position the old @app.middleware("http")
# function occupied — so headers are injected outside CORS/rate-limit and
# also land on 429s, error envelopes and CORS preflight responses.
app.add_middleware(SecurityHeadersMiddleware)


class RequestIDMiddleware:
    """Pure-ASGI middleware: propagate an inbound X-Request-Id or generate
    one, echo it on the response, and bind it to structlog contextvars so
    every log line emitted during the request carries request_id.

    Pure ASGI (not BaseHTTPMiddleware) so the contextvar binding covers the
    entire downstream stack — endpoints, dependencies, and other middleware.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = None
        for name, value in scope.get("headers") or []:
            if name.lower() == b"x-request-id":
                request_id = value.decode("latin-1")
                break
        if not request_id:
            request_id = str(uuid.uuid4())

        structlog.contextvars.bind_contextvars(request_id=request_id)

        async def send_with_request_id(message):
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)["X-Request-Id"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            structlog.contextvars.clear_contextvars()


# Optional Host-header allowlist (ALLOWED_HOSTS, comma-separated). Empty =
# middleware not installed — the ingress/ALB remains the enforcement point.
# Registered before RequestIDMiddleware so even a rejected host still gets a
# request_id + security headers on its 400 response.
if settings.ALLOWED_HOSTS:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[
            host.strip() for host in settings.ALLOWED_HOSTS.split(",") if host.strip()
        ],
    )

# Registered last → outermost middleware, so request_id is bound before
# CORS/rate-limit/security-header handling and reaches every log call.
app.add_middleware(RequestIDMiddleware)

app.include_router(auth.router)
app.include_router(patients.router)
app.include_router(doctors.router)
app.include_router(notifications.router)
app.include_router(search.router)

# Medicine endpoints (EMR schema)
app.include_router(medicines_emr.router, prefix="/api/v1")
app.include_router(interactions.router, prefix="/api/v1")

# Admin endpoints (protected) - EMR schema
app.include_router(admin_brands.router, prefix="/api/v1")
app.include_router(admin_doctors.router)
app.include_router(admin_manufacturers.router, prefix="/api/v1")
app.include_router(admin_salts.router, prefix="/api/v1")
app.include_router(admin_stats.router)
app.include_router(admin_users.router)
app.include_router(admin_clinics.router)
app.include_router(admin_audit.router)
app.include_router(admin_audit.reports_router)
app.include_router(admin_audit.audit_logs_router)
app.include_router(admin_lab_results.router)
app.include_router(admin_exports.router)
app.include_router(admin_broadcast.router)
app.include_router(admin_patients.router)
# clinic_invites before clinics: /api/v1/clinics/search must match before
# clinics.router's /{clinic_id} path param swallows the literal "search".
app.include_router(clinic_invites.router)
app.include_router(clinics.router)
app.include_router(clinic_webhooks.router)
app.include_router(onboarding.router)
app.include_router(patient_links.router)
app.include_router(record_access.router)
app.include_router(appointments.router)
app.include_router(uploads.router)
app.include_router(vitals.router)
app.include_router(prescriptions_pdf.router)
app.include_router(billing.router)
app.include_router(revenue.router)
app.include_router(queue.router)
app.include_router(push.router)
app.include_router(availability.router)
app.include_router(encounters.router)
app.include_router(encounters_pdf.router)
app.include_router(lab_results.router)
app.include_router(admin_visits.router)
app.include_router(admin_health.router)
# NOTE: routers/medicines.py, routers/prescriptions.py,
# routers/admin/medicines.py and routers/admin/components.py are dead/broken
# and have been removed — do not re-add imports or include_router calls.


@app.get("/livez", include_in_schema=False)
async def livez():
    """Shallow liveness probe — 200 if the process can serve requests.

    No dependency checks; a DB/Redis outage must NOT restart the pod.
    /health remains the deep readiness check."""
    return {"status": "ok"}


@app.get("/health")
async def health():
    from sqlalchemy import text

    from app.database import async_session, medicine_async_session

    db_ok = False
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
            db_ok = True
    except Exception:
        pass

    medicine_db_ok = False
    try:
        async with medicine_async_session() as session:
            await session.execute(text("SELECT 1"))
            medicine_db_ok = True
    except Exception:
        pass

    redis_ok = False
    try:
        from app.middleware.rate_limit import _get_redis
        await _get_redis().ping()
        redis_ok = True
    except Exception:
        pass

    all_ok = db_ok and medicine_db_ok and redis_ok
    return JSONResponse(
        status_code=status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "ok" if all_ok else "degraded",
            "db": "ok" if db_ok else "error",
            "medicine_db": "ok" if medicine_db_ok else "error",
            "redis": "ok" if redis_ok else "error",
            "version": "0.1.0",
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Unify the error envelope: always emit {"error": {"code", "message"}}
    at the TOP LEVEL, whether the endpoint raised detail as a plain string
    or as the {"error": {...}} dict convention. StarletteHTTPException covers
    both fastapi.HTTPException and framework-raised errors (404/405/etc)."""
    detail = exc.detail
    if isinstance(detail, dict) and isinstance(detail.get("error"), dict):
        error = detail["error"]
        code = error.get("code") or f"HTTP_{exc.status_code}"
        message = error.get("message") or "Request failed"
    elif isinstance(detail, dict):
        code = detail.get("code") or f"HTTP_{exc.status_code}"
        message = detail.get("message") or "Request failed"
    else:
        code = f"HTTP_{exc.status_code}"
        message = str(detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": code, "message": message}},
        headers=exc.headers,
    )


@app.exception_handler(422)
async def validation_exception_handler(request: Request, exc):
    # MD-395: Do not expose Pydantic field names/types — they leak internal schema details.
    # But a deliberate HTTPException(422) from app code carries a domain error
    # envelope that must pass through untouched (INVALID_TRANSITION etc.).
    detail = getattr(exc, "detail", None)
    if isinstance(exc, HTTPException) and isinstance(detail, dict) and "error" in detail:
        return JSONResponse(status_code=exc.status_code, content=detail, headers=exc.headers)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid request data",
            }
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger = structlog.get_logger()
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": {"code": "INTERNAL_SERVER_ERROR", "message": "An unexpected error occurred"}},
    )
