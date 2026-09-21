"""Schemas for app/routers/notifications.py.

Response models match what each endpoint returns today — every key the
handlers emit is represented so FastAPI's response_model filtering drops
nothing the frontend consumes.
"""
from pydantic import BaseModel, ConfigDict

from app.models.notification import Notification


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


class UnreadCountResponse(BaseModel):
    count: int


class MarkAllReadResponse(BaseModel):
    message: str


class DeletedCountResponse(BaseModel):
    deleted_count: int


class NotificationPreferencesResponse(BaseModel):
    """Bare preferences map returned by GET/PUT /notifications/preferences.

    Known keys carry the documented defaults; stored rows may contain legacy
    keys, so extras are allowed through rather than filtered."""

    model_config = ConfigDict(extra="allow")

    email_notifications: bool = True
    push_notifications: bool = True
    sms_notifications: bool = False
    whatsapp_notifications: bool = False
    appointment_reminders: bool = True
    lab_results: bool = True
    prescription_alerts: bool = True
    system_alerts: bool = True


class NotificationPreferencesUpdate(BaseModel):
    """Validated body for PUT /preferences. Unset fields keep their current value."""

    email_notifications: bool = True
    push_notifications: bool = True
    sms_notifications: bool = False
    whatsapp_notifications: bool = False
    appointment_reminders: bool = True
    lab_results: bool = True
    prescription_alerts: bool = True
    system_alerts: bool = True
