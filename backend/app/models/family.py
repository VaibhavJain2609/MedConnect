import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm import relationship as orm_relationship

from app.database import Base

# Dependents are data profiles owned by a patient account — NOT full users.
# Validated at the API layer (app/schemas/family.py); kept in sync here for
# the migration CHECK constraint.
FAMILY_RELATIONSHIPS = ["child", "spouse", "parent", "sibling", "other"]


class FamilyMember(Base):
    __tablename__ = "family_members"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    dob: Mapped[date] = mapped_column(Date, nullable=False)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    relationship: Mapped[str] = mapped_column(String(20), nullable=False)
    blood_group: Mapped[str | None] = mapped_column(String(5), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Column named `relationship` shadows sqlalchemy.orm.relationship in the
    # class body, hence the orm_relationship alias.
    owner: Mapped["User"] = orm_relationship(back_populates="family_members")

    __table_args__ = (
        Index("idx_family_members_owner", "owner_user_id", postgresql_where=(deleted_at.is_(None))),
    )
