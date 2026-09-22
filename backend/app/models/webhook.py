"""Outbound webhook models — clinic-level integration endpoints + deliveries.

``webhook_endpoints`` holds per-clinic subscription config (target URL, HMAC
signing secret, subscribed event types). ``webhook_deliveries`` is the
append-only delivery log: one row per (endpoint, emitted event), updated by
the ARQ ``deliver_webhook`` task as pending → sent | failed.

PHI minimization: ``payload_json`` must only ever contain IDs, statuses and
timestamps — never names, diagnoses or free text. See RUNBOOK.md § webhooks.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# Event types emitted today (see app.services.webhook_service emit sites):
#   appointment.booked           — patient/guest/staff booking created
#   appointment.status_changed   — appointment status transition
#   prescription.issued          — prescription created
WEBHOOK_EVENT_TYPES = (
    "appointment.booked",
    "appointment.status_changed",
    "prescription.issued",
)

# webhook_deliveries.status values
DELIVERY_STATUSES = ("pending", "sent", "failed")


class WebhookEndpoint(Base):
    __tablename__ = "webhook_endpoints"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clinics.id", ondelete="CASCADE"),
        nullable=False,
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    # HMAC-SHA256 signing secret ("whsec_..."). Stored in plaintext because the
    # worker must compute request signatures; NEVER exposed in API responses
    # beyond the masked "whsec_****last4" form (returned in full only once, on
    # creation).
    secret: Mapped[str] = mapped_column(String(255), nullable=False)
    event_types: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_webhook_endpoints_clinic", "clinic_id", postgresql_where=(deleted_at.is_(None))),
    )


class WebhookDelivery(Base):
    """One delivery attempt record per endpoint per emitted event.

    Child table — no ``deleted_at`` (follows reminder_logs / billing_items
    convention: rows disappear only with a hard delete of the endpoint, which
    cascades).
    """

    __tablename__ = "webhook_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    endpoint_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("webhook_endpoints.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_webhook_deliveries_endpoint_id", "endpoint_id"),
        Index("ix_webhook_deliveries_status", "status"),
        Index("ix_webhook_deliveries_created", "created_at"),
    )
