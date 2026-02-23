import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import create_test_token


async def create_doctor_and_patient(client: AsyncClient) -> tuple[str, str, str]:
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

    return doctor_token, patient_token, patient_id


@pytest.mark.asyncio
async def test_create_record(client: AsyncClient):
    doctor_token, patient_token, patient_id = await create_doctor_and_patient(client)

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
async def test_patient_timeline(client: AsyncClient):
    doctor_token, patient_token, patient_id = await create_doctor_and_patient(client)

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
    assert len(data["data"]) == 2
    assert data["pagination"]["has_more"] is False


@pytest.mark.asyncio
async def test_patient_cannot_access_other_records(client: AsyncClient):
    doctor_token, patient_token, patient_id = await create_doctor_and_patient(client)

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
