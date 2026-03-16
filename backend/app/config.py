from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "MedConnect"
    APP_ENV: str = "development"
    DEBUG: bool = True

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

    SENTRY_DSN: str = ""

    BACKEND_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:3000"

    # File storage
    STORAGE_BACKEND: str = "local"  # "local" | "s3"
    UPLOADS_DIR: str = "/tmp/medconnect-uploads"

    @model_validator(mode="after")
    def check_production_config(self) -> "Settings":
        if self.APP_ENV == "production":
            if "@postgres:5432" in self.DATABASE_URL:
                raise ValueError("DATABASE_URL must be set to a real production database in production")
            if self.KEYCLOAK_URL == "http://keycloak:8080":
                raise ValueError("KEYCLOAK_URL must be set to a real Keycloak URL in production")
            if self.REDIS_URL == "redis://redis:6379/0":
                raise ValueError("REDIS_URL must be set to a real Redis URL in production")
        return self

    class Config:
        env_file = ".env"


settings = Settings()
