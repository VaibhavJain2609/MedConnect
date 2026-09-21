"""Opportunistic Redis cache for the medicine catalog.

The medicine catalog (salts, brands, manufacturers, strengths) is effectively
static — it only changes through admin mutations. Read paths in
``routers/medicines_emr.py`` cache serialized responses under the ``medcat:*``
namespace; admin mutations flush the whole namespace via
:func:`invalidate_catalog`.

The cache is strictly opportunistic: every function degrades gracefully. Any
Redis error (connection refused, timeout, serialization failure) is logged and
treated as a miss/no-op, so the API never depends on Redis being available.
"""

import json
import logging
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import redis.asyncio as aioredis
from pydantic import BaseModel

from app.config import settings

_logger = logging.getLogger(__name__)

# All medicine-catalog cache entries live under this prefix so invalidation is
# a single namespace flush.
KEY_PREFIX = "medcat:"

# Search/autocomplete results: short-ish TTL as a second layer of safety on top
# of mutation-driven invalidation.
SEARCH_TTL_SECONDS = 300

# Detail lookups (salt/brand/manufacturer by id): effectively static.
DETAIL_TTL_SECONDS = 3600

_redis_client: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    """Lazy Redis client (same pattern as rate_limit / storage_service).

    Tests patch this function with a fakeredis instance — see conftest.py.
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            max_connections=10,
        )
    return _redis_client


def make_key(*parts) -> str:
    """Build a namespaced cache key from path segments.

    Example: ``make_key("salt", salt_id)`` -> ``"medcat:salt:<uuid>"``.
    """
    return KEY_PREFIX + ":".join(str(p) for p in parts)


def _json_default(obj):
    """Serialize types json can't handle natively: datetimes, dates, UUIDs,
    Decimals, and Pydantic models (dumped in json mode so nested values are
    already primitives)."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


async def get_cached(key: str):
    """Return the cached value for ``key``, or None on miss/error."""
    try:
        raw = await _get_redis().get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as exc:
        _logger.warning("medcat cache get failed for %s (%s)", key, exc)
        return None


async def set_cached(key: str, value, ttl: int = SEARCH_TTL_SECONDS) -> bool:
    """Serialize ``value`` to JSON and store it under ``key`` with ``ttl``.

    Returns True on success, False on any error (never raises).
    """
    try:
        payload = json.dumps(value, default=_json_default)
        await _get_redis().set(key, payload, ex=ttl)
        return True
    except Exception as exc:
        _logger.warning("medcat cache set failed for %s (%s)", key, exc)
        return False


async def invalidate_pattern(pattern: str) -> int:
    """Delete all keys matching ``pattern`` (SCAN + DEL). Returns the number
    of keys removed; 0 on error."""
    try:
        redis = _get_redis()
        keys = [key async for key in redis.scan_iter(match=pattern, count=500)]
        if not keys:
            return 0
        return await redis.delete(*keys)
    except Exception as exc:
        _logger.warning("medcat cache invalidation failed for %s (%s)", pattern, exc)
        return 0


async def invalidate_catalog() -> int:
    """Flush the entire ``medcat:*`` namespace. Called by admin mutations on
    brands/salts/manufacturers after the DB commit succeeds."""
    return await invalidate_pattern(f"{KEY_PREFIX}*")
