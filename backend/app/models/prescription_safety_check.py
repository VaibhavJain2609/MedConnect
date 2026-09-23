"""Persisted clinical-safety check snapshot for a prescription.

One row is written per successful prescription creation (R13) capturing what
the safety gate evaluated and what it surfaced, so the alerted/overridden
history is auditable after the fact via
``GET /api/v1/prescriptions/{id}/safety-check``.

PHI note: ``items_json`` and ``alerts_json`` embed brand/salt/medicine names —
clinical data that already lives verbatim on the ``prescriptions.medicines``
JSONB column, so persisting the snapshot in the main DB is acceptable. The row
carries no patient identifiers beyond the prescription FK.

Unlike the per-(item, salt) ``PrescriptionAudit`` rows in the medicine DB,
this table is a single per-prescription JSON snapshot of the gate output —
the source of truth for "which alerts were shown / overridden at issue time".

No ``deleted_at``: rows are immutable audit data, hard-deleted only via the
``ON DELETE CASCADE`` FK if a prescription row is ever removed.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PrescriptionSafetyCheck(Base):
    __tablename__ = "prescription_safety_checks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prescription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prescriptions.id", ondelete="CASCADE"),
        nullable=False,
    )
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Snapshot of the medicine items the gate evaluated (as submitted).
    items_json: Mapped[list] = mapped_column(JSONB, nullable=False)
    # Computed alerts: [{severity, kind, detail, salts?, salt_ids?, medicine?, ...}]
    alerts_json: Mapped[list] = mapped_column(JSONB, nullable=False)
    # Set when a "major" alert was overridden via safety_override_reason.
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_rx_safety_checks_prescription", "prescription_id", "checked_at"),
    )
