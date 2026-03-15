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
        logger.debug("Decoding token, expected issuer: %s", expected_issuer)
        decode_kwargs: dict = {
            "algorithms": ["RS256"],
            "issuer": expected_issuer,
        }
        if settings.VERIFY_JWT_AUDIENCE:
            decode_kwargs["audience"] = settings.KEYCLOAK_CLIENT_ID
        else:
            decode_kwargs["options"] = {"verify_aud": False}
        payload = jwt.decode(token, signing_key.key, **decode_kwargs)
        logger.debug("Token decoded successfully, issuer: %s", payload.get("iss"))
        return payload
    except jwt.PyJWTError as e:
        logger.error("JWT validation failed: %s: %s", type(e).__name__, e)
        return None
    except Exception as e:
        logger.error("Unexpected error validating token: %s: %s", type(e).__name__, e)
        return None
