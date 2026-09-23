"""
Upload router — handles presigned URL generation and local file serving.

Routes:
  POST /api/v1/uploads/presign   — generate upload URL + object key
  PUT  /api/v1/uploads/{key}     — receive raw bytes (local backend only)
  GET  /api/v1/uploads/{key}     — serve file (local backend only)
"""
import logging
import mimetypes
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.clinic import ClinicMembership
from app.models.doctor import Doctor
from app.models.medical_record import MedicalRecord
from app.models.patient_link import PatientClinicLink
from app.models.user import User
from app.services import access_service
from app.services.storage_service import (
    MAX_UPLOAD_BYTES,
    generate_presigned_upload,
    get_local_file_path,
    get_upload_key_owner,
)

_logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/uploads", tags=["uploads"])

ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "application/pdf",
}

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}

# Magic byte signatures for supported file types
_MAGIC_SIGNATURES: dict[str, bytes] = {
    "image/jpeg": b"\xff\xd8\xff",
    "image/png": b"\x89PNG\r\n\x1a\n",
    "application/pdf": b"%PDF",
}


def _check_magic_bytes(data: bytes, content_type: str) -> bool:
    """Return True only when the leading bytes of *data* match the expected
    magic signature for *content_type*.  Returns False for unknown types."""
    sig = _MAGIC_SIGNATURES.get(content_type)
    if sig is None:
        return False
    return data[: len(sig)] == sig


