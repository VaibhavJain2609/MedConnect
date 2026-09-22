"""Production-config guard tests for app.config.Settings.

Every test builds a fresh ``Settings(_env_file=None)`` so a developer's local
``backend/.env`` can never leak in, and the ``clean_env`` fixture scrubs all
settings env vars so ambient CI/dev environment can't either.
"""

import pytest
from pydantic import ValidationError

from app.config import Settings

# Every env var Settings reads — scrubbed per test so defaults are exercised.
_SETTINGS_ENV_VARS = [
    "APP_NAME", "APP_ENV", "DEBUG", "LOG_LEVEL", "ALLOWED_HOSTS",
    "DATABASE_URL", "DATABASE_URL_SYNC",
    "MEDICINE_DB_URL", "MEDICINE_DB_URL_SYNC", "DB_TRANSACTION_POOLING",
    "REDIS_URL",
    "KEYCLOAK_URL", "KEYCLOAK_PUBLIC_URL", "KEYCLOAK_REALM",
    "KEYCLOAK_CLIENT_ID", "VERIFY_JWT_AUDIENCE",
    "KEYCLOAK_ADMIN_USER", "KEYCLOAK_ADMIN_PASSWORD",
    "SENTRY_DSN", "BACKEND_URL", "FRONTEND_URL",
    "RATE_LIMIT_USER_PER_MINUTE", "JITSI_BASE_URL",
    "STORAGE_BACKEND", "UPLOADS_DIR",
    "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM", "SMTP_TLS",
    "MSG91_AUTH_KEY", "MSG91_AUTHKEY", "MSG91_SENDER_ID", "MSG91_TEMPLATE_ID",
    "WHATSAPP_ACCESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID",
    "WHATSAPP_BUSINESS_ACCOUNT_ID", "WHATSAPP_TEMPLATE_NAME", "WHATSAPP_TEMPLATE_LANG",
    "VAPID_SUBJECT", "VAPID_PRIVATE_KEY", "VAPID_PUBLIC_KEY",
    "OCR_PROVIDER", "OCR_LLM_BASE_URL", "OCR_LLM_API_KEY", "OCR_LLM_MODEL",
    "OCR_LLM_TIMEOUT_SECONDS",
]

# A fully-populated, guard-passing production config. Individual tests
# override one key at a time to prove it is the failing variable.
_PROD_ENV = {
    "APP_ENV": "production",
    "DATABASE_URL": "postgresql+asyncpg://app_user:s3cr3t@db.prod.internal:5432/medconnect",
    "DATABASE_URL_SYNC": "postgresql://app_user:s3cr3t@db.prod.internal:5432/medconnect",
    "MEDICINE_DB_URL": "postgresql+asyncpg://app_user:s3cr3t@db.prod.internal:5432/medconnect_medicines",
    "MEDICINE_DB_URL_SYNC": "postgresql://app_user:s3cr3t@db.prod.internal:5432/medconnect_medicines",
    "REDIS_URL": "redis://:s3cr3t@redis.prod.internal:6379/0",
    "KEYCLOAK_URL": "http://keycloak.medconnect-prod.svc.cluster.local:8080",
    "KEYCLOAK_PUBLIC_URL": "https://auth.example.com",
    "KEYCLOAK_ADMIN_USER": "kc-admin",
    "KEYCLOAK_ADMIN_PASSWORD": "s3cr3t-not-admin",
    "FRONTEND_URL": "https://app.example.com",
    "BACKEND_URL": "https://api.example.com",
    "UPLOADS_DIR": "/data/uploads",
}


@pytest.fixture
def clean_env(monkeypatch):
    for name in _SETTINGS_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------

def test_development_defaults_construct(clean_env):
    s = _settings()
    assert s.APP_ENV == "development"


def test_production_full_config_passes(clean_env):
    s = _settings(**_PROD_ENV)
    assert s.APP_ENV == "production"


def test_env_var_path_also_enforced(clean_env):
    """Same guard must fire when values arrive via real env vars."""
    clean_env.setenv("APP_ENV", "production")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


# ---------------------------------------------------------------------------
# Production guard — dev defaults must fail
# ---------------------------------------------------------------------------

def test_production_rejects_all_dev_defaults(clean_env):
    with pytest.raises(ValidationError) as exc:
        _settings(APP_ENV="production")
    msg = str(exc.value)
    for name in (
        "DATABASE_URL", "MEDICINE_DB_URL", "REDIS_URL", "KEYCLOAK_URL",
        "FRONTEND_URL", "BACKEND_URL", "KEYCLOAK_PUBLIC_URL",
        "KEYCLOAK_ADMIN_USER", "KEYCLOAK_ADMIN_PASSWORD", "UPLOADS_DIR",
    ):
        assert name in msg, f"expected {name} in error: {msg}"


@pytest.mark.parametrize(
    "field",
    ["DATABASE_URL", "DATABASE_URL_SYNC", "MEDICINE_DB_URL", "MEDICINE_DB_URL_SYNC"],
)
def test_production_rejects_dev_db_host(clean_env, field):
    env = {**_PROD_ENV, field: "postgresql+asyncpg://app_user:s3cr3t@postgres:5432/medconnect"}
    with pytest.raises(ValidationError) as exc:
        _settings(**env)
    assert field in str(exc.value)


