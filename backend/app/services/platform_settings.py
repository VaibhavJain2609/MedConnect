"""Read-side helpers for the platform_settings table.

Kept dependency-free of routers so workers/middleware can share it. Values are
JSONB; callers get the raw value or the supplied default.
"""
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform_setting import PlatformSetting

# Mirrors routers/admin/broadcast.py DEFAULT_SETTINGS — duplicated here so
# readers don't need the router module (and a missing row still gets a sane
# default, e.g. test DBs built from metadata without migrations).
DEFAULT_VALUES: dict[str, Any] = {
    "maintenance_mode": False,
    "registration_enabled": True,
    "reminder_channels_enabled": {"in_app": True, "email": False, "sms": False, "whatsapp": False},
    "max_upload_mb": 10,
}


async def get_setting(db: AsyncSession, key: str) -> Any:
    """Return the platform setting value, falling back to the known default."""
    row = await db.execute(
        select(PlatformSetting.value).where(PlatformSetting.key == key)
    )
    value = row.scalar_one_or_none()
    if value is None:
        return DEFAULT_VALUES.get(key)
    return value


async def platform_channel_enabled(db: AsyncSession, channel: str) -> bool:
    """Platform-level kill-switch for reminder channels (admin settings)."""
    channels = await get_setting(db, "reminder_channels_enabled")
    if isinstance(channels, dict):
        return bool(channels.get(channel, False))
    return bool(channels)
