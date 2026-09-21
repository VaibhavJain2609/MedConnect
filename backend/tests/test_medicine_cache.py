"""Tests for the medicine catalog Redis cache (``medcat:*`` namespace).

Covers:
- Unit behaviour of ``app.services.medicine_cache`` (roundtrip, serialization
  of UUID/datetime/Decimal/Pydantic, graceful degradation on Redis errors)
- Cache population + hits on the EMR read endpoints
- Namespace invalidation on admin mutations
"""

import uuid
from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import BaseModel

from app.services import medicine_cache
from app.services.medicine_search_service import MedicineSearchService


@pytest.fixture
def fake_redis(monkeypatch):
    """Fresh fakeredis instance per test, patched into medicine_cache.

    Mirrors the pattern in conftest's ``_isolated_security_state`` which swaps
    the rate-limit and storage Redis clients for fakeredis.
    """
    fakeredis = pytest.importorskip("fakeredis.aioredis")
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(medicine_cache, "_get_redis", lambda: fake)
    return fake


async def _medcat_keys(fake) -> list[str]:
    return [key async for key in fake.scan_iter(match="medcat:*")]


# ---------------------------------------------------------------------------
# Unit tests: medicine_cache primitives
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_and_get_cached_roundtrip(fake_redis):
    salt_id = uuid.uuid4()
    payload = {
        "salt_id": salt_id,
        "created_at": datetime(2024, 1, 15, 10, 30, 0),
        "strength": Decimal("500.00"),
    }
    assert await medicine_cache.set_cached("medcat:test:roundtrip", payload, ttl=60)

    cached = await medicine_cache.get_cached("medcat:test:roundtrip")
    assert cached == {
        "salt_id": str(salt_id),
        "created_at": "2024-01-15T10:30:00",
        "strength": 500.0,
    }


@pytest.mark.asyncio
async def test_set_cached_serializes_pydantic_models(fake_redis):
    class _Item(BaseModel):
        item_id: uuid.UUID
        when: datetime

    model = _Item(item_id=uuid.uuid4(), when=datetime(2024, 6, 1, 8, 0, 0))
    assert await medicine_cache.set_cached("medcat:test:model", model, ttl=60)

    cached = await medicine_cache.get_cached("medcat:test:model")
    assert cached == model.model_dump(mode="json")


@pytest.mark.asyncio
async def test_get_cached_miss_returns_none(fake_redis):
    assert await medicine_cache.get_cached("medcat:missing") is None


@pytest.mark.asyncio
async def test_set_cached_unserializable_returns_false(fake_redis):
    assert await medicine_cache.set_cached("medcat:bad", object()) is False
    assert await medicine_cache.get_cached("medcat:bad") is None


@pytest.mark.asyncio
async def test_invalidate_pattern_removes_only_matching_keys(fake_redis):
    await medicine_cache.set_cached("medcat:a", 1)
    await medicine_cache.set_cached("medcat:b", 2)
    await fake_redis.set("other:key", "keep")

    removed = await medicine_cache.invalidate_pattern("medcat:*")
    assert removed == 2
    assert await _medcat_keys(fake_redis) == []
    assert await fake_redis.get("other:key") == "keep"


@pytest.mark.asyncio
async def test_redis_error_degrades_gracefully(monkeypatch):
    """Any Redis failure must behave like a cache miss / no-op."""

    def _boom():
        raise ConnectionError("redis unavailable")

    monkeypatch.setattr(medicine_cache, "_get_redis", _boom)

    assert await medicine_cache.get_cached("medcat:x") is None
    assert await medicine_cache.set_cached("medcat:x", {"a": 1}) is False
    assert await medicine_cache.invalidate_catalog() == 0


# ---------------------------------------------------------------------------
# Endpoint tests: reads populate and serve from the cache
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_caches_result_and_hits_on_repeat(
    patient_client, sample_salt, sample_brand, fake_redis, monkeypatch
):
    calls = 0
    original = MedicineSearchService.search_all

    async def _counting(db, search, limit=50):
        nonlocal calls
        calls += 1
        return await original(db, search=search, limit=limit)

    monkeypatch.setattr(MedicineSearchService, "search_all", _counting)

    r1 = await patient_client.get("/api/v1/medicines/search?q=para")
    assert r1.status_code == 200
    # Case-insensitive normalization means this hits the same cache key.
    r2 = await patient_client.get("/api/v1/medicines/search?q=PARA")
    assert r2.status_code == 200

    assert r1.json() == r2.json()
    assert calls == 1
    keys = await _medcat_keys(fake_redis)
    assert any(k.startswith("medcat:search:para") for k in keys)


