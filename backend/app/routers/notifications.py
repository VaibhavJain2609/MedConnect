from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.notification import Notification, NotificationPreferences, NotificationType
from app.models.user import User
from app.schemas.notification import (
    DeletedCountResponse,
    MarkAllReadResponse,
    NotificationPreferencesResponse,
    NotificationPreferencesUpdate,
    NotificationResponse,
    NotificationsListResponse,
    UnreadCountResponse,
)

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


DEFAULT_NOTIFICATION_PREFERENCES: dict = {
    "email_notifications": True,
    "push_notifications": True,
    "appointment_reminders": True,
    "lab_results": True,
    "prescription_alerts": True,
    "system_alerts": True,
    # Channel toggles consumed by services/notification_channels.py —
    # without these, sms/whatsapp are opt-out-impossible.
    "sms_notifications": False,
    "whatsapp_notifications": False,
}


# Endpoints
@router.get("", response_model=NotificationsListResponse)
async def get_notifications(
    unread_only: bool = Query(False, description="Filter to unread notifications only"),
    type: str | None = Query(None, description="Filter by notification type"),
    limit: int = Query(20, ge=1, le=100, description="Number of notifications to return"),
    offset: int = Query(0, ge=0, description="Number of notifications to skip"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user's notifications with optional filters."""
    # Build base query
    query = select(Notification).where(
        and_(
            Notification.user_id == user.id,
            Notification.deleted_at.is_(None),
        )
    )

    # Apply filters
    if unread_only:
        query = query.where(Notification.read.is_(False))

    if type:
        try:
            notification_type = NotificationType(type)
            query = query.where(Notification.type == notification_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "INVALID_TYPE", "message": f"Invalid notification type: {type}"}},
            )

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Get unread count
    unread_query = select(func.count()).where(
        and_(
            Notification.user_id == user.id,
            Notification.deleted_at.is_(None),
            Notification.read.is_(False),
        )
    )
    unread_result = await db.execute(unread_query)
    unread_count = unread_result.scalar_one()

    # Apply pagination and ordering
    query = query.order_by(Notification.created_at.desc()).offset(offset).limit(limit)

    # Execute query
    result = await db.execute(query)
    notifications = result.scalars().all()

    return NotificationsListResponse(
        notifications=[NotificationResponse.from_orm(n) for n in notifications],
        total=total,
        unread_count=unread_count,
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get count of unread notifications."""
    query = select(func.count()).where(
        and_(
            Notification.user_id == user.id,
            Notification.deleted_at.is_(None),
            Notification.read.is_(False),
        )
    )
    result = await db.execute(query)
    count = result.scalar_one()

    return {"count": count}


@router.post("/{notification_id}/read", response_model=NotificationResponse)
async def mark_as_read(
    notification_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark notification as read."""
    # Get notification (ensure it belongs to current user)
    query = select(Notification).where(
        and_(
            Notification.id == notification_id,
            Notification.user_id == user.id,
            Notification.deleted_at.is_(None),
        )
    )
    result = await db.execute(query)
    notification = result.scalar_one_or_none()

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Notification not found"}},
        )

    # Mark as read
    notification.read = True
    notification.read_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(notification)

    return NotificationResponse.from_orm(notification)


@router.post("/{notification_id}/unread", response_model=NotificationResponse)
async def mark_as_unread(
    notification_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark notification as unread."""
    # Get notification (ensure it belongs to current user)
    query = select(Notification).where(
        and_(
            Notification.id == notification_id,
            Notification.user_id == user.id,
            Notification.deleted_at.is_(None),
        )
    )
    result = await db.execute(query)
    notification = result.scalar_one_or_none()

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Notification not found"}},
        )

    # Mark as unread
    notification.read = False
    notification.read_at = None
    await db.commit()
    await db.refresh(notification)

    return NotificationResponse.from_orm(notification)


@router.post("/read-all", response_model=MarkAllReadResponse)
async def mark_all_as_read(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark all user's notifications as read."""
    stmt = (
        update(Notification)
        .where(
            and_(
                Notification.user_id == user.id,
                Notification.deleted_at.is_(None),
                Notification.read.is_(False),
            )
        )
        .values(read=True, read_at=datetime.now(timezone.utc))
    )
    await db.execute(stmt)
    await db.commit()

    return {"message": "All notifications marked as read"}


@router.delete("/read", response_model=DeletedCountResponse)
async def delete_all_read(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft delete all read notifications."""
    stmt = (
        update(Notification)
        .where(
            and_(
                Notification.user_id == user.id,
                Notification.deleted_at.is_(None),
                Notification.read.is_(True),
            )
        )
        .values(deleted_at=datetime.now(timezone.utc))
    )
    result = await db.execute(stmt)
    await db.commit()

    deleted_count = result.rowcount

    return {"deleted_count": deleted_count}


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    notification_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft delete a notification."""
    query = select(Notification).where(
        and_(
            Notification.id == notification_id,
            Notification.user_id == user.id,
            Notification.deleted_at.is_(None),
        )
    )
    result = await db.execute(query)
    notification = result.scalar_one_or_none()

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Notification not found"}},
        )

    notification.deleted_at = datetime.now(timezone.utc)
    await db.commit()

    return None


@router.get("/preferences", response_model=NotificationPreferencesResponse)
async def get_notification_preferences(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user's notification preferences."""
    query = select(NotificationPreferences).where(
        NotificationPreferences.user_id == user.id,
    )
    result = await db.execute(query)
    preferences = result.scalar_one_or_none()

    if not preferences:
        # Return default preferences
        return DEFAULT_NOTIFICATION_PREFERENCES

    return preferences.preferences


@router.put("/preferences", response_model=NotificationPreferencesResponse)
async def update_notification_preferences(
    preferences: NotificationPreferencesUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create or update user's notification preferences."""
    # Check if preferences exist
    query = select(NotificationPreferences).where(
        NotificationPreferences.user_id == user.id,
    )
    result = await db.execute(query)
    existing_prefs = result.scalar_one_or_none()

    # Only the keys the client actually sent are updated; the rest are preserved.
    updates = preferences.model_dump(exclude_unset=True)

    if existing_prefs:
        # Update existing
        merged = {**(existing_prefs.preferences or {}), **updates}
        existing_prefs.preferences = merged
        existing_prefs.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(existing_prefs)
        return existing_prefs.preferences
    else:
        # Create new
        new_prefs = NotificationPreferences(
            user_id=user.id,
            preferences={**DEFAULT_NOTIFICATION_PREFERENCES, **updates},
        )
        db.add(new_prefs)
        await db.commit()
        await db.refresh(new_prefs)
        return new_prefs.preferences
