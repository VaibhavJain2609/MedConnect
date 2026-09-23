"""Tests for SecurityHeadersMiddleware (app/middleware/security_headers.py).

Verifies the hardening header set is applied to every HTTP response —
including unauthenticated rejections — and that PHI-bearing /api/v1/*
responses additionally carry Cache-Control: no-store.
"""
from httpx import AsyncClient

from app.config import settings

EXPECTED_HEADERS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "strict-origin-when-cross-origin",
    "permissions-policy": "camera=(), microphone=(), geolocation=(), payment=()",
}


def _assert_security_headers(resp):
    for name, value in EXPECTED_HEADERS.items():
        assert resp.headers.get(name) == value, f"missing/incorrect {name}"
    csp = resp.headers.get("content-security-policy", "")
    # Strict JSON-API policy: no markup resources at all; frame-ancestors
    # 'none' is the modern clickjacking guard (supersedes X-Frame-Options).
    assert "default-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "script-src 'none'" in csp
    # No unsafe concessions anywhere on the API surface.
    assert "unsafe-inline" not in csp
    assert "unsafe-eval" not in csp
    # connect-src is the only non-'none' source — the SPA origin.
    assert settings.FRONTEND_URL in csp
    # The Report-Only CSP is a frontend concern (next.config.js) — the API
    # must not emit it.
    assert "content-security-policy-report-only" not in resp.headers
    # Deprecated header must never appear.
    assert "x-xss-protection" not in resp.headers


async def test_security_headers_on_api_route(client: AsyncClient):
    """Unauthenticated 401/403 responses still carry the full header set —
    the middleware wraps send at the ASGI level, outside auth."""
    resp = await client.get("/api/v1/patients/timeline")
    assert resp.status_code in (401, 403)
    _assert_security_headers(resp)


async def test_api_route_is_no_store(client: AsyncClient):
    """PHI must never be stored by shared caches."""
    resp = await client.get("/api/v1/patients/timeline")
    assert resp.headers.get("cache-control") == "no-store"
    assert resp.headers.get("pragma") == "no-cache"


async def test_api_404_also_no_store(client: AsyncClient):
    """Even error envelopes under /api/v1 get no-store."""
    resp = await client.get("/api/v1/does-not-exist")
    assert resp.status_code == 404
    _assert_security_headers(resp)
    assert resp.headers.get("cache-control") == "no-store"


async def test_non_api_route_has_no_cache_override(client: AsyncClient):
    """Probes/docs keep default cache semantics — no-store is API-only."""
    resp = await client.get("/livez")
    assert resp.status_code == 200
    _assert_security_headers(resp)
    assert "cache-control" not in resp.headers
    assert "pragma" not in resp.headers


async def test_health_endpoint_still_works(client: AsyncClient):
    """/health responds (200 when DBs+Redis reachable, 503 degraded) and
    still carries security headers."""
    resp = await client.get("/health")
    assert resp.status_code in (200, 503)
    assert "status" in resp.json()
    _assert_security_headers(resp)


async def test_security_headers_on_authenticated_route(
    patient_client: AsyncClient,
):
    """Happy-path authenticated responses carry headers + no-store too."""
    resp = await patient_client.get("/api/v1/patients/timeline")
    assert resp.status_code == 200
    _assert_security_headers(resp)
    assert resp.headers.get("cache-control") == "no-store"
