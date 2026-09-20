"""
File storage service — local filesystem in dev, S3-ready in prod.

Uses STORAGE_BACKEND env var: "local" (default) | "s3"
For local: saves to UPLOADS_DIR/{object_key}
Serves via GET /api/v1/uploads/{object_key}
"""
import os
import re
import uuid

import redis.asyncio as aioredis

from app.config import settings

# Maximum accepted upload size (15 MB). Enforced by the PUT endpoint via
# Content-Length pre-check and a hard cap while streaming the body.
MAX_UPLOAD_BYTES = 15 * 1024 * 1024

# Issued upload keys are bound to the presigning user for this many seconds.
UPLOAD_KEY_TTL_SECONDS = 900

_UPLOAD_KEY_PREFIX = "upload_key:"

_redis_client: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    """Lazy Redis client for the upload-key registry."""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            max_connections=10,
        )
    return _redis_client


async def register_upload_key(object_key: str, user_id) -> None:
    """Bind an issued object key to the user it was presigned for.

    The local PUT endpoint is not a real presigned URL (no HMAC/expiry), so
    issued keys are registered in Redis with a TTL matching the advertised
    expiry.  PUT rejects keys that are unknown, expired, or owned by another
    user.
    """
    await _get_redis().setex(
        f"{_UPLOAD_KEY_PREFIX}{object_key}", UPLOAD_KEY_TTL_SECONDS, str(user_id)
    )


async def get_upload_key_owner(object_key: str) -> str | None:
    """Return the user_id an object key was presigned for, or None if the key
    was never issued or has expired."""
    return await _get_redis().get(f"{_UPLOAD_KEY_PREFIX}{object_key}")


def _sanitize_filename(filename: str) -> str:
    """Remove path traversal characters and sanitize file name."""
    # Strip directory components
    filename = os.path.basename(filename)
    # Replace anything that isn't alphanumeric, dash, underscore, or dot
    filename = re.sub(r"[^\w.\-]", "_", filename)
    # Collapse multiple underscores
    filename = re.sub(r"_+", "_", filename)
    return filename or "file"


async def generate_presigned_upload(file_name: str, content_type: str, owner_id) -> dict:
    """
    Generate an upload URL and object key.

    For local backend: returns a URL pointing to our own PUT endpoint and
    registers the key in Redis bound to *owner_id* so only that user can
    upload to it (and only once — existing files are never overwritten).
    For S3 backend: returns a presigned S3 PUT URL (already bound by the
    signature, so no registry entry is needed).

    Returns:
        {
            "presigned_url": str,
            "object_key": str,
            "method": "PUT",
        }
    """
    sanitized = _sanitize_filename(file_name)
    object_key = f"{uuid.uuid4()}/{sanitized}"

    if settings.STORAGE_BACKEND == "s3":
        presigned_url = await _generate_s3_presigned_url(object_key, content_type)
    else:
        # Local: return our own upload endpoint and bind the key to the user
        await register_upload_key(object_key, owner_id)
        presigned_url = f"{settings.BACKEND_URL}/api/v1/uploads/{object_key}"

    return {
        "presigned_url": presigned_url,
        "object_key": object_key,
        "method": "PUT",
    }


def get_local_file_path(object_key: str) -> str:
    """Return the absolute filesystem path for a local object key."""
    # Prevent path traversal: resolve and ensure it stays under UPLOADS_DIR
    uploads_dir = os.path.abspath(settings.UPLOADS_DIR)
    # Normalize the key (remove leading slashes, collapse ..)
    safe_key = os.path.normpath(object_key).lstrip(os.sep)
    full_path = os.path.abspath(os.path.join(uploads_dir, safe_key))
    if not full_path.startswith(uploads_dir + os.sep) and full_path != uploads_dir:
        raise ValueError("Invalid object key")
    return full_path


# ---------------------------------------------------------------------------
# S3 stubs — wire up boto3 when STORAGE_BACKEND=s3
# ---------------------------------------------------------------------------

async def _generate_s3_presigned_url(object_key: str, content_type: str) -> str:  # pragma: no cover
    """Generate an S3 presigned PUT URL. Requires boto3 + S3_BUCKET env vars."""
    import boto3  # type: ignore

    s3 = boto3.client(
        "s3",
        region_name=getattr(settings, "AWS_REGION", "ap-south-1"),
        aws_access_key_id=getattr(settings, "AWS_ACCESS_KEY_ID", None),
        aws_secret_access_key=getattr(settings, "AWS_SECRET_ACCESS_KEY", None),
    )
    bucket = getattr(settings, "S3_BUCKET", "medconnect-uploads")
    url = s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": bucket, "Key": object_key, "ContentType": content_type},
        ExpiresIn=900,
    )
    return url


async def _generate_s3_download_url(object_key: str) -> str:  # pragma: no cover
    """Generate an S3 presigned GET URL."""
    import boto3  # type: ignore

    s3 = boto3.client(
        "s3",
        region_name=getattr(settings, "AWS_REGION", "ap-south-1"),
        aws_access_key_id=getattr(settings, "AWS_ACCESS_KEY_ID", None),
        aws_secret_access_key=getattr(settings, "AWS_SECRET_ACCESS_KEY", None),
    )
    bucket = getattr(settings, "S3_BUCKET", "medconnect-uploads")
    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": object_key},
        ExpiresIn=3600,
    )
    return url
