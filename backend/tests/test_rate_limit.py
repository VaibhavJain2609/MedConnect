"""Tests for rate limiting middleware (MD-141)."""
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.middleware.rate_limit import (
    _check_limit,
    _get_category,
    _get_user_key,
)


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------

class TestGetCategory:
    def test_auth_path_is_auth_category(self):
        assert _get_category("GET", "/api/v1/auth/me") == "auth"

    def test_auth_post_is_still_auth_category(self):
        assert _get_category("POST", "/api/v1/auth/login") == "auth"

    def test_get_is_read(self):
        assert _get_category("GET", "/api/v1/patients/timeline") == "read"

    def test_post_is_write(self):
        assert _get_category("POST", "/api/v1/records") == "write"

    def test_put_is_write(self):
        assert _get_category("PUT", "/api/v1/patients/1") == "write"

    def test_patch_is_write(self):
        assert _get_category("PATCH", "/api/v1/patients/1") == "write"

    def test_delete_is_write(self):
        assert _get_category("DELETE", "/api/v1/records/1") == "write"

    def test_health_path_is_read(self):
        # /health is exempt from middleware entirely, but category helper still classifies
        assert _get_category("GET", "/health") == "read"


class TestGetUserKey:
    def _make_request(self, auth_header=None, forwarded_for=None, client_host="127.0.0.1"):
        request = MagicMock()
        headers = {}
        if auth_header:
            headers["Authorization"] = auth_header
        if forwarded_for:
            headers["X-Forwarded-For"] = forwarded_for
        request.headers = headers
        request.client = MagicMock()
        request.client.host = client_host
        return request

    def test_extracts_sub_from_valid_jwt(self):
        import jwt as pyjwt
        token = pyjwt.encode({"sub": "user-abc-123"}, "secret", algorithm="HS256")
        request = self._make_request(auth_header=f"Bearer {token}")
        key = _get_user_key(request)
        assert key == "user:user-abc-123"

    def test_falls_back_to_ip_when_no_auth(self):
        request = self._make_request()
        key = _get_user_key(request)
        assert key == "ip:127.0.0.1"

    def test_falls_back_to_ip_on_malformed_token(self):
        request = self._make_request(auth_header="Bearer not-a-valid-jwt")
        key = _get_user_key(request)
        assert key == "ip:127.0.0.1"

    def test_uses_x_forwarded_for_when_present(self):
        request = self._make_request(forwarded_for="10.0.0.5, 10.0.0.1")
        key = _get_user_key(request)
        assert key == "ip:10.0.0.5"

    def test_uses_first_ip_in_x_forwarded_for(self):
        request = self._make_request(forwarded_for="192.168.1.1, 10.0.0.1, proxy")
        key = _get_user_key(request)
        assert key == "ip:192.168.1.1"


# ---------------------------------------------------------------------------
# Unit tests for _check_limit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestCheckLimit:
    async def _make_redis(self, incr_return: int):
        mock_pipe = AsyncMock()
        mock_pipe.execute = AsyncMock(return_value=[incr_return, True])
        mock_pipe.incr = MagicMock(return_value=mock_pipe)
        mock_pipe.expire = MagicMock(return_value=mock_pipe)
        mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
        mock_pipe.__aexit__ = AsyncMock(return_value=False)

        mock_redis = MagicMock()
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)
        return mock_redis

    async def test_allows_first_request(self):
        redis = await self._make_redis(incr_return=1)
        allowed, retry_after = await _check_limit(redis, "user:abc", "read", limit=100)
        assert allowed is True
        assert retry_after == 0

    async def test_allows_request_at_limit(self):
        redis = await self._make_redis(incr_return=100)
        allowed, retry_after = await _check_limit(redis, "user:abc", "read", limit=100)
        assert allowed is True
        assert retry_after == 0

    async def test_blocks_request_over_limit(self):
        redis = await self._make_redis(incr_return=101)
        allowed, retry_after = await _check_limit(redis, "user:abc", "read", limit=100)
        assert allowed is False
        assert retry_after >= 1

    async def test_blocks_auth_limit(self):
        redis = await self._make_redis(incr_return=6)
        allowed, retry_after = await _check_limit(redis, "user:abc", "auth", limit=5)
        assert allowed is False

    async def test_retry_after_is_positive(self):
        redis = await self._make_redis(incr_return=25)
        allowed, retry_after = await _check_limit(redis, "user:abc", "write", limit=20)
        assert allowed is False
        assert retry_after >= 1

    async def test_fails_open_when_redis_errors(self):
        mock_redis = MagicMock()
        mock_pipe = AsyncMock()
        mock_pipe.execute = AsyncMock(side_effect=Exception("Redis down"))
        mock_pipe.incr = MagicMock(return_value=mock_pipe)
        mock_pipe.expire = MagicMock(return_value=mock_pipe)
        mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
        mock_pipe.__aexit__ = AsyncMock(return_value=False)
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)

        allowed, retry_after = await _check_limit(mock_redis, "user:abc", "read", limit=100)
        assert allowed is True
        assert retry_after == 0


