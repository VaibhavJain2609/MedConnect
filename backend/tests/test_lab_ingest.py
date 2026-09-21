"""Tests for POST /api/v1/lab-results/ingest — lab-report OCR scaffold.

Covers:
- Authz gates: unauthenticated → 401, patient → 403, unverified doctor → 403.
- Upload-key binding: unregistered key → 403 INVALID_UPLOAD_KEY, a key
  presigned by another user → 403, non-image keys → 415.
- Provider gating: OCR_PROVIDER=none → 503 OCR_NOT_CONFIGURED; the "llm"
  stub → 503 OCR_UNAVAILABLE; a fake configured provider → candidates shape.
- Patient-link check: patient_id without a doctor–patient relationship → 403.
- No LabResult rows are ever written (human-in-the-loop).
"""

import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import app.models.reminder_log  # noqa: F401 — register for drop_all teardown
from app.config import settings
from app.models.doctor import Doctor
from app.models.lab_result import LabResult
from app.models.user import User
from app.services.providers.ocr import LabValueCandidate
from tests.conftest import create_test_token, make_auth_header

pytestmark = pytest.mark.asyncio

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.fixture
def uploads_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOADS_DIR", str(tmp_path))
    return tmp_path


class _FakeProvider:
    """Stand-in for a configured OCR backend — returns fixed candidates."""

    name = "fake"

    async def extract_lab_values(self, *, image_bytes=None, storage_key=None, content_type=None):
        assert image_bytes == PNG_BYTES or storage_key is not None
        return [
            LabValueCandidate(
                name="Hemoglobin", value="13.2", unit="g/dL",
                ref_low="12.0", ref_high="16.0", flag="normal",
            ),
            LabValueCandidate(
                name="Fasting Glucose", value="142", unit="mg/dL",
                ref_low="70", ref_high="100", flag="high",
            ),
        ]


def _use_fake_provider(monkeypatch):
    import app.routers.lab_results as lr

    monkeypatch.setattr(lr, "get_ocr_provider", lambda: _FakeProvider())


async def _upload_image(client, file_name="labs.png") -> str:
    """Presign + PUT a PNG as the client's user; return the object key."""
    presign = await client.post(
        "/api/v1/uploads/presign",
        json={"file_name": file_name, "content_type": "image/png"},
    )
    assert presign.status_code == 200, presign.text
    key = presign.json()["object_key"]
    put = await client.put(f"/api/v1/uploads/{key}", content=PNG_BYTES)
    assert put.status_code == 200, put.text
    return key


# ---------------------------------------------------------------------------
# Authz gates
# ---------------------------------------------------------------------------


