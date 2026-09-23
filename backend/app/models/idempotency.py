"""Idempotency-Key bookkeeping for unsafe POST endpoints.

One row per (key, user_id, endpoint):

- ``response_json`` NULL → the request is in-flight (claim row committed
  before the handler runs); a concurrent duplicate gets 409.
- ``response_json`` set → the stored response is replayed verbatim with an
  ``Idempotent-Replay: true`` header instead of re-running the handler.

Rows are single-use for ``app.idempotency.IDEMPOTENCY_TTL`` (24h); expired
rows are lazily deleted on read so a reused key re-processes normally.
No worker / TTL job required.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    # Composite PK — a client-generated key is only unique per caller +
    # endpoint, so the same UUID may legitimately exist for different
    # users or different operations.
    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    endpoint: Mapped[str] = mapped_column(String(255), primary_key=True)

    # SHA-256 of the raw request body — a key reused with a *different*
    # payload is rejected (409 IDEMPOTENCY_MISMATCH) rather than replayed.
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # NULL while the original request is still in-flight.
    response_json: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
