import time
import uuid
from collections.abc import AsyncGenerator
from unittest.mock import MagicMock, patch

import jwt as pyjwt
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.dependencies as _dependencies
from app.database import Base, MedicineBase, get_db, get_medicine_db
from app.main import app
from app.models.doctor import Doctor
from app.models.user import User

TEST_DATABASE_URL = "postgresql+asyncpg://medconnect:medconnect@postgres:5432/medconnect_test"
# The medicine catalog lives on the same Postgres instance; init.sql creates
# the medicine_db_test database alongside medconnect_test.
TEST_MEDICINE_DATABASE_URL = "postgresql+asyncpg://medconnect:medconnect@postgres:5432/medicine_db_test"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

medicine_engine = create_async_engine(TEST_MEDICINE_DATABASE_URL, echo=False)
test_medicine_session = async_sessionmaker(medicine_engine, class_=AsyncSession, expire_on_commit=False)

# Generate RSA key pair for test tokens
_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_public_key = _private_key.public_key()

PRIVATE_KEY_PEM = _private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
)
PUBLIC_KEY_PEM = _public_key.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
)


def create_test_token(
    sub: str,
    email: str = "test@example.com",
    name: str = "Test User",
    roles: list[str] | None = None,
) -> str:
    """Create a signed JWT token that mimics a Keycloak access token."""
    if roles is None:
        roles = ["patient"]

    now = int(time.time())
    payload = {
        "sub": sub,
        "email": email,
        "name": name,
        "preferred_username": email,
        "realm_access": {"roles": roles},
        "aud": "medconnect-backend",
        "iss": "http://localhost:8080/realms/medconnect",
        "iat": now,
        "exp": now + 3600,
    }
    return pyjwt.encode(payload, PRIVATE_KEY_PEM, algorithm="RS256")


# ---------------------------------------------------------------------------
# Per-test isolation for module-level state
# ---------------------------------------------------------------------------


class _PermissivePipeline:
    """Async pipeline stand-in that always reports the request under the limit."""

    def incr(self, *args, **kwargs):
        return self

    def expire(self, *args, **kwargs):
        return self

    async def execute(self):
        return [1, True]


class _PermissiveRedis:
    """Fallback for fakeredis: responds like a healthy Redis that never
    rate-limits (mirrors the middleware's fail-open behaviour)."""

    async def ping(self):
        return True

    def pipeline(self):
        return _PermissivePipeline()


@pytest.fixture(autouse=True)
def _isolated_security_state(monkeypatch):
    """Keep module-level auth/rate-limit state from leaking between tests.

    - ``app.dependencies._user_cache`` caches ``User`` objects keyed by
      Keycloak sub with a 30s TTL. Fixtures reuse fixed subs
      (``admin-123``, ``patient-123``), so without clearing, a stale user
      (with a stale role) from a previous test would be returned.
    - ``RateLimitMiddleware`` calls ``_get_redis()`` per request; without a
      patch it opens a real Redis connection. A fresh fakeredis instance per
      test gives deterministic counters; the permissive stub is a fallback
      when fakeredis isn't installed.
    """
    _dependencies._user_cache.clear()

    try:
        import fakeredis.aioredis

        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    except ImportError:  # pragma: no cover - fakeredis ships in requirements-dev.txt
        fake_redis = _PermissiveRedis()

    monkeypatch.setattr("app.middleware.rate_limit._get_redis", lambda: fake_redis)
    yield fake_redis
    _dependencies._user_cache.clear()


