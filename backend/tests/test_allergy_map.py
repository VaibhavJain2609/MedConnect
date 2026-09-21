"""Tests for POST /api/v1/interactions/check-allergies.

Structured allergy -> salt check that backs the Rx page (replacing the
client-side fuzzy substring matching in prescriptions/new/page.tsx).

Contract:
    POST /api/v1/interactions/check-allergies
    {patient_id, salt_ids: [UUID...]}
    -> {conflicts: [{salt_id, salt_name, allergy, match}],
        checked_allergies: [<allergy terms that produced no match>]}
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from tests.conftest import grant_doctor_patient_relationship, make_auth_header

URL = "/api/v1/interactions/check-allergies"


@pytest.fixture(autouse=True)
def _fake_medcat_cache(monkeypatch):
    """Patch the medcat Redis client used by allergy_service._load_salt_names.

    The cache is fail-open, but without this each request would attempt a
    real connection to settings.REDIS_URL on every salt lookup.
    """
    fakeredis = pytest.importorskip("fakeredis.aioredis")
    from app.services import medicine_cache

    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(medicine_cache, "_get_redis", lambda: fake)
    return fake


async def _set_allergies(db: AsyncSession, user: User, allergies) -> None:
    user.allergies = allergies
    await db.commit()


# ---------------------------------------------------------------------------
# Matching behaviour (patient self-check)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exact_match_returns_conflict(
    patient_client: AsyncClient, patient_user: User, sample_salt, db: AsyncSession
):
    await _set_allergies(db, patient_user, ["Paracetamol"])

    resp = await patient_client.post(
        URL,
        json={
            "patient_id": str(patient_user.id),
            "salt_ids": [str(sample_salt.salt_id)],
        },
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data["conflicts"]) == 1
    conflict = data["conflicts"][0]
    assert conflict["salt_id"] == str(sample_salt.salt_id)
    assert conflict["salt_name"] == "Paracetamol"
    assert conflict["allergy"] == "Paracetamol"
    assert conflict["match"] == "exact"
    assert data["checked_allergies"] == []


@pytest.mark.asyncio
async def test_partial_match_returns_conflict(
    patient_client: AsyncClient, patient_user: User, sample_salt, db: AsyncSession
):
    """Length-guarded containment (>=4 chars both ways) reports match=partial."""
    await _set_allergies(db, patient_user, ["paracet"])  # 7 chars

    resp = await patient_client.post(
        URL,
        json={
            "patient_id": str(patient_user.id),
            "salt_ids": [str(sample_salt.salt_id)],
        },
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data["conflicts"]) == 1
    assert data["conflicts"][0]["match"] == "partial"
    assert data["conflicts"][0]["allergy"] == "paracet"
    assert data["checked_allergies"] == []


@pytest.mark.asyncio
async def test_non_matching_allergy_reported_as_checked(
    patient_client: AsyncClient, patient_user: User, sample_salt, db: AsyncSession
):
    await _set_allergies(db, patient_user, ["Penicillin"])

    resp = await patient_client.post(
        URL,
        json={
            "patient_id": str(patient_user.id),
            "salt_ids": [str(sample_salt.salt_id)],
        },
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["conflicts"] == []
    assert data["checked_allergies"] == ["Penicillin"]


@pytest.mark.asyncio
async def test_short_allergy_terms_never_partial_match(
    patient_client: AsyncClient, patient_user: User, sample_salt, db: AsyncSession
):
    """'mol' is a substring of 'Paracetamol' but only 3 chars — no match."""
    await _set_allergies(db, patient_user, ["mol"])

    resp = await patient_client.post(
        URL,
        json={
            "patient_id": str(patient_user.id),
            "salt_ids": [str(sample_salt.salt_id)],
        },
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["conflicts"] == []
    assert data["checked_allergies"] == ["mol"]


@pytest.mark.asyncio
async def test_dict_allergy_entries_match_on_name_key(
    patient_client: AsyncClient, patient_user: User, sample_salt, db: AsyncSession
):
    """JSONB dict entries contribute their name-ish value (same semantics as
    clinical_safety_service._patient_terms)."""
    await _set_allergies(db, patient_user, [{"name": "Paracetamol", "severity": "severe"}])

    resp = await patient_client.post(
        URL,
        json={
            "patient_id": str(patient_user.id),
            "salt_ids": [str(sample_salt.salt_id)],
        },
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data["conflicts"]) == 1
    assert data["conflicts"][0]["match"] == "exact"


@pytest.mark.asyncio
async def test_mixed_allergies_split_matched_and_checked(
    patient_client: AsyncClient, patient_user: User, sample_salt, db: AsyncSession
):
    await _set_allergies(db, patient_user, ["Paracetamol", "Penicillin", "latex"])

    resp = await patient_client.post(
        URL,
        json={
            "patient_id": str(patient_user.id),
            "salt_ids": [str(sample_salt.salt_id)],
        },
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert [c["allergy"] for c in data["conflicts"]] == ["Paracetamol"]
    assert sorted(data["checked_allergies"]) == ["Penicillin", "latex"]


@pytest.mark.asyncio
async def test_empty_salt_ids_returns_no_conflicts(
    patient_client: AsyncClient, patient_user: User, db: AsyncSession
):
    await _set_allergies(db, patient_user, ["Paracetamol"])

    resp = await patient_client.post(
        URL,
        json={"patient_id": str(patient_user.id), "salt_ids": []},
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["conflicts"] == []
    assert data["checked_allergies"] == ["Paracetamol"]


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patient_cannot_check_another_patient(
    patient_client: AsyncClient, patient_user: User, sample_salt, db: AsyncSession
):
    await _set_allergies(db, patient_user, ["Paracetamol"])

    resp = await patient_client.post(
        URL,
        json={
            "patient_id": str(uuid4()),  # someone else's id
            "salt_ids": [str(sample_salt.salt_id)],
        },
    )

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_unauthenticated_request_rejected(client: AsyncClient, sample_salt):
    resp = await client.post(
        URL,
        json={"patient_id": str(uuid4()), "salt_ids": [str(sample_salt.salt_id)]},
    )

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_doctor_without_relationship_forbidden(
    doctor_client: AsyncClient, patient_user: User, sample_salt, db: AsyncSession
):
    await _set_allergies(db, patient_user, ["Paracetamol"])

    resp = await doctor_client.post(
        URL,
        json={
            "patient_id": str(patient_user.id),
            "salt_ids": [str(sample_salt.salt_id)],
        },
    )

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_doctor_with_relationship_can_check(
    doctor_client: AsyncClient,
    doctor_user: User,
    patient_user: User,
    sample_salt,
    db: AsyncSession,
):
    await _set_allergies(db, patient_user, ["Paracetamol"])
    await grant_doctor_patient_relationship(db, doctor_user.keycloak_sub, patient_user.id)

    resp = await doctor_client.post(
        URL,
        json={
            "patient_id": str(patient_user.id),
            "salt_ids": [str(sample_salt.salt_id)],
        },
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data["conflicts"]) == 1
    assert data["conflicts"][0]["salt_name"] == "Paracetamol"


@pytest.mark.asyncio
async def test_admin_role_forbidden(
    admin_client: AsyncClient, patient_user: User, sample_salt, db: AsyncSession
):
    await _set_allergies(db, patient_user, ["Paracetamol"])

    resp = await admin_client.post(
        URL,
        json={
            "patient_id": str(patient_user.id),
            "salt_ids": [str(sample_salt.salt_id)],
        },
    )

    assert resp.status_code == 403
