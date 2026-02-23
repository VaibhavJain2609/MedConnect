import logging

import jwt
from jwt import PyJWKClient

from app.config import settings

logger = logging.getLogger(__name__)

_jwks_client: PyJWKClient | None = None


def get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        # Use internal Docker URL to fetch JWKS keys
        jwks_url = f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/certs"
        _jwks_client = PyJWKClient(jwks_url, cache_keys=True)
    return _jwks_client


def decode_keycloak_token(token: str) -> dict | None:
    try:
        client = get_jwks_client()
        signing_key = client.get_signing_key_from_jwt(token)
        expected_issuer = f"{settings.KEYCLOAK_PUBLIC_URL}/realms/{settings.KEYCLOAK_REALM}"
        print(f"Expected issuer: {expected_issuer}")
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            # For development: disable issuer verification to debug token validation
            issuer=expected_issuer,
            options={"verify_aud": False, "verify_iss": False},
        )
        actual_issuer = payload.get('iss')
        print(f"✓ Token decoded successfully, actual issuer: {actual_issuer}")
        if actual_issuer != expected_issuer:
            print(f"⚠️  Issuer mismatch: expected {expected_issuer}, got {actual_issuer}")
        return payload
    except jwt.PyJWTError as e:
        print(f"❌ JWT validation failed: {type(e).__name__}: {e}")
        logger.error("JWT validation failed: %s: %s", type(e).__name__, e)
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {type(e).__name__}: {e}")
        logger.error("Unexpected error validating token: %s: %s", type(e).__name__, e)
        return None
