import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from tests.conftest import create_test_token, grant_doctor_patient_relationship, verify_provisioned_doctor


async def create_doctor_and_patient(client: AsyncClient, db) -> tuple[str, str, str]:
    """Create a doctor and patient via Keycloak tokens, return (doctor_token, patient_token, patient_id)."""
    patient_sub = str(uuid.uuid4())
    patient_token = create_test_token(sub=patient_sub, email="patient@records.com", name="Test Patient", roles=["patient"])

    # Auto-provision patient by calling /me
    me_resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {patient_token}"})
    patient_id = me_resp.json()["id"]

    doctor_sub = str(uuid.uuid4())
    doctor_token = create_test_token(sub=doctor_sub, email="doctor@records.com", name="Dr. Test", roles=["doctor"])

    # Auto-provision doctor by calling /me
    await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {doctor_token}"})
    await verify_provisioned_doctor(db, doctor_sub)
    await grant_doctor_patient_relationship(db, doctor_sub, patient_id)

    return doctor_token, patient_token, patient_id


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_create_record(client: AsyncClient, db):
    doctor_token, patient_token, patient_id = await create_doctor_and_patient(client, db)

    response = await client.post(
        "/api/v1/doctors/records",
        json={
            "patient_id": patient_id,
            "record_type": "opd_note",
            "title": "General Checkup",
            "description": "Patient presents with mild fever.",
        },
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert response.status_code == 201
    assert response.json()["title"] == "General Checkup"
    assert response.json()["record_type"] == "opd_note"


@pytest.mark.asyncio
async def test_patient_timeline(client: AsyncClient, db):
    doctor_token, patient_token, patient_id = await create_doctor_and_patient(client, db)

    # Create 2 records
    await client.post(
        "/api/v1/doctors/records",
        json={"patient_id": patient_id, "record_type": "opd_note", "title": "Visit 1"},
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    await client.post(
        "/api/v1/doctors/records",
        json={"patient_id": patient_id, "record_type": "lab_report", "title": "Blood Work"},
        headers={"Authorization": f"Bearer {doctor_token}"},
    )

    response = await client.get(
        "/api/v1/patients/timeline",
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    titles = {r["title"] for r in data["data"]}
    assert {"Visit 1", "Blood Work"} <= titles
    assert data["pagination"]["has_more"] is False


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_patient_cannot_access_other_records(client: AsyncClient, db):
    doctor_token, patient_token, patient_id = await create_doctor_and_patient(client, db)

    # Create another patient
    other_sub = str(uuid.uuid4())
    other_token = create_test_token(sub=other_sub, email="other@records.com", name="Other Patient", roles=["patient"])
    await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {other_token}"})

    # Create record for first patient
    create_resp = await client.post(
        "/api/v1/doctors/records",
        json={"patient_id": patient_id, "record_type": "opd_note", "title": "Private Visit"},
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    record_id = create_resp.json()["id"]

    # Other patient tries to access
    response = await client.get(
        f"/api/v1/patients/records/{record_id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_patient_record_versions(client: AsyncClient, db):
    doctor_token, patient_token, patient_id = await create_doctor_and_patient(client, db)

    create_resp = await client.post(
        "/api/v1/doctors/records",
        json={
            "patient_id": patient_id,
            "record_type": "opd_note",
            "title": "Visit",
            "description": "initial note",
        },
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert create_resp.status_code == 201
    record_id = create_resp.json()["id"]

    # No amendments yet — chain is just the original
    resp = await client.get(
        f"/api/v1/patients/records/{record_id}/versions",
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["data"][0]["version"] == 1
    assert data["data"][0]["is_latest"] is True
    assert data["data"][0]["amended_from_id"] is None

    amend_resp = await client.post(
        f"/api/v1/doctors/records/{record_id}/amend",
        json={
            "record_type": "opd_note",
            "title": "Visit (corrected)",
            "description": "amended note",
        },
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert amend_resp.status_code == 201
    amendment_id = amend_resp.json()["id"]

    resp = await client.get(
        f"/api/v1/patients/records/{record_id}/versions",
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert data["root_record_id"] == record_id
    v1, v2 = data["data"]
    assert v1["version"] == 1 and v1["is_latest"] is False
    assert v2["version"] == 2 and v2["is_latest"] is True
    assert v2["amended_from_id"] == record_id
    assert v2["doctor_name"] == "Dr. Test"

    # Chain resolves the same way when queried via the amendment's id
    resp = await client.get(
        f"/api/v1/patients/records/{amendment_id}/versions",
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


@pytest.mark.asyncio
async def test_patient_cannot_access_other_record_versions(client: AsyncClient, db):
    doctor_token, _, patient_id = await create_doctor_and_patient(client, db)

    create_resp = await client.post(
        "/api/v1/doctors/records",
        json={"patient_id": patient_id, "record_type": "opd_note", "title": "Private"},
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    record_id = create_resp.json()["id"]

    other_sub = str(uuid.uuid4())
    other_token = create_test_token(sub=other_sub, email="other2@records.com", name="Other", roles=["patient"])
    await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {other_token}"})

    response = await client.get(
        f"/api/v1/patients/records/{record_id}/versions",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/patients/records — list filters (type / q / from_date / to_date)
# ---------------------------------------------------------------------------


async def _seed_records(client: AsyncClient, doctor_token: str, patient_id: str):
    """Create two records of different types/titles for `patient_id`."""
    r1 = await client.post(
        "/api/v1/doctors/records",
        json={"patient_id": patient_id, "record_type": "opd_note", "title": "General Checkup"},
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert r1.status_code == 201
    r2 = await client.post(
        "/api/v1/doctors/records",
        json={"patient_id": patient_id, "record_type": "lab_report", "title": "Blood Work Panel"},
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert r2.status_code == 201


@pytest.mark.asyncio
async def test_patient_records_filter_by_type(client: AsyncClient, db):
    doctor_token, patient_token, patient_id = await create_doctor_and_patient(client, db)
    await _seed_records(client, doctor_token, patient_id)

    # New record_type param
    resp = await client.get(
        "/api/v1/patients/records?record_type=lab_report",
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["record_type"] == "lab_report"
    assert data[0]["title"] == "Blood Work Panel"

    # Legacy `type` param still works — opd_note matches both the seeded
    # "General Checkup" and the relationship-seed record from
    # grant_doctor_patient_relationship.
    resp = await client.get(
        "/api/v1/patients/records?type=opd_note",
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 2
    assert {r["record_type"] for r in data} == {"opd_note"}


@pytest.mark.asyncio
async def test_patient_records_filter_by_query(client: AsyncClient, db):
    doctor_token, patient_token, patient_id = await create_doctor_and_patient(client, db)
    await _seed_records(client, doctor_token, patient_id)

    resp = await client.get(
        "/api/v1/patients/records?q=blood",
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["title"] == "Blood Work Panel"


@pytest.mark.asyncio
async def test_patient_records_filter_by_date_range(client: AsyncClient, db):
    doctor_token, patient_token, patient_id = await create_doctor_and_patient(client, db)
    await _seed_records(client, doctor_token, patient_id)

    today = date.today()
    yesterday = (today - timedelta(days=1)).isoformat()
    tomorrow = (today + timedelta(days=1)).isoformat()

    auth = {"Authorization": f"Bearer {patient_token}"}

    # All records (2 seeded + relationship-seed opd_note) were created today —
    # a range ending yesterday excludes them
    resp = await client.get(f"/api/v1/patients/records?to_date={yesterday}", headers=auth)
    assert resp.status_code == 200
    assert resp.json()["data"] == []

    # A range starting tomorrow excludes them
    resp = await client.get(f"/api/v1/patients/records?from_date={tomorrow}", headers=auth)
    assert resp.status_code == 200
    assert resp.json()["data"] == []

    # A range spanning today includes all 3 (to_date is inclusive of the day)
    resp = await client.get(
        f"/api/v1/patients/records?from_date={today.isoformat()}&to_date={today.isoformat()}",
        headers=auth,
    )
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 3

    # Wide range sanity check
    resp = await client.get(
        "/api/v1/patients/records?from_date=2000-01-01&to_date=2099-12-31",
        headers=auth,
    )
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 3


@pytest.mark.asyncio
async def test_patient_records_filters_do_not_leak_other_patients(client: AsyncClient, db):
    doctor_token, patient_token, patient_id = await create_doctor_and_patient(client, db)
    await _seed_records(client, doctor_token, patient_id)

    # Second patient with no records — filters must not widen the scope
    other_sub = str(uuid.uuid4())
    other_token = create_test_token(
        sub=other_sub, email="other3@records.com", name="Other", roles=["patient"]
    )
    await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {other_token}"})

    for qs in ("record_type=lab_report", "q=blood", "from_date=2000-01-01&to_date=2099-12-31"):
        resp = await client.get(
            f"/api/v1/patients/records?{qs}",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"] == []


@pytest.mark.asyncio
async def test_patient_records_combined_filters(client: AsyncClient, db):
    doctor_token, patient_token, patient_id = await create_doctor_and_patient(client, db)
    await _seed_records(client, doctor_token, patient_id)

    today = date.today().isoformat()
    auth = {"Authorization": f"Bearer {patient_token}"}

    # type + q + date range together
    resp = await client.get(
        f"/api/v1/patients/records?record_type=lab_report&q=blood&from_date={today}&to_date={today}",
        headers=auth,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["title"] == "Blood Work Panel"

    # Matching type but non-matching query → empty
    resp = await client.get(
        "/api/v1/patients/records?record_type=lab_report&q=checkup",
        headers=auth,
    )
    assert resp.status_code == 200
    assert resp.json()["data"] == []
