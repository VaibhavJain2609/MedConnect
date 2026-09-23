"""
Tests for the provider-agnostic comm adapters (app/services/comms).

Covers:
- NullProvider is the default (flags off / no creds) and always skips.
- TwilioProvider request shape (URL, basic auth, form body, whatsapp:
  address prefixes) with httpx mocked out.
- get_comm_provider() flag/credential selection.
- notification_channels routes sms/whatsapp through the comm layer when
  SMS_ENABLED / WHATSAPP_ENABLED are set, and through the legacy
  MSG91/Meta adapters otherwise.
- PHI minimisation: sms/whatsapp receive the generic channel_bodies
  override, never the full PHI-bearing reminder body.

No DB fixtures needed — channel sends are exercised with prefs passed
explicitly and a lightweight user namespace.
"""
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.config import settings
from app.services import notification_channels
from app.services.comms import (
    CommResult,
    NullProvider,
    TwilioProvider,
    get_comm_provider,
    to_e164,
)
from app.services.comms.base import CommProvider
from app.workers.tasks.appointment_reminders import comms_reminder_body


def _user(phone: str | None = "+91 98765-43210") -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4(), phone=phone, email=None)


class _FakeResponse:
    def __init__(self, status_code: int = 201, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {"sid": "SMdeadbeef"}

    def json(self):
        return self._payload


def _mock_http_client(response: _FakeResponse | None = None) -> AsyncMock:
    """AsyncMock standing in for httpx.AsyncClient (async context manager)."""
    client = AsyncMock()
    client.post = AsyncMock(return_value=response or _FakeResponse())
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


def _twilio_creds(monkeypatch) -> None:
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "AC123")
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "secret-token")
    monkeypatch.setattr(settings, "TWILIO_FROM_NUMBER", "+15551234567")
    monkeypatch.setattr(settings, "TWILIO_WHATSAPP_FROM", "+15557654321")


# ----------------------------------------------------------------------
# to_e164
# ----------------------------------------------------------------------


def test_to_e164_normalises_numbers():
    assert to_e164("+91 98765-43210") == "+919876543210"
    assert to_e164("9876543210") == "+9876543210"
    assert to_e164("(555) 123-4567") == "+5551234567"
    assert to_e164(None) is None
    assert to_e164("") is None
    assert to_e164("no digits") is None


# ----------------------------------------------------------------------
# Factory selection
# ----------------------------------------------------------------------


def test_factory_returns_null_when_flags_off():
    assert isinstance(get_comm_provider(), NullProvider)


def test_factory_returns_null_when_flag_on_but_no_creds(monkeypatch):
    monkeypatch.setattr(settings, "SMS_ENABLED", True)
    # Twilio creds intentionally unset -> still NullProvider, never raises.
    assert isinstance(get_comm_provider(), NullProvider)


def test_factory_returns_twilio_when_flag_and_creds(monkeypatch):
    monkeypatch.setattr(settings, "SMS_ENABLED", True)
    _twilio_creds(monkeypatch)
    provider = get_comm_provider()
    assert isinstance(provider, TwilioProvider)
    assert isinstance(provider, CommProvider)


