"""Tests for GET /api/v1/doctors/analytics — counts + doctor scoping."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment
from app.models.clinic import Clinic, ClinicMembership
from app.models.doctor import Doctor
from app.models.medical_record import MedicalRecord
from app.models.prescription import Prescription
from app.models.queue import QueueEntry
from app.models.user import User

pytestmark = pytest.mark.asyncio

ANALYTICS_URL = "/api/v1/doctors/analytics"
NOW = datetime.now(timezone.utc)


async def _make_other_doctor(db: AsyncSession) -> tuple[User, Doctor]:
    user = User(
        keycloak_sub=f"doctor-{uuid.uuid4()}",
        email="other-doctor@test.com",
        full_name="Other Doctor",
        role="doctor",
    )
    db.add(user)
    await db.flush()
    profile = Doctor(id=uuid.uuid4(), user_id=user.id)
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return user, profile


def _appointment(
    *,
    patient_id: uuid.UUID,
    doctor_id: uuid.UUID,
    created_by: uuid.UUID,
    status: str,
    scheduled_at: datetime,
) -> Appointment:
    return Appointment(
        id=uuid.uuid4(),
        patient_id=patient_id,
        doctor_id=doctor_id,
        scheduled_at=scheduled_at,
        duration_minutes=30,
        type="in-person",
        status=status,
        created_by=created_by,
    )


async def _make_prescription(
    db: AsyncSession,
    *,
    doctor_id: uuid.UUID,
    patient_id: uuid.UUID,
    medicines: list[dict],
) -> Prescription:
    record = MedicalRecord(
        patient_id=patient_id,
        doctor_id=doctor_id,
        record_type="prescription",
        title="Prescription",
    )
    db.add(record)
    await db.flush()
    rx = Prescription(
        id=uuid.uuid4(),
        record_id=record.id,
        doctor_id=doctor_id,
        patient_id=patient_id,
        medicines=medicines,
    )
    db.add(rx)
    await db.flush()
    return rx


def _med(brand_name: str) -> dict:
    return {
        "brand_name": brand_name,
        "dose": "500mg",
        "frequency": "BD",
        "duration": "5 days",
        "route": "oral",
    }


def _week_start(dt: datetime) -> str:
    """ISO week Monday (YYYY-MM-DD) matching the endpoint's buckets."""
    return (dt.date() - timedelta(days=dt.weekday())).isoformat()


# ---------------------------------------------------------------------------
# Auth / role gating
# ---------------------------------------------------------------------------


async def test_analytics_requires_auth(client: AsyncClient):
    resp = await client.get(ANALYTICS_URL)
    assert resp.status_code == 401


async def test_analytics_forbidden_for_patient(patient_client: AsyncClient):
    resp = await patient_client.get(ANALYTICS_URL)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Counts + doctor scoping
# ---------------------------------------------------------------------------


async def test_analytics_counts_and_doctor_scoping(
    doctor_client: AsyncClient,
    doctor_profile: Doctor,
    doctor_user: User,
    patient_user: User,
    db: AsyncSession,
):
    _, other_doctor = await _make_other_doctor(db)

    three_weeks_ago = NOW - timedelta(days=21)
    # This doctor's appointments
    db.add_all(
        [
            _appointment(
                patient_id=patient_user.id, doctor_id=doctor_profile.id,
                created_by=doctor_user.id, status="scheduled",
                scheduled_at=NOW + timedelta(days=1),
            ),
            _appointment(
                patient_id=patient_user.id, doctor_id=doctor_profile.id,
                created_by=doctor_user.id, status="scheduled",
                scheduled_at=NOW + timedelta(days=2),
            ),
            _appointment(
                patient_id=patient_user.id, doctor_id=doctor_profile.id,
                created_by=doctor_user.id, status="completed", scheduled_at=NOW,
            ),
            _appointment(
                patient_id=patient_user.id, doctor_id=doctor_profile.id,
                created_by=doctor_user.id, status="completed",
                scheduled_at=three_weeks_ago,
            ),
            _appointment(
                patient_id=patient_user.id, doctor_id=doctor_profile.id,
                created_by=doctor_user.id, status="cancelled",
                scheduled_at=NOW - timedelta(days=1),
            ),
            _appointment(
                patient_id=patient_user.id, doctor_id=doctor_profile.id,
                created_by=doctor_user.id, status="no-show",
                scheduled_at=NOW - timedelta(days=2),
            ),
            # Soft-deleted row — must be excluded
            Appointment(
                id=uuid.uuid4(), patient_id=patient_user.id,
                doctor_id=doctor_profile.id, scheduled_at=NOW,
                duration_minutes=30, type="in-person", status="completed",
                created_by=doctor_user.id, deleted_at=NOW,
            ),
            # Other doctor's appointments — must be excluded
            _appointment(
                patient_id=patient_user.id, doctor_id=other_doctor.id,
                created_by=other_doctor.user_id, status="completed",
                scheduled_at=NOW,
            ),
            _appointment(
                patient_id=patient_user.id, doctor_id=other_doctor.id,
                created_by=other_doctor.user_id, status="scheduled",
                scheduled_at=NOW + timedelta(days=1),
            ),
        ]
    )
    await db.commit()

    # This doctor's prescriptions: Crocin x2, Dolo x1
    await _make_prescription(
        db, doctor_id=doctor_profile.id, patient_id=patient_user.id,
        medicines=[_med("Crocin"), _med("Dolo")],
    )
    await _make_prescription(
        db, doctor_id=doctor_profile.id, patient_id=patient_user.id,
        medicines=[_med("Crocin")],
    )
    # Other doctor's prescription — must be excluded
    await _make_prescription(
        db, doctor_id=other_doctor.id, patient_id=patient_user.id,
        medicines=[_med("Augmentin"), _med("Crocin")],
    )
    await db.commit()

    resp = await doctor_client.get(ANALYTICS_URL)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    # Appointments by status — only this doctor's live rows
    assert data["appointments_by_status"] == {
        "scheduled": 2,
        "arrived": 0,
        "in-progress": 0,
        "completed": 2,
        "cancelled": 1,
        "no-show": 1,
    }

    # Weekly completions — 8 buckets, one completion in current week and
    # one in the week containing `three_weeks_ago`; everything else zero.
    weekly = data["weekly_completions"]
    assert len(weekly) == 8
    by_week = {w["week_start"]: w["count"] for w in weekly}
    assert by_week[_week_start(NOW)] == 1
    assert by_week[_week_start(three_weeks_ago)] == 1
    assert sum(by_week.values()) == 2

    # Top medicines — this doctor only (other doctor's Augmentin excluded,
    # and their Crocin does not inflate the count)
    assert data["top_medicines"] == [
        {"name": "Crocin", "count": 2},
        {"name": "Dolo", "count": 1},
    ]

    # No queue data seeded / no clinic header — both keys omitted
    assert "avg_consult_minutes" not in data
    assert "queue_today" not in data


