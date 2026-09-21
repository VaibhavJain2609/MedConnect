"""Round-10 coverage for the auth router + token-claim sync pipeline.

Covers:
- GET /api/v1/auth/me: auto-provisioning (patient + doctor incl. Doctor
  profile), claim sync (name/email/role — the r2 propagation fix), role
  priority (admin > doctor > patient), the MD-383 in-process user cache,
  erased-user PII protection, and token edge cases (missing header,
  malformed, expired, wrong key, wrong issuer, wrong audience, missing sub).
- POST /api/v1/auth/set-role: patient self-assign, doctor gating via clinic
  invite code (missing/invalid/expired/exhausted/wrong-role invite), the
  admin bypass, consent_version capture, and invite non-consumption.

``assign_realm_role`` (Keycloak Admin REST) is monkeypatched — no real
Keycloak in tests. JWKS is mocked by conftest's ``client`` fixture; token
edge cases are exercised by crafting JWTs directly.
"""

import time
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import jwt as pyjwt
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.dependencies as _dependencies
from app.models.clinic import Clinic
from app.models.clinic_invite import ClinicInvite
from app.models.doctor import Doctor
from app.models.user import User
from tests.conftest import PRIVATE_KEY_PEM, create_test_token

pytestmark = pytest.mark.asyncio

ISSUER = "http://localhost:8080/realms/medconnect"
AUDIENCE = "medconnect-backend"

# A second RSA keypair — tokens signed with it must be rejected by the
# mocked JWKS client (which always returns the conftest public key).
_OTHER_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_PRIVATE_KEY_PEM = _OTHER_PRIVATE_KEY.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
)


def _encode(payload: dict, key=PRIVATE_KEY_PEM) -> str:
    return pyjwt.encode(payload, key, algorithm="RS256")


def _payload(
    sub: str | None = "sub-1",
    roles: list[str] | None = None,
    email: str = "edge@test.com",
    name: str = "Edge Case",
    exp: int | None = None,
    iss: str = ISSUER,
    aud: str = AUDIENCE,
) -> dict:
    now = int(time.time())
    payload = {
        "email": email,
        "name": name,
        "preferred_username": email,
        "realm_access": {"roles": roles if roles is not None else ["patient"]},
        "aud": aud,
        "iss": iss,
        "iat": now,
        "exp": exp if exp is not None else now + 3600,
    }
    if sub is not None:
        payload["sub"] = sub
    return payload


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_keycloak_admin(monkeypatch):
    """Stub out the Keycloak Admin REST call made by POST /auth/set-role."""
    mock = AsyncMock()
    monkeypatch.setattr("app.routers.auth.assign_realm_role", mock)
    return mock


@pytest_asyncio.fixture
async def clinic(db: AsyncSession, admin_user: User) -> Clinic:
    c = Clinic(id=uuid.uuid4(), name="Invite Clinic", city="Pune", created_by=admin_user.id)
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