class TestAuthz:
    async def test_unauthenticated_401(self, client):
        resp = await client.post(
            "/api/v1/lab-results/ingest", json={"upload_key": "x/y.png"}
        )
        assert resp.status_code == 401

    async def test_patient_forbidden_403(self, patient_client):
        resp = await patient_client.post(
            "/api/v1/lab-results/ingest", json={"upload_key": "x/y.png"}
        )
        assert resp.status_code == 403

    async def test_unverified_doctor_forbidden_403(self, client, db):
        """A doctor who isn't verified/onboarded can't ingest."""
        user = User(
            keycloak_sub=f"doc-{uuid.uuid4()}",
            email="newdoc@test.com",
            full_name="New Doc",
            role="doctor",
        )
        db.add(user)
        await db.flush()
        db.add(
            Doctor(id=uuid.uuid4(), user_id=user.id, verified=False,
                   onboarding_step="pending")
        )
        await db.commit()
        resp = await client.post(
            "/api/v1/lab-results/ingest",
            json={"upload_key": "x/y.png"},
            headers=make_auth_header(user, roles=["doctor"]),
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "ONBOARDING_INCOMPLETE"


# ---------------------------------------------------------------------------
# Upload-key validation
# ---------------------------------------------------------------------------


class TestUploadKey:
    async def test_unregistered_key_403(self, doctor_client, uploads_dir):
        resp = await doctor_client.post(
            "/api/v1/lab-results/ingest",
            json={"upload_key": f"{uuid.uuid4()}/labs.png"},
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "INVALID_UPLOAD_KEY"

    async def test_key_owned_by_other_user_403(
        self, client, db, doctor_client, patient_user, uploads_dir
    ):
        """A key presigned by the patient can't be ingested by the doctor."""
        patient_auth = make_auth_header(patient_user)
        presign = await client.post(
            "/api/v1/uploads/presign",
            json={"file_name": "labs.png", "content_type": "image/png"},
            headers=patient_auth,
        )
        key = presign.json()["object_key"]
        resp = await doctor_client.post(
            "/api/v1/lab-results/ingest", json={"upload_key": key}
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "INVALID_UPLOAD_KEY"

    async def test_non_image_key_415(self, doctor_client, uploads_dir):
        presign = await doctor_client.post(
            "/api/v1/uploads/presign",
            json={"file_name": "labs.pdf", "content_type": "application/pdf"},
        )
        key = presign.json()["object_key"]
        resp = await doctor_client.post(
            "/api/v1/lab-results/ingest", json={"upload_key": key}
        )
        assert resp.status_code == 415
        assert resp.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"


# ---------------------------------------------------------------------------
# Provider gating
# ---------------------------------------------------------------------------


class TestProviderGating:
    async def test_null_provider_503_not_configured(
        self, doctor_client, uploads_dir
    ):
        """OCR_PROVIDER=none (default) → 503 OCR_NOT_CONFIGURED."""
        key = await _upload_image(doctor_client)
        resp = await doctor_client.post(
            "/api/v1/lab-results/ingest", json={"upload_key": key}
        )
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "OCR_NOT_CONFIGURED"

    async def test_llm_stub_503_unavailable(
        self, doctor_client, uploads_dir, monkeypatch
    ):
        """OCR_PROVIDER=llm selects the stub, which raises OcrUnavailable
        cleanly (no real backend wired in)."""
        monkeypatch.setattr(settings, "OCR_PROVIDER", "llm")
        key = await _upload_image(doctor_client)
        resp = await doctor_client.post(
            "/api/v1/lab-results/ingest", json={"upload_key": key}
        )
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "OCR_UNAVAILABLE"

    async def test_llm_stub_missing_config_unavailable(
        self, doctor_client, uploads_dir, monkeypatch
    ):
        monkeypatch.setattr(settings, "OCR_PROVIDER", "llm")
        monkeypatch.setattr(settings, "OCR_LLM_BASE_URL", None)
        key = await _upload_image(doctor_client)
        resp = await doctor_client.post(
            "/api/v1/lab-results/ingest", json={"upload_key": key}
        )
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "OCR_UNAVAILABLE"

    async def test_presigned_but_not_uploaded_404(
        self, doctor_client, uploads_dir, monkeypatch
    ):
        _use_fake_provider(monkeypatch)
        presign = await doctor_client.post(
            "/api/v1/uploads/presign",
            json={"file_name": "labs.png", "content_type": "image/png"},
        )
        key = presign.json()["object_key"]
        resp = await doctor_client.post(
            "/api/v1/lab-results/ingest", json={"upload_key": key}
        )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "UPLOAD_NOT_FOUND"


# ---------------------------------------------------------------------------
# Extraction — response shape + human-in-the-loop
# ---------------------------------------------------------------------------


class TestExtraction:
    async def test_candidates_response_shape(
        self, doctor_client, uploads_dir, monkeypatch
    ):
        _use_fake_provider(monkeypatch)
        key = await _upload_image(doctor_client)
        resp = await doctor_client.post(
            "/api/v1/lab-results/ingest", json={"upload_key": key}
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["upload_key"] == key
        assert body["provider"] == "fake"
        assert len(body["candidates"]) == 2
        for cand in body["candidates"]:
            assert set(cand) >= {
                "name", "value", "unit", "ref_low", "ref_high", "flag"
            }
        hb = body["candidates"][0]
        assert hb["name"] == "Hemoglobin"
        assert hb["value"] == "13.2"
        assert hb["unit"] == "g/dL"
        assert hb["ref_low"] == "12.0"
        assert hb["ref_high"] == "16.0"
        assert hb["flag"] == "normal"

    async def test_ingest_writes_no_lab_result_rows(
        self, doctor_client, db, uploads_dir, monkeypatch
    ):
        _use_fake_provider(monkeypatch)
        key = await _upload_image(doctor_client)
        resp = await doctor_client.post(
            "/api/v1/lab-results/ingest", json={"upload_key": key}
        )
        assert resp.status_code == 200
        count = await db.scalar(
            select(func.count()).select_from(LabResult)
        )
        assert count == 0


# ---------------------------------------------------------------------------
# Optional patient_id scoping
# ---------------------------------------------------------------------------


class TestPatientScope:
    async def test_unrelated_patient_403(
        self, doctor_client, patient_user, uploads_dir, monkeypatch
    ):
        _use_fake_provider(monkeypatch)
        key = await _upload_image(doctor_client)
        resp = await doctor_client.post(
            "/api/v1/lab-results/ingest",
            json={"upload_key": key, "patient_id": str(patient_user.id)},
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"

    async def test_related_patient_ok(
        self, client, db, doctor_user, doctor_profile, patient_user,
        uploads_dir, monkeypatch,
    ):
        """A doctor who authored a record for the patient passes the link
        check and reaches extraction."""
        _use_fake_provider(monkeypatch)
        doctor_auth = make_auth_header(doctor_user, roles=["doctor"])
        presign = await client.post(
            "/api/v1/uploads/presign",
            json={"file_name": "labs.png", "content_type": "image/png"},
            headers=doctor_auth,
        )
        key = presign.json()["object_key"]
        await client.put(
            f"/api/v1/uploads/{key}", content=PNG_BYTES, headers=doctor_auth
        )

        from app.models.medical_record import MedicalRecord

        db.add(
            MedicalRecord(
                patient_id=patient_user.id,
                doctor_id=doctor_profile.id,
                record_type="lab_report",
                title="Prior labs",
            )
        )
        await db.commit()

        resp = await client.post(
            "/api/v1/lab-results/ingest",
            json={"upload_key": key, "patient_id": str(patient_user.id)},
            headers=doctor_auth,
        )
        assert resp.status_code == 200, resp.text
        assert len(resp.json()["candidates"]) == 2
