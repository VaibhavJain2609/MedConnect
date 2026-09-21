"""
Lab-result ingest router — AI/OCR-assisted entry (doctor-scoped).

POST /api/v1/lab-results/ingest — extract candidate lab values from an
already-uploaded report image for human review.

Human-in-the-loop: this endpoint NEVER writes LabResult rows. It returns
``candidates[]`` only; the clinician reviews/edits them and saves through
the normal lab-result create/update paths.

Authz: verified doctor (``get_verified_doctor``) who owns the upload key
(the image must have been presigned by the same user). When ``patient_id``
is supplied, the doctor must also have an active relationship with that
patient (authored record or approved clinic link — revoked links do NOT
count, matching the create-new-data rule).

Provider: resolved per-request via ``services.providers.ocr.get_ocr_provider``.
``OCR_PROVIDER=none`` (default) → 503 OCR_NOT_CONFIGURED. The "llm" stub
raises OcrUnavailable → 503 OCR_UNAVAILABLE until a real vision backend
is wired in.
"""
import asyncio
import mimetypes
import os
import uuid
from dataclasses import asdict

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_verified_doctor
from app.models.doctor import Doctor
from app.models.user import User
from app.services import access_service
from app.services.providers.ocr import (
    NullOcrProvider,
    OcrUnavailable,
    get_ocr_provider,
)
from app.services.storage_service import (
    get_local_file_path,
    get_upload_key_owner,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/lab-results", tags=["lab-results"])

# Only raster images go to the vision provider — PDFs would need a
# rasterization step the stub does not cover.
_INGESTIBLE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


class LabIngestRequest(BaseModel):
    upload_key: str
    patient_id: uuid.UUID | None = None


@router.post("/ingest")
async def ingest_lab_report_image(
    body: LabIngestRequest,
    doctor_info: tuple[User, Doctor] = Depends(get_verified_doctor),
    db: AsyncSession = Depends(get_db),
):
    """Extract lab-value candidates from an uploaded report image."""
    user, doctor = doctor_info

    # If a patient context is supplied, require an active doctor–patient
    # relationship (allow_revoked=False — ingest feeds NEW data creation).
    if body.patient_id is not None:
        related = await access_service.doctor_patient_relationship_exists(
            db, doctor.user_id, doctor.id, body.patient_id, allow_revoked=False
        )
        if not related:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "FORBIDDEN", "message": "No relationship with this patient"}},
            )

    # The image must have been presigned by this doctor — same owner-binding
    # rule as PUT /api/v1/uploads/{key}. Registry outage fails closed (503).
    try:
        owner = await get_upload_key_owner(body.upload_key)
    except Exception as exc:
        logger.error("lab_ingest_key_registry_error", error=str(exc), error_type=type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": {"code": "UPLOAD_UNAVAILABLE", "message": "Upload service temporarily unavailable"}},
        )
    if owner is None or owner != str(user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "INVALID_UPLOAD_KEY", "message": "Upload key is unknown, expired, or was not issued to this user"}},
        )

    ext = os.path.splitext(body.upload_key.lower())[1]
    if ext not in _INGESTIBLE_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={"error": {"code": "UNSUPPORTED_FILE_TYPE", "message": "Only JPEG/PNG report images can be ingested"}},
        )

    provider = get_ocr_provider()
    if isinstance(provider, NullOcrProvider):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": {"code": "OCR_NOT_CONFIGURED", "message": "Lab-report OCR is not enabled on this server"}},
        )

    # Resolve the image: local backend reads bytes from disk; other backends
    # hand the provider the storage key (it fetches the object itself).
    image_bytes: bytes | None = None
    if settings.STORAGE_BACKEND == "local":
        try:
            file_path = get_local_file_path(body.upload_key)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "INVALID_KEY", "message": "Invalid object key"}},
            )
        if not os.path.isfile(file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "UPLOAD_NOT_FOUND", "message": "No file stored at this key — upload the image first"}},
            )
        image_bytes = await asyncio.to_thread(_read_file, file_path)

    content_type, _ = mimetypes.guess_type(body.upload_key)

    try:
        candidates = await provider.extract_lab_values(
            image_bytes=image_bytes,
            storage_key=body.upload_key,
            content_type=content_type,
        )
    except OcrUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": {"code": "OCR_UNAVAILABLE", "message": str(exc) or "OCR provider unavailable"}},
        )

    # PHI note: log identifiers only — never candidate values.
    logger.info(
        "lab_ingest_extracted",
        provider=provider.name,
        doctor_id=str(doctor.id),
        candidate_count=len(candidates),
    )
    return {
        "upload_key": body.upload_key,
        "provider": provider.name,
        "candidates": [asdict(c) for c in candidates],
    }


def _read_file(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()
