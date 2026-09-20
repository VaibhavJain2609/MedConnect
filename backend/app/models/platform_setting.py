import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# Any JSON-serializable value
JSONValue = dict | list | str | int | float | bool | None


class PlatformSetting(Base):
    """Key/value platform configuration + feature flags.

    Rows are upserted by `key` (unique). `value` is arbitrary JSONB so both
    scalar flags (e.g. maintenance_mode: false) and structured config (e.g.
    reminder_channels_enabled: {"in_app": true, ...}) fit the same table.
    No soft delete — settings are updated in place, never deleted.
    """

    __tablename__ = "platform_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[JSONValue] = mapped_column(JSONB, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("key", name="uq_platform_settings_key"),
        Index("idx_platform_settings_key", "key"),
    )