def test_factory_returns_twilio_for_whatsapp_only(monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_ENABLED", True)
    _twilio_creds(monkeypatch)
    assert isinstance(get_comm_provider(), TwilioProvider)


# ----------------------------------------------------------------------
# NullProvider
# ----------------------------------------------------------------------


async def test_null_provider_skips_sms():
    result = await NullProvider().send_sms("+15551234567", "hello")
    assert result.status == "skipped"
    assert result.reason == "provider_not_configured"
    assert result.channel == "sms"


async def test_null_provider_skips_whatsapp():
    result = await NullProvider().send_whatsapp("+15551234567", "hello")
    assert result.status == "skipped"
    assert result.reason == "provider_not_configured"
    assert result.channel == "whatsapp"


# ----------------------------------------------------------------------
# TwilioProvider request shape
# ----------------------------------------------------------------------


async def test_twilio_sms_request_shape(monkeypatch):
    monkeypatch.setattr(settings, "SMS_ENABLED", True)
    provider = TwilioProvider(
        account_sid="AC123",
        auth_token="secret-token",
        from_number="+15551234567",
    )
    client = _mock_http_client()
    with patch(
        "app.services.comms.twilio.httpx.AsyncClient", return_value=client
    ):
        result = await provider.send_sms("+919876543210", "generic body")

    assert result.status == "sent"
    assert result.provider_message_id == "SMdeadbeef"
    client.post.assert_awaited_once()
    call = client.post.await_args
    assert (
        call.args[0]
        == "https://api.twilio.com/2010-04-01/Accounts/AC123/Messages.json"
    )
    assert call.kwargs["auth"] == ("AC123", "secret-token")
    assert call.kwargs["data"] == {
        "To": "+919876543210",
        "From": "+15551234567",
        "Body": "generic body",
    }


async def test_twilio_whatsapp_uses_whatsapp_scheme(monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_ENABLED", True)
    provider = TwilioProvider(
        account_sid="AC123",
        auth_token="secret-token",
        whatsapp_from="+15557654321",
    )
    client = _mock_http_client()
    with patch(
        "app.services.comms.twilio.httpx.AsyncClient", return_value=client
    ):
        result = await provider.send_whatsapp("+919876543210", "generic body")

    assert result.status == "sent"
    data = client.post.await_args.kwargs["data"]
    assert data["To"] == "whatsapp:+919876543210"
    assert data["From"] == "whatsapp:+15557654321"
    assert data["Body"] == "generic body"


async def test_twilio_sms_skipped_when_flag_off(monkeypatch):
    monkeypatch.setattr(settings, "SMS_ENABLED", False)
    provider = TwilioProvider(
        account_sid="AC123", auth_token="t", from_number="+15551234567"
    )
    client = _mock_http_client()
    with patch(
        "app.services.comms.twilio.httpx.AsyncClient", return_value=client
    ):
        result = await provider.send_sms("+919876543210", "body")
    assert result.status == "skipped"
    assert result.reason == "channel_disabled"
    client.post.assert_not_awaited()


async def test_twilio_sms_skipped_without_from_number(monkeypatch):
    monkeypatch.setattr(settings, "SMS_ENABLED", True)
    provider = TwilioProvider(account_sid="AC123", auth_token="t")
    result = await provider.send_sms("+919876543210", "body")
    assert result.status == "skipped"
    assert result.reason == "provider_not_configured"


async def test_twilio_http_error_maps_to_failed(monkeypatch):
    monkeypatch.setattr(settings, "SMS_ENABLED", True)
    provider = TwilioProvider(
        account_sid="AC123", auth_token="t", from_number="+15551234567"
    )
    client = _mock_http_client(_FakeResponse(status_code=401, payload={}))
    with patch(
        "app.services.comms.twilio.httpx.AsyncClient", return_value=client
    ):
        result = await provider.send_sms("+919876543210", "body")
    assert result.status == "failed"
    assert result.reason == "provider_http_401"


async def test_twilio_transport_error_maps_to_failed(monkeypatch):
    monkeypatch.setattr(settings, "SMS_ENABLED", True)
    provider = TwilioProvider(
        account_sid="AC123", auth_token="t", from_number="+15551234567"
    )
    client = _mock_http_client()
    client.post = AsyncMock(side_effect=RuntimeError("boom"))
    with patch(
        "app.services.comms.twilio.httpx.AsyncClient", return_value=client
    ):
        result = await provider.send_sms("+919876543210", "body")
    assert result.status == "failed"
    assert result.reason == "send_error"


# ----------------------------------------------------------------------
# Channel routing in notification_channels
# ----------------------------------------------------------------------


async def test_sms_channel_routes_through_comm_provider(monkeypatch):
    """SMS_ENABLED -> send() dispatches via get_comm_provider, E.164-normalised."""
    monkeypatch.setattr(settings, "SMS_ENABLED", True)
    provider = AsyncMock()
    provider.send_sms = AsyncMock(
        return_value=CommResult(channel="sms", status="sent")
    )
    monkeypatch.setattr(
        notification_channels, "get_comm_provider", lambda: provider
    )

    result = await notification_channels.send(
        _user(phone="(91) 98765 43210"),
        "sms",
        "Title",
        "full body",
        db=None,
        prefs={"sms_notifications": True},
    )

    assert result.status == "sent"
    provider.send_sms.assert_awaited_once_with("+919876543210", "full body")


async def test_sms_channel_falls_back_to_msg91_when_flag_off(monkeypatch):
    """SMS_ENABLED off -> legacy MSG91 adapter still owns the channel."""
    monkeypatch.setattr(settings, "SMS_ENABLED", False)
    msg91_send = AsyncMock(
        return_value=notification_channels.ChannelResult(
            channel="sms", status="sent"
        )
    )
    monkeypatch.setattr(notification_channels.sms_provider, "send", msg91_send)
    comm = AsyncMock()
    monkeypatch.setattr(notification_channels, "get_comm_provider", lambda: comm)

    result = await notification_channels.send(
        _user(),
        "sms",
        "Title",
        "body",
        db=None,
        prefs={"sms_notifications": True},
    )

    assert result.status == "sent"
    msg91_send.assert_awaited_once()
    comm.send_sms.assert_not_called()


async def test_whatsapp_channel_routes_through_comm_provider(monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_ENABLED", True)
    provider = AsyncMock()
    provider.send_whatsapp = AsyncMock(
        return_value=CommResult(channel="whatsapp", status="sent")
    )
    monkeypatch.setattr(
        notification_channels, "get_comm_provider", lambda: provider
    )

    result = await notification_channels.send(
        _user(),
        "whatsapp",
        "Title",
        "body",
        db=None,
        prefs={"whatsapp_notifications": True},
    )

    assert result.status == "sent"
    provider.send_whatsapp.assert_awaited_once_with("+919876543210", "body")


async def test_sms_channel_skips_without_phone(monkeypatch):
    monkeypatch.setattr(settings, "SMS_ENABLED", True)
    provider = AsyncMock()
    monkeypatch.setattr(
        notification_channels, "get_comm_provider", lambda: provider
    )

    result = await notification_channels.send(
        _user(phone=None),
        "sms",
        "Title",
        "body",
        db=None,
        prefs={"sms_notifications": True},
    )

    assert result.status == "skipped"
    assert result.reason == "no_recipient"
    provider.send_sms.assert_not_called()


async def test_sms_channel_respects_pref_opt_out(monkeypatch):
    """Channel pref still gates before the provider is consulted."""
    monkeypatch.setattr(settings, "SMS_ENABLED", True)
    provider = AsyncMock()
    monkeypatch.setattr(
        notification_channels, "get_comm_provider", lambda: provider
    )

    result = await notification_channels.send(
        _user(),
        "sms",
        "Title",
        "body",
        db=None,
        prefs={"sms_notifications": False},
    )

    assert result.status == "skipped"
    assert result.reason == "channel_disabled"
    provider.send_sms.assert_not_called()


# ----------------------------------------------------------------------
# PHI minimisation
# ----------------------------------------------------------------------


def test_comms_reminder_body_is_phi_free():
    """The sms/whatsapp body carries clinic + time only — no names/PHI."""
    body = comms_reminder_body("City Heart Clinic", "01 Jan 2026 at 10:00 AM IST")
    assert "City Heart Clinic" in body
    assert "01 Jan 2026 at 10:00 AM IST" in body
    # Names / clinical terms must never appear — the helper doesn't accept
    # them, so this guards the template itself.
    for forbidden in ("Dr", "Patient", "diagnos", "medicine", "http"):
        assert forbidden not in body


def test_comms_reminder_body_falls_back_when_no_clinic():
    body = comms_reminder_body(None, "01 Jan 2026 at 10:00 AM IST")
    assert "your clinic" in body


async def test_channel_bodies_override_reaches_sms_not_full_body(monkeypatch):
    """
    The reminder worker passes channel_bodies so sms/whatsapp get the
    generic text while other channels keep the full body — assert the
    provider never sees the PHI-bearing body.
    """
    monkeypatch.setattr(settings, "SMS_ENABLED", True)
    provider = AsyncMock()
    provider.send_sms = AsyncMock(
        return_value=CommResult(channel="sms", status="sent")
    )
    monkeypatch.setattr(
        notification_channels, "get_comm_provider", lambda: provider
    )

    full_body = "Reminder: Jane Doe, your appointment with Dr Smith is in 2 hour(s)."
    generic = comms_reminder_body("City Clinic", "01 Jan 2026 at 10:00 AM IST")

    result = await notification_channels.send(
        _user(),
        "sms",
        "Appointment in 2 hour(s)",
        full_body,
        db=None,
        prefs={"sms_notifications": True},
        channel_bodies={"sms": generic},
    )

    assert result.status == "sent"
    provider.send_sms.assert_awaited_once_with("+919876543210", generic)
    sent_body = provider.send_sms.await_args.args[1]
    assert "Jane Doe" not in sent_body
    assert "Dr Smith" not in sent_body
