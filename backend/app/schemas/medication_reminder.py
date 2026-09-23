import re
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

_TIME_RE = re.compile(r"^([01][0-9]|2[0-3]):[0-5][0-9]$")


def _normalise_times(v: list[str]) -> list[str]:
    """Validate HH:MM entries, drop duplicates, sort chronologically."""
    if not v:
        raise ValueError("times_of_day must contain at least one time")
    if len(v) > 8:
        raise ValueError("times_of_day may contain at most 8 times")
    for t in v:
        if not isinstance(t, str) or not _TIME_RE.match(t):
            raise ValueError(f"invalid time {t!r} — expected 24h 'HH:MM'")
    return sorted(set(v))


class MedicationReminderCreate(BaseModel):
    """Enable (or replace) a reminder schedule on one of the patient's prescriptions."""

    prescription_id: UUID
    times_of_day: list[str] = Field(min_length=1, max_length=8)
    enabled: bool = True

    @field_validator("times_of_day")
    @classmethod
    def _check_times(cls, v: list[str]) -> list[str]:
        return _normalise_times(v)


class MedicationReminderUpdate(BaseModel):
    """Partial update — change the schedule and/or pause the reminder."""

    times_of_day: Optional[list[str]] = Field(default=None, min_length=1, max_length=8)
    enabled: Optional[bool] = None

    @field_validator("times_of_day")
    @classmethod
    def _check_times(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is None:
            return v
        return _normalise_times(v)
