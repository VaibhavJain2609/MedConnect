import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PushSubscription(Base):
    """A Web Push (Push API) subscription for one user + browser/device.

    Rows are upserted by `endpoint` — the push-service URL uniquely identifies
    a browser subscription, so re-subscribing the same device refreshes the
    keys and re-links it to the current user instead of creating a duplicate.

    `p256dh` / `auth` are the client's encryption secrets from
    `PushSubscription.keys` — required to encrypt payloads for that endpoint.
    They are credentials, not PHI, but must still never appear in logs.
    """

    __tablename__ = "push_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    # Push-service URL — globally unique per browser subscription.
    endpoint: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    p256dh: Mapped[str] = mapped_column(String(255), nullable=False)
    auth: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index(
            "idx_push_subscriptions_user",
            "user_id",
            postgresql_where=(deleted_at.is_(None)),
        ),
    )