async def _make_invite(
    db: AsyncSession,
    clinic_id,
    creator_id,
    *,
    code: str = "INVITE1",
    role: str = "doctor",
    expires_at: datetime | None = None,
    max_uses: int | None = None,
    use_count: int = 0,
) -> ClinicInvite:
    invite = ClinicInvite(
        id=uuid.uuid4(),
        clinic_id=clinic_id,
        invite_type="code",
        code=code,
        role=role,
        expires_at=expires_at or (datetime.now(timezone.utc) + timedelta(days=7)),
        max_uses=max_uses,
        use_count=use_count,
        created_by=creator_id,
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    return invite


# ---------------------------------------------------------------------------
# GET /auth/me — provisioning
# ---------------------------------------------------------------------------


class TestMeProvisioning:
    async def test_provisions_patient_row(self, client, db):
        sub = f"new-{uuid.uuid4()}"
        token = create_test_token(
            sub=sub, email="newbie@test.com", name="New Patient", roles=["patient"]
        )
        resp = await client.get("/api/v1/auth/me", headers=_auth(token))
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["email"] == "newbie@test.com"
        assert body["full_name"] == "New Patient"
        assert body["role"] == "patient"
        assert body["language_pref"] == "en"

        user = await db.scalar(select(User).where(User.keycloak_sub == sub))
        assert user is not None
        assert str(user.id) == body["id"]

    async def test_provisions_doctor_with_profile(self, client, db):
        sub = f"new-{uuid.uuid4()}"
        token = create_test_token(
            sub=sub, email="newdoc@test.com", name="New Doc", roles=["doctor"]
        )
        resp = await client.get("/api/v1/auth/me", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["role"] == "doctor"

        user = await db.scalar(select(User).where(User.keycloak_sub == sub))
        doctor = await db.scalar(
            select(Doctor).where(Doctor.user_id == user.id, Doctor.deleted_at.is_(None))
        )
        assert doctor is not None

    async def test_no_roles_claim_defaults_to_patient(self, client, db):
        """A token with an empty realm_access.roles list provisions as patient."""
        sub = f"new-{uuid.uuid4()}"
        token = _encode(_payload(sub=sub, roles=[], email="noroles@test.com"))
        resp = await client.get("/api/v1/auth/me", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["role"] == "patient"

    async def test_repeated_me_returns_same_user(self, client):
        sub = f"new-{uuid.uuid4()}"
        token = create_test_token(sub=sub, email="rep@test.com", roles=["patient"])
        first = await client.get("/api/v1/auth/me", headers=_auth(token))
        second = await client.get("/api/v1/auth/me", headers=_auth(token))
        assert first.status_code == 200 and second.status_code == 200
        assert first.json()["id"] == second.json()["id"]


# ---------------------------------------------------------------------------
# GET /auth/me — claim sync (the r2 fix)
# ---------------------------------------------------------------------------


class TestClaimSync:
    async def test_name_change_propagates(self, client, db, patient_user):
        token = create_test_token(
            sub=patient_user.keycloak_sub,
            email=patient_user.email,
            name="Renamed Patient",
            roles=["patient"],
        )
        resp = await client.get("/api/v1/auth/me", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "Renamed Patient"
        await db.refresh(patient_user)
        assert patient_user.full_name == "Renamed Patient"

    async def test_email_change_propagates(self, client, db, patient_user):
        token = create_test_token(
            sub=patient_user.keycloak_sub,
            email="newmail@test.com",
            name=patient_user.full_name,
            roles=["patient"],
        )
        resp = await client.get("/api/v1/auth/me", headers=_auth(token))
        assert resp.json()["email"] == "newmail@test.com"
        await db.refresh(patient_user)
        assert patient_user.email == "newmail@test.com"

    async def test_role_upgrade_creates_doctor_profile(self, client, db, patient_user):
        """Keycloak grants doctor role → next /me upgrades role + profile."""
        token = create_test_token(
            sub=patient_user.keycloak_sub,
            email=patient_user.email,
            name=patient_user.full_name,
            roles=["doctor"],
        )
        resp = await client.get("/api/v1/auth/me", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["role"] == "doctor"

        await db.refresh(patient_user)
        assert patient_user.role == "doctor"
        doctor = await db.scalar(
            select(Doctor).where(
                Doctor.user_id == patient_user.id, Doctor.deleted_at.is_(None)
            )
        )
        assert doctor is not None

    async def test_role_priority_admin_beats_doctor(self, client, db, patient_user):
        token = create_test_token(
            sub=patient_user.keycloak_sub,
            email=patient_user.email,
            name=patient_user.full_name,
            roles=["doctor", "admin"],
        )
        resp = await client.get("/api/v1/auth/me", headers=_auth(token))
        assert resp.json()["role"] == "admin"

    async def test_role_downgrade_when_claim_removed(
        self, client, db, doctor_user, doctor_profile
    ):
        """Keycloak is the source of truth: a token without the doctor role
        downgrades the local role on the next request."""
        token = create_test_token(
            sub=doctor_user.keycloak_sub,
            email=doctor_user.email,
            name=doctor_user.full_name,
            roles=["patient"],
        )
        resp = await client.get("/api/v1/auth/me", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["role"] == "patient"
        await db.refresh(doctor_user)
        assert doctor_user.role == "patient"

    async def test_erased_user_pii_not_resurrected(self, client, db):
        """DPDP-erased accounts keep their anonymized PII — only the role is
        synced from token claims (name/email must NOT be restored)."""
        user = User(
            keycloak_sub=f"erased-{uuid.uuid4()}",
            email=None,
            full_name="Erased User 4f2a",
            role="patient",
            erased_at=datetime.now(timezone.utc),
            erasure_requested_at=datetime.now(timezone.utc),
        )
        db.add(user)
        await db.commit()

        token = create_test_token(
            sub=user.keycloak_sub,
            email="realname@test.com",
            name="Real Name",
            roles=["patient"],
        )
        resp = await client.get("/api/v1/auth/me", headers=_auth(token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["full_name"] == "Erased User 4f2a"
        assert body["email"] is None


# ---------------------------------------------------------------------------
# GET /auth/me — user cache (MD-383)
# ---------------------------------------------------------------------------


class TestUserCache:
    async def test_me_populates_cache(self, client):
        sub = f"cache-{uuid.uuid4()}"
        token = create_test_token(sub=sub, email="c@test.com", roles=["patient"])
        resp = await client.get("/api/v1/auth/me", headers=_auth(token))
        assert resp.status_code == 200
        assert sub in _dependencies._user_cache

    async def test_deactivation_propagates_within_ttl(self, client, db):
        """A cached sub must not keep serving a deactivated account — the
        cached path re-loads the row via db.get and falls through to the
        ACCOUNT_DISABLED check."""
        sub = f"cache-{uuid.uuid4()}"
        token = create_test_token(sub=sub, email="c2@test.com", roles=["patient"])
        assert (await client.get("/api/v1/auth/me", headers=_auth(token))).status_code == 200
        assert sub in _dependencies._user_cache

        user = await db.scalar(select(User).where(User.keycloak_sub == sub))
        user.is_active = False
        await db.commit()

        resp = await client.get("/api/v1/auth/me", headers=_auth(token))
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "ACCOUNT_DISABLED"

    async def test_claim_change_busts_cache(self, client, db):
        """A name/email/role claim mismatch forces a cache miss so the sync
        path propagates updated claims inside the TTL window."""
        sub = f"cache-{uuid.uuid4()}"
        t1 = create_test_token(sub=sub, email="same@test.com", name="Old Name", roles=["patient"])
        assert (await client.get("/api/v1/auth/me", headers=_auth(t1))).status_code == 200
        assert _dependencies._user_cache[sub].full_name == "Old Name"

        t2 = create_test_token(sub=sub, email="same@test.com", name="New Name", roles=["patient"])
        resp = await client.get("/api/v1/auth/me", headers=_auth(t2))
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "New Name"

    async def test_soft_deleted_user_rejected(self, client, db, patient_user):
        patient_user.deleted_at = datetime.now(timezone.utc)
        await db.commit()
        token = create_test_token(
            sub=patient_user.keycloak_sub,
            email=patient_user.email,
            name=patient_user.full_name,
            roles=["patient"],
        )
        resp = await client.get("/api/v1/auth/me", headers=_auth(token))
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "ACCOUNT_DISABLED"


# ---------------------------------------------------------------------------
# GET /auth/me — token edge cases
# ---------------------------------------------------------------------------


class TestTokenEdgeCases:
    async def test_missing_authorization_header(self, client):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "UNAUTHORIZED"
        assert resp.headers.get("www-authenticate") == "Bearer"

    async def test_malformed_token(self, client):
        resp = await client.get("/api/v1/auth/me", headers=_auth("not.a.jwt"))
        assert resp.status_code == 401

    async def test_expired_token(self, client):
        token = _encode(
            _payload(sub=f"exp-{uuid.uuid4()}", exp=int(time.time()) - 60)
        )
        resp = await client.get("/api/v1/auth/me", headers=_auth(token))
        assert resp.status_code == 401

    async def test_wrong_signing_key(self, client):
        token = _encode(
            _payload(sub=f"wrongkey-{uuid.uuid4()}"), key=OTHER_PRIVATE_KEY_PEM
        )
        resp = await client.get("/api/v1/auth/me", headers=_auth(token))
        assert resp.status_code == 401

    async def test_wrong_issuer(self, client):
        token = _encode(
            _payload(sub=f"iss-{uuid.uuid4()}", iss="http://evil.example.com/realms/x")
        )
        resp = await client.get("/api/v1/auth/me", headers=_auth(token))
        assert resp.status_code == 401

    async def test_wrong_audience(self, client):
        token = _encode(_payload(sub=f"aud-{uuid.uuid4()}", aud="some-other-client"))
        resp = await client.get("/api/v1/auth/me", headers=_auth(token))
        assert resp.status_code == 401

    async def test_missing_sub_claim(self, client):
        token = _encode(_payload(sub=None))
        resp = await client.get("/api/v1/auth/me", headers=_auth(token))
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /auth/set-role
# ---------------------------------------------------------------------------


class TestSetRole:
    async def test_patient_self_assign(
        self, client, patient_user, mock_keycloak_admin
    ):
        token = create_test_token(
            sub=patient_user.keycloak_sub,
            email=patient_user.email,
            name=patient_user.full_name,
            roles=["patient"],
        )
        resp = await client.post(
            "/api/v1/auth/set-role", json={"role": "patient"}, headers=_auth(token)
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["message"] == "Role updated to patient"
        mock_keycloak_admin.assert_awaited_once_with(patient_user.keycloak_sub, "patient")

    async def test_patient_role_stores_consent(
        self, client, db, patient_user, mock_keycloak_admin
    ):
        token = create_test_token(
            sub=patient_user.keycloak_sub,
            email=patient_user.email,
            name=patient_user.full_name,
            roles=["patient"],
        )
        resp = await client.post(
            "/api/v1/auth/set-role",
            json={"role": "patient", "consent_version": "dpdp-v1"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        # The patient path commits only when the role changes; the consent
        # write relies on get_db's post-handler commit in prod. Here the
        # attributes are set on the shared session — flush proves they
        # persist cleanly.
        assert patient_user.consent_version == "dpdp-v1"
        assert patient_user.consent_at is not None
        await db.flush()

    async def test_invalid_role_rejected(
        self, client, patient_user, mock_keycloak_admin
    ):
        token = create_test_token(
            sub=patient_user.keycloak_sub,
            email=patient_user.email,
            name=patient_user.full_name,
            roles=["patient"],
        )
        resp = await client.post(
            "/api/v1/auth/set-role", json={"role": "admin"}, headers=_auth(token)
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_ROLE"
        mock_keycloak_admin.assert_not_awaited()

    async def test_doctor_requires_invite_for_non_admin(
        self, client, patient_user, mock_keycloak_admin
    ):
        token = create_test_token(
            sub=patient_user.keycloak_sub,
            email=patient_user.email,
            name=patient_user.full_name,
            roles=["patient"],
        )
        resp = await client.post(
            "/api/v1/auth/set-role", json={"role": "doctor"}, headers=_auth(token)
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "INVITE_REQUIRED"
        mock_keycloak_admin.assert_not_awaited()

    async def test_doctor_invalid_invite(
        self, client, patient_user, mock_keycloak_admin
    ):
        token = create_test_token(
            sub=patient_user.keycloak_sub,
            email=patient_user.email,
            name=patient_user.full_name,
            roles=["patient"],
        )
        resp = await client.post(
            "/api/v1/auth/set-role",
            json={"role": "doctor", "invite_code": "NOSUCHCODE"},
            headers=_auth(token),
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "INVALID_INVITE"
        mock_keycloak_admin.assert_not_awaited()

    async def test_doctor_expired_invite(
        self, client, db, clinic, admin_user, patient_user, mock_keycloak_admin
    ):
        await _make_invite(
            db, clinic.id, admin_user.id,
            code="OLDINVITE",
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        token = create_test_token(
            sub=patient_user.keycloak_sub,
            email=patient_user.email,
            name=patient_user.full_name,
            roles=["patient"],
        )
        resp = await client.post(
            "/api/v1/auth/set-role",
            json={"role": "doctor", "invite_code": "OLDINVITE"},
            headers=_auth(token),
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "INVALID_INVITE"

    async def test_doctor_exhausted_invite(
        self, client, db, clinic, admin_user, patient_user, mock_keycloak_admin
    ):
        await _make_invite(
            db, clinic.id, admin_user.id,
            code="FULLINVITE", max_uses=1, use_count=1,
        )
        token = create_test_token(
            sub=patient_user.keycloak_sub,
            email=patient_user.email,
            name=patient_user.full_name,
            roles=["patient"],
        )
        resp = await client.post(
            "/api/v1/auth/set-role",
            json={"role": "doctor", "invite_code": "FULLINVITE"},
            headers=_auth(token),
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "INVALID_INVITE"

    async def test_doctor_receptionist_invite_rejected(
        self, client, db, clinic, admin_user, patient_user, mock_keycloak_admin
    ):
        """A receptionist invite must not grant the doctor role."""
        await _make_invite(db, clinic.id, admin_user.id, code="RECINVITE", role="receptionist")
        token = create_test_token(
            sub=patient_user.keycloak_sub,
            email=patient_user.email,
            name=patient_user.full_name,
            roles=["patient"],
        )
        resp = await client.post(
            "/api/v1/auth/set-role",
            json={"role": "doctor", "invite_code": "RECINVITE"},
            headers=_auth(token),
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "INVALID_INVITE"

    async def test_doctor_valid_invite_upgrades_without_consuming(
        self, client, db, clinic, admin_user, patient_user, mock_keycloak_admin
    ):
        invite = await _make_invite(db, clinic.id, admin_user.id, code="GOODINVITE")
        token = create_test_token(
            sub=patient_user.keycloak_sub,
            email=patient_user.email,
            name=patient_user.full_name,
            roles=["patient"],
        )
        resp = await client.post(
            "/api/v1/auth/set-role",
            json={"role": "doctor", "invite_code": "goodinvite"},  # case-insensitive
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["message"] == "Role updated to doctor"
        mock_keycloak_admin.assert_awaited_once_with(patient_user.keycloak_sub, "doctor")

        await db.refresh(patient_user)
        assert patient_user.role == "doctor"
        doctor = await db.scalar(
            select(Doctor).where(
                Doctor.user_id == patient_user.id, Doctor.deleted_at.is_(None)
            )
        )
        assert doctor is not None

        # set-role validates but does NOT consume the invite — use_count is
        # only incremented on actual clinic redemption.
        await db.refresh(invite)
        assert invite.use_count == 0

    async def test_admin_can_set_doctor_without_invite(
        self, client, db, admin_user, mock_keycloak_admin
    ):
        token = create_test_token(
            sub=admin_user.keycloak_sub,
            email=admin_user.email,
            name=admin_user.full_name,
            roles=["admin"],
        )
        resp = await client.post(
            "/api/v1/auth/set-role", json={"role": "doctor"}, headers=_auth(token)
        )
        assert resp.status_code == 200, resp.text
        await db.refresh(admin_user)
        assert admin_user.role == "doctor"

    async def test_set_role_requires_auth(self, client, mock_keycloak_admin):
        resp = await client.post("/api/v1/auth/set-role", json={"role": "patient"})
        assert resp.status_code == 401
        mock_keycloak_admin.assert_not_awaited()

    async def test_local_patient_role_reapplied_by_token_sync(
        self, client, db, doctor_user, doctor_profile, mock_keycloak_admin
    ):
        """set-role patient cannot strip a Keycloak-granted doctor role:
        locally it flips to patient, but the next request's claim sync
        re-applies the doctor role from the token."""
        token = create_test_token(
            sub=doctor_user.keycloak_sub,
            email=doctor_user.email,
            name=doctor_user.full_name,
            roles=["doctor"],
        )
        resp = await client.post(
            "/api/v1/auth/set-role", json={"role": "patient"}, headers=_auth(token)
        )
        assert resp.status_code == 200
        await db.refresh(doctor_user)
        assert doctor_user.role == "patient"

        restored = await client.get("/api/v1/auth/me", headers=_auth(token))
        assert restored.status_code == 200
        assert restored.json()["role"] == "doctor"