@pytest.mark.asyncio
async def test_search_serves_preseeded_cache_without_db(
    patient_client, fake_redis, monkeypatch
):
    sentinel = {"salts": [{"name": "CachedSalt"}], "brands": [], "total_salts": 1, "total_brands": 0}
    await medicine_cache.set_cached("medcat:search:zztop:50", sentinel)

    async def _should_not_run(*args, **kwargs):  # pragma: no cover
        raise AssertionError("search_all should not be called on cache hit")

    monkeypatch.setattr(MedicineSearchService, "search_all", _should_not_run)

    r = await patient_client.get("/api/v1/medicines/search?q=zztop")
    assert r.status_code == 200
    assert r.json() == sentinel


@pytest.mark.asyncio
async def test_autocomplete_populates_and_serves_cache(
    patient_client, sample_brand, fake_redis
):
    r1 = await patient_client.get("/api/v1/medicines/autocomplete?q=Cro")
    assert r1.status_code == 200

    cached = await medicine_cache.get_cached("medcat:autocomplete:cro")
    assert cached == r1.json()

    # Overwrite the cache with a sentinel — the next request must return it
    # verbatim (proving the hit path bypasses the database entirely).
    sentinel = {"results": [{"brand_name": "Sentinel"}], "count": 1}
    await medicine_cache.set_cached("medcat:autocomplete:cro", sentinel)
    r2 = await patient_client.get("/api/v1/medicines/autocomplete?q=Cro")
    assert r2.status_code == 200
    assert r2.json() == sentinel


@pytest.mark.asyncio
async def test_salt_detail_is_cached(patient_client, sample_salt, fake_redis):
    r1 = await patient_client.get(f"/api/v1/salts/{sample_salt.salt_id}")
    assert r1.status_code == 200

    cached = await medicine_cache.get_cached(f"medcat:salt:{sample_salt.salt_id}")
    assert cached is not None
    assert cached["salt_name"] == "Paracetamol"

    r2 = await patient_client.get(f"/api/v1/salts/{sample_salt.salt_id}")
    assert r2.status_code == 200
    assert r2.json() == r1.json()


@pytest.mark.asyncio
async def test_brand_detail_is_cached(patient_client, sample_brand, fake_redis):
    r1 = await patient_client.get(f"/api/v1/brands/{sample_brand.brand_id}")
    assert r1.status_code == 200

    cached = await medicine_cache.get_cached(f"medcat:brand:{sample_brand.brand_id}")
    assert cached is not None
    assert cached["brand_name"] == "Crocin"

    r2 = await patient_client.get(f"/api/v1/brands/{sample_brand.brand_id}")
    assert r2.status_code == 200
    assert r2.json() == r1.json()


@pytest.mark.asyncio
async def test_read_endpoints_work_when_redis_is_down(
    patient_client, sample_salt, monkeypatch
):
    """Cache is opportunistic: endpoints must still answer without Redis."""
    monkeypatch.setattr(
        medicine_cache,
        "_get_redis",
        lambda: (_ for _ in ()).throw(ConnectionError("redis down")),
    )

    r = await patient_client.get("/api/v1/medicines/search?q=para")
    assert r.status_code == 200
    assert any(s["name"] == "Paracetamol" for s in r.json()["salts"])

    r = await patient_client.get(f"/api/v1/salts/{sample_salt.salt_id}")
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Invalidation: admin mutations flush the medcat:* namespace
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_salt_update_invalidates_cache(
    admin_client, sample_salt, fake_redis
):
    await medicine_cache.set_cached("medcat:search:para:50", {"x": 1})
    await medicine_cache.set_cached(f"medcat:salt:{sample_salt.salt_id}", {"x": 1})
    assert len(await _medcat_keys(fake_redis)) == 2

    r = await admin_client.put(
        f"/api/v1/admin/salts/{sample_salt.salt_id}",
        json={"description": "Updated description"},
    )
    assert r.status_code == 200
    assert await _medcat_keys(fake_redis) == []


@pytest.mark.asyncio
async def test_admin_salt_create_invalidates_cache(admin_client, fake_redis):
    await medicine_cache.set_cached("medcat:salts:-:-:-:1:50", {"x": 1})

    r = await admin_client.post(
        "/api/v1/admin/salts",
        json={"salt_name": "Amoxicillin", "prescription_required": True},
    )
    assert r.status_code == 201
    assert await _medcat_keys(fake_redis) == []


@pytest.mark.asyncio
async def test_admin_manufacturer_create_invalidates_cache(admin_client, fake_redis):
    await medicine_cache.set_cached("medcat:manufacturers:-:True:50:0", [{"x": 1}])

    r = await admin_client.post(
        "/api/v1/admin/manufacturers",
        json={"manufacturer_name": "New Pharma Co"},
    )
    assert r.status_code == 201
    assert await _medcat_keys(fake_redis) == []


@pytest.mark.asyncio
async def test_admin_brand_delete_invalidates_cache(
    admin_client, sample_brand, fake_redis
):
    await medicine_cache.set_cached(f"medcat:brand:{sample_brand.brand_id}", {"x": 1})

    r = await admin_client.delete(f"/api/v1/admin/brands/{sample_brand.brand_id}")
    assert r.status_code == 204
    assert await _medcat_keys(fake_redis) == []
