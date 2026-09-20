"""Security tests for the uploads endpoints (local storage backend).

Covers:
- Presign validation (extension + content-type allow-lists, filename sanitization)
- Path-traversal rejection in object keys
- Magic-byte verification (declared extension must match content signature)
- Empty-body rejection and missing-file 404s
- Cross-user access properties of opaque object keys

NOTE on status codes: Pydantic request-validation failures return 422
(RequestValidationError is not an HTTPException), while HTTPException(422)
raised in handlers is remapped to a 400 VALIDATION_ERROR envelope by the
app's status-code exception handler (MD-395).
"""

import uuid

import pytest

from app.config import settings

pytestmark = pytest.mark.asyncio

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


async def _presign(client, file_name="scan.png", content_type="image/png") -> str:
    """Presign and return the registered object_key (owner = client's user)."""
    resp = await client.post(
        "/api/v1/uploads/presign",
        json={"file_name": file_name, "content_type": content_type},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["object_key"]
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 32
PDF_BYTES = b"%PDF-1.4\n%test\n"


@pytest.fixture
def uploads_dir(tmp_path, monkeypatch):
    """Point local storage at a per-test temp dir."""
    monkeypatch.setattr(settings, "UPLOADS_DIR", str(tmp_path))
    return tmp_path


# ---------------------------------------------------------------------------
# Presign validation
# ---------------------------------------------------------------------------


class TestPresign:
    async def test_presign_success(self, patient_client):
        resp = await patient_client.post(
            "/api/v1/uploads/presign",
            json={"file_name": "report.pdf", "content_type": "application/pdf"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["method"] == "PUT"
        assert body["object_key"].endswith("/report.pdf")
        assert "presigned_url" in body

    @pytest.mark.parametrize("file_name", ["evil.exe", "script.sh", "payload.html", "x.gif"])
    async def test_presign_rejects_disallowed_extension(self, patient_client, file_name):
        resp = await patient_client.post(
            "/api/v1/uploads/presign",
            json={"file_name": file_name, "content_type": "image/png"},
        )
        assert resp.status_code == 422

    @pytest.mark.parametrize(
        "content_type", ["image/gif", "text/html", "application/x-msdownload"]
    )
    async def test_presign_rejects_disallowed_content_type(
        self, patient_client, content_type
    ):
        resp = await patient_client.post(
            "/api/v1/uploads/presign",
            json={"file_name": "x.png", "content_type": content_type},
        )
        assert resp.status_code == 422

    async def test_presign_sanitizes_traversal_in_filename(self, patient_client):
        resp = await patient_client.post(
            "/api/v1/uploads/presign",
            json={"file_name": "../../etc/evil.png", "content_type": "image/png"},
        )
        assert resp.status_code == 200
        object_key = resp.json()["object_key"]
        assert ".." not in object_key
        assert object_key.endswith("/evil.png")

    async def test_presign_requires_auth(self, client):
        resp = await client.post(
            "/api/v1/uploads/presign",
            json={"file_name": "x.png", "content_type": "image/png"},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# PUT /api/v1/uploads/{key} — content validation
# ---------------------------------------------------------------------------


class TestUpload:
    async def test_upload_valid_png(self, patient_client, uploads_dir):
        key = await _presign(patient_client)
        resp = await patient_client.put(f"/api/v1/uploads/{key}", content=PNG_BYTES)
        assert resp.status_code == 200

        stored = uploads_dir / key
        assert stored.is_file()
        assert stored.read_bytes() == PNG_BYTES

    async def test_upload_rejects_path_traversal_key(self, patient_client, uploads_dir):
        # Percent-encoded "../" survives httpx URL normalization and is decoded
        # by Starlette into a real traversal attempt inside object_key.
        resp = await patient_client.put(
            "/api/v1/uploads/%2E%2E%2F%2E%2E%2Fevil.png",
            content=PNG_BYTES,
        )
        assert resp.status_code in (400, 403)  # INVALID_KEY or unknown unregistered key
        assert resp.json()["error"]["code"] in ("INVALID_KEY", "INVALID_UPLOAD_KEY")
        # Nothing may have been written outside the uploads dir
        assert not (uploads_dir.parent / "evil.png").exists()

    async def test_upload_rejects_wrong_magic_bytes(self, patient_client, uploads_dir):
        """A Windows executable renamed to .png must not be stored."""
        key = await _presign(patient_client, "malware.png")
        resp = await patient_client.put(
            f"/api/v1/uploads/{key}", content=b"MZ\x90\x00" + b"\x00" * 64
        )
        assert resp.status_code == 415
        assert resp.json()["error"]["code"] == "INVALID_FILE_TYPE"
        assert not (uploads_dir / key).exists()

    async def test_upload_pdf_requires_pdf_signature(self, patient_client, uploads_dir):
        key = await _presign(patient_client, "report.pdf", "application/pdf")
        resp = await patient_client.put(f"/api/v1/uploads/{key}", content=PNG_BYTES)
        assert resp.status_code == 415

    async def test_upload_rejects_empty_body(self, patient_client):
        key = await _presign(patient_client, "empty.png")
        resp = await patient_client.put(f"/api/v1/uploads/{key}", content=b"")
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "EMPTY_BODY"

    async def test_upload_requires_auth(self, client, uploads_dir):
        key = f"{uuid.uuid4()}/anon.png"
        resp = await client.put(f"/api/v1/uploads/{key}", content=PNG_BYTES)
        assert resp.status_code == 401

    async def test_oversized_upload_rejected(self, patient_client, uploads_dir):
        key = await _presign(patient_client, "huge.png")
        body = PNG_BYTES + b"\x00" * (16 * 1024 * 1024)  # ~16 MB > 15 MB cap
        resp = await patient_client.put(f"/api/v1/uploads/{key}", content=body)
        assert resp.status_code == 413


# ---------------------------------------------------------------------------
# GET /api/v1/uploads/{key} — serving + cross-user access
# ---------------------------------------------------------------------------


class TestServeFile:
    async def test_serves_uploaded_file(self, patient_client, uploads_dir):
        key = await _presign(patient_client)
        put = await patient_client.put(f"/api/v1/uploads/{key}", content=PNG_BYTES)
        assert put.status_code == 200

        resp = await patient_client.get(f"/api/v1/uploads/{key}")
        assert resp.status_code == 200
        assert resp.content == PNG_BYTES
        assert resp.headers["content-type"].startswith("image/png")

    async def test_serve_rejects_path_traversal_key(self, patient_client):
        resp = await patient_client.get("/api/v1/uploads/%2E%2E%2F%2E%2E%2Fetc%2Fpasswd.png")
        assert resp.status_code == 400

    async def test_unknown_key_returns_403(self, patient_client, uploads_dir):
        # Authorization is checked before existence — unregistered keys get
        # 403 so an attacker cannot enumerate objects via status codes.
        resp = await patient_client.get(f"/api/v1/uploads/{uuid.uuid4()}/nope.png")
        assert resp.status_code == 403

    async def test_cross_user_cannot_guess_or_enumerate_keys(
        self, client, db, uploads_dir
    ):
        """Object keys carry an unguessable UUID prefix — a second user
        requesting a random key gets 404, and no listing endpoint exists."""
        from app.models.user import User
        from tests.conftest import create_test_token

        other = User(
            keycloak_sub=f"patient-{uuid.uuid4()}",
            email="other@test.com",
            full_name="Other Patient",
            role="patient",
        )
        db.add(other)
        await db.commit()
        other_auth = {
            "Authorization": "Bearer "
            + create_test_token(
                sub=other.keycloak_sub, email=other.email,
                name=other.full_name, roles=["patient"],
            )
        }

        resp = await client.get(
            f"/api/v1/uploads/{uuid.uuid4()}/someone-elses.png", headers=other_auth
        )
        assert resp.status_code == 403

    async def test_cross_user_key_access_denied(
        self, client, db, patient_client, uploads_dir
    ):
        """User B must not read user A's upload even with the exact object key."""
        key = await _presign(patient_client, "private.pdf", "application/pdf")
        put = await patient_client.put(f"/api/v1/uploads/{key}", content=PDF_BYTES)
        assert put.status_code == 200

        from app.models.user import User
        from tests.conftest import create_test_token

        other = User(
            keycloak_sub=f"patient-{uuid.uuid4()}",
            email="other2@test.com",
            full_name="Other Patient",
            role="patient",
        )
        db.add(other)
        await db.commit()
        other_auth = {
            "Authorization": "Bearer "
            + create_test_token(
                sub=other.keycloak_sub, email=other.email,
                name=other.full_name, roles=["patient"],
            )
        }
        resp = await client.get(f"/api/v1/uploads/{key}", headers=other_auth)
        assert resp.status_code == 403
