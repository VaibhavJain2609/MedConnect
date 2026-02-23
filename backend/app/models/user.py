import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(15), unique=True, nullable=True)
    keycloak_sub: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # patient, doctor, admin
    language_pref: Mapped[str] = mapped_column(String(10), default="en")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    doctor_profile: Mapped["Doctor"] = relationship(back_populates="user", uselist=False)
    records_as_patient: Mapped[list["MedicalRecord"]] = relationship(
        back_populates="patient", foreign_keys="MedicalRecord.patient_id"
    )

    __table_args__ = (
        Index("idx_users_email", "email", postgresql_where=(deleted_at.is_(None))),
        Index("idx_users_phone", "phone", postgresql_where=(deleted_at.is_(None))),
        Index("idx_users_role", "role", postgresql_where=(deleted_at.is_(None))),
    )
