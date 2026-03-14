import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PatientClinicLink(Base):
    __tablename__ = "patient_clinic_links"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    clinic_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False)
    linked_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    consent_status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | approved | revoked
    consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    patient: Mapped["User"] = relationship(foreign_keys=[patient_id])
    clinic: Mapped["Clinic"] = relationship()
    linker: Mapped["User"] = relationship(foreign_keys=[linked_by])

    __table_args__ = (
        UniqueConstraint("patient_id", "clinic_id", name="uq_patient_clinic_link"),
        Index("idx_pcl_patient", "patient_id", postgresql_where=(deleted_at.is_(None))),
        Index("idx_pcl_clinic", "clinic_id", postgresql_where=(deleted_at.is_(None))),
    )


class PatientLinkCode(Base):
    __tablename__ = "patient_link_codes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True)
    code: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    patient: Mapped["User"] = relationship()

    __table_args__ = (
        Index("idx_plc_patient", "patient_id", postgresql_where=(deleted_at.is_(None))),
        Index("idx_plc_code", "code", postgresql_where=(deleted_at.is_(None))),
    )
