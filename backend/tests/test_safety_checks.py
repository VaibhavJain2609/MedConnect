"""Tests for persisted prescription safety checks (R13).

- POST /api/v1/doctors/prescriptions writes one prescription_safety_checks row
  per successful create (including the safety_override_reason path).
- GET /api/v1/prescriptions/{id}/safety-check returns the latest snapshot to
  the authoring doctor, clinic members, admins, and the patient themselves;
  other doctors/patients get 403, unknown ids get 404.
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clinic import Clinic, ClinicMembership
from app.models.doctor import Doctor
from app.models.medical_record import MedicalRecord
from app.models.patient_link import PatientClinicLink
from app.models.prescription import Prescription
from app.models.prescription_safety_check import PrescriptionSafetyCheck
from app.models.user import User
from tests.conftest import create_test_token, grant_doctor_patient_relationship, make_auth_header


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _rx_payload(patient_id, medicines=None, **extra):
    return {
        "patient_id": str(patient_id),
        "medicines": medicines
        or [
            {
                "brand_name": "Amoxicillin 500mg",
                "dose": "500mg",
                "frequency": "TDS",
                "duration": "5 days",
            }
        ],
        **extra,
    }


async def _create_rx(doctor_client: AsyncClient, db: AsyncSession, patient_id, **kwargs) -> dict:
    await grant_doctor_patient_relationship(db, "doctor-123", patient_id)
    headers = kwargs.pop("headers", None)
    res = await doctor_client.post(
        "/api/v1/doctors/prescriptions",
        json=_rx_payload(patient_id, **kwargs),
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_safety_check_row_written_on_create(
    doctor_client: AsyncClient, doctor_profile, patient_user, db: AsyncSession
):
    """A normal create persists one snapshot row retrievable via the API."""
    created = await _create_rx(doctor_client, db, patient_user.id, diagnosis="URI")

    # Row exists in the main DB with the submitted items snapshot.
    row = (
        await db.execute(
            select(PrescriptionSafetyCheck).where(
                PrescriptionSafetyCheck.prescription_id == uuid.UUID(created["id"])
            )
        )
    ).scalar_one()
    assert len(row.items_json) == 1
    assert row.items_json[0]["brand_name"] == "Amoxicillin 500mg"
    assert row.override_reason is None
    # Free-text item can't resolve to catalog salts -> unresolved_item alert.
    assert [a["kind"] for a in row.alerts_json] == ["unresolved_item"]

    res = await doctor_client.get(f"/api/v1/prescriptions/{created['id']}/safety-check")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["id"] == str(row.id)
    assert body["prescription_id"] == created["id"]
    assert body["checked_at"]
    assert body["created_at"]
    assert body["items"] == row.items_json
    assert body["alerts"] == row.alerts_json
    assert body["alerts"][0]["severity"] == "moderate"
    assert body["override_reason"] is None


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_override_path_records_reason(
    doctor_client: AsyncClient,
    doctor_profile,
    patient_user,
    db: AsyncSession,
    medicine_db: AsyncSession,
    sample_salt,
):
    """Major (allergy) alert + safety_override_reason -> reason persisted."""
    patient_user.allergies = ["Paracetamol"]
    await db.commit()

    medicines = [
        {
            "brand_name": "Paracetamol 500",
            "salt_id": str(sample_salt.salt_id),  # sample_salt is Paracetamol
            "dose": "500mg",
            "frequency": "BD",
            "duration": "3 days",
        }
    ]

    await grant_doctor_patient_relationship(db, "doctor-123", patient_user.id)

    # Without the reason the gate refuses to issue the prescription.
    blocked = await doctor_client.post(
        "/api/v1/doctors/prescriptions",
        json=_rx_payload(patient_user.id, medicines=medicines),
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "SAFETY_OVERRIDE_REQUIRED"

    created = await doctor_client.post(
        "/api/v1/doctors/prescriptions",
        json=_rx_payload(
            patient_user.id,
            medicines=medicines,
            safety_override_reason="Patient tolerates it; monitored",
        ),
    )
    assert created.status_code == 201, created.text
    rx_id = created.json()["id"]

    res = await doctor_client.get(f"/api/v1/prescriptions/{rx_id}/safety-check")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["override_reason"] == "Patient tolerates it; monitored"
    kinds = {a["kind"] for a in body["alerts"]}
    assert "allergy" in kinds
    assert any(a["severity"] == "major" for a in body["alerts"])


@pytest.mark.asyncio
async def test_safety_check_scoping(
    client: AsyncClient,
    doctor_user,
    doctor_profile,
    patient_user,
    admin_user,
    db: AsyncSession,
):
    # NOTE: the authed-client fixtures share one client object, so this test
    # uses per-request auth headers on the bare client instead.
    doctor_headers = make_auth_header(doctor_user)
    await grant_doctor_patient_relationship(db, "doctor-123", patient_user.id)
    res = await client.post(
        "/api/v1/doctors/prescriptions",
        json=_rx_payload(patient_user.id),
        headers=doctor_headers,
    )
    assert res.status_code == 201, res.text
    rx_id = res.json()["id"]

    # Authoring doctor can read the check.
    res = await client.get(
        f"/api/v1/prescriptions/{rx_id}/safety-check", headers=doctor_headers
    )
    assert res.status_code == 200, res.text

    # Patient can read their own prescription's check.
    res = await client.get(
        f"/api/v1/prescriptions/{rx_id}/safety-check",
        headers=make_auth_header(patient_user),
    )
    assert res.status_code == 200, res.text
    assert res.json()["prescription_id"] == rx_id

    # Admin can read any prescription's check.
    res = await client.get(
        f"/api/v1/prescriptions/{rx_id}/safety-check",
        headers=make_auth_header(admin_user),
    )
    assert res.status_code == 200, res.text

    # Another verified doctor (not the author, no shared clinic) -> 403.
    other_user = User(
        keycloak_sub="doctor-999", email="d2@test.com", full_name="Dr Two", role="doctor"
    )
    db.add(other_user)
    await db.flush()
    db.add(
        Doctor(
            id=uuid.uuid4(),
            user_id=other_user.id,
            verified=True,
            onboarding_step="completed",
        )
    )
    await db.commit()
    other_token = create_test_token(
        sub="doctor-999", email="d2@test.com", name="Dr Two", roles=["doctor"]
    )
    res = await client.get(
        f"/api/v1/prescriptions/{rx_id}/safety-check", headers=_auth(other_token)
    )
    assert res.status_code == 403

    # Another patient -> 403.
    other_patient = User(
        keycloak_sub="patient-999",
        email="p2@test.com",
        full_name="Patient Two",
        role="patient",
    )
    db.add(other_patient)
    await db.commit()
    other_patient_token = create_test_token(
        sub="patient-999", email="p2@test.com", name="Patient Two", roles=["patient"]
    )
    res = await client.get(
        f"/api/v1/prescriptions/{rx_id}/safety-check", headers=_auth(other_patient_token)
    )
    assert res.status_code == 403

    # Unknown prescription -> 404.
    res = await client.get(
        f"/api/v1/prescriptions/{uuid.uuid4()}/safety-check", headers=doctor_headers
    )
    assert res.status_code == 404

    # Unauthenticated -> 401.
    res = await client.get(f"/api/v1/prescriptions/{rx_id}/safety-check")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_clinic_member_can_view_check(
    doctor_client: AsyncClient,
    doctor_profile,
    doctor_user,
    patient_user,
    client: AsyncClient,
    db: AsyncSession,
):
    """A non-authoring doctor with an active membership in the rx's clinic
    can read the safety check."""
    clinic = Clinic(id=uuid.uuid4(), name="Shared Clinic", created_by=doctor_user.id)
    db.add(clinic)
    await db.flush()
    db.add(
        ClinicMembership(
            id=uuid.uuid4(), clinic_id=clinic.id, user_id=doctor_user.id,
            role="owner", is_active=True,
        )
    )
    # Second doctor — member of the same clinic, not the author.
    member_user = User(
        keycloak_sub="doctor-888", email="d3@test.com", full_name="Dr Three", role="doctor"
    )
    db.add(member_user)
    await db.flush()
    member_doctor = Doctor(
        id=uuid.uuid4(),
        user_id=member_user.id,
        verified=True,
        onboarding_step="completed",
    )
    db.add(member_doctor)
    db.add(
        ClinicMembership(
            id=uuid.uuid4(), clinic_id=clinic.id, user_id=member_user.id,
            role="doctor", is_active=True,
        )
    )
    # Approved patient consent so the clinic-scoped create is allowed.
    db.add(
        PatientClinicLink(
            id=uuid.uuid4(),
            patient_id=patient_user.id,
            clinic_id=clinic.id,
            linked_by=doctor_user.id,
            consent_status="approved",
        )
    )
    await db.commit()

    created = await _create_rx(
        doctor_client, db, patient_user.id, headers={"X-Clinic-Id": str(clinic.id)}
    )
    assert created["clinic_id"] == str(clinic.id)

    member_token = create_test_token(
        sub="doctor-888", email="d3@test.com", name="Dr Three", roles=["doctor"]
    )
    res = await client.get(
        f"/api/v1/prescriptions/{created['id']}/safety-check",
        headers=_auth(member_token),
    )
    assert res.status_code == 200, res.text
    assert res.json()["prescription_id"] == created["id"]


@pytest.mark.asyncio
async def test_missing_check_row_returns_404(
    doctor_client: AsyncClient, doctor_profile, patient_user, db: AsyncSession
):
    """A prescription with no persisted snapshot (e.g. predates R13) -> 404."""
    record = MedicalRecord(
        patient_id=patient_user.id,
        doctor_id=doctor_profile.id,
        record_type="prescription",
        title="Legacy rx",
    )
    db.add(record)
    await db.flush()
    rx = Prescription(
        id=uuid.uuid4(),
        record_id=record.id,
        doctor_id=doctor_profile.id,
        patient_id=patient_user.id,
        medicines=[{"brand_name": "Legacy", "dose": "1", "frequency": "OD", "duration": "1d"}],
    )
    db.add(rx)
    await db.commit()

    res = await doctor_client.get(f"/api/v1/prescriptions/{rx.id}/safety-check")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "NOT_FOUND"
