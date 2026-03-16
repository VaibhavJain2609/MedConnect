"""
Upload router — handles presigned URL generation and local file serving.

Routes:
  POST /api/v1/uploads/presign   — generate upload URL + object key
  PUT  /api/v1/uploads/{key}     — receive raw bytes (local backend only)
  GET  /api/v1/uploads/{key}     — serve file (local backend only)
"""
import mimetypes
import os

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, field_validator

from app.config import settings
from app.dependencies import get_current_user
from app.models.user import User
from app.services.storage_service import (
    generate_presigned_upload,
    get_local_file_path,
)

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
    _user: User = Depends(get_current_user),
):
    """Generate a presigned upload URL for any authenticated user."""
    result = await generate_presigned_upload(
        file_name=body.file_name,
        content_type=body.content_type,
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
    _user: User = Depends(get_current_user),
):
    """Receive raw file bytes and save to local storage (local backend only)."""
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

    # Create parent directories
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    body_bytes = await request.body()
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

    with open(file_path, "wb") as f:
        f.write(body_bytes)

    return {"status": "ok", "object_key": object_key}


@router.get("/{object_key:path}")
async def serve_file(
    object_key: str,
    _user: User = Depends(get_current_user),
):
    """Serve a stored file (local backend only)."""
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

    if not os.path.isfile(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "File not found"}},
        )

    # Guess content type from extension
    content_type, _ = mimetypes.guess_type(file_path)
    content_type = content_type or "application/octet-stream"

    return FileResponse(file_path, media_type=content_type)
