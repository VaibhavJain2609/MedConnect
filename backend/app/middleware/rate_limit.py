"""Redis-based rate limiting middleware.

Limits per token hash or IP address:
- Auth endpoints (/api/v1/auth/*): 5 req/min
- Write endpoints (POST/PUT/PATCH/DELETE): 20 req/min
- Read endpoints (GET): 100 req/min
"""
import hashlib
import logging
import time

import redis.asyncio as aioredis
from fastapi import status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings

_logger = logging.getLogger(__name__)

# Paths exempt from rate limiting
_EXEMPT_PATHS = {"/health", "/docs", "/redoc", "/openapi.json"}

# Rate limits per category (requests per minute)
_LIMITS: dict[str, int] = {
    "auth": 5,
    "write": 20,
    "read": 100,
}

_redis_client: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
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

    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return f"ip:{forwarded.split(',')[0].strip()}"
    host = request.client.host if request.client else "unknown"
    return f"ip:{host}"


async def _check_limit(
    redis: aioredis.Redis,
    user_key: str,
    category: str,
    limit: int,
    window: int = 60,
) -> tuple[bool, int]:
    """Increment counter; return (allowed, retry_after_seconds)."""
    current_window = int(time.time() // window)
    redis_key = f"rate_limit:{user_key}:{category}:{current_window}"
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
        _logger.error("Redis rate-limit unavailable (%s: %s); failing open", type(exc).__name__, exc)
        return True, 0


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        if path in _EXEMPT_PATHS:
            return await call_next(request)

        method = request.method.upper()

        if method == "OPTIONS":
            return await call_next(request)
        category = _get_category(method, path)
        limit = _LIMITS[category]
        user_key = _get_user_key(request)

        redis = _get_redis()
        allowed, retry_after = await _check_limit(redis, user_key, category, limit)

        if not allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": f"Rate limit exceeded. Maximum {limit} {category} requests per minute.",
                    }
                },
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)
