"""Web Push subscription management.

The browser Push API hands each device a globally-unique ``endpoint`` URL plus
encryption keys (``p256dh``/``auth``). Rows in ``push_subscriptions`` are
keyed by that endpoint: re-subscribing refreshes the keys and re-links the
subscription to the current user rather than creating a duplicate, and a
previously soft-deleted endpoint is revived.

Endpoints:
    POST   /api/v1/push/subscribe     — upsert {endpoint, keys:{p256dh, auth}}
    DELETE /api/v1/push/subscribe     — soft-delete {endpoint} for this user
    GET    /api/v1/push/vapid-public  — VAPID public key for pushManager.subscribe()

The VAPID keypair is env-only config (never committed):
    npx web-push generate-vapid-keys
    VAPID_SUBJECT=mailto:ops@example.com
    VAPID_PRIVATE_KEY=... VAPID_PUBLIC_KEY=...

PHI note: endpoints and keys are credentials — never log them.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.push_subscription import PushSubscription
from app.models.user import User

router = APIRouter(
    prefix="/api/v1/push",
    tags=["push"],
    dependencies=[Depends(get_current_user)],
)


class PushKeys(BaseModel):
    """Client encryption keys from ``PushSubscription.keys``."""

    p256dh: str = Field(min_length=1, max_length=255)
    auth: str = Field(min_length=1, max_length=255)


class PushSubscribeRequest(BaseModel):
    endpoint: str = Field(min_length=1, max_length=2048)
    keys: PushKeys


class PushUnsubscribeRequest(BaseModel):
    endpoint: str = Field(min_length=1, max_length=2048)


@router.post("/subscribe", status_code=status.HTTP_201_CREATED)
async def subscribe(
    payload: PushSubscribeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upsert a browser push subscription, keyed by its unique endpoint."""
    res = await db.execute(
        select(PushSubscription).where(
            PushSubscription.endpoint == payload.endpoint
        )
    )
    sub = res.scalar_one_or_none()
    if sub is None:
        sub = PushSubscription(
            user_id=user.id,
            endpoint=payload.endpoint,
            p256dh=payload.keys.p256dh,
            auth=payload.keys.auth,
        )
        db.add(sub)
    else:
        # Re-subscribe / ownership change / revive a soft-deleted row.
        sub.user_id = user.id
        sub.p256dh = payload.keys.p256dh
        sub.auth = payload.keys.auth
        sub.deleted_at = None
    await db.commit()
    return {"status": "subscribed"}


@router.delete("/subscribe")
async def unsubscribe(
    payload: PushUnsubscribeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete one of the current user's subscriptions by endpoint."""
    res = await db.execute(
        select(PushSubscription).where(
            PushSubscription.endpoint == payload.endpoint,
            PushSubscription.user_id == user.id,
            PushSubscription.deleted_at.is_(None),
        )
    )
    sub = res.scalar_one_or_none()
    if sub is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": "Push subscription not found",
                }
            },
        )
    sub.deleted_at = datetime.now(tz=timezone.utc)
    await db.commit()
    return {"status": "unsubscribed"}


@router.get("/vapid-public")
async def vapid_public_key():
    """Return the VAPID public key browsers need for pushManager.subscribe().

    404 when push is not configured — the frontend treats that as "push
    unavailable" and hides the enable button.
    """
    if not settings.VAPID_PUBLIC_KEY:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "PUSH_NOT_CONFIGURED",
                    "message": "Web Push is not configured on this server",
                }
            },
        )
    return {"public_key": settings.VAPID_PUBLIC_KEY}