async def test_analytics_empty_for_new_doctor(doctor_client: AsyncClient):
    resp = await doctor_client.get(ANALYTICS_URL)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["appointments_by_status"] == {
        "scheduled": 0,
        "arrived": 0,
        "in-progress": 0,
        "completed": 0,
        "cancelled": 0,
        "no-show": 0,
    }
    assert len(data["weekly_completions"]) == 8
    assert all(w["count"] == 0 for w in data["weekly_completions"])
    assert data["top_medicines"] == []
    assert "avg_consult_minutes" not in data
    assert "queue_today" not in data


# ---------------------------------------------------------------------------
# Queue stats (clinic context) + avg consult duration
# ---------------------------------------------------------------------------


async def test_analytics_queue_today_and_avg_consult(
    doctor_client: AsyncClient,
    doctor_profile: Doctor,
    doctor_user: User,
    patient_user: User,
    db: AsyncSession,
):
    clinic = Clinic(id=uuid.uuid4(), name="Analytics Clinic")
    db.add(clinic)
    await db.flush()
    db.add(
        ClinicMembership(
            clinic_id=clinic.id, user_id=doctor_user.id,
            role="doctor", is_active=True,
        )
    )

    other_user, other_doctor = await _make_other_doctor(db)
    db.add(
        ClinicMembership(
            clinic_id=clinic.id, user_id=other_user.id,
            role="doctor", is_active=True,
        )
    )
    await db.flush()

    db.add_all(
        [
            # This doctor: 1 waiting + 2 completed (20 min and 10 min consults)
            QueueEntry(
                id=uuid.uuid4(), clinic_id=clinic.id,
                patient_id=patient_user.id, doctor_id=doctor_profile.id,
                queue_number=1, status="waiting",
            ),
            QueueEntry(
                id=uuid.uuid4(), clinic_id=clinic.id,
                patient_id=patient_user.id, doctor_id=doctor_profile.id,
                queue_number=2, status="completed",
                called_at=NOW - timedelta(minutes=50),
                completed_at=NOW - timedelta(minutes=30),
            ),
            QueueEntry(
                id=uuid.uuid4(), clinic_id=clinic.id,
                patient_id=patient_user.id, doctor_id=doctor_profile.id,
                queue_number=3, status="completed",
                called_at=NOW - timedelta(minutes=20),
                completed_at=NOW - timedelta(minutes=10),
            ),
            # Other doctor at the same clinic — must be excluded
            QueueEntry(
                id=uuid.uuid4(), clinic_id=clinic.id,
                patient_id=patient_user.id, doctor_id=other_doctor.id,
                queue_number=4, status="waiting",
            ),
        ]
    )
    await db.commit()

    resp = await doctor_client.get(
        ANALYTICS_URL, headers={"X-Clinic-Id": str(clinic.id)}
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["queue_today"] == {
        "waiting": 1,
        "in_consultation": 0,
        "completed": 2,
        "cancelled": 0,
        "total": 3,
    }
    # (20 min + 10 min) / 2 = 15
    assert data["avg_consult_minutes"] == pytest.approx(15.0, abs=0.1)


async def test_analytics_queue_today_requires_membership(
    doctor_client: AsyncClient,
    db: AsyncSession,
):
    """X-Clinic-Id for a clinic the doctor doesn't belong to → 403."""
    clinic = Clinic(id=uuid.uuid4(), name="Other Clinic")
    db.add(clinic)
    await db.commit()

    resp = await doctor_client.get(
        ANALYTICS_URL, headers={"X-Clinic-Id": str(clinic.id)}
    )
    assert resp.status_code == 403
