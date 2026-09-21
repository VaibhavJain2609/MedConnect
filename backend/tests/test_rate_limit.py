"""Tests for rate limiting middleware (MD-141)."""
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.middleware.rate_limit import (
    _check_limit,
    _get_category,
    _get_jwt_sub,
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

    def test_hashes_bearer_token_to_stable_key(self):
        import hashlib

        import jwt as pyjwt
        token = pyjwt.encode({"sub": "user-abc-123"}, "secret", algorithm="HS256")
        request = self._make_request(auth_header=f"Bearer {token}")
        key = _get_user_key(request)
        expected = hashlib.sha256(token.encode()).hexdigest()[:32]
        assert key == f"token:{expected}"

    def test_falls_back_to_ip_when_no_auth(self):
        request = self._make_request()
        key = _get_user_key(request)
        assert key == "ip:127.0.0.1"

    def test_hashes_any_bearer_token_without_validating(self):
        # The middleware hashes the raw token (it does not validate the JWT),
        # so a malformed bearer token still produces a stable token key.
        request = self._make_request(auth_header="Bearer not-a-valid-jwt")
        key = _get_user_key(request)
        assert key.startswith("token:")

    def test_ignores_x_forwarded_for_from_untrusted_peer(self):
        # XFF is only honored when the immediate peer is in TRUSTED_PROXY_IPS;
        # an untrusted client cannot spoof its rate-limit identity.
        request = self._make_request(forwarded_for="10.0.0.5, 10.0.0.1")
        key = _get_user_key(request)
        assert key == "ip:127.0.0.1"

    def test_uses_x_forwarded_for_from_trusted_proxy(self, monkeypatch):
        from app.middleware import rate_limit

        monkeypatch.setattr(rate_limit, "_TRUSTED_PROXIES", {"127.0.0.1"})
        request = self._make_request(forwarded_for="192.168.1.1, 10.0.0.1")
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

        @mini_app.post("/api/v1/uploads/presign")
        async def presign():
            return {"ok": True}

        @mini_app.post("/api/v1/interactions/check")
        async def interactions_check():
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


# ---------------------------------------------------------------------------
# Per-user bucket (JWT sub) + per-endpoint limit tests
# ---------------------------------------------------------------------------

def _mock_pipe(incr_return: int):
    """Build a mock redis pipeline whose execute() returns [incr_return, True]."""
    mock_pipe = AsyncMock()
    mock_pipe.execute = AsyncMock(return_value=[incr_return, True])
    mock_pipe.incr = MagicMock(return_value=mock_pipe)
    mock_pipe.expire = MagicMock(return_value=mock_pipe)
    mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
    mock_pipe.__aexit__ = AsyncMock(return_value=False)
    return mock_pipe


def _mock_redis(*incr_returns: int):
    """Mock redis whose pipeline() yields one pipe per call, in order.

    Returns (mock_redis, pipes) so tests can inspect the keys each pipeline
    was asked to increment.
    """
    pipes = [_mock_pipe(v) for v in incr_returns]
    mock_redis = MagicMock()
    mock_redis.pipeline = MagicMock(side_effect=pipes)
    return mock_redis, pipes


def _make_token(sub: str = "user-abc-123") -> str:
    import jwt as pyjwt

    return pyjwt.encode({"sub": sub}, "secret", algorithm="HS256")


class TestGetJwtSub:
    def _make_request(self, auth_header=None):
        request = MagicMock()
        request.headers = {"Authorization": auth_header} if auth_header else {}
        return request

    def test_returns_sub_from_valid_jwt(self):
        token = _make_token("user-abc-123")
        request = self._make_request(f"Bearer {token}")
        assert _get_jwt_sub(request) == "user-abc-123"

    def test_decodes_without_verifying_signature(self):
        # The middleware decode is for bucketing only, not authz — a token
        # signed with any key still yields its sub for rate-limit purposes.
        import jwt as pyjwt

        token = pyjwt.encode({"sub": "u-other"}, "a-different-key", algorithm="HS256")
        request = self._make_request(f"Bearer {token}")
        assert _get_jwt_sub(request) == "u-other"

    def test_returns_none_without_authorization_header(self):
        assert _get_jwt_sub(self._make_request()) is None

    def test_returns_none_for_non_bearer_scheme(self):
        assert _get_jwt_sub(self._make_request("Basic dXNlcjpwYXNz")) is None

    def test_returns_none_for_malformed_jwt(self):
        assert _get_jwt_sub(self._make_request("Bearer not-a-valid-jwt")) is None

    def test_returns_none_when_sub_claim_missing(self):
        import jwt as pyjwt

        token = pyjwt.encode({"email": "a@b.c"}, "secret", algorithm="HS256")
        assert _get_jwt_sub(self._make_request(f"Bearer {token}")) is None


@pytest.mark.asyncio
class TestPerUserBucketIntegration:
    """Second (per-user) bucket evaluated alongside the caller/IP bucket."""

    def _make_app(self):
        from fastapi import FastAPI
        from app.middleware.rate_limit import RateLimitMiddleware

        mini_app = FastAPI()

        @mini_app.get("/api/v1/patients/timeline")
        async def timeline():
            return {"ok": True}

        @mini_app.post("/api/v1/uploads/presign")
        async def presign():
            return {"ok": True}

        @mini_app.post("/api/v1/interactions/check")
        async def interactions_check():
            return {"ok": True}

        mini_app.add_middleware(RateLimitMiddleware)
        return mini_app

    async def _call(self, app, path, method="GET", headers=None):
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            fn = getattr(c, method.lower())
            return await fn(path, headers=headers or {})

    async def test_authenticated_request_uses_separate_user_bucket(self):
        """Caller bucket and user bucket are distinct counters; both checked."""
        app = self._make_app()
        mock_redis, pipes = _mock_redis(1, 1)

        with patch("app.middleware.rate_limit._get_redis", return_value=mock_redis):
            resp = await self._call(
                app,
                "/api/v1/patients/timeline",
                headers={"Authorization": f"Bearer {_make_token()}"},
            )
        assert resp.status_code == 200
        assert mock_redis.pipeline.call_count == 2
        caller_key = pipes[0].incr.call_args[0][0]
        user_key = pipes[1].incr.call_args[0][0]
        assert caller_key.startswith("rate_limit:token:")
        assert user_key.startswith("rl:user:user-abc-123:all:")

    async def test_429_when_user_limit_exceeded(self):
        """Caller bucket passes but user bucket (240/min) is exhausted."""
        app = self._make_app()
        mock_redis, _ = _mock_redis(1, 241)

        with patch("app.middleware.rate_limit._get_redis", return_value=mock_redis):
            resp = await self._call(
                app,
                "/api/v1/patients/timeline",
                headers={"Authorization": f"Bearer {_make_token()}"},
            )
        assert resp.status_code == 429
        assert resp.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
        assert resp.headers["x-ratelimit-bucket"] == "user"
        assert "240" in resp.json()["error"]["message"]
        assert "retry-after" in resp.headers

    async def test_caller_bucket_429_marks_bucket_ip(self):
        app = self._make_app()
        mock_redis, _ = _mock_redis(101)

        with patch("app.middleware.rate_limit._get_redis", return_value=mock_redis):
            resp = await self._call(app, "/api/v1/patients/timeline")
        assert resp.status_code == 429
        assert resp.headers["x-ratelimit-bucket"] == "ip"

    async def test_malformed_jwt_falls_back_to_ip_only(self):
        """An undecodable Bearer token skips the user bucket entirely."""
        app = self._make_app()
        mock_redis, _ = _mock_redis(101)

        with patch("app.middleware.rate_limit._get_redis", return_value=mock_redis):
            resp = await self._call(
                app,
                "/api/v1/patients/timeline",
                headers={"Authorization": "Bearer not-a-valid-jwt"},
            )
        assert resp.status_code == 429
        assert resp.headers["x-ratelimit-bucket"] == "ip"
        # Only the caller bucket was evaluated — no second pipeline.
        assert mock_redis.pipeline.call_count == 1

    async def test_malformed_jwt_under_limit_allowed_with_single_check(self):
        app = self._make_app()
        mock_redis, _ = _mock_redis(1)

        with patch("app.middleware.rate_limit._get_redis", return_value=mock_redis):
            resp = await self._call(
                app,
                "/api/v1/patients/timeline",
                headers={"Authorization": "Bearer not-a-valid-jwt"},
            )
        assert resp.status_code == 200
        assert mock_redis.pipeline.call_count == 1


@pytest.mark.asyncio
class TestPerEndpointLimits:
    """Expensive endpoints get a dedicated counter/limit on the caller bucket."""

    def _make_app(self):
        from fastapi import FastAPI
        from app.middleware.rate_limit import RateLimitMiddleware

        mini_app = FastAPI()

        @mini_app.post("/api/v1/uploads/presign")
        async def presign():
            return {"ok": True}

        @mini_app.post("/api/v1/interactions/check")
        async def interactions_check():
            return {"ok": True}

        mini_app.add_middleware(RateLimitMiddleware)
        return mini_app

    async def _call(self, app, path, method="POST", headers=None):
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            fn = getattr(c, method.lower())
            return await fn(path, headers=headers or {})

    async def test_presign_blocked_over_20(self):
        app = self._make_app()
        mock_redis, pipes = _mock_redis(21)

        with patch("app.middleware.rate_limit._get_redis", return_value=mock_redis):
            resp = await self._call(app, "/api/v1/uploads/presign")
        assert resp.status_code == 429
        assert "20" in resp.json()["error"]["message"]
        # Dedicated endpoint counter, not the generic "write" bucket.
        assert "endpoint:/api/v1/uploads/presign" in pipes[0].incr.call_args[0][0]

    async def test_interactions_check_allows_more_than_write_limit(self):
        """check is capped at 60/min on its own bucket — 30 passes even though
        the generic write limit is only 20."""
        app = self._make_app()
        mock_redis, pipes = _mock_redis(30)

        with patch("app.middleware.rate_limit._get_redis", return_value=mock_redis):
            resp = await self._call(app, "/api/v1/interactions/check")
        assert resp.status_code == 200
        assert "endpoint:/api/v1/interactions/check" in pipes[0].incr.call_args[0][0]

    async def test_interactions_check_blocked_over_60(self):
        app = self._make_app()
        mock_redis, _ = _mock_redis(61)

        with patch("app.middleware.rate_limit._get_redis", return_value=mock_redis):
            resp = await self._call(app, "/api/v1/interactions/check")
        assert resp.status_code == 429
        assert "60" in resp.json()["error"]["message"]


@pytest.mark.asyncio
class TestSearchEndpointLimits:
    """Global search has a dedicated 30/min limit on BOTH the caller bucket
    and the per-user bucket (token rotation must not reset the budget)."""

    def _make_app(self):
        from fastapi import FastAPI
        from app.middleware.rate_limit import RateLimitMiddleware

        mini_app = FastAPI()

        @mini_app.get("/api/v1/search")
        async def search():
            return {"ok": True}

        @mini_app.get("/api/v1/search/suggestions")
        async def suggestions():
            return {"ok": True}

        mini_app.add_middleware(RateLimitMiddleware)
        return mini_app

    async def _call(self, app, path, headers=None):
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            return await c.get(path, headers=headers or {})

    async def test_search_blocked_over_30_on_caller_bucket(self):
        app = self._make_app()
        mock_redis, pipes = _mock_redis(31)

        with patch("app.middleware.rate_limit._get_redis", return_value=mock_redis):
            resp = await self._call(app, "/api/v1/search")
        assert resp.status_code == 429
        assert "30" in resp.json()["error"]["message"]
        assert "endpoint:/api/v1/search" in pipes[0].incr.call_args[0][0]

    async def test_search_suggestions_blocked_over_30(self):
        app = self._make_app()
        mock_redis, _ = _mock_redis(31)

        with patch("app.middleware.rate_limit._get_redis", return_value=mock_redis):
            resp = await self._call(app, "/api/v1/search/suggestions")
        assert resp.status_code == 429
        assert "30" in resp.json()["error"]["message"]

    async def test_search_endpoint_limit_also_enforced_per_user(self):
        """Caller bucket passes (fresh token) but the per-user endpoint bucket
        is exhausted — bucket header must be 'user'."""
        app = self._make_app()
        # pipes: caller endpoint check (1 ≤ 30 → allow), user endpoint check
        # (31 > 30 → deny). The flat user "all" bucket is never reached.
        mock_redis, pipes = _mock_redis(1, 31)

        with patch("app.middleware.rate_limit._get_redis", return_value=mock_redis):
            resp = await self._call(
                app,
                "/api/v1/search",
                headers={"Authorization": f"Bearer {_make_token()}"},
            )
        assert resp.status_code == 429
        assert resp.headers["x-ratelimit-bucket"] == "user"
        assert "30" in resp.json()["error"]["message"]
        user_key = pipes[1].incr.call_args[0][0]
        assert user_key.startswith("rl:user:user-abc-123:endpoint:/api/v1/search:")

    async def test_search_under_limit_checks_all_three_buckets(self):
        app = self._make_app()
        mock_redis, pipes = _mock_redis(1, 1, 1)

        with patch("app.middleware.rate_limit._get_redis", return_value=mock_redis):
            resp = await self._call(
                app,
                "/api/v1/search",
                headers={"Authorization": f"Bearer {_make_token()}"},
            )
        assert resp.status_code == 200
        # caller endpoint bucket + user endpoint bucket + flat user bucket
        assert mock_redis.pipeline.call_count == 3
        assert pipes[2].incr.call_args[0][0].startswith("rl:user:user-abc-123:all:")
