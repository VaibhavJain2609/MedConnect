"""Web Push channel: subscription endpoints, VAPID config, provider dispatch."""
import uuid
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.notification import NotificationPreferences
from app.models.push_subscription import PushSubscription
from app.models.user import User
from app.services import notification_channels
from app.services.providers import webpush as webpush_provider

ENDPOINT = "https://push.example.com/sub/abc123"
SUBSCRIBE_PAYLOAD = {
    "endpoint": ENDPOINT,
    "keys": {"p256dh": "test-p256dh-key", "auth": "test-auth-secret"},
}


@pytest.fixture
def vapid_configured(monkeypatch):
    """Pretend VAPID is fully configured."""
    monkeypatch.setattr(settings, "VAPID_SUBJECT", "mailto:ops@test.com")
    monkeypatch.setattr(settings, "VAPID_PRIVATE_KEY", "test-private-key")
    monkeypatch.setattr(settings, "VAPID_PUBLIC_KEY", "test-public-key")


# ---------------------------------------------------------------------------
# Subscription endpoints
# ---------------------------------------------------------------------------


class TestSubscribe:
    async def test_subscribe_creates_row(
        self, patient_client: AsyncClient, patient_user: User, db: AsyncSession
    ):
        res = await patient_client.post("/api/v1/push/subscribe", json=SUBSCRIBE_PAYLOAD)
        assert res.status_code == 201, res.text

        row = (
            await db.execute(
                select(PushSubscription).where(PushSubscription.endpoint == ENDPOINT)
            )
        ).scalar_one()
        assert row.user_id == patient_user.id
        assert row.p256dh == "test-p256dh-key"
        assert row.deleted_at is None

    async def test_subscribe_upserts_by_endpoint(
        self, patient_client: AsyncClient, db: AsyncSession
    ):
        await patient_client.post("/api/v1/push/subscribe", json=SUBSCRIBE_PAYLOAD)
        rotated = {
            "endpoint": ENDPOINT,
            "keys": {"p256dh": "rotated-p256dh", "auth": "rotated-auth"},
        }
        res = await patient_client.post("/api/v1/push/subscribe", json=rotated)
        assert res.status_code == 201, res.text

        rows = (
            (await db.execute(select(PushSubscription))).scalars().all()
        )
        assert len(rows) == 1  # same endpoint -> same row, refreshed keys
        assert rows[0].p256dh == "rotated-p256dh"
        assert rows[0].auth == "rotated-auth"

    async def test_subscribe_revives_soft_deleted(
        self, patient_client: AsyncClient, db: AsyncSession
    ):
        await patient_client.post("/api/v1/push/subscribe", json=SUBSCRIBE_PAYLOAD)
        await patient_client.request(
            "DELETE", "/api/v1/push/subscribe", json={"endpoint": ENDPOINT}
        )
        res = await patient_client.post("/api/v1/push/subscribe", json=SUBSCRIBE_PAYLOAD)
        assert res.status_code == 201, res.text

        row = (
            await db.execute(
                select(PushSubscription).where(PushSubscription.endpoint == ENDPOINT)
            )
        ).scalar_one()
        assert row.deleted_at is None

    async def test_subscribe_requires_auth(self, client: AsyncClient):
        res = await client.post("/api/v1/push/subscribe", json=SUBSCRIBE_PAYLOAD)
        assert res.status_code == 401


class TestUnsubscribe:
    async def test_unsubscribe_soft_deletes(
        self, patient_client: AsyncClient, db: AsyncSession
    ):
        await patient_client.post("/api/v1/push/subscribe", json=SUBSCRIBE_PAYLOAD)
        res = await patient_client.request(
            "DELETE", "/api/v1/push/subscribe", json={"endpoint": ENDPOINT}
        )
        assert res.status_code == 200, res.text

        row = (
            await db.execute(
                select(PushSubscription).where(PushSubscription.endpoint == ENDPOINT)
            )
        ).scalar_one()
        assert row.deleted_at is not None

    async def test_unsubscribe_unknown_endpoint_404(self, patient_client: AsyncClient):
        res = await patient_client.request(
            "DELETE", "/api/v1/push/subscribe", json={"endpoint": ENDPOINT}
        )
        assert res.status_code == 404
        assert res.json()["error"]["code"] == "NOT_FOUND"

    async def test_unsubscribe_only_own_rows(
        self,
        patient_client: AsyncClient,
        db: AsyncSession,
    ):
        """A user cannot delete another user's subscription row."""
        other = User(
            keycloak_sub="other-1", email="o@t.com", full_name="Other", role="patient"
        )
        db.add(other)
        await db.flush()
        db.add(
            PushSubscription(
                id=uuid.uuid4(),
                user_id=other.id,
                endpoint=ENDPOINT,
                p256dh="k",
                auth="a",
            )
        )
        await db.commit()

        res = await patient_client.request(
            "DELETE", "/api/v1/push/subscribe", json={"endpoint": ENDPOINT}
        )
        assert res.status_code == 404
        row = (
            await db.execute(
                select(PushSubscription).where(PushSubscription.endpoint == ENDPOINT)
            )
        ).scalar_one()
        assert row.deleted_at is None


