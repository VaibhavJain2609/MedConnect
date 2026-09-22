"""Family member (dependent) profiles — R12.

Covers:
  - CRUD auth: unauthenticated 401, wrong role 403
  - owner isolation: a patient can only see/edit their own dependents
  - medical_records.family_member_id attach + list filter
  - validation: invalid relationship / future dob → 422
"""
import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import create_test_token

FAMILY_URL = "/api/v1/family/members"
RECORDS_URL = "/api/v1/patients/records"


async def _other_patient_token(client: AsyncClient) -> str:
    """Auto-provision a second patient and return their token."""
    sub = str(uuid.uuid4())
    token = create_test_token(
        sub=sub, email=f"{sub}@family.test", name="Other Patient", roles=["patient"]
    )
    resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    return token


async def _create_member(
    client: AsyncClient, token: str | None = None, **overrides
) -> dict:
    payload = {
        "full_name": "Asha Kid",
        "dob": "2018-06-15",
        "relationship": "child",
        "gender": "female",
        "blood_group": "O+",
        "notes": "Asthmatic",
    }
    payload.update(overrides)
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    resp = await client.post(FAMILY_URL, json=payload, headers=headers)
    return resp


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_family_requires_auth(client: AsyncClient):
    resp = await client.get(FAMILY_URL)
    assert resp.status_code == 401
    resp = await client.post(FAMILY_URL, json={})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_family_wrong_role_403(admin_client: AsyncClient):
    resp = await admin_client.get(FAMILY_URL)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_member_201_with_age(patient_client: AsyncClient):
    resp = await _create_member(patient_client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["member_id"]
    assert body["id"] == body["member_id"]
    assert body["full_name"] == "Asha Kid"
    assert body["relationship"] == "child"
    assert body["blood_group"] == "O+"
    assert isinstance(body["age"], int) and body["age"] >= 6


@pytest.mark.asyncio
async def test_list_members(patient_client: AsyncClient):
    await _create_member(patient_client, full_name="Kid One")
    await _create_member(
        patient_client, full_name="Parent Two", relationship="parent", dob="1960-01-01"
    )
    resp = await patient_client.get(FAMILY_URL)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    names = {m["full_name"] for m in data["data"]}
    assert names == {"Kid One", "Parent Two"}


@pytest.mark.asyncio
async def test_get_member(patient_client: AsyncClient):
    created = (await _create_member(patient_client)).json()
    resp = await patient_client.get(f"{FAMILY_URL}/{created['member_id']}")
    assert resp.status_code == 200
    assert resp.json()["member_id"] == created["member_id"]


@pytest.mark.asyncio
async def test_update_member(patient_client: AsyncClient):
    created = (await _create_member(patient_client)).json()
    resp = await patient_client.patch(
        f"{FAMILY_URL}/{created['member_id']}",
        json={"full_name": "Asha Renamed", "notes": "Updated"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["full_name"] == "Asha Renamed"
    assert body["notes"] == "Updated"
    assert body["relationship"] == "child"  # unchanged


@pytest.mark.asyncio
async def test_delete_member_soft(patient_client: AsyncClient):
    created = (await _create_member(patient_client)).json()
    resp = await patient_client.delete(f"{FAMILY_URL}/{created['member_id']}")
    assert resp.status_code == 204

    # Gone from detail + list
    assert (
        await patient_client.get(f"{FAMILY_URL}/{created['member_id']}")
    ).status_code == 404
    listed = (await patient_client.get(FAMILY_URL)).json()
    assert listed["total"] == 0


# ---------------------------------------------------------------------------
# Cross-owner isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cross_owner_isolation(patient_client: AsyncClient, client: AsyncClient):
    created = (await _create_member(patient_client)).json()
    member_id = created["member_id"]
    other_token = await _other_patient_token(client)
    auth = {"Authorization": f"Bearer {other_token}"}

    # Other patient's list is empty and untouched
    listed = (await client.get(FAMILY_URL, headers=auth)).json()
    assert listed["total"] == 0

    for method in ("get", "patch", "delete"):
        resp = await getattr(client, method)(
            f"{FAMILY_URL}/{member_id}",
            headers=auth,
            **({"json": {"full_name": "Hijack"}} if method == "patch" else {}),
        )
        assert resp.status_code == 404, method

    # Original owner still sees the member intact
    resp = await patient_client.get(f"{FAMILY_URL}/{member_id}")
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Asha Kid"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalid_relationship_422(patient_client: AsyncClient):
    resp = await _create_member(patient_client, relationship="cousin")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_future_dob_422(patient_client: AsyncClient):
    resp = await _create_member(patient_client, dob="2999-01-01")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_missing_required_fields_422(patient_client: AsyncClient):
    resp = await patient_client.post(FAMILY_URL, json={"relationship": "child"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Records attached to a dependent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_attach_and_filter(patient_client: AsyncClient):
    member = (await _create_member(patient_client)).json()
    member_id = member["member_id"]

    # Record for the dependent
    resp = await patient_client.post(
        RECORDS_URL,
        json={
            "record_type": "lab_report",
            "title": "Kid blood panel",
            "family_member_id": member_id,
        },
    )
    assert resp.status_code == 201
    assert resp.json()["family_member_id"] == member_id

    # Record for the patient themselves
    resp = await patient_client.post(
        RECORDS_URL, json={"record_type": "imaging", "title": "Own x-ray"}
    )
    assert resp.status_code == 201
    assert resp.json()["family_member_id"] is None

    # Filtered list returns only the dependent's record
    resp = await patient_client.get(
        RECORDS_URL, params={"family_member_id": member_id}
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["title"] == "Kid blood panel"
    assert data[0]["family_member_id"] == member_id

    # Unfiltered list returns both
    resp = await patient_client.get(RECORDS_URL)
    assert len(resp.json()["data"]) == 2


@pytest.mark.asyncio
async def test_record_attach_other_owner_member_400(
    patient_client: AsyncClient, client: AsyncClient
):
    other_token = await _other_patient_token(client)
    member = (await _create_member(client, token=other_token)).json()

    resp = await patient_client.post(
        RECORDS_URL,
        json={
            "record_type": "lab_report",
            "title": "Not my kid",
            "family_member_id": member["member_id"],
        },
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_record_attach_deleted_member_400(patient_client: AsyncClient):
    member = (await _create_member(patient_client)).json()
    await patient_client.delete(f"{FAMILY_URL}/{member['member_id']}")

    resp = await patient_client.post(
        RECORDS_URL,
        json={
            "record_type": "lab_report",
            "title": "Gone member",
            "family_member_id": member["member_id"],
        },
    )
    assert resp.status_code == 400