@pytest_asyncio.fixture(scope="function")
async def db() -> AsyncGenerator[AsyncSession, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with test_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def medicine_db() -> AsyncGenerator[AsyncSession, None]:
    async with medicine_engine.begin() as conn:
        await conn.run_sync(MedicineBase.metadata.create_all)

    async with test_medicine_session() as session:
        yield session

    async with medicine_engine.begin() as conn:
        await conn.run_sync(MedicineBase.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db: AsyncSession, medicine_db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db

    async def override_get_medicine_db():
        yield medicine_db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_medicine_db] = override_get_medicine_db

    # Mock the JWKS client to use our test RSA public key
    mock_signing_key = MagicMock()
    mock_signing_key.key = _public_key

    mock_jwks_client = MagicMock()
    mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key

    with patch("app.utils.security.get_jwks_client", return_value=mock_jwks_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def admin_user(db: AsyncSession) -> User:
    """Create an admin user."""
    user = User(
        keycloak_sub="admin-123",
        email="admin@test.com",
        full_name="Admin User",
        role="admin",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def patient_user(db: AsyncSession) -> User:
    """Create a patient user."""
    user = User(
        keycloak_sub="patient-123",
        email="patient@test.com",
        full_name="Patient User",
        role="patient",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def admin_client(client: AsyncClient, admin_user: User) -> AsyncClient:
    """Authenticated client as admin."""
    token = create_test_token(
        sub=admin_user.keycloak_sub,
        email=admin_user.email,
        name=admin_user.full_name,
        roles=["admin"],
    )
    client.headers["Authorization"] = f"Bearer {token}"
    return client


@pytest_asyncio.fixture(scope="function")
async def patient_client(client: AsyncClient, patient_user: User) -> AsyncClient:
    """Authenticated client as patient."""
    token = create_test_token(
        sub=patient_user.keycloak_sub,
        email=patient_user.email,
        name=patient_user.full_name,
        roles=["patient"],
    )
    client.headers["Authorization"] = f"Bearer {token}"
    return client


@pytest_asyncio.fixture(scope="function")
async def doctor_user(db: AsyncSession) -> User:
    """Create a doctor user."""
    user = User(
        keycloak_sub="doctor-123",
        email="doctor@test.com",
        full_name="Doctor User",
        role="doctor",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def doctor_profile(db: AsyncSession, doctor_user: User) -> Doctor:
    """Create a verified, fully-onboarded Doctor profile for ``doctor_user``."""
    doctor = Doctor(
        id=uuid.uuid4(),
        user_id=doctor_user.id,
        specialization="General Physician",
        verified=True,
        onboarding_step="completed",
    )
    db.add(doctor)
    await db.commit()
    await db.refresh(doctor)
    return doctor


@pytest_asyncio.fixture(scope="function")
async def doctor_client(
    client: AsyncClient, doctor_user: User, doctor_profile: Doctor
) -> AsyncClient:
    """Authenticated client as a verified doctor (doctor profile included)."""
    token = create_test_token(
        sub=doctor_user.keycloak_sub,
        email=doctor_user.email,
        name=doctor_user.full_name,
        roles=["doctor"],
    )
    client.headers["Authorization"] = f"Bearer {token}"
    return client


def make_auth_header(user: User, roles: list[str] | None = None) -> dict[str, str]:
    """Return an Authorization header for an existing user row."""
    token = create_test_token(
        sub=user.keycloak_sub,
        email=user.email,
        name=user.full_name,
        roles=roles if roles is not None else [user.role],
    )
    return {"Authorization": f"Bearer {token}"}


# Medicine database fixtures
@pytest_asyncio.fixture(scope="function")
async def sample_manufacturer(medicine_db: AsyncSession):
    """Create a sample manufacturer."""
    from app.models.medicine.commercial import Manufacturer

    manufacturer = Manufacturer(
        manufacturer_name="GSK Pharmaceuticals",
        country="India",
        license_number="MFG-123456",
    )
    medicine_db.add(manufacturer)
    await medicine_db.commit()
    await medicine_db.refresh(manufacturer)
    return manufacturer


@pytest_asyncio.fixture(scope="function")
async def sample_salt(medicine_db: AsyncSession):
    """Create a sample salt."""
    from app.models.medicine.salts import Salt

    salt = Salt(
        salt_name="Paracetamol",
        chemical_formula="C8H9NO2",
        description="Analgesic and antipyretic",
        habit_forming=False,
        prescription_required=False,
    )
    medicine_db.add(salt)
    await medicine_db.commit()
    await medicine_db.refresh(salt)
    return salt


@pytest_asyncio.fixture(scope="function")
async def sample_salt_strength(medicine_db: AsyncSession, sample_salt):
    """Create a sample salt strength."""
    from app.models.medicine.salts import SaltStrength

    strength = SaltStrength(
        salt_id=sample_salt.salt_id,
        strength_value=500,
        strength_unit="mg",
        is_standard_strength=True,
    )
    medicine_db.add(strength)
    await medicine_db.commit()
    await medicine_db.refresh(strength)
    return strength


@pytest_asyncio.fixture(scope="function")
async def sample_brand(medicine_db: AsyncSession, sample_manufacturer, sample_salt_strength):
    """Create a sample brand with composition."""
    from app.models.medicine.commercial import Brand, BrandComposition

    brand = Brand(
        brand_name="Crocin",
        manufacturer_id=sample_manufacturer.manufacturer_id,
        is_discontinued=False,
        drug_type="allopathy",
    )
    medicine_db.add(brand)
    await medicine_db.flush()

    composition = BrandComposition(
        brand_id=brand.brand_id,
        salt_strength_id=sample_salt_strength.salt_strength_id,
        sequence=1,
    )
    medicine_db.add(composition)
    await medicine_db.commit()
    await medicine_db.refresh(brand)
    return brand