# ---------------------------------------------------------------------------
# Integration-style tests for the middleware via ASGI
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestRateLimitMiddlewareIntegration:
    """Test middleware via lightweight ASGI app (no DB/Keycloak needed)."""

    def _make_app_with_mock_redis(self, incr_return: int):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.middleware.rate_limit import RateLimitMiddleware

        mini_app = FastAPI()

        @mini_app.get("/api/v1/patients/timeline")
        async def timeline():
            return {"ok": True}

        @mini_app.post("/api/v1/records")
        async def create_record():
            return {"ok": True}

        @mini_app.get("/api/v1/auth/me")
        async def auth_me():
            return {"ok": True}

        @mini_app.get("/health")
        async def health():
            return {"ok": True}

        mini_app.add_middleware(RateLimitMiddleware)
        return mini_app

    async def _call(self, app, path, method="GET", headers=None):
        from httpx import ASGITransport, AsyncClient
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            fn = getattr(c, method.lower())
            return await fn(path, headers=headers or {})

    async def test_health_exempt_from_rate_limit(self):
        app = self._make_app_with_mock_redis(incr_return=9999)
        mock_pipe = AsyncMock()
        mock_pipe.execute = AsyncMock(return_value=[9999, True])
        mock_pipe.incr = MagicMock(return_value=mock_pipe)
        mock_pipe.expire = MagicMock(return_value=mock_pipe)
        mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
        mock_pipe.__aexit__ = AsyncMock(return_value=False)
        mock_redis = MagicMock()
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)

        with patch("app.middleware.rate_limit._get_redis", return_value=mock_redis):
            resp = await self._call(app, "/health")
        assert resp.status_code == 200
        # Pipeline should NOT have been called for exempt path
        mock_redis.pipeline.assert_not_called()

    async def test_returns_429_when_over_limit(self):
        app = self._make_app_with_mock_redis(incr_return=101)
        mock_pipe = AsyncMock()
        mock_pipe.execute = AsyncMock(return_value=[101, True])
        mock_pipe.incr = MagicMock(return_value=mock_pipe)
        mock_pipe.expire = MagicMock(return_value=mock_pipe)
        mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
        mock_pipe.__aexit__ = AsyncMock(return_value=False)
        mock_redis = MagicMock()
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)

        with patch("app.middleware.rate_limit._get_redis", return_value=mock_redis):
            resp = await self._call(app, "/api/v1/patients/timeline")
        assert resp.status_code == 429
        body = resp.json()
        assert body["error"]["code"] == "RATE_LIMIT_EXCEEDED"

    async def test_429_includes_retry_after_header(self):
        app = self._make_app_with_mock_redis(incr_return=200)
        mock_pipe = AsyncMock()
        mock_pipe.execute = AsyncMock(return_value=[200, True])
        mock_pipe.incr = MagicMock(return_value=mock_pipe)
        mock_pipe.expire = MagicMock(return_value=mock_pipe)
        mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
        mock_pipe.__aexit__ = AsyncMock(return_value=False)
        mock_redis = MagicMock()
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)

        with patch("app.middleware.rate_limit._get_redis", return_value=mock_redis):
            resp = await self._call(app, "/api/v1/patients/timeline")
        assert resp.status_code == 429
        assert "retry-after" in resp.headers
        assert int(resp.headers["retry-after"]) >= 1

    async def test_allows_request_under_limit(self):
        app = self._make_app_with_mock_redis(incr_return=1)
        mock_pipe = AsyncMock()
        mock_pipe.execute = AsyncMock(return_value=[1, True])
        mock_pipe.incr = MagicMock(return_value=mock_pipe)
        mock_pipe.expire = MagicMock(return_value=mock_pipe)
        mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
        mock_pipe.__aexit__ = AsyncMock(return_value=False)
        mock_redis = MagicMock()
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)

        with patch("app.middleware.rate_limit._get_redis", return_value=mock_redis):
            resp = await self._call(app, "/api/v1/patients/timeline")
        assert resp.status_code == 200

    async def test_auth_endpoint_uses_auth_limit(self):
        """Auth limit is 5 – counter at 6 should be blocked."""
        app = self._make_app_with_mock_redis(incr_return=6)
        mock_pipe = AsyncMock()
        mock_pipe.execute = AsyncMock(return_value=[6, True])
        mock_pipe.incr = MagicMock(return_value=mock_pipe)
        mock_pipe.expire = MagicMock(return_value=mock_pipe)
        mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
        mock_pipe.__aexit__ = AsyncMock(return_value=False)
        mock_redis = MagicMock()
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)

        with patch("app.middleware.rate_limit._get_redis", return_value=mock_redis):
            resp = await self._call(app, "/api/v1/auth/me")
        assert resp.status_code == 429
        assert "100" not in resp.json()["error"]["message"]  # auth limit, not read limit
        assert "5" in resp.json()["error"]["message"]

    async def test_write_endpoint_uses_write_limit(self):
        """Write limit is 20 – counter at 21 should be blocked."""
        app = self._make_app_with_mock_redis(incr_return=21)
        mock_pipe = AsyncMock()
        mock_pipe.execute = AsyncMock(return_value=[21, True])
        mock_pipe.incr = MagicMock(return_value=mock_pipe)
        mock_pipe.expire = MagicMock(return_value=mock_pipe)
        mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
        mock_pipe.__aexit__ = AsyncMock(return_value=False)
        mock_redis = MagicMock()
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)

        with patch("app.middleware.rate_limit._get_redis", return_value=mock_redis):
            resp = await self._call(app, "/api/v1/records", method="POST")
        assert resp.status_code == 429
        assert "20" in resp.json()["error"]["message"]
