"""Round-8 coverage: /api/v1/uploads — presign → PUT → GET lifecycle.

Complements test_uploads_security.py (which covers traversal/magic-byte
attacks). This file targets:

- Happy path: presign registers an owner-bound key (r2 owner-binding model),
  PUT stores bytes, GET serves them back with the right content type.
- Owner binding: a key presigned for user A cannot be PUT by user B;
  unregistered keys are rejected on PUT (403 INVALID_UPLOAD_KEY).
- GET authorization-before-existence semantics: unknown keys → 403 for
  regular users (no existence leak), 404 only once the caller is authorized
  but the object is absent; admin bypasses authorization → honest 404.
- Size cap: max_upload_mb platform setting is the effective cap
  (min(setting, 15 MB hard ceiling)), enforced via Content-Length pre-check
  AND a hard cap while streaming a body with no declared length.
- Allowlists: content_type + extension are validated independently at
  presign; magic bytes are re-checked against the *extension-inferred* type
  at PUT time.

NOTE: pydantic presign-validation failures return 422 with FastAPI's default
{"detail": ...} body (not the {"error": ...} envelope).
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Register ReminderLog in Base.metadata so teardown drop_all can clear a
# stale migration-created reminder_logs table (FK to appointments) on the
# shared test DB — see test_encounters.py for the same workaround.
import app.models.reminder_log  # noqa: F401
from app.config import settings
from app.models.audit import AuditLog
from app.models.clinic import Clinic, ClinicMembership
from app.models.doctor import Doctor
from app.models.medical_record import MedicalRecord
from app.models.patient_link import PatientClinicLink
from app.models.platform_setting import PlatformSetting
from app.models.user import User
from tests.conftest import make_auth_header

pytestmark = pytest.mark.asyncio

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
PDF_BYTES = b"%PDF-1.4\n%test\n"


@pytest.fixture
def uploads_dir(tmp_path, monkeypatch):
    """Point local storage at a per-test temp dir."""
    monkeypatch.setattr(settings, "UPLOADS_DIR", str(tmp_path))
    return tmp_path


async def _presign(client, file_name="scan.png", content_type="image/png") -> str:
    """Presign and return the registered object_key (owner = client's user)."""
    resp = await client.post(
        "/api/v1/uploads/presign",
        json={"file_name": file_name, "content_type": content_type},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["object_key"]


async def _presign_with(
    client, headers: dict, file_name: str, content_type: str
) -> str:
    """Presign on the shared client with explicit auth headers."""
    resp = await client.post(
        "/api/v1/uploads/presign",
        json={"file_name": file_name, "content_type": content_type},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["object_key"]


async def _make_patient(db: AsyncSession, email: str) -> tuple[User, dict]:
    user = User(
        keycloak_sub=f"patient-{uuid.uuid4()}",
        email=email,
        full_name="Second Patient",
        role="patient",
    )
    db.add(user)
    await db.commit()
    return user, make_auth_header(user)


async def _set_max_upload_mb(db: AsyncSession, value) -> None:
    db.add(PlatformSetting(id=uuid.uuid4(), key="max_upload_mb", value=value))
    await db.commit()


async def _body_chunks(data: bytes, chunk_size: int = 65536):
    """Async body iterator — httpx sends this chunked, WITHOUT a
    Content-Length header, exercising the streaming hard cap."""
    for i in range(0, len(data), chunk_size):
        yield data[i:i + chunk_size]


# ---------------------------------------------------------------------------
# POST /presign — contract + allowlists
# ---------------------------------------------------------------------------


class TestPresignContract:
    async def test_presign_response_shape(self, patient_client):
        resp = await patient_client.post(
            "/api/v1/uploads/presign",
            json={"file_name": "scan.png", "content_type": "image/png"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["method"] == "PUT"
        assert body["expires_in"] == 900
        # object_key = "{uuid}/{sanitized filename}"
        prefix, _, name = body["object_key"].rpartition("/")
        uuid.UUID(prefix)  # raises if not a uuid
        assert name == "scan.png"
        assert body["presigned_url"].endswith(f"/api/v1/uploads/{body['object_key']}")

    @pytest.mark.parametrize(
        "file_name,content_type",
        [
            ("x.jpg", "image/jpeg"),
            ("x.jpeg", "image/jpeg"),
            ("x.png", "image/png"),
            ("x.pdf", "application/pdf"),
            ("SCAN.PNG", "image/png"),  # extension check lowercases
        ],
    )
    async def test_presign_allowlist_accepts(
        self, patient_client, file_name, content_type
    ):
        resp = await patient_client.post(
            "/api/v1/uploads/presign",
            json={"file_name": file_name, "content_type": content_type},
        )
        assert resp.status_code == 200, resp.text

    @pytest.mark.parametrize("content_type", ["text/plain", "image/webp", "video/mp4"])
    async def test_presign_unsupported_content_type_422(
        self, patient_client, content_type
    ):
        resp = await patient_client.post(
            "/api/v1/uploads/presign",
            json={"file_name": "x.png", "content_type": content_type},
        )
        assert resp.status_code == 422

    @pytest.mark.parametrize("file_name", ["notes.txt", "archive.zip", "doc.docx"])
    async def test_presign_extension_not_in_allowlist_422(
        self, patient_client, file_name
    ):
        resp = await patient_client.post(
            "/api/v1/uploads/presign",
            json={"file_name": file_name, "content_type": "image/png"},
        )
        assert resp.status_code == 422

    async def test_presign_validates_filename_and_type_independently(
        self, patient_client, uploads_dir
    ):
        """A .pdf name + image/png type presigns fine (validators don't
        cross-check), but the PUT is gated by magic bytes inferred from the
        key's extension — PNG bytes under a .pdf key are rejected."""
        key = await _presign(patient_client, "report.pdf", "image/png")
        resp = await patient_client.put(f"/api/v1/uploads/{key}", content=PNG_BYTES)
        assert resp.status_code == 415
        assert resp.json()["error"]["code"] == "INVALID_FILE_TYPE"
        assert not (uploads_dir / key).exists()


# ---------------------------------------------------------------------------
# Presign → PUT → GET happy path + owner binding (r2 model)
# ---------------------------------------------------------------------------


class TestOwnerBinding:
    async def test_happy_path_presign_put_get(self, patient_client, uploads_dir):
        key = await _presign(patient_client, "scan.png", "image/png")

        put = await patient_client.put(f"/api/v1/uploads/{key}", content=PNG_BYTES)
        assert put.status_code == 200, put.text
        assert put.json() == {"status": "ok", "object_key": key}
        assert (uploads_dir / key).read_bytes() == PNG_BYTES

        got = await patient_client.get(f"/api/v1/uploads/{key}")
        assert got.status_code == 200
        assert got.content == PNG_BYTES
        assert got.headers["content-type"].startswith("image/png")

    async def test_put_foreign_presigned_key_403(
        self, client, db, patient_client, uploads_dir
    ):
        """r2 owner-binding: a key issued to user A cannot be written by
        user B even with the exact object key."""
        key = await _presign(patient_client, "private.png")
        _, other_auth = await _make_patient(db, "b@test.com")
        resp = await client.put(
            f"/api/v1/uploads/{key}", content=PNG_BYTES, headers=other_auth
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "INVALID_UPLOAD_KEY"
        assert not (uploads_dir / key).exists()

    async def test_put_unregistered_key_403(self, patient_client, uploads_dir):
        key = f"{uuid.uuid4()}/never-presigned.png"
        resp = await patient_client.put(f"/api/v1/uploads/{key}", content=PNG_BYTES)
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "INVALID_UPLOAD_KEY"

    async def test_get_presigned_but_not_uploaded_404(
        self, patient_client, uploads_dir
    ):
        """The owner is authorized via the registry, so the honest
        'file not on disk' 404 is safe to return."""
        key = await _presign(patient_client, "pending.png")
        resp = await patient_client.get(f"/api/v1/uploads/{key}")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "NOT_FOUND"

    async def test_get_unregistered_key_403_for_non_admin(
        self, patient_client, uploads_dir
    ):
        """Unknown key → 403 (not 404): authorization is checked before
        existence so the response cannot be used to enumerate objects."""
        resp = await patient_client.get(f"/api/v1/uploads/{uuid.uuid4()}/x.png")
        assert resp.status_code == 403

    async def test_get_wrong_owner_403(
        self, client, db, patient_client, uploads_dir
    ):
        """User B cannot read a file user A uploaded, even with the key."""
        key = await _presign(patient_client, "a-file.pdf", "application/pdf")
        put = await patient_client.put(f"/api/v1/uploads/{key}", content=PDF_BYTES)
        assert put.status_code == 200

        _, other_auth = await _make_patient(db, "c@test.com")
        resp = await client.get(f"/api/v1/uploads/{key}", headers=other_auth)
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"

    async def test_second_put_conflict_409(self, patient_client, uploads_dir):
        """An issued key is single-use: existing objects are never
        overwritten."""
        key = await _presign(patient_client, "once.png")
        first = await patient_client.put(f"/api/v1/uploads/{key}", content=PNG_BYTES)
        assert first.status_code == 200
        second = await patient_client.put(f"/api/v1/uploads/{key}", content=PNG_BYTES)
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "ALREADY_EXISTS"

    async def test_successful_upload_writes_audit_row(
        self, patient_client, db, uploads_dir
    ):
        key = await _presign(patient_client, "audited.png")
        put = await patient_client.put(f"/api/v1/uploads/{key}", content=PNG_BYTES)
        assert put.status_code == 200
        logs = (
            await db.execute(
                select(AuditLog).where(
                    AuditLog.table_name == "uploads", AuditLog.action == "INSERT"
                )
            )
        ).scalars().all()
        assert len(logs) == 1
        assert logs[0].new_values["object_key"] == key
        assert logs[0].new_values["mime_type"] == "image/png"


# ---------------------------------------------------------------------------
# PUT size cap — max_upload_mb platform setting
# ---------------------------------------------------------------------------


class TestUploadSizeCap:
    async def test_platform_setting_caps_upload(
        self, patient_client, db, uploads_dir
    ):
        """max_upload_mb=1 → a ~1.1 MB body is rejected via the declared
        Content-Length pre-check (413 FILE_TOO_LARGE)."""
        await _set_max_upload_mb(db, 1)
        key = await _presign(patient_client, "big.png")
        body = PNG_BYTES + b"\x00" * (1024 * 1024)  # ~1.05 MB
        resp = await patient_client.put(f"/api/v1/uploads/{key}", content=body)
        assert resp.status_code == 413
        assert resp.json()["error"]["code"] == "FILE_TOO_LARGE"
        assert not (uploads_dir / key).exists()

    async def test_streaming_body_capped_without_content_length(
        self, patient_client, db, uploads_dir
    ):
        """Chunked upload with no Content-Length still hits the hard cap
        while streaming."""
        await _set_max_upload_mb(db, 1)
        key = await _presign(patient_client, "stream.png")
        body = PNG_BYTES + b"\x00" * (1024 * 1024)
        resp = await patient_client.put(
            f"/api/v1/uploads/{key}", content=_body_chunks(body)
        )
        assert resp.status_code == 413
        assert resp.json()["error"]["code"] == "FILE_TOO_LARGE"
        assert not (uploads_dir / key).exists()

    async def test_under_setting_cap_succeeds(
        self, patient_client, db, uploads_dir
    ):
        await _set_max_upload_mb(db, 1)
        key = await _presign(patient_client, "small.png")
        resp = await patient_client.put(f"/api/v1/uploads/{key}", content=PNG_BYTES)
        assert resp.status_code == 200

    async def test_hard_ceiling_applies_above_setting(
        self, patient_client, db, uploads_dir
    ):
        """max_upload_mb=50 cannot raise the cap past the 15 MB
        MAX_UPLOAD_BYTES ceiling."""
        await _set_max_upload_mb(db, 50)
        key = await _presign(patient_client, "huge.png")
        body = PNG_BYTES + b"\x00" * (16 * 1024 * 1024)  # ~16 MB
        resp = await patient_client.put(f"/api/v1/uploads/{key}", content=body)
        assert resp.status_code == 413
        assert resp.json()["error"]["code"] == "FILE_TOO_LARGE"

    async def test_default_cap_is_10mb_when_setting_absent(
        self, patient_client, uploads_dir
    ):
        """No platform_settings row → DEFAULT_VALUES['max_upload_mb']=10."""
        key = await _presign(patient_client, "eleven.png")
        body = PNG_BYTES + b"\x00" * (11 * 1024 * 1024)  # ~11 MB
        resp = await patient_client.put(f"/api/v1/uploads/{key}", content=body)
        assert resp.status_code == 413

    async def test_malformed_setting_falls_back_to_hard_cap(
        self, patient_client, db, uploads_dir
    ):
        """A non-numeric max_upload_mb falls back to MAX_UPLOAD_BYTES
        rather than crashing or disabling the cap."""
        await _set_max_upload_mb(db, "bogus")
        key = await _presign(patient_client, "fallback.png")
        body = PNG_BYTES + b"\x00" * (16 * 1024 * 1024)
        resp = await patient_client.put(f"/api/v1/uploads/{key}", content=body)
        assert resp.status_code == 413


# ---------------------------------------------------------------------------
# GET authorization via referencing MedicalRecord
# ---------------------------------------------------------------------------


class TestServeAuthorization:
    async def test_doctor_reads_file_via_patient_record(
        self, client, db, doctor_user, doctor_profile, patient_user,
        uploads_dir,
    ):
        """A file the patient uploaded becomes readable by a doctor once a
        MedicalRecord authored by that doctor references its object key."""
        # NOTE: *_client fixtures share one AsyncClient — use per-request
        # headers so each call really carries the intended identity.
        patient_auth = make_auth_header(patient_user)
        key = await _presign_with(client, patient_auth, "labs.pdf", "application/pdf")
        put = await client.put(
            f"/api/v1/uploads/{key}", content=PDF_BYTES, headers=patient_auth
        )
        assert put.status_code == 200

        db.add(
            MedicalRecord(
                id=uuid.uuid4(),
                patient_id=patient_user.id,
                doctor_id=doctor_profile.id,
                record_type="lab_report",
                title="Blood work",
                document_url=key,
            )
        )
        await db.commit()

        resp = await client.get(
            f"/api/v1/uploads/{key}",
            headers=make_auth_header(doctor_user, roles=["doctor"]),
        )
        assert resp.status_code == 200
        assert resp.content == PDF_BYTES
        assert resp.headers["content-type"].startswith("application/pdf")

    async def test_unrelated_doctor_gets_403(
        self, client, db, patient_client, patient_user, uploads_dir
    ):
        """A doctor with no relationship to the record's patient is denied."""
        key = await _presign(patient_client, "labs.pdf", "application/pdf")
        await patient_client.put(f"/api/v1/uploads/{key}", content=PDF_BYTES)

        stranger = User(
            keycloak_sub=f"doctor-{uuid.uuid4()}",
            email="stranger-doc@test.com",
            full_name="Stranger Doc",
            role="doctor",
        )
        db.add(stranger)
        await db.flush()
        db.add(
            Doctor(
                id=uuid.uuid4(), user_id=stranger.id,
                verified=True, onboarding_step="completed",
            )
        )
        await db.commit()

        resp = await client.get(
            f"/api/v1/uploads/{key}",
            headers=make_auth_header(stranger, roles=["doctor"]),
        )
        assert resp.status_code == 403

    async def test_admin_can_fetch_any_object(
        self, client, admin_user, patient_user, uploads_dir
    ):
        patient_auth = make_auth_header(patient_user)
        key = await _presign_with(client, patient_auth, "for-admin.png", "image/png")
        await client.put(
            f"/api/v1/uploads/{key}", content=PNG_BYTES, headers=patient_auth
        )
        resp = await client.get(
            f"/api/v1/uploads/{key}", headers=make_auth_header(admin_user)
        )
        assert resp.status_code == 200
        assert resp.content == PNG_BYTES

    async def test_admin_gets_honest_404_for_missing_object(
        self, admin_client, uploads_dir
    ):
        """Admin bypasses authorization, so a nonexistent key yields a real
        404 instead of the privacy-preserving 403 regular users get."""
        resp = await admin_client.get(f"/api/v1/uploads/{uuid.uuid4()}/none.png")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "NOT_FOUND"


# ---------------------------------------------------------------------------
# GET authorization — PHI access matrix (r15 regression tests)
# ---------------------------------------------------------------------------


async def _clinic_with_doctor(
    db: AsyncSession, doctor_user: User
) -> tuple[Clinic, ClinicMembership]:
    """A clinic where ``doctor_user`` holds an active membership."""
    clinic = Clinic(
        id=uuid.uuid4(),
        name="Authz Clinic",
        city="Mumbai",
        created_by=doctor_user.id,
    )
    db.add(clinic)
    await db.flush()
    membership = ClinicMembership(
        id=uuid.uuid4(),
        clinic_id=clinic.id,
        user_id=doctor_user.id,
        role="doctor",
        is_active=True,
    )
    db.add(membership)
    await db.commit()
    return clinic, membership


async def _patient_link(
    db: AsyncSession,
    clinic: Clinic,
    patient_id,
    linked_by,
    consent_status: str,
    revoked_at=None,
) -> PatientClinicLink:
    link = PatientClinicLink(
        id=uuid.uuid4(),
        patient_id=patient_id,
        clinic_id=clinic.id,
        linked_by=linked_by,
        consent_status=consent_status,
        consented_at=datetime.now(timezone.utc),
        revoked_at=revoked_at,
    )
    db.add(link)
    await db.commit()
    return link


class TestServeAccessMatrix:
    """Regression coverage for the download authorization matrix on
    GET /api/v1/uploads/{key}: unauthenticated 401, cross-patient 403,
    consented doctor 200, revoked-consent doctor 403/200 by revoked_at."""

    async def test_unauthenticated_get_401(self, client, patient_user, uploads_dir):
        """No Bearer token → 401 before any object lookup, even for a file
        that exists on disk."""
        # Per-request headers only: the shared client's default headers stay
        # unauthenticated (patient_client would set a default Authorization).
        patient_auth = make_auth_header(patient_user)
        key = await _presign_with(client, patient_auth, "phi.png", "image/png")
        put = await client.put(
            f"/api/v1/uploads/{key}", content=PNG_BYTES, headers=patient_auth
        )
        assert put.status_code == 200

        resp = await client.get(f"/api/v1/uploads/{key}")
        assert resp.status_code == 401

    async def test_patient_cannot_read_other_patients_record_file(
        self, client, db, patient_client, patient_user, uploads_dir
    ):
        """Even when a MedicalRecord references the key, a different patient
        gets 403 — record-ownership is checked, not just key knowledge."""
        key = await _presign(patient_client, "labs.pdf", "application/pdf")
        put = await patient_client.put(f"/api/v1/uploads/{key}", content=PDF_BYTES)
        assert put.status_code == 200
        db.add(
            MedicalRecord(
                id=uuid.uuid4(),
                patient_id=patient_user.id,
                record_type="lab_report",
                title="Patient A labs",
                document_url=key,
            )
        )
        await db.commit()

        _, other_auth = await _make_patient(db, "patient-b@test.com")
        resp = await client.get(f"/api/v1/uploads/{key}", headers=other_auth)
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"

    async def test_patient_reads_doctor_uploaded_record_file(
        self, client, db, doctor_user, doctor_profile, patient_user, uploads_dir
    ):
        """A file uploaded by a doctor and referenced by the patient's record
        is readable by that patient (record ownership, not upload ownership)."""
        doctor_auth = make_auth_header(doctor_user, roles=["doctor"])
        key = await _presign_with(client, doctor_auth, "imaging.pdf", "application/pdf")
        put = await client.put(
            f"/api/v1/uploads/{key}", content=PDF_BYTES, headers=doctor_auth
        )
        assert put.status_code == 200
        db.add(
            MedicalRecord(
                id=uuid.uuid4(),
                patient_id=patient_user.id,
                doctor_id=doctor_profile.id,
                record_type="imaging",
                title="X-ray",
                document_url=key,
            )
        )
        await db.commit()

        resp = await client.get(
            f"/api/v1/uploads/{key}", headers=make_auth_header(patient_user)
        )
        assert resp.status_code == 200
        assert resp.content == PDF_BYTES

    async def test_doctor_reads_file_via_approved_clinic_link(
        self, client, db, doctor_user, doctor_profile, patient_user, uploads_dir
    ):
        """A doctor with an active membership at a clinic holding an
        APPROVED PatientClinicLink for the record's patient may download —
        even though the doctor did not author the record."""
        patient_auth = make_auth_header(patient_user)
        key = await _presign_with(client, patient_auth, "labs.pdf", "application/pdf")
        put = await client.put(
            f"/api/v1/uploads/{key}", content=PDF_BYTES, headers=patient_auth
        )
        assert put.status_code == 200

        clinic, _ = await _clinic_with_doctor(db, doctor_user)
        await _patient_link(
            db, clinic, patient_user.id, doctor_user.id, "approved"
        )
        # Patient-uploaded record — NOT authored by this doctor, so only the
        # clinic-link path can grant access.
        db.add(
            MedicalRecord(
                id=uuid.uuid4(),
                patient_id=patient_user.id,
                record_type="lab_report",
                title="Self-uploaded labs",
                source="patient_uploaded",
                document_url=key,
            )
        )
        await db.commit()

        resp = await client.get(
            f"/api/v1/uploads/{key}",
            headers=make_auth_header(doctor_user, roles=["doctor"]),
        )
        assert resp.status_code == 200
        assert resp.content == PDF_BYTES

    async def test_revoked_consent_doctor_denied_for_new_record(
        self, client, db, doctor_user, doctor_profile, patient_user, uploads_dir
    ):
        """Revoked consent only preserves reads of records created at or
        before revoked_at. A record created after revocation → 403."""
        patient_auth = make_auth_header(patient_user)
        key = await _presign_with(client, patient_auth, "new-labs.pdf", "application/pdf")
        put = await client.put(
            f"/api/v1/uploads/{key}", content=PDF_BYTES, headers=patient_auth
        )
        assert put.status_code == 200

        clinic, _ = await _clinic_with_doctor(db, doctor_user)
        await _patient_link(
            db, clinic, patient_user.id, doctor_user.id,
            "revoked", revoked_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        db.add(
            MedicalRecord(
                id=uuid.uuid4(),
                patient_id=patient_user.id,
                record_type="lab_report",
                title="Post-revocation labs",
                source="patient_uploaded",
                document_url=key,
            )
        )
        await db.commit()

        resp = await client.get(
            f"/api/v1/uploads/{key}",
            headers=make_auth_header(doctor_user, roles=["doctor"]),
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"

    async def test_revoked_consent_doctor_reads_pre_revocation_record(
        self, client, db, doctor_user, doctor_profile, patient_user, uploads_dir
    ):
        """The revoked-link extension: records created at/before revoked_at
        stay readable (clinical continuity), so this download is 200."""
        patient_auth = make_auth_header(patient_user)
        key = await _presign_with(client, patient_auth, "old-labs.pdf", "application/pdf")
        put = await client.put(
            f"/api/v1/uploads/{key}", content=PDF_BYTES, headers=patient_auth
        )
        assert put.status_code == 200

        clinic, _ = await _clinic_with_doctor(db, doctor_user)
        await _patient_link(
            db, clinic, patient_user.id, doctor_user.id,
            "revoked", revoked_at=datetime.now(timezone.utc),
        )
        # created_at explicitly set BEFORE the revocation timestamp.
        db.add(
            MedicalRecord(
                id=uuid.uuid4(),
                patient_id=patient_user.id,
                record_type="lab_report",
                title="Pre-revocation labs",
                source="patient_uploaded",
                document_url=key,
                created_at=datetime.now(timezone.utc) - timedelta(days=2),
            )
        )
        await db.commit()

        resp = await client.get(
            f"/api/v1/uploads/{key}",
            headers=make_auth_header(doctor_user, roles=["doctor"]),
        )
        assert resp.status_code == 200
        assert resp.content == PDF_BYTES

    async def test_pending_consent_doctor_denied(
        self, client, db, doctor_user, doctor_profile, patient_user, uploads_dir
    ):
        """A pending (never-approved) link grants nothing — 403."""
        patient_auth = make_auth_header(patient_user)
        key = await _presign_with(client, patient_auth, "pending.pdf", "application/pdf")
        put = await client.put(
            f"/api/v1/uploads/{key}", content=PDF_BYTES, headers=patient_auth
        )
        assert put.status_code == 200

        clinic, _ = await _clinic_with_doctor(db, doctor_user)
        await _patient_link(
            db, clinic, patient_user.id, doctor_user.id, "pending"
        )
        db.add(
            MedicalRecord(
                id=uuid.uuid4(),
                patient_id=patient_user.id,
                record_type="lab_report",
                title="Labs",
                source="patient_uploaded",
                document_url=key,
            )
        )
        await db.commit()

        resp = await client.get(
            f"/api/v1/uploads/{key}",
            headers=make_auth_header(doctor_user, roles=["doctor"]),
        )
        assert resp.status_code == 403
