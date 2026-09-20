from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "MedConnect"
    APP_ENV: str = "development"
    DEBUG: bool = False

    DATABASE_URL: str = "postgresql+asyncpg://medconnect:medconnect@postgres:5432/medconnect"
    DATABASE_URL_SYNC: str = "postgresql://medconnect:medconnect@postgres:5432/medconnect"

    # Separate database for medicine data
    MEDICINE_DB_URL: str = "postgresql+asyncpg://medconnect:medconnect@postgres:5432/medconnect_medicines"
    MEDICINE_DB_URL_SYNC: str = "postgresql://medconnect:medconnect@postgres:5432/medconnect_medicines"

    REDIS_URL: str = "redis://redis:6379/0"

    KEYCLOAK_URL: str = "http://keycloak:8080"
    KEYCLOAK_PUBLIC_URL: str = "http://localhost:8080"
    KEYCLOAK_REALM: str = "medconnect"
    KEYCLOAK_CLIENT_ID: str = "medconnect-backend"
    # Set to False in dev .env if Keycloak lacks audience mappers
    VERIFY_JWT_AUDIENCE: bool = True
    KEYCLOAK_ADMIN_USER: str = "admin"
    KEYCLOAK_ADMIN_PASSWORD: str = "admin"

    SENTRY_DSN: str = ""

    BACKEND_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:3000"

    # Teleconsultation — base URL for generated Jitsi meeting rooms
    JITSI_BASE_URL: str = "https://meet.jit.si"

    # File storage
    STORAGE_BACKEND: str = "local"  # "local" | "s3"
    UPLOADS_DIR: str = "/tmp/medconnect-uploads"

    # Notification channels — all optional. When unset the channel is skipped
    # with a logged `channel_unavailable` result; safe to leave empty in any env.
    # Email (SMTP)
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM: str | None = None
    SMTP_TLS: bool = True  # STARTTLS after connect
    # SMS via MSG91 (provider stub — real wiring pending)
    MSG91_AUTH_KEY: str | None = None
    MSG91_SENDER_ID: str | None = None
    MSG91_TEMPLATE_ID: str | None = None
    # WhatsApp Business Cloud API (provider stub — real wiring pending)
    WHATSAPP_ACCESS_TOKEN: str | None = None
    WHATSAPP_PHONE_NUMBER_ID: str | None = None
    WHATSAPP_BUSINESS_ACCOUNT_ID: str | None = None

    @model_validator(mode="after")
    def check_production_config(self) -> "Settings":
        if self.APP_ENV == "production":
            if "@postgres:5432" in self.DATABASE_URL:
                raise ValueError("DATABASE_URL must be set to a real production database in production")
            if self.KEYCLOAK_URL == "http://keycloak:8080":
                raise ValueError("KEYCLOAK_URL must be set to a real Keycloak URL in production")
            if self.REDIS_URL == "redis://redis:6379/0":
                raise ValueError("REDIS_URL must be set to a real Redis URL in production")
            if "localhost" in self.FRONTEND_URL:
                raise ValueError("FRONTEND_URL must be set to a real production URL in production")
            if self.KEYCLOAK_ADMIN_USER == "admin" and self.KEYCLOAK_ADMIN_PASSWORD == "admin":
                raise ValueError("KEYCLOAK_ADMIN_USER and KEYCLOAK_ADMIN_PASSWORD must be changed from defaults in production")
            if self.STORAGE_BACKEND == "local" and self.UPLOADS_DIR.startswith("/tmp"):
                raise ValueError("UPLOADS_DIR must not use /tmp in production; set STORAGE_BACKEND=s3 or use a persistent path")
        return self

    class Config:
        env_file = ".env"


settings = Settings()
