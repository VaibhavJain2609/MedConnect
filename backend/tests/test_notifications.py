import uuid
from datetime import datetime

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationPreferences, NotificationType
from app.models.user import User
from tests.conftest import create_test_token


@pytest_asyncio.fixture(scope="function")
async def user_with_notifications(db: AsyncSession, patient_user: User) -> tuple[User, list[Notification]]:
    """Create a user with sample notifications."""
    notifications = [
        Notification(
            user_id=patient_user.id,
            type=NotificationType.APPOINTMENT,
            title="Upcoming Appointment",
            message="You have an appointment tomorrow at 10 AM",
            read=False,
            action_url="/appointments/123",
        ),
        Notification(
            user_id=patient_user.id,
            type=NotificationType.LAB_RESULT,
            title="Lab Results Available",
            message="Your blood test results are ready",
            read=True,
            read_at=datetime.now(),
        ),
        Notification(
            user_id=patient_user.id,
            type=NotificationType.PRESCRIPTION,
            title="New Prescription",
            message="Dr. Smith has issued a new prescription",
            read=False,
        ),
        Notification(
            user_id=patient_user.id,
            type=NotificationType.SYSTEM,
            title="System Maintenance",
            message="Scheduled maintenance tonight at 11 PM",
            read=False,
        ),
    ]
    for notif in notifications:
        db.add(notif)
    await db.commit()
    for notif in notifications:
        await db.refresh(notif)
    return patient_user, notifications


@pytest.mark.asyncio
async def test_get_notifications_requires_auth(client: AsyncClient):
    """GET /api/v1/notifications requires authentication."""
    response = await client.get("/api/v1/notifications")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_notifications_list(patient_client: AsyncClient, user_with_notifications):
    """GET /api/v1/notifications returns user's notifications."""
    user, notifications = user_with_notifications

    response = await patient_client.get("/api/v1/notifications")
    assert response.status_code == 200

    data = response.json()
    assert "notifications" in data
    assert "total" in data
    assert "unread_count" in data

    assert data["total"] == 4
    assert data["unread_count"] == 3  # 3 unread notifications
    assert len(data["notifications"]) == 4

    # Notifications should be ordered by created_at desc (most recent first)
    for notif in data["notifications"]:
        assert "id" in notif
        assert "title" in notif
        assert "message" in notif
        assert "read" in notif
        assert "type" in notif


@pytest.mark.asyncio
async def test_get_notifications_unread_only(patient_client: AsyncClient, user_with_notifications):
    """GET /api/v1/notifications?unread_only=true filters to unread notifications."""
    user, notifications = user_with_notifications

    response = await patient_client.get("/api/v1/notifications?unread_only=true")
    assert response.status_code == 200

    data = response.json()
    assert data["total"] == 3  # Only unread
    assert len(data["notifications"]) == 3

    # All returned notifications should be unread
    for notif in data["notifications"]:
        assert notif["read"] is False


@pytest.mark.asyncio
async def test_get_notifications_filter_by_type(patient_client: AsyncClient, user_with_notifications):
    """GET /api/v1/notifications?type=appointment filters by notification type."""
    user, notifications = user_with_notifications

    response = await patient_client.get("/api/v1/notifications?type=appointment")
    assert response.status_code == 200

    data = response.json()
    assert data["total"] == 1
    assert len(data["notifications"]) == 1
    assert data["notifications"][0]["type"] == "appointment"