class PresignRequest(BaseModel):
    file_name: str
    content_type: str

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, v: str) -> str:
        if v not in ALLOWED_CONTENT_TYPES:
            raise ValueError(
                f"content_type must be one of: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}"
            )
        return v

    @field_validator("file_name")
    @classmethod
    def validate_extension(cls, v: str) -> str:
        ext = os.path.splitext(v.lower())[1]
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(
                f"File extension must be one of: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )
        return v


@router.post("/presign")
async def presign(
    body: PresignRequest,
    current_user: User = Depends(get_current_user),
):
    """Generate a presigned upload URL for any authenticated user."""
    result = await generate_presigned_upload(
        file_name=body.file_name,
        content_type=body.content_type,
        owner_id=current_user.id,
    )
    return {
        "presigned_url": result["presigned_url"],
        "object_key": result["object_key"],
        "method": result["method"],
        "expires_in": 900,
    }


@router.put("/{object_key:path}")
async def upload_file(
    object_key: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Receive raw file bytes and save to local storage (local backend only).

    The key must have been issued to this user via POST /presign within the
    last 15 minutes, the declared/actual size must not exceed 15 MB, and an
    existing object is never overwritten.
    """
    if settings.STORAGE_BACKEND != "local":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Direct upload not available for this storage backend"}},
        )

    try:
        file_path = get_local_file_path(object_key)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_KEY", "message": "Invalid object key"}},
        )

    # The local PUT URL carries no signature/expiry, so the key must have been
    # registered by this user at presign time.  Fail closed if the registry is
    # unavailable — accepting unverifiable keys would defeat the binding.
    try:
        owner = await get_upload_key_owner(object_key)
    except Exception as exc:
        _logger.error("Upload-key registry error (%s: %s); rejecting upload", type(exc).__name__, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": {"code": "UPLOAD_UNAVAILABLE", "message": "Upload service temporarily unavailable"}},
        )
    if owner is None or owner != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "INVALID_UPLOAD_KEY", "message": "Upload key is unknown, expired, or was not issued to this user"}},
        )

    # Never overwrite an existing object.
    if os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "ALREADY_EXISTS", "message": "An object already exists at this key"}},
        )

    # Platform-configurable cap (admin → settings → max_upload_mb); the
    # hardcoded MAX_UPLOAD_BYTES stays as the absolute ceiling.
    from app.services import platform_settings
    _setting_mb = await platform_settings.get_setting(db, "max_upload_mb")
    try:
        max_upload_bytes = min(int(_setting_mb) * 1024 * 1024, MAX_UPLOAD_BYTES)
    except (TypeError, ValueError):
        max_upload_bytes = MAX_UPLOAD_BYTES

    # Reject oversized uploads up front when the client declares a length.
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            declared = int(content_length)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "INVALID_CONTENT_LENGTH", "message": "Invalid Content-Length header"}},
            )
        if declared > max_upload_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail={"error": {"code": "FILE_TOO_LARGE", "message": f"File exceeds maximum size of {max_upload_bytes // (1024 * 1024)} MB"}},
            )

    # Stream the body with a hard cap (covers chunked/missing Content-Length).
    chunks = bytearray()
    async for chunk in request.stream():
        chunks.extend(chunk)
        if len(chunks) > max_upload_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail={"error": {"code": "FILE_TOO_LARGE", "message": f"File exceeds maximum size of {max_upload_bytes // (1024 * 1024)} MB"}},
            )
    body_bytes = bytes(chunks)

    if not body_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "EMPTY_BODY", "message": "Request body is empty"}},
        )

    # Validate magic bytes against the content type inferred from the object key
    # extension before writing anything to disk.  This prevents an attacker from
    # renaming an executable to .pdf (or similar) and having it stored as-is.
    inferred_type, _ = mimetypes.guess_type(object_key)
    if not inferred_type or not _check_magic_bytes(body_bytes, inferred_type):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={"error": {"code": "INVALID_FILE_TYPE", "message": "File content does not match declared type"}},
        )

    # Create parent directories
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    # "xb" = exclusive create: atomically refuses to overwrite an existing
    # file, closing the race between the exists() check above and the write.
    try:
        with open(file_path, "xb") as f:
            f.write(body_bytes)
    except FileExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "ALREADY_EXISTS", "message": "An object already exists at this key"}},
        )

    # Audit the successful upload — object metadata only, never content.
    # record_id is derived deterministically from object_key (uuid5).
    from app.services.audit_service import log_change
    await log_change(
        db=db,
        table_name="uploads",
        record_id=uuid.uuid5(uuid.NAMESPACE_URL, object_key),
        action="INSERT",
        old_values=None,
        new_values={
            "object_key": object_key,
            "size_bytes": len(body_bytes),
            "mime_type": inferred_type,
        },
    )

    return {"status": "ok", "object_key": object_key}


async def _doctor_has_any_patient_relationship(
    db: AsyncSession, doctor: Doctor, records: list[MedicalRecord]
) -> bool:
    """True when the doctor may access ANY of the records' patients.

    Set-based form of the doctor↔patient rule from
    access_service.doctor_patient_relationship_exists (authored record, or
    shared clinic with an approved link) plus the upload-specific extension:
    a revoked link still grants read access to records created before its
    revoked_at timestamp. Runs a constant 3 queries instead of ~3 per record
    (R12 N+1 fix)."""
    patient_ids = {r.patient_id for r in records}
    if not patient_ids:
        return False

    # (1) Authored-record path — one query for the whole patient set.
    authored = await db.execute(
        select(MedicalRecord.patient_id)
        .where(
            MedicalRecord.doctor_id == doctor.id,
            MedicalRecord.patient_id.in_(patient_ids),
            MedicalRecord.deleted_at.is_(None),
        )
        .limit(1)
    )
    if authored.first() is not None:
        return True

    # (2) Approved clinic-link path at a shared clinic — one exists query.
    shared = await db.execute(
        select(PatientClinicLink.id)
        .join(ClinicMembership, PatientClinicLink.clinic_id == ClinicMembership.clinic_id)
        .where(
            ClinicMembership.user_id == doctor.user_id,
            ClinicMembership.is_active.is_(True),
            ClinicMembership.deleted_at.is_(None),
            PatientClinicLink.patient_id.in_(patient_ids),
            PatientClinicLink.consent_status == "approved",
            PatientClinicLink.deleted_at.is_(None),
        )
        .limit(1)
    )
    if shared.first() is not None:
        return True

    # (3) Revoked-link extension: read-only access to records created before
    # the link's revoked_at — one query returning (patient_id, revoked_at)
    # for every relevant revoked link, evaluated per record in Python.
    revoked = await db.execute(
        select(PatientClinicLink.patient_id, PatientClinicLink.revoked_at)
        .join(ClinicMembership, PatientClinicLink.clinic_id == ClinicMembership.clinic_id)
        .where(
            ClinicMembership.user_id == doctor.user_id,
            ClinicMembership.is_active.is_(True),
            ClinicMembership.deleted_at.is_(None),
            PatientClinicLink.patient_id.in_(patient_ids),
            PatientClinicLink.consent_status == "revoked",
            PatientClinicLink.deleted_at.is_(None),
        )
    )
    revoked_by_patient: dict[uuid.UUID, list] = {}
    for patient_id, revoked_at in revoked.all():
        if revoked_at is not None:
            revoked_by_patient.setdefault(patient_id, []).append(revoked_at)
    if not revoked_by_patient:
        return False
    return any(
        r.created_at is not None
        and any(r.created_at <= ra for ra in revoked_by_patient.get(r.patient_id, ()))
        for r in records
    )


async def _user_can_access_object(db: AsyncSession, user: User, object_key: str) -> bool:
    """Authorize a download of *object_key* for *user*.

    Access rules (same as for the MedicalRecord referencing the file):
    - admin: always allowed
    - patient: the record belongs to them
    - doctor: they have a relationship with the record's patient
      (authored a record, or share an approved/revoked clinic link)
    - anyone: they uploaded the file themselves (covers the window between
      upload and the record that references it being created)
    """
    # Uploader can fetch a file they just uploaded.
    try:
        owner = await get_upload_key_owner(object_key)
    except Exception as exc:
        _logger.error("Upload-key registry error (%s: %s); treating key as unknown", type(exc).__name__, exc)
        owner = None
    if owner is not None and owner == str(user.id):
        return True

    # Admin can fetch any stored object (verification review, audit, support).
    # Must run before the records early-return: standalone uploads (e.g. a
    # doctor's license document) have no MedicalRecord referencing them.
    if user.role == "admin":
        return True

    # A doctor can always fetch their own onboarding/license documents and
    # signature image even after the upload-key TTL expired.
    if user.role == "doctor":
        own_doc = await db.execute(
            select(Doctor.id).where(
                Doctor.user_id == user.id,
                Doctor.deleted_at.is_(None),
                (Doctor.license_document_url == object_key)
                | (Doctor.signature_url == object_key),
            )
        )
        if own_doc.scalar_one_or_none() is not None:
            return True

    result = await db.execute(
        select(MedicalRecord).where(
            MedicalRecord.document_url == object_key,
            MedicalRecord.deleted_at.is_(None),
        )
    )
    records = result.scalars().all()
    if not records:
        return False

    if user.role == "patient":
        return any(r.patient_id == user.id for r in records)
    if user.role == "doctor":
        doc_result = await db.execute(
            select(Doctor).where(
                Doctor.user_id == user.id,
                Doctor.deleted_at.is_(None),
            )
        )
        doctor = doc_result.scalar_one_or_none()
        if not doctor:
            return False
        # Batched: constant 3 queries for the whole record set rather than
        # ~3 per record (R12 N+1 fix).
        return await _doctor_has_any_patient_relationship(db, doctor, list(records))
    return False


@router.get("/{object_key:path}")
async def serve_file(
    object_key: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Serve a stored file (local backend only) with object-level authorization."""
    if settings.STORAGE_BACKEND != "local":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Direct serve not available for this storage backend"}},
        )

    try:
        file_path = get_local_file_path(object_key)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_KEY", "message": "Invalid object key"}},
        )

    # Authorization is checked before file existence so a denied response does
    # not reveal whether the key exists on disk.
    if not await _user_can_access_object(db, current_user, object_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Access denied"}},
        )

    if not os.path.isfile(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "File not found"}},
        )

    # Guess content type from extension
    content_type, _ = mimetypes.guess_type(file_path)
    content_type = content_type or "application/octet-stream"

    return FileResponse(file_path, media_type=content_type)
