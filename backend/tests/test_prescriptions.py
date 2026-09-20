import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import create_test_token, grant_doctor_patient_relationship, verify_provisioned_doctor


async def setup_users(client: AsyncClient, db) -> tuple[str, str, str]:
    patient_sub = str(uuid.uuid4())
    patient_token = create_test_token(sub=patient_sub, email="patient@rx.com", name="Rx Patient", roles=["patient"])
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {patient_token}"})
    patient_id = me.json()["id"]

    doctor_sub = str(uuid.uuid4())
    doctor_token = create_test_token(sub=doctor_sub, email="doctor@rx.com", name="Dr. Rx", roles=["doctor"])
    await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {doctor_token}"})
    await verify_provisioned_doctor(db, doctor_sub)
    await grant_doctor_patient_relationship(db, doctor_sub, patient_id)

    return doctor_token, patient_token, patient_id


@pytest.mark.asyncio
async def test_create_prescription(client: AsyncClient, db):
    doctor_token, patient_token, patient_id = await setup_users(client, db)

    response = await client.post(
        "/api/v1/doctors/prescriptions",
        json={
            "patient_id": patient_id,
            "medicines": [
                {
                    "brand_name": "Amoxicillin 500mg",
                    "dose": "500mg",
                    "frequency": "3 times daily",
                    "duration": "5 days",
                    "instructions": "after food",
                }
            ],
            "diagnosis": "Upper respiratory infection",
            "notes": "Complete full course",
        },
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert len(data["medicines"]) == 1
    assert data["diagnosis"] == "Upper respiratory infection"


@pytest.mark.asyncio
async def test_patient_sees_prescription_in_timeline(client: AsyncClient, db):
    doctor_token, patient_token, patient_id = await setup_users(client, db)

    await client.post(
        "/api/v1/doctors/prescriptions",
        json={
            "patient_id": patient_id,
            "medicines": [{"brand_name": "Paracetamol", "dose": "500mg", "frequency": "twice daily", "duration": "3 days"}],
            "diagnosis": "Fever",
        },
        headers={"Authorization": f"Bearer {doctor_token}"},
    )

    timeline = await client.get(
        "/api/v1/patients/timeline",
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert timeline.status_code == 200
    rx = [r for r in timeline.json()["data"] if r["record_type"] == "prescription"]
    assert len(rx) == 1
    assert timeline.json()["data"][0]["record_type"] == "prescription"


@pytest.mark.asyncio
async def test_patient_prescriptions_endpoint(client: AsyncClient, db):
    doctor_token, patient_token, patient_id = await setup_users(client, db)

    await client.post(
        "/api/v1/doctors/prescriptions",
        json={
            "patient_id": patient_id,
            "medicines": [{"brand_name": "Metformin", "dose": "500mg", "frequency": "twice daily", "duration": "ongoing"}],
            "diagnosis": "Type 2 Diabetes",
        },
        headers={"Authorization": f"Bearer {doctor_token}"},
    )

    response = await client.get(
        "/api/v1/patients/prescriptions",
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert response.status_code == 200
    assert len(response.json()["data"]) == 1
