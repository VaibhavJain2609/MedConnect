from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.notification import Notification, NotificationPreferences, NotificationType
from app.models.user import User

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


# Pydantic Schemas
class NotificationResponse(BaseModel):
    id: str
    user_id: str
    type: str
    title: str
    message: str
    read: bool
    action_url: str | None
    metadata: dict | None  # Frontend expects 'metadata', DB uses 'meta'
    created_at: str
    read_at: str | None

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm(cls, notification: Notification):
        return cls(
            id=str(notification.id),
            user_id=str(notification.user_id),
            type=notification.type.value if hasattr(notification.type, "value") else notification.type,
            title=notification.title,
            message=notification.message,
            read=notification.read,
            action_url=notification.action_url,
            metadata=notification.meta,  # Map 'meta' field to 'metadata' for frontend
            created_at=notification.created_at.isoformat(),
            read_at=notification.read_at.isoformat() if notification.read_at else None,
        )


class NotificationsListResponse(BaseModel):
    notifications: list[NotificationResponse]
    total: int
    unread_count: int


class NotificationPreferencesResponse(BaseModel):
    preferences: dict


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


@router.get("/unread-count")
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
    notification.read_at = datetime.now()
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


@router.post("/read-all")
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
        .values(read=True, read_at=datetime.now())
    )
    await db.execute(stmt)
    await db.commit()

    return {"message": "All notifications marked as read"}


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    notification_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft delete a notification."""
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

    # Soft delete
    notification.deleted_at = datetime.now()
    await db.commit()

    return None


@router.delete("/read")
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
        .values(deleted_at=datetime.now())
    )
    result = await db.execute(stmt)
    await db.commit()

    deleted_count = result.rowcount

    return {"deleted_count": deleted_count}


@router.get("/preferences")
async def get_notification_preferences(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user's notification preferences."""
    query = select(NotificationPreferences).where(NotificationPreferences.user_id == user.id)
    result = await db.execute(query)
    preferences = result.scalar_one_or_none()

    if not preferences:
        # Return default preferences
        return {
            "email_notifications": True,
            "push_notifications": True,
            "appointment_reminders": True,
            "lab_results": True,
            "prescription_alerts": True,
            "system_alerts": True,
        }

    return preferences.preferences


@router.put("/preferences")
async def update_notification_preferences(
    preferences: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create or update user's notification preferences."""
    # Check if preferences exist
    query = select(NotificationPreferences).where(NotificationPreferences.user_id == user.id)
    result = await db.execute(query)
    existing_prefs = result.scalar_one_or_none()

    if existing_prefs:
        # Update existing
        existing_prefs.preferences = preferences
        existing_prefs.updated_at = datetime.now()
        await db.commit()
        await db.refresh(existing_prefs)
        return existing_prefs.preferences
    else:
        # Create new
        new_prefs = NotificationPreferences(
            user_id=user.id,
            preferences=preferences,
        )
        db.add(new_prefs)
        await db.commit()
        await db.refresh(new_prefs)
        return new_prefs.preferences