class TestVapidPublicKey:
    async def test_unconfigured_returns_404(self, patient_client: AsyncClient):
        res = await patient_client.get("/api/v1/push/vapid-public")
        assert res.status_code == 404
        assert res.json()["error"]["code"] == "PUSH_NOT_CONFIGURED"

    async def test_configured_returns_key(
        self, patient_client: AsyncClient, vapid_configured
    ):
        res = await patient_client.get("/api/v1/push/vapid-public")
        assert res.status_code == 200
        assert res.json() == {"public_key": "test-public-key"}


# ---------------------------------------------------------------------------
# Provider + channel dispatch
# ---------------------------------------------------------------------------


class TestWebpushProvider:
    async def test_skips_when_unconfigured(
        self, patient_user: User, db: AsyncSession
    ):
        result = await webpush_provider.send(patient_user, "Hi", db=db)
        assert result.status == "skipped"
        assert result.reason == "provider_not_configured"

    async def test_skips_no_subscriptions(
        self, patient_user: User, db: AsyncSession, vapid_configured
    ):
        result = await webpush_provider.send(patient_user, "Hi", db=db)
        assert result.status == "skipped"
        assert result.reason == "no_recipient"

    async def test_dispatch_calls_pywebpush(
        self, patient_user: User, db: AsyncSession, vapid_configured
    ):
        db.add(
            PushSubscription(
                id=uuid.uuid4(),
                user_id=patient_user.id,
                endpoint=ENDPOINT,
                p256dh="p256",
                auth="auth",
            )
        )
        await db.commit()

        resp = MagicMock()
        resp.status_code = 201
        with patch("pywebpush.webpush", return_value=resp) as mock_webpush:
            result = await notification_channels.send(
                patient_user,
                "push",
                "Appointment in 24 hours",
                "Body must NOT be pushed",
                db=db,
                action_url="/patient/appointments",
            )

        assert result.status == "sent"
        assert result.channel == "push"
        mock_webpush.assert_called_once()
        kwargs = mock_webpush.call_args.kwargs
        assert kwargs["subscription_info"] == {
            "endpoint": ENDPOINT,
            "keys": {"p256dh": "p256", "auth": "auth"},
        }
        assert kwargs["vapid_private_key"] == "test-private-key"
        # Payload carries title + url only — never the body (PHI).
        assert "Appointment in 24 hours" in kwargs["data"]
        assert "Body must NOT be pushed" not in kwargs["data"]

    async def test_gone_endpoint_soft_deleted(
        self, patient_user: User, db: AsyncSession, vapid_configured
    ):
        sub = PushSubscription(
            id=uuid.uuid4(),
            user_id=patient_user.id,
            endpoint=ENDPOINT,
            p256dh="p256",
            auth="auth",
        )
        db.add(sub)
        await db.commit()

        resp = MagicMock()
        resp.status_code = 410
        with patch("pywebpush.webpush", return_value=resp):
            result = await webpush_provider.send(patient_user, "Hi", db=db)

        assert result.status == "failed"
        assert sub.deleted_at is not None

    async def test_channel_disabled_by_pref(
        self, patient_user: User, db: AsyncSession, vapid_configured
    ):
        db.add(
            NotificationPreferences(
                user_id=patient_user.id, preferences={"push_notifications": False}
            )
        )
        await db.commit()
        result = await notification_channels.send(
            patient_user, "push", "t", "b", db=db
        )
        assert result.status == "skipped"
        assert result.reason == "channel_disabled"
