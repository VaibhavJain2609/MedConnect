"""Schemas for clinic webhook endpoints + delivery log."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


def mask_secret(secret: str) -> str:
    """Return the response-safe masked form: ``whsec_****last4``."""
    if len(secret) <= 4:
        return "****"
    return f"{secret[:6]}****{secret[-4:]}"


class WebhookEndpointCreate(BaseModel):
    url: str = Field(max_length=2048)
    event_types: list[str] = Field(min_length=1)
    is_active: bool = True

    @field_validator("url")
    @classmethod
    def _url_must_be_http(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith(("https://", "http://")):
            raise ValueError("url must start with https:// (or http:// for local testing)")
        return v

    @field_validator("event_types")
    @classmethod
    def _event_types_nonempty(cls, v: list[str]) -> list[str]:
        return [e.strip() for e in v if e.strip()]


class WebhookEndpointUpdate(BaseModel):
    url: str | None = Field(None, max_length=2048)
    event_types: list[str] | None = None
    is_active: bool | None = None

    @field_validator("url")
    @classmethod
    def _url_must_be_http(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v.startswith(("https://", "http://")):
            raise ValueError("url must start with https:// (or http:// for local testing)")
        return v


class WebhookEndpointResponse(BaseModel):
    """List/detail shape — the signing secret is ALWAYS masked."""

    id: str
    clinic_id: str
    url: str
    event_types: list[str]
    is_active: bool
    secret_masked: str
    created_at: datetime


class WebhookEndpointCreatedResponse(WebhookEndpointResponse):
    """Create-only shape — the only response that ever carries the full secret."""

    secret: str


class WebhookDeliveryResponse(BaseModel):
    id: str
    endpoint_id: str
    event_type: str
    payload: dict
    status: str
    attempts: int
    last_error: str | None
    created_at: datetime
    delivered_at: datetime | None


def endpoint_response(ep) -> dict:
    """Serialize a WebhookEndpoint ORM row to the masked response shape."""
    return {
        "id": str(ep.id),
        "clinic_id": str(ep.clinic_id),
        "url": ep.url,
        "event_types": list(ep.event_types or []),
        "is_active": ep.is_active,
        "secret_masked": mask_secret(ep.secret),
        "created_at": ep.created_at,
    }


def delivery_response(d) -> dict:
    """Serialize a WebhookDelivery ORM row."""
    return {
        "id": str(d.id),
        "endpoint_id": str(d.endpoint_id),
        "event_type": d.event_type,
        "payload": d.payload_json,
        "status": d.status,
        "attempts": d.attempts,
        "last_error": d.last_error,
        "created_at": d.created_at,
        "delivered_at": d.delivered_at,
    }
