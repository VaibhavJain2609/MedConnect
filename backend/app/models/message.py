import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MessageThread(Base):
    """A secure messaging thread between one patient and one clinic.

    ``clinic_id`` is nullable so a patient's threads survive clinic deletion
    (FK is SET NULL at the DB level); clinic-side reads require an active
    membership via the ``X-Clinic-Id`` context, so orphaned threads simply
    become patient-only history.

    Read state is per side, not per user: ``patient_last_seen_at`` tracks the
    patient, ``clinic_last_seen_at`` is shared by all clinic staff. This keeps
    unread-badge math to a simple ``created_at > last_seen`` comparison.
    """

    __tablename__ = "message_threads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    clinic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id", ondelete="SET NULL"), nullable=True
    )
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")  # open | closed
    patient_last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    clinic_last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    patient: Mapped["User"] = relationship(foreign_keys=[patient_id])
    clinic: Mapped["Clinic"] = relationship(foreign_keys=[clinic_id])
    messages: Mapped[list["ThreadMessage"]] = relationship(back_populates="thread")

    __table_args__ = (
        Index("idx_threads_patient", "patient_id", postgresql_where=(deleted_at.is_(None))),
        Index("idx_threads_clinic", "clinic_id", postgresql_where=(deleted_at.is_(None))),
    )


class ThreadMessage(Base):
    """One message inside a MessageThread. Immutable by design — no edit
    endpoint exists; soft-delete is retained only for moderation/compliance."""

    __tablename__ = "thread_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("message_threads.id"), nullable=False
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    thread: Mapped["MessageThread"] = relationship(back_populates="messages")
    sender: Mapped["User"] = relationship(foreign_keys=[sender_id])

    __table_args__ = (
        Index(
            "idx_thread_messages_thread",
            "thread_id",
            "created_at",
            postgresql_where=(deleted_at.is_(None)),
        ),
    )
