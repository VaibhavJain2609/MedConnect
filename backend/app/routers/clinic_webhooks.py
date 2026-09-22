"""
Clinic webhook endpoints — CRUD for outbound webhook subscriptions.

POST   /api/v1/clinics/{clinic_id}/webhooks            — create (full secret returned ONCE)
GET    /api/v1/clinics/{clinic_id}/webhooks            — list (masked secret)
GET    /api/v1/clinics/{clinic_id}/webhooks/deliveries — delivery log (paginated, ?status=)
GET    /api/v1/clinics/{clinic_id}/webhooks/{id}       — detail (masked secret)
PATCH  /api/v1/clinics/{clinic_id}/webhooks/{id}       — update url/events/is_active
DELETE /api/v1/clinics/{clinic_id}/webhooks/{id}       — deactivate (soft delete)

All routes require an active clinic membership with role owner|admin
(clinic-scoped admin). The signing secret is stored in plaintext (the worker
needs it to compute HMACs) but is NEVER returned in list/detail/update
responses — only the masked "whsec_****last4" form.
"""
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.webhook import WebhookDelivery, WebhookEndpoint
from app.models.user import User
from app.schemas.webhook import (
    WebhookDeliveryResponse,
    WebhookEndpointCreate,
    WebhookEndpointCreatedResponse,
    WebhookEndpointResponse,
    WebhookEndpointUpdate,
    delivery_response,
    endpoint_response,
)
from app.services import access_service

router = APIRouter(prefix="/api/v1/clinics/{clinic_id}/webhooks", tags=["clinic-webhooks"])

CLINIC_ADMIN_ROLES = {"owner", "admin"}


async def _require_clinic_admin(db: AsyncSession, user: User, clinic_id: str) -> uuid.UUID:
    """Parse clinic_id and require an owner|admin membership."""
    try:
        cid = uuid.UUID(clinic_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"error": {"code": "INVALID_ID", "message": "Invalid clinic ID"}},
        )
    await access_service.require_membership_role(db, user, cid, allowed_roles=CLINIC_ADMIN_ROLES)
    return cid


async def _get_endpoint_or_404(
    db: AsyncSession, clinic_id: uuid.UUID, endpoint_id: str
) -> WebhookEndpoint:
    try:
        eid = uuid.UUID(endpoint_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"error": {"code": "INVALID_ID", "message": "Invalid endpoint ID"}},
        )
    res = await db.execute(
        select(WebhookEndpoint).where(
            WebhookEndpoint.id == eid,
            WebhookEndpoint.clinic_id == clinic_id,
            WebhookEndpoint.deleted_at.is_(None),
        )
    )
    ep = res.scalar_one_or_none()
    if ep is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Webhook endpoint not found"}},
        )
    return ep


@router.post("", response_model=WebhookEndpointCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_webhook_endpoint(
    clinic_id: str,
    data: WebhookEndpointCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cid = await _require_clinic_admin(db, user, clinic_id)
    ep = WebhookEndpoint(
        clinic_id=cid,
        url=data.url,
        secret=f"whsec_{secrets.token_urlsafe(24)}",
        event_types=data.event_types,
        is_active=data.is_active,
    )
    db.add(ep)
    await db.flush()
    await db.refresh(ep)
    body = endpoint_response(ep)
    # Full secret is returned only here — store it immediately; it cannot be
    # recovered later (only masked in all other responses).
    body["secret"] = ep.secret
    return body


@router.get("", response_model=dict)
async def list_webhook_endpoints(
    clinic_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cid = await _require_clinic_admin(db, user, clinic_id)
    res = await db.execute(
        select(WebhookEndpoint)
        .where(
            WebhookEndpoint.clinic_id == cid,
            WebhookEndpoint.deleted_at.is_(None),
        )
        .order_by(WebhookEndpoint.created_at.desc())
    )
    return {"data": [endpoint_response(ep) for ep in res.scalars().all()]}


# NOTE: declared before /{endpoint_id} so the literal "deliveries" segment is
# not swallowed by the UUID path param (FastAPI matches routes in order).
@router.get("/deliveries", response_model=dict)
async def list_webhook_deliveries(
    clinic_id: str,
    status_filter: str | None = Query(None, alias="status"),
    endpoint_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Paginated delivery log for debugging, join-filtered to this clinic."""
    cid = await _require_clinic_admin(db, user, clinic_id)

    stmt = (
        select(WebhookDelivery)
        .join(WebhookEndpoint, WebhookDelivery.endpoint_id == WebhookEndpoint.id)
        .where(WebhookEndpoint.clinic_id == cid)
    )
    count_stmt = (
        select(func.count())
        .select_from(WebhookDelivery)
        .join(WebhookEndpoint, WebhookDelivery.endpoint_id == WebhookEndpoint.id)
        .where(WebhookEndpoint.clinic_id == cid)
    )
    if status_filter:
        stmt = stmt.where(WebhookDelivery.status == status_filter)
        count_stmt = count_stmt.where(WebhookDelivery.status == status_filter)
    if endpoint_id:
        try:
            eid = uuid.UUID(endpoint_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"error": {"code": "INVALID_ID", "message": "Invalid endpoint_id"}},
            )
        stmt = stmt.where(WebhookDelivery.endpoint_id == eid)
        count_stmt = count_stmt.where(WebhookDelivery.endpoint_id == eid)

    total = (await db.execute(count_stmt)).scalar_one()
    res = await db.execute(
        stmt.order_by(WebhookDelivery.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    return {
        "data": [delivery_response(d) for d in res.scalars().all()],
        "total": total,
        "page": page,
        "limit": limit,
        "totalPages": max(1, -(-total // limit)),
    }


@router.get("/{endpoint_id}", response_model=WebhookEndpointResponse)
async def get_webhook_endpoint(
    clinic_id: str,
    endpoint_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cid = await _require_clinic_admin(db, user, clinic_id)
    ep = await _get_endpoint_or_404(db, cid, endpoint_id)
    return endpoint_response(ep)


@router.patch("/{endpoint_id}", response_model=WebhookEndpointResponse)
async def update_webhook_endpoint(
    clinic_id: str,
    endpoint_id: str,
    data: WebhookEndpointUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cid = await _require_clinic_admin(db, user, clinic_id)
    ep = await _get_endpoint_or_404(db, cid, endpoint_id)
    if data.url is not None:
        ep.url = data.url
    if data.event_types is not None:
        if not data.event_types:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"error": {"code": "VALIDATION_ERROR", "message": "event_types must not be empty"}},
            )
        ep.event_types = data.event_types
    if data.is_active is not None:
        ep.is_active = data.is_active
    await db.flush()
    await db.refresh(ep)
    return endpoint_response(ep)


@router.delete("/{endpoint_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook_endpoint(
    clinic_id: str,
    endpoint_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from datetime import datetime, timezone

    cid = await _require_clinic_admin(db, user, clinic_id)
    ep = await _get_endpoint_or_404(db, cid, endpoint_id)
    ep.deleted_at = datetime.now(timezone.utc)
    ep.is_active = False
    await db.flush()
