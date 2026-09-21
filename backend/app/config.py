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

    # Set true when DATABASE_URL / MEDICINE_DB_URL point at PgBouncer in
    # pool_mode=transaction: disables asyncpg's client-side prepared-statement
    # cache, which breaks when server connections are recycled per transaction.
    # See docs/pgbouncer.md.
    DB_TRANSACTION_POOLING: bool = False

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

    # Rate limiting — flat per-user bucket (requests/minute) applied on top of
    # the per-caller (IP/token-hash) limit whenever a Bearer JWT is present.
    # Deliberately higher than the per-IP category limits so legitimate users
    # behind shared NAT aren't throttled by neighbors, while a single account
    # still can't hammer the API or evade limits by rotating tokens.
    RATE_LIMIT_USER_PER_MINUTE: int = 240

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
    # SMS via MSG91 (services/providers/sms.py — flow API adapter)
    MSG91_AUTH_KEY: str | None = None
    MSG91_AUTHKEY: str | None = None  # preferred name; MSG91_AUTH_KEY still honoured
    MSG91_SENDER_ID: str | None = None
    MSG91_TEMPLATE_ID: str | None = None
    # WhatsApp Business Cloud API (services/providers/whatsapp.py — Graph API adapter)
    WHATSAPP_ACCESS_TOKEN: str | None = None
    WHATSAPP_PHONE_NUMBER_ID: str | None = None
    WHATSAPP_BUSINESS_ACCOUNT_ID: str | None = None
    WHATSAPP_TEMPLATE_NAME: str | None = None  # approved template; required to send
    WHATSAPP_TEMPLATE_LANG: str = "en_US"
    # Web Push (services/providers/webpush.py — VAPID-signed requests via
    # pywebpush). Generate a keypair with `npx web-push generate-vapid-keys`;
    # never commit keys. All three must be set or the channel is skipped.
    VAPID_SUBJECT: str | None = None    # contact URI, e.g. "mailto:ops@example.com"
    VAPID_PRIVATE_KEY: str | None = None  # base64url VAPID private key
    VAPID_PUBLIC_KEY: str | None = None   # base64url public key (served at /api/v1/push/vapid-public)

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
