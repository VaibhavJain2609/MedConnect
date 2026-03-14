import uuid
from datetime import datetime
from typing import Optional

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