def test_production_rejects_default_db_password_on_real_host(clean_env):
    env = {
        **_PROD_ENV,
        "DATABASE_URL": "postgresql+asyncpg://medconnect:medconnect@db.prod.internal:5432/medconnect",
    }
    with pytest.raises(ValidationError) as exc:
        _settings(**env)
    assert "DATABASE_URL" in str(exc.value)


def test_production_rejects_dev_redis_host(clean_env):
    env = {**_PROD_ENV, "REDIS_URL": "redis://:s3cr3t@redis:6379/0"}
    with pytest.raises(ValidationError) as exc:
        _settings(**env)
    assert "REDIS_URL" in str(exc.value)


def test_production_rejects_compose_keycloak_url(clean_env):
    env = {**_PROD_ENV, "KEYCLOAK_URL": "http://keycloak:8080"}
    with pytest.raises(ValidationError) as exc:
        _settings(**env)
    assert "KEYCLOAK_URL" in str(exc.value)


# ---------------------------------------------------------------------------
# Production guard — public origins / CORS
# ---------------------------------------------------------------------------

def test_production_rejects_wildcard_frontend_url(clean_env):
    """FRONTEND_URL feeds CORSMiddleware allow_origins — '*' is a wildcard-CORS hole."""
    env = {**_PROD_ENV, "FRONTEND_URL": "*"}
    with pytest.raises(ValidationError) as exc:
        _settings(**env)
    assert "FRONTEND_URL" in str(exc.value)


@pytest.mark.parametrize("field", ["FRONTEND_URL", "BACKEND_URL", "KEYCLOAK_PUBLIC_URL"])
def test_production_rejects_localhost_public_urls(clean_env, field):
    env = {**_PROD_ENV, field: "http://localhost:3000"}
    with pytest.raises(ValidationError) as exc:
        _settings(**env)
    assert field in str(exc.value)


@pytest.mark.parametrize("field", ["FRONTEND_URL", "BACKEND_URL", "KEYCLOAK_PUBLIC_URL"])
def test_production_rejects_plain_http_public_urls(clean_env, field):
    env = {**_PROD_ENV, field: "http://app.example.com"}
    with pytest.raises(ValidationError) as exc:
        _settings(**env)
    assert field in str(exc.value)


# ---------------------------------------------------------------------------
# Production guard — credentials and safety switches
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad_password", ["admin", "CHANGE_ME", "password"])
def test_production_rejects_weak_admin_password(clean_env, bad_password):
    env = {**_PROD_ENV, "KEYCLOAK_ADMIN_PASSWORD": bad_password}
    with pytest.raises(ValidationError) as exc:
        _settings(**env)
    assert "KEYCLOAK_ADMIN_PASSWORD" in str(exc.value)


def test_production_rejects_default_admin_user(clean_env):
    env = {**_PROD_ENV, "KEYCLOAK_ADMIN_USER": "admin"}
    with pytest.raises(ValidationError) as exc:
        _settings(**env)
    assert "KEYCLOAK_ADMIN_USER" in str(exc.value)


def test_production_rejects_debug_true(clean_env):
    env = {**_PROD_ENV, "DEBUG": True}
    with pytest.raises(ValidationError) as exc:
        _settings(**env)
    assert "DEBUG" in str(exc.value)


def test_production_rejects_verify_jwt_audience_false(clean_env):
    env = {**_PROD_ENV, "VERIFY_JWT_AUDIENCE": False}
    with pytest.raises(ValidationError) as exc:
        _settings(**env)
    assert "VERIFY_JWT_AUDIENCE" in str(exc.value)


def test_production_rejects_tmp_uploads_dir(clean_env):
    env = {**_PROD_ENV, "UPLOADS_DIR": "/tmp/uploads"}
    with pytest.raises(ValidationError) as exc:
        _settings(**env)
    assert "UPLOADS_DIR" in str(exc.value)


# ---------------------------------------------------------------------------
# Field validators (env-agnostic)
# ---------------------------------------------------------------------------

def test_invalid_app_env_rejected(clean_env):
    """A typo like 'prod' must not silently bypass the production guards."""
    with pytest.raises(ValidationError):
        _settings(APP_ENV="prod")


@pytest.mark.parametrize("env", ["development", "test", "staging", "production"])
def test_valid_app_envs_accepted(clean_env, env):
    if env == "production":
        s = _settings(**_PROD_ENV)
    else:
        s = _settings(APP_ENV=env)
    assert s.APP_ENV == env


def test_invalid_log_level_rejected(clean_env):
    with pytest.raises(ValidationError):
        _settings(LOG_LEVEL="CHATTER")


def test_log_level_normalised(clean_env):
    assert _settings(LOG_LEVEL="debug").LOG_LEVEL == "DEBUG"


def test_invalid_storage_backend_rejected(clean_env):
    with pytest.raises(ValidationError):
        _settings(STORAGE_BACKEND="ftp")


def test_allowed_hosts_and_sentry_optional(clean_env):
    s = _settings()
    assert s.ALLOWED_HOSTS == ""
    assert s.SENTRY_DSN == ""
