"""Redis-based rate limiting middleware.

Two buckets are evaluated per request; a request is allowed only if BOTH pass:

1. Caller bucket (outer bound) — keyed by bearer-token hash when an
   Authorization header is present, else by client IP (X-Forwarded-For is
   honored only from configured trusted proxies). Per-category limits:
   - Auth endpoints (/api/v1/auth/*): 5 req/min
   - Write endpoints (POST/PUT/PATCH/DELETE): 20 req/min
   - Read endpoints (GET): 100 req/min
   - Selected expensive endpoints get a dedicated counter/limit
     (_ENDPOINT_LIMITS) so they are throttled independently of the generic
     read/write buckets.

2. User bucket — when a Bearer token is present, the JWT `sub` claim is read
   WITHOUT verifying the signature. The token is fully verified downstream by
   the auth dependencies; this decode is only a cheap, stable bucket key and
   is never used for authorization. Keyed ``rl:user:{sub}``, flat
   ``RATE_LIMIT_USER_PER_MINUTE`` (default 240/min) — deliberately higher
   than the caller bucket so legitimate users behind shared-NAT IPs aren't
   throttled by their neighbors, while a single account still can't hammer
   the API or evade limits by rotating access tokens.

429 responses carry ``X-RateLimit-Bucket``: ``ip`` for the caller bucket,
``user`` for the per-user bucket.
"""
import hashlib
import logging
import os
import time

import jwt
import redis.asyncio as aioredis
from fastapi import status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings

_logger = logging.getLogger(__name__)

# Paths exempt from rate limiting (applies to both buckets)
_EXEMPT_PATHS = {"/health", "/docs", "/redoc", "/openapi.json"}

# Rate limits per category (requests per minute)
_LIMITS: dict[str, int] = {
    "auth": 5,
    "write": 20,
    "read": 100,
}

# Per-endpoint limits for expensive routes (requests per minute). Each gets a
# dedicated counter on the caller bucket, independent of the generic
# read/write/auth categories.
_ENDPOINT_LIMITS: dict[str, int] = {
    "/api/v1/uploads/presign": 20,
    "/api/v1/interactions/check": 60,
}

_redis_client: aioredis.Redis | None = None

# IPs of trusted reverse proxies whose X-Forwarded-For header we honor.
# Comma-separated list via TRUSTED_PROXY_IPS env var. Empty = never trust XFF;
# the direct peer address is used instead (unauthenticated callers can
# otherwise spoof XFF to evade per-IP rate limits).
_TRUSTED_PROXIES = {
    ip.strip()
    for ip in os.environ.get("TRUSTED_PROXY_IPS", "").split(",")
    if ip.strip()
}


def _get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        # MD-384: Explicit pool bound prevents unbounded connection growth under load
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            max_connections=20,
        )
    return _redis_client


def _get_category(method: str, path: str) -> str:
    if path.startswith("/api/v1/auth/"):
        return "auth"
    if method in ("POST", "PUT", "PATCH", "DELETE"):
        return "write"
    return "read"


def _get_user_key(request: Request) -> str:
    """Return a stable identifier for the caller (token hash or client IP)."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        token_hash = hashlib.sha256(token.encode()).hexdigest()[:32]
        return f"token:{token_hash}"

    host = request.client.host if request.client else None
    # Only honor X-Forwarded-For when the immediate peer is a configured
    # trusted proxy — the header is trivially spoofed by direct clients.
    if host and host in _TRUSTED_PROXIES:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"
    return f"ip:{host or 'unknown'}"


def _get_jwt_sub(request: Request) -> str | None:
    """Return the ``sub`` claim of the bearer JWT, or None if unavailable.

    The token is decoded WITHOUT signature verification: this runs before the
    auth dependencies, and the result is used only to pick a rate-limit bucket
    — never to authorize anything. A malformed token yields None and the
    request simply falls back to the caller (IP/token-hash) bucket alone.
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        payload = jwt.decode(auth[7:], options={"verify_signature": False})
    except jwt.PyJWTError:
        return None
    sub = payload.get("sub")
    return sub if isinstance(sub, str) and sub else None


async def _check_limit(
    redis: aioredis.Redis,
    user_key: str,
    category: str,
    limit: int,
    window: int = 60,
    *,
    key_prefix: str = "rate_limit",
) -> tuple[bool, int]:
    """Increment counter; return (allowed, retry_after_seconds)."""
    current_window = int(time.time() // window)
    redis_key = f"{key_prefix}:{user_key}:{category}:{current_window}"
    try:
        pipe = redis.pipeline()
        pipe.incr(redis_key)
        pipe.expire(redis_key, window + 5)
        results = await pipe.execute()
        count = results[0]
        if count > limit:
            next_window = (current_window + 1) * window
            retry_after = max(1, int(next_window - time.time()) + 1)
            return False, retry_after
        return True, 0
    except Exception as exc:
        # MD-381: Fail open — allow the request rather than blocking all traffic when
        # Redis is unavailable. Rate limiting degrades gracefully; availability takes priority.
        _logger.error("Redis rate-limit error (%s: %s); failing open", type(exc).__name__, exc)
        return True, 0


def _too_many_requests(limit: int, label: str, retry_after: int, bucket: str) -> JSONResponse:
    """Build the shared 429 body; ``bucket`` identifies which limit tripped."""
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "error": {
                "code": "RATE_LIMIT_EXCEEDED",
                "message": f"Rate limit exceeded. Maximum {limit} {label} requests per minute.",
            }
        },
        headers={
            "Retry-After": str(retry_after),
            "X-RateLimit-Bucket": bucket,
        },
    )


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        if path in _EXEMPT_PATHS:
            return await call_next(request)

        method = request.method.upper()

        if method == "OPTIONS":
            return await call_next(request)

        category = _get_category(method, path)
        user_key = _get_user_key(request)
        redis = _get_redis()

        # Bucket 1 (outer bound): per-caller limit. Expensive endpoints get a
        # dedicated counter/limit instead of the generic category bucket.
        endpoint_limit = _ENDPOINT_LIMITS.get(path)
        if endpoint_limit is not None:
            bucket_name, limit, label = f"endpoint:{path}", endpoint_limit, "endpoint"
        else:
            bucket_name, limit, label = category, _LIMITS[category], category

        allowed, retry_after = await _check_limit(redis, user_key, bucket_name, limit)
        if not allowed:
            return _too_many_requests(limit, label, retry_after, bucket="ip")

        # Bucket 2: flat per-user limit keyed on the JWT `sub` (unverified
        # decode — see _get_jwt_sub). Skipped entirely without a usable token.
        sub = _get_jwt_sub(request)
        if sub is not None:
            allowed, retry_after = await _check_limit(
                redis,
                f"user:{sub}",
                "all",
                settings.RATE_LIMIT_USER_PER_MINUTE,
                key_prefix="rl",
            )
            if not allowed:
                return _too_many_requests(
                    settings.RATE_LIMIT_USER_PER_MINUTE,
                    "user",
                    retry_after,
                    bucket="user",
                )

        return await call_next(request)
