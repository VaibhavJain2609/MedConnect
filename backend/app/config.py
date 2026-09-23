from urllib.parse import urlparse

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Hostnames that only ever exist inside the local compose network or on a
# dev machine. If any connection URL resolves to one of these while
# APP_ENV=production, the process refuses to boot.
_LOCAL_HOSTS = {"postgres", "pgbouncer", "redis", "keycloak", "localhost", "127.0.0.1", "::1"}

# Credential markers that appear in the committed dev defaults / .env.example
# placeholders. Seeing one in a production URL means the secret was never
# overridden (or the example file was copied verbatim).
_WEAK_DB_CRED_MARKERS = ("medconnect:medconnect@", "USER:PASS@", ":PASS@")
_WEAK_REDIS_CRED_MARKERS = (":REDIS_PASS@", ":CHANGE_ME@")

# Values that are acceptable as the local-dev/placeholder admin password but
# must never authenticate the Keycloak admin REST user in production.
_WEAK_ADMIN_PASSWORDS = {"admin", "changeme", "change_me", "password"}


def _hostname(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


class Settings(BaseSettings):
    APP_NAME: str = "MedConnect"
    # Restricted to a known set by the field validator below — a typo like
    # "prod" would otherwise silently bypass every production guard.
    APP_ENV: str = "development"
    DEBUG: bool = False

    # Root logger level for the structlog/stdlib JSON pipeline in main.py.
    LOG_LEVEL: str = "INFO"

    # Comma-separated Host-header allowlist, wired to TrustedHostMiddleware
    # in main.py. Empty = middleware not installed (the ingress/ALB remains
    # the enforcement point). Recommended in production, e.g.
    # ALLOWED_HOSTS=api.example.com,medconnect.example.com
    ALLOWED_HOSTS: str = ""

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
    # Set to False in dev .env if Keycloak lacks audience mappers.
    # Forced to True by the production guard below — disabling audience
    # verification in prod accepts tokens minted for ANY client in the realm.
    VERIFY_JWT_AUDIENCE: bool = True
    KEYCLOAK_ADMIN_USER: str = "admin"
    KEYCLOAK_ADMIN_PASSWORD: str = "admin"

    # Optional — empty disables sentry_sdk.init in main.py.
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

    # Lab-report OCR ingest (services/providers/ocr.py) — disabled by default.
    # POST /api/v1/lab-results/ingest returns 503 OCR_NOT_CONFIGURED until
    # OCR_PROVIDER is set to a real backend. The "llm" provider is a stub
    # (raises OcrUnavailable) until an OpenAI-compatible vision endpoint is
    # wired in — see the provider module docstring and RUNBOOK.md.
    OCR_PROVIDER: str = "none"  # "none" | "llm"
    OCR_LLM_BASE_URL: str | None = None
    OCR_LLM_API_KEY: str | None = None
    OCR_LLM_MODEL: str | None = None
    OCR_LLM_TIMEOUT_SECONDS: float = 30.0

    # Outbound clinic webhooks — disabled by default. When False,
    # services.webhook_service.emit_event is a no-op (no delivery rows, no ARQ
    # jobs). See RUNBOOK.md § webhooks.
    WEBHOOKS_ENABLED: bool = False
    WEBHOOK_TIMEOUT_SECONDS: float = 5.0
    WEBHOOK_MAX_ATTEMPTS: int = 3

    # Medication adherence reminders — the 15-minute
    # ``send_medication_reminders`` ARQ cron task notifies patients who opted
    # in per prescription. False unregisters the cron job entirely.
    MEDICATION_REMINDERS_ENABLED: bool = True

    # Audit-log retention — the daily ``audit_retention`` ARQ cron task moves
    # audit_logs rows older than this many days into audit_log_archive and
    # deletes them from the live table. 0 disables retention (keep forever).
    AUDIT_RETENTION_DAYS: int = 365

    @field_validator("APP_ENV")
    @classmethod
    def _check_app_env(cls, v: str) -> str:
        allowed = {"development", "test", "staging", "production"}
        if v not in allowed:
            raise ValueError(f"APP_ENV must be one of {sorted(allowed)}; got {v!r}")
        return v

    @field_validator("LOG_LEVEL")
    @classmethod
    def _normalise_log_level(cls, v: str) -> str:
        level = v.strip().upper()
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if level not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {sorted(allowed)}; got {v!r}")
        return level

    @field_validator("STORAGE_BACKEND")
    @classmethod
    def _check_storage_backend(cls, v: str) -> str:
        if v not in {"local", "s3"}:
            raise ValueError(f"STORAGE_BACKEND must be 'local' or 's3'; got {v!r}")
        return v

    @model_validator(mode="after")
    def check_production_config(self) -> "Settings":
        """Fail fast at startup when APP_ENV=production and any setting still
        carries its local-dev default. Every violation is collected and
        reported in one error so a misconfigured deploy fixes everything in
        a single iteration instead of crash-looping once per variable."""
        if self.APP_ENV != "production":
            return self

        errors: list[str] = []

        # --- Connection URLs: must not resolve to compose/dev hostnames ---
        db_url_fields = (
            "DATABASE_URL",
            "DATABASE_URL_SYNC",
            "MEDICINE_DB_URL",
            "MEDICINE_DB_URL_SYNC",
        )
        for name in db_url_fields:
            url = getattr(self, name)
            if _hostname(url) in _LOCAL_HOSTS:
                errors.append(f"{name} still points at a local/dev host — set a real production database URL")
            if any(marker in url for marker in _WEAK_DB_CRED_MARKERS):
                errors.append(f"{name} still uses the default dev credential — set a real password")

        if _hostname(self.REDIS_URL) in _LOCAL_HOSTS:
            errors.append("REDIS_URL still points at a local/dev host — set a real production Redis URL")
        if any(marker in self.REDIS_URL for marker in _WEAK_REDIS_CRED_MARKERS):
            errors.append("REDIS_URL still uses the default dev credential — set a real password")

        if _hostname(self.KEYCLOAK_URL) in _LOCAL_HOSTS:
            errors.append("KEYCLOAK_URL must be set to a real Keycloak URL in production")

        # --- Public origins: https only, no localhost, no wildcards ---
        # FRONTEND_URL feeds CORSMiddleware allow_origins and CSP
        # connect-src; a "*" here is a wildcard-CORS hole.
        for name in ("FRONTEND_URL", "BACKEND_URL", "KEYCLOAK_PUBLIC_URL"):
            url = getattr(self, name)
            if "*" in url:
                errors.append(f"{name} must not contain a wildcard in production")
            if _hostname(url) in {"localhost", "127.0.0.1", "::1"}:
                errors.append(f"{name} must be set to a real production URL (got {url!r})")
            elif not url.startswith("https://"):
                errors.append(f"{name} must be an https:// URL in production (got {url!r})")

        # --- Credentials ---
        if self.KEYCLOAK_ADMIN_USER == "admin":
            errors.append("KEYCLOAK_ADMIN_USER must be changed from the 'admin' default in production")
        if self.KEYCLOAK_ADMIN_PASSWORD.strip().lower() in _WEAK_ADMIN_PASSWORDS:
            errors.append("KEYCLOAK_ADMIN_PASSWORD must be changed from the dev default in production")

        # --- Safety switches that must stay on/off ---
        if self.DEBUG:
            errors.append("DEBUG must be false in production")
        if not self.VERIFY_JWT_AUDIENCE:
            errors.append("VERIFY_JWT_AUDIENCE must be true in production — disabling it accepts tokens minted for any client in the realm")

        # --- Uploads ---
        if self.STORAGE_BACKEND == "local" and self.UPLOADS_DIR.startswith("/tmp"):
            errors.append("UPLOADS_DIR must not use /tmp in production; set STORAGE_BACKEND=s3 or use a persistent path")

        if errors:
            raise ValueError("Invalid production configuration: " + "; ".join(errors))
        return self

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
