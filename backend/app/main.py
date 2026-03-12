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
# from app.routers.admin import components as admin_components
# from app.routers.admin import medicines as admin_medicines

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
)

if settings.SENTRY_DSN:
    sentry_sdk.init(dsn=settings.SENTRY_DSN, traces_sample_rate=0.1)

app = FastAPI(
    title="MedConnect API",
    description="EMR + Patient Portal for India's Digital Health Ecosystem",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Configuration - Allow frontend to access API
allowed_origins = [settings.FRONTEND_URL]

# In development, also allow localhost variations
if settings.APP_ENV == "development":
    allowed_origins.extend([
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ])

app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

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
# app.include_router(admin_components.router, prefix="/api/v1")
# app.include_router(admin_medicines.router, prefix="/api/v1")


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
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.REDIS_URL)
        await r.ping()
        redis_ok = True
        await r.aclose()
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
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid request data",
                "details": exc.errors() if hasattr(exc, "errors") else [],
            }
        },
    )
