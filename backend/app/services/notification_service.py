import uuid
from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationType


async def create_notification(
    db: AsyncSession,
    user_id: uuid.UUID,
    notif_type: str,
    title: str,
    body: str,
    action_url: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> Notification:
    """Create a notification for a user.

    Args:
        db: Database session
        user_id: ID of the user to notify
        notif_type: Notification type (use NotificationType enum values)
        title: Short notification title
        body: Notification message body
        action_url: Optional URL to navigate to when clicked
        metadata: Optional extra metadata dict

    Returns:
        The created Notification instance (not yet committed).
    """
    notif = Notification(
        id=uuid.uuid4(),
        user_id=user_id,
        type=notif_type,
        title=title,
        message=body,
        action_url=action_url,
        meta=metadata or {},
        read=False,
    )
    db.add(notif)
    await db.flush()
    return notif


async def create_notifications_bulk(
    db: AsyncSession,
    user_ids: Sequence[uuid.UUID],
    notif_type: str,
    title: str,
    body: str,
    action_url: Optional[str] = None,
    metadata: Optional[dict] = None,
    chunk_size: int = 1000,
) -> int:
    """Insert the same notification for many users via batched executemany.

    Used by the admin announcement broadcast — one row per recipient with a
    shared `broadcast_id` in `meta` so the send can be traced/listed later.

    Args:
        db: Database session
        user_ids: Recipient user IDs
        notif_type: Notification type (use NotificationType enum values)
        title: Short notification title
        body: Notification message body
        action_url: Optional URL to navigate to when clicked
        metadata: Optional extra metadata dict (same for every recipient)
        chunk_size: Max rows per INSERT statement

    Returns:
        Number of notification rows inserted (not yet committed).
    """
    ids = list(user_ids)
    if not ids:
        return 0

    meta = metadata or {}
    rows = [
        {
            "id": uuid.uuid4(),
            "user_id": uid,
            "type": notif_type,
            "title": title,
            "message": body,
            "action_url": action_url,
            "meta": meta,
            "read": False,
        }
        for uid in ids
    ]
    for start in range(0, len(rows), chunk_size):
        await db.execute(insert(Notification), rows[start : start + chunk_size])
    await db.flush()
    return len(rows)
