import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import create_test_token, grant_doctor_patient_relationship, verify_provisioned_doctor


async def setup_prescription(client: AsyncClient, db) -> tuple[str, str, str]:
    """Create doctor, patient, and prescription for testing."""
    # Create patient
    patient_sub = str(uuid.uuid4())
    patient_token = create_test_token(
        sub=patient_sub,
        email="patient@pdf.com",
        name="PDF Patient",
        roles=["patient"]
    )
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {patient_token}"})
    patient_id = me.json()["id"]

    # Create doctor
    doctor_sub = str(uuid.uuid4())
    doctor_token = create_test_token(
        sub=doctor_sub,
        email="doctor@pdf.com",
        name="Dr. PDF",
        roles=["doctor"]
    )
    await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {doctor_token}"})
    await verify_provisioned_doctor(db, doctor_sub)
    await grant_doctor_patient_relationship(db, doctor_sub, patient_id)

    # Update doctor profile
    await client.put(
        "/api/v1/doctors/profile",
        json={
            "specialization": "General Physician",
            "license_number": "MH-12345",
            "facility_name": "MedConnect Clinic",
            "facility_city": "Mumbai"
        },
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    # Create prescription
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
                    "notes": "Complete full course"
                },
                {
                    "brand_name": "Paracetamol 500mg",
                    "dose": "500mg",
                    "frequency": "as needed",
                    "duration": "3 days",
                    "instructions": "after food"
                }
            ],
            "diagnosis": "Upper Respiratory Tract Infection",
            "notes": "Rest and plenty of fluids. Return if symptoms worsen."
        },
        headers={"Authorization": f"Bearer {doctor_token}"}
    )
    prescription_id = response.json()["id"]

    return doctor_token, patient_token, prescription_id


@pytest.mark.asyncio
async def test_doctor_can_download_prescription_pdf(client: AsyncClient, db):
    """Test that doctor can download PDF of their prescription."""
    doctor_token, _, prescription_id = await setup_prescription(client, db)

    response = await client.get(
        f"/api/v1/prescriptions/{prescription_id}/pdf",
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "filename=" in response.headers.get("content-disposition", "")  # served inline for in-browser viewing
    assert len(response.content) > 1000  # PDF should be reasonably sized


@pytest.mark.asyncio
async def test_patient_can_download_their_prescription_pdf(client: AsyncClient, db):
    """Test that patient can download PDF of their own prescription."""
    _, patient_token, prescription_id = await setup_prescription(client, db)

    response = await client.get(
        f"/api/v1/prescriptions/{prescription_id}/pdf",
        headers={"Authorization": f"Bearer {patient_token}"}
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"


@pytest.mark.asyncio
async def test_unauthorized_user_cannot_download_pdf(client: AsyncClient, db):
    """Test that unauthorized user cannot download someone else's prescription PDF."""
    _, _, prescription_id = await setup_prescription(client, db)

    # Create different user
    other_sub = str(uuid.uuid4())
    other_token = create_test_token(
        sub=other_sub,
        email="other@test.com",
        name="Other User",
        roles=["patient"]
    )
    await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {other_token}"})

    response = await client.get(
        f"/api/v1/prescriptions/{prescription_id}/pdf",
        headers={"Authorization": f"Bearer {other_token}"}
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_pdf_download_for_nonexistent_prescription(client: AsyncClient, db):
    """Test 404 for non-existent prescription."""
    doctor_token, _, _ = await setup_prescription(client, db)

    fake_id = str(uuid.uuid4())
    response = await client.get(
        f"/api/v1/prescriptions/{fake_id}/pdf",
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 404
