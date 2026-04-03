import sentry_sdk
import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.middleware.rate_limit import RateLimitMiddleware
from app.routers import auth, doctors, patients, notifications
from app.routers import medicines_emr, interactions
from app.routers.admin import brands as admin_brands
from app.routers.admin import doctors as admin_doctors
from app.routers.admin import manufacturers as admin_manufacturers
from app.routers.admin import salts as admin_salts
from app.routers.admin import stats as admin_stats
from app.routers.admin import users as admin_users
from app.routers.admin import clinics as admin_clinics
from app.routers.admin import audit as admin_audit
from app.routers.admin import lab_results as admin_lab_results
from app.routers import clinics
from app.routers import onboarding
from app.routers import clinic_invites
from app.routers import patient_links
from app.routers import record_access
from app.routers import appointments
from app.routers import uploads
from app.routers import vitals
from app.routers import prescriptions_pdf
from app.routers import billing, revenue, queue
from app.routers.admin import components as admin_components
from app.routers.admin import medicines as admin_medicines

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
)

if settings.SENTRY_DSN:
    sentry_sdk.init(dsn=settings.SENTRY_DSN, traces_sample_rate=0.1)

_api_docs_enabled = settings.APP_ENV != "production"

app = FastAPI(
    title="MedConnect API",
    description="EMR + Patient Portal for India's Digital Health Ecosystem",
    version="0.1.0",
    docs_url="/docs" if _api_docs_enabled else None,
    redoc_url="/redoc" if _api_docs_enabled else None,
    openapi_url="/openapi.json" if _api_docs_enabled else None,
)

# CORS Configuration - Allow frontend to access API
allowed_origins = [settings.FRONTEND_URL]

# In development, also allow localhost frontend variations (never add backend ports)
if settings.APP_ENV == "development":
    allowed_origins.extend([
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ])

app.add_middleware(RateLimitMiddleware)


@app.middleware("http")
async def set_audit_context(request: Request, call_next):
    from app.services.audit_service import set_audit_user
    try:
        set_audit_user(None)
    except Exception:
        pass
    response = await call_next(request)
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Clinic-Id", "X-Forwarded-For"],
    expose_headers=["X-Total-Count", "X-Next-Cursor"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    # API-level CSP: strict policy for JSON/REST responses.
    # No unsafe-inline — the backend serves data, not HTML/JS/CSS.
    # frame-ancestors supersedes X-Frame-Options in modern browsers.
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; "
        "script-src 'none'; "
        "style-src 'none'; "
        "img-src 'none'; "
        "font-src 'none'; "
        f"connect-src 'self' {settings.FRONTEND_URL}; "
        "frame-ancestors 'none';"
    )
    if settings.APP_ENV == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

app.include_router(auth.router)
app.include_router(patients.router)
app.include_router(doctors.router)
app.include_router(notifications.router)

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
app.include_router(admin_lab_results.router)
app.include_router(clinics.router)
app.include_router(onboarding.router)
app.include_router(clinic_invites.router)
app.include_router(patient_links.router)
app.include_router(record_access.router)
app.include_router(appointments.router)
app.include_router(uploads.router)
app.include_router(vitals.router)
app.include_router(prescriptions_pdf.router)
app.include_router(billing.router)
app.include_router(revenue.router)
app.include_router(queue.router)
app.include_router(admin_components.router, prefix="/api/v1")
app.include_router(admin_medicines.router, prefix="/api/v1")


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


@app.exception_handler(422)
async def validation_exception_handler(request: Request, exc):
    # MD-395: Do not expose Pydantic field names/types — they leak internal schema details
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
