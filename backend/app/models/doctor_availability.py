import uuid
from datetime import date, datetime, time

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Time, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# TIMEZONE ASSUMPTION (documented, revisit before multi-region launch):
# start_time / end_time are stored as NAIVE wall-clock times representing the
# clinic's local time (e.g. Asia/Kolkata). They are deliberately NOT
# timezone-aware UTC instants. Slot computation in routers/availability.py
# currently interprets them against timestamptz Appointment.scheduled_at
# values using UTC day boundaries — which is consistent with how the rest of
# the codebase treats appointment dates (see routers/appointments.py) and with
# clients that submit naive local ISO datetimes. A proper fix requires an
# explicit timezone column on Clinic and conversion at the API boundary.


class DoctorAvailability(Base):
    """A recurring weekly availability window for a doctor.

    One row = "every <weekday> from <start_time> to <end_time>, bookable in
    <slot_duration_minutes> chunks". weekday follows date.weekday():
    0=Monday .. 6=Sunday. clinic_id/branch_id scope the window to a specific
    clinic location; NULL clinic_id means the window applies generally.
    """

    __tablename__ = "doctor_availability"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doctor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("doctors.id"), nullable=False)
    clinic_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=True)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("clinic_branches.id"), nullable=True)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Monday .. 6=Sunday
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    slot_duration_minutes: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    doctor: Mapped["Doctor"] = relationship(foreign_keys=[doctor_id])
    clinic: Mapped["Clinic"] = relationship(foreign_keys=[clinic_id])
    branch: Mapped["ClinicBranch"] = relationship(foreign_keys=[branch_id])

    __table_args__ = (
        Index(
            "idx_doctor_availability_doctor_weekday",
            "doctor_id",
            "weekday",
            postgresql_where=(deleted_at.is_(None)),
        ),
        Index(
            "idx_doctor_availability_clinic",
            "clinic_id",
            postgresql_where=(deleted_at.is_(None)),
        ),
        CheckConstraint("weekday >= 0 AND weekday <= 6", name="ck_doctor_availability_weekday"),
        CheckConstraint("start_time < end_time", name="ck_doctor_availability_time_range"),
        CheckConstraint("slot_duration_minutes > 0", name="ck_doctor_availability_slot_duration"),
    )


class DoctorLeave(Base):
    """A full-day leave/block for a doctor — no bookable slots on that date.

    date is a naive calendar date in clinic-local time (same timezone
    assumption as DoctorAvailability above). One leave row per doctor+date;
    enforced by the partial unique index below.
    """

    __tablename__ = "doctor_leaves"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doctor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("doctors.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    doctor: Mapped["Doctor"] = relationship(foreign_keys=[doctor_id])

    __table_args__ = (
        Index(
            "uq_doctor_leaves_doctor_date",
            "doctor_id",
            "date",
            unique=True,
            postgresql_where=(deleted_at.is_(None)),
        ),
        Index(
            "idx_doctor_leaves_doctor",
            "doctor_id",
            postgresql_where=(deleted_at.is_(None)),
        ),
    )
