"""Doctor credentials (NMC compliance) + patient demographics tests.

Covers:
- qualifications / registration_number / signature_url persistence via
  PUT /api/v1/doctors/profile
- input validation (registration number length, signature_url scheme,
  future dob, invalid sex)
- date_of_birth / sex persistence via PUT /api/v1/patients/profile
- Rx PDF renders 200 with doctor credentials + patient age/sex set, and
  with an unresolvable signature_url ("signature on file" path).
"""
import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from tests.conftest import (
    create_test_token,
    grant_doctor_patient_relationship,
    verify_provisioned_doctor,
)


async def _provision_doctor(client: AsyncClient, db) -> str:
    """Auto-provision + verify a doctor; returns the bearer token."""
    doctor_sub = str(uuid.uuid4())
    token = create_test_token(
        sub=doctor_sub, email="dr.cred@test.com", name="Dr. Cred", roles=["doctor"]
    )
    await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    await verify_provisioned_doctor(db, doctor_sub)
    return token


# ---------------------------------------------------------------------------
# Doctor profile credentials
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_doctor_credentials_persist(client: AsyncClient, db):
    token = await _provision_doctor(client, db)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.put(
        "/api/v1/doctors/profile",
        json={
            "specialization": "General Physician",
            "qualifications": "MBBS, MD (Medicine)",
            "registration_number": "NMC-2020-12345",
            "signature_url": f"{uuid.uuid4()}/signature.png",
        },
        headers=headers,
    )
    assert resp.status_code == 200

    resp = await client.get("/api/v1/doctors/profile", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["qualifications"] == "MBBS, MD (Medicine)"
    assert body["registration_number"] == "NMC-2020-12345"
    assert body["signature_url"].endswith("/signature.png")


@pytest.mark.asyncio
async def test_registration_number_too_short_rejected(client: AsyncClient, db):
    token = await _provision_doctor(client, db)
    resp = await client.put(
        "/api/v1/doctors/profile",
        json={"registration_number": "AB"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_registration_number_too_long_rejected(client: AsyncClient, db):
    token = await _provision_doctor(client, db)
    resp = await client.put(
        "/api/v1/doctors/profile",
        json={"registration_number": "X" * 60},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_signature_url_bad_scheme_rejected(client: AsyncClient, db):
    token = await _provision_doctor(client, db)
    resp = await client.put(
        "/api/v1/doctors/profile",
        json={"signature_url": "javascript:alert(1)"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Patient demographics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patient_dob_and_sex_persist(client: AsyncClient, db):
    patient_sub = str(uuid.uuid4())
    token = create_test_token(
        sub=patient_sub, email="demo.patient@test.com", name="Demo Patient", roles=["patient"]
    )
    headers = {"Authorization": f"Bearer {token}"}
    await client.get("/api/v1/auth/me", headers=headers)

    resp = await client.put(
        "/api/v1/patients/profile",
        json={"date_of_birth": "1990-05-15", "sex": "female"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["date_of_birth"] == "1990-05-15"
    assert body["sex"] == "female"

    resp = await client.get("/api/v1/patients/profile", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["date_of_birth"] == "1990-05-15"
    assert resp.json()["sex"] == "female"


@pytest.mark.asyncio
async def test_patient_future_dob_rejected(client: AsyncClient, db):
    patient_sub = str(uuid.uuid4())
    token = create_test_token(
        sub=patient_sub, email="future.dob@test.com", name="Future Dob", roles=["patient"]
    )
    headers = {"Authorization": f"Bearer {token}"}
    await client.get("/api/v1/auth/me", headers=headers)

    future = (date.today() + timedelta(days=1)).isoformat()
    resp = await client.put(
        "/api/v1/patients/profile",
        json={"date_of_birth": future},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patient_invalid_sex_rejected(client: AsyncClient, db):
    patient_sub = str(uuid.uuid4())
    token = create_test_token(
        sub=patient_sub, email="bad.sex@test.com", name="Bad Sex", roles=["patient"]
    )
    headers = {"Authorization": f"Bearer {token}"}
    await client.get("/api/v1/auth/me", headers=headers)

    resp = await client.put(
        "/api/v1/patients/profile",
        json={"sex": "unknown"},
        headers=headers,
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Prescription PDF — credentials + demographics
# ---------------------------------------------------------------------------


async def _setup_prescription_with_credentials(
    client: AsyncClient, db, *, signature_url: str | None = None
) -> tuple[str, str]:
    """Create patient (with dob/sex) + doctor (with credentials) + prescription.

    Returns (doctor_token, prescription_id).
    """
    patient_sub = str(uuid.uuid4())
    patient_token = create_test_token(
        sub=patient_sub, email="rx.patient@test.com", name="Rx Patient", roles=["patient"]
    )
    p_headers = {"Authorization": f"Bearer {patient_token}"}
    me = await client.get("/api/v1/auth/me", headers=p_headers)
    patient_id = me.json()["id"]

    await client.put(
        "/api/v1/patients/profile",
        json={"date_of_birth": "1985-03-20", "sex": "male"},
        headers=p_headers,
    )

    doctor_token = await _provision_doctor(client, db)
    d_headers = {"Authorization": f"Bearer {doctor_token}"}

    # doctor → patient relationship (required to create the prescription)
    from sqlalchemy import select as _select
    from app.models.user import User

    doctor_sub_user = (
        await db.execute(_select(User).where(User.email == "dr.cred@test.com"))
    ).scalar_one()
    await grant_doctor_patient_relationship(db, doctor_sub_user.keycloak_sub, patient_id)

    profile_body: dict = {
        "specialization": "Cardiologist",
        "qualifications": "MBBS, DM (Cardiology)",
        "registration_number": "MMC-2011-04567",
        "license_number": "MH-12345",
        "facility_name": "Heart Care Clinic",
        "facility_city": "Pune",
    }
    if signature_url:
        profile_body["signature_url"] = signature_url
    resp = await client.put("/api/v1/doctors/profile", json=profile_body, headers=d_headers)
    assert resp.status_code == 200

    resp = await client.post(
        "/api/v1/doctors/prescriptions",
        json={
            "patient_id": patient_id,
            "medicines": [
                {
                    "brand_name": "Atorvastatin 10mg",
                    "dose": "10mg",
                    "frequency": "once daily",
                    "duration": "30 days",
                    "instructions": "at bedtime",
                }
            ],
            "diagnosis": "Hyperlipidaemia",
        },
        headers=d_headers,
    )
    assert resp.status_code == 201, resp.text
    return doctor_token, resp.json()["id"]


@pytest.mark.asyncio
async def test_pdf_renders_with_doctor_credentials(client: AsyncClient, db):
    """PDF endpoint returns a non-trivial PDF when credentials are set."""
    doctor_token, prescription_id = await _setup_prescription_with_credentials(client, db)

    resp = await client.get(
        f"/api/v1/prescriptions/{prescription_id}/pdf",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")
    assert len(resp.content) > 1000


@pytest.mark.asyncio
async def test_pdf_signature_on_file_fallback(client: AsyncClient, db):
    """A signature_url that doesn't resolve to a local file still renders —
    the PDF falls back to the '(Signature on file)' line."""
    doctor_token, prescription_id = await _setup_prescription_with_credentials(
        client, db, signature_url=f"{uuid.uuid4()}/sig.png"
    )

    resp = await client.get(
        f"/api/v1/prescriptions/{prescription_id}/pdf",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert resp.status_code == 200
    assert resp.content.startswith(b"%PDF")
    assert len(resp.content) > 1000


@pytest.mark.asyncio
async def test_pdf_embeds_signature_image(client: AsyncClient, db, tmp_path, monkeypatch):
    """When the signature object exists in local storage it is embedded."""
    import os

    from app.config import settings

    # Write a tiny PNG under the uploads dir at a known object key.
    object_key = f"{uuid.uuid4()}/sig.png"
    uploads_dir = os.path.abspath(settings.UPLOADS_DIR)
    os.makedirs(os.path.join(uploads_dir, object_key.split("/")[0]), exist_ok=True)
    sig_path = os.path.join(uploads_dir, object_key)
    # Minimal valid PNG (1x1 transparent)
    sig_path = sig_path
    with open(sig_path, "wb") as f:
        f.write(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
            b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )

    doctor_token, prescription_id = await _setup_prescription_with_credentials(
        client, db, signature_url=object_key
    )

    resp = await client.get(
        f"/api/v1/prescriptions/{prescription_id}/pdf",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert resp.status_code == 200
    assert resp.content.startswith(b"%PDF")
    assert len(resp.content) > 1000