@pytest.mark.asyncio
async def test_get_notifications_pagination(patient_client: AsyncClient, user_with_notifications):
    """GET /api/v1/notifications supports limit and offset pagination."""
    user, notifications = user_with_notifications

    # First page (limit=2)
    response = await patient_client.get("/api/v1/notifications?limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data["notifications"]) == 2
    assert data["total"] == 4

    # Second page (offset=2, limit=2)
    response = await patient_client.get("/api/v1/notifications?limit=2&offset=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data["notifications"]) == 2


@pytest.mark.asyncio
async def test_get_notifications_only_shows_own(patient_client: AsyncClient, db: AsyncSession, patient_user: User):
    """Users can only see their own notifications."""
    # Create another user with a notification
    other_user = User(
        keycloak_sub="other-user-123",
        email="other@test.com",
        full_name="Other User",
        role="patient",
    )
    db.add(other_user)
    await db.commit()
    await db.refresh(other_user)

    other_notification = Notification(
        user_id=other_user.id,
        type=NotificationType.SYSTEM,
        title="Other User's Notification",
        message="This should not be visible",
        read=False,
    )
    db.add(other_notification)
    await db.commit()

    # Patient client should not see other user's notification
    response = await patient_client.get("/api/v1/notifications")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_get_unread_count(patient_client: AsyncClient, user_with_notifications):
    """GET /api/v1/notifications/unread-count returns unread count."""
    user, notifications = user_with_notifications

    response = await patient_client.get("/api/v1/notifications/unread-count")
    assert response.status_code == 200

    data = response.json()
    assert "count" in data
    assert data["count"] == 3


@pytest.mark.asyncio
async def test_mark_notification_as_read(patient_client: AsyncClient, user_with_notifications):
    """POST /api/v1/notifications/{id}/read marks notification as read."""
    user, notifications = user_with_notifications
    unread_notif = [n for n in notifications if not n.read][0]

    response = await patient_client.post(f"/api/v1/notifications/{unread_notif.id}/read")
    assert response.status_code == 200

    data = response.json()
    assert data["read"] is True
    assert "read_at" in data
    assert data["read_at"] is not None


@pytest.mark.asyncio
async def test_mark_notification_as_read_not_found(patient_client: AsyncClient):
    """POST /api/v1/notifications/{id}/read returns 404 for non-existent notification."""
    fake_id = str(uuid.uuid4())
    response = await patient_client.post(f"/api/v1/notifications/{fake_id}/read")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_mark_notification_as_read_forbidden(patient_client: AsyncClient, db: AsyncSession):
    """Users cannot mark other users' notifications as read."""
    # Create another user with a notification
    other_user = User(
        keycloak_sub="other-user-456",
        email="other2@test.com",
        full_name="Other User 2",
        role="patient",
    )
    db.add(other_user)
    await db.commit()

    other_notification = Notification(
        user_id=other_user.id,
        type=NotificationType.SYSTEM,
        title="Other User's Notification",
        message="Cannot access",
        read=False,
    )
    db.add(other_notification)
    await db.commit()
    await db.refresh(other_notification)

    response = await patient_client.post(f"/api/v1/notifications/{other_notification.id}/read")
    assert response.status_code == 404  # Should act as if it doesn't exist


@pytest.mark.asyncio
async def test_mark_notification_as_unread(patient_client: AsyncClient, user_with_notifications):
    """POST /api/v1/notifications/{id}/unread marks notification as unread."""
    user, notifications = user_with_notifications
    read_notif = [n for n in notifications if n.read][0]

    response = await patient_client.post(f"/api/v1/notifications/{read_notif.id}/unread")
    assert response.status_code == 200

    data = response.json()
    assert data["read"] is False
    assert data["read_at"] is None


@pytest.mark.asyncio
async def test_mark_all_as_read(patient_client: AsyncClient, user_with_notifications):
    """POST /api/v1/notifications/read-all marks all notifications as read."""
    user, notifications = user_with_notifications

    response = await patient_client.post("/api/v1/notifications/read-all")
    assert response.status_code == 200

    # Verify all notifications are now read
    response = await patient_client.get("/api/v1/notifications/unread-count")
    data = response.json()
    assert data["count"] == 0


@pytest.mark.asyncio
async def test_delete_notification(patient_client: AsyncClient, user_with_notifications):
    """DELETE /api/v1/notifications/{id} soft deletes notification."""
    user, notifications = user_with_notifications
    notif_to_delete = notifications[0]

    response = await patient_client.delete(f"/api/v1/notifications/{notif_to_delete.id}")
    assert response.status_code == 204

    # Verify notification is not in list anymore
    response = await patient_client.get("/api/v1/notifications")
    data = response.json()
    assert data["total"] == 3  # One less
    notif_ids = [n["id"] for n in data["notifications"]]
    assert str(notif_to_delete.id) not in notif_ids


@pytest.mark.asyncio
async def test_delete_notification_not_found(patient_client: AsyncClient):
    """DELETE /api/v1/notifications/{id} returns 404 for non-existent notification."""
    fake_id = str(uuid.uuid4())
    response = await patient_client.delete(f"/api/v1/notifications/{fake_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_all_read_notifications(patient_client: AsyncClient, user_with_notifications):
    """DELETE /api/v1/notifications/read deletes all read notifications."""
    user, notifications = user_with_notifications

    # One notification is read
    response = await patient_client.delete("/api/v1/notifications/read")
    assert response.status_code == 200

    data = response.json()
    assert "deleted_count" in data
    assert data["deleted_count"] == 1

    # Verify total is now 3
    response = await patient_client.get("/api/v1/notifications")
    data = response.json()
    assert data["total"] == 3


@pytest.mark.asyncio
async def test_get_notification_preferences_default(patient_client: AsyncClient, patient_user: User):
    """GET /api/v1/notifications/preferences returns default preferences if none exist."""
    response = await patient_client.get("/api/v1/notifications/preferences")
    assert response.status_code == 200

    data = response.json()
    # Should return default preferences
    assert isinstance(data, dict)


@pytest.mark.asyncio
async def test_update_notification_preferences(patient_client: AsyncClient, patient_user: User):
    """PUT /api/v1/notifications/preferences creates or updates preferences."""
    preferences = {
        "email_notifications": True,
        "push_notifications": False,
        "appointment_reminders": True,
        "lab_results": True,
        "prescription_alerts": False,
    }

    response = await patient_client.put("/api/v1/notifications/preferences", json=preferences)
    assert response.status_code == 200

    data = response.json()
    assert data["email_notifications"] is True
    assert data["push_notifications"] is False

    # Verify preferences are persisted
    response = await patient_client.get("/api/v1/notifications/preferences")
    data = response.json()
    assert data["email_notifications"] is True
    assert data["appointment_reminders"] is True


@pytest.mark.asyncio
async def test_soft_delete_filtering(db: AsyncSession, patient_user: User, patient_client: AsyncClient):
    """Soft deleted notifications are not returned in API responses."""
    # Create a notification
    notif = Notification(
        user_id=patient_user.id,
        type=NotificationType.SYSTEM,
        title="Test Notification",
        message="Test message",
        read=False,
    )
    db.add(notif)
    await db.commit()
    await db.refresh(notif)

    # Soft delete it
    notif.deleted_at = datetime.now()
    await db.commit()

    # Should not appear in API results
    response = await patient_client.get("/api/v1/notifications")
    data = response.json()
    assert data["total"] == 0
