import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

ReminderTypeEnum = Enum("24h", "2h", name="reminder_type_enum")
# NOTE: "log" is retained for backwards compatibility with rows written before
# real channel dispatch existed; new rows always use a real channel value.
# DB-side enum values must be added via an Alembic migration
# (ALTER TYPE reminder_channel_enum ADD VALUE ...).
ChannelEnum = Enum("in_app", "log", "email", "sms", "whatsapp", name="reminder_channel_enum")
ReminderStatusEnum = Enum("pending", "sent", "failed", "skipped", name="reminder_status_enum")


class ReminderLog(Base):
    __tablename__ = "reminder_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    appointment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("appointments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reminder_type: Mapped[str] = mapped_column(
        ReminderTypeEnum,
        nullable=False,
    )
    channel: Mapped[str] = mapped_column(
        ChannelEnum,
        nullable=False,
        default="log",
        server_default="log",
    )
    status: Mapped[str] = mapped_column(
        ReminderStatusEnum,
        nullable=False,
        default="pending",
        server_default="pending",
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        # One reminder of each type per appointment per channel — prevents
        # duplicate sends while allowing one log row per attempted channel.
        UniqueConstraint(
            "appointment_id",
            "reminder_type",
            "channel",
            name="uq_reminder_log_appointment_type",
        ),
    )
