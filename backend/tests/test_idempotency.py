"""Tests for Idempotency-Key double-submit protection.

Covers POST /api/v1/appointments and POST /api/v1/patients/records:

- replay: same key + same body returns the stored response (with
  ``Idempotent-Replay: true``) without double-creating;
- a different key is an independent request and creates again;
- a missing key passes straight through to normal handler semantics;
- same key + different body → 409 IDEMPOTENCY_MISMATCH;
- a claimed-but-unfinished key → 409 IDEMPOTENCY_IN_PROGRESS;
- an expired key (>24h) is re-processed and the row refreshed;
- keys are scoped per-user (same key, different user → independent).
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment
from app.models.idempotency import IdempotencyKey
from app.models.medical_record import MedicalRecord
from app.models.user import User
from tests.conftest import create_test_token

pytestmark = pytest.mark.asyncio

NEXT_WEEK = datetime.now(timezone.utc) + timedelta(days=7)


def _appt_payload(patient_user, doctor_profile, scheduled_at: datetime) -> dict:
    return {
        "patient_id": str(patient_user.id),
        "doctor_id": str(doctor_profile.id),
        "scheduled_at": scheduled_at.isoformat(),
        "duration_minutes": 30,
        "type": "in-person",
    }


async def _appointment_count(db: AsyncSession) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(Appointment)
        .where(Appointment.deleted_at.is_(None))
    )
    return result.scalar_one()


class TestAppointmentIdempotency:
    async def test_replay_returns_same_response_without_double_creating(
        self, patient_client, db, patient_user, doctor_profile
    ):
        key = str(uuid.uuid4())
        payload = _appt_payload(patient_user, doctor_profile, NEXT_WEEK)
        headers = {"Idempotency-Key": key}

        resp1 = await patient_client.post(
            "/api/v1/appointments", json=payload, headers=headers
        )
        assert resp1.status_code == 201
        assert "idempotent-replay" not in {k.lower() for k in resp1.headers}

        resp2 = await patient_client.post(
            "/api/v1/appointments", json=payload, headers=headers
        )
        assert resp2.status_code == resp1.status_code
        assert resp2.headers.get("Idempotent-Replay") == "true"
        assert resp2.json() == resp1.json()

        assert await _appointment_count(db) == 1

        # The claim row holds the stored response for future replays.
        row = (
            await db.execute(
                select(IdempotencyKey).where(
                    IdempotencyKey.key == key,
                    IdempotencyKey.user_id == patient_user.id,
                    IdempotencyKey.endpoint == "appointments.create",
                )
            )
        ).scalar_one()
        assert row.response_json == resp1.json()
        assert row.status_code == 201

    async def test_different_key_creates_twice(
        self, patient_client, db, patient_user, doctor_profile
    ):
        for i, slot in enumerate((NEXT_WEEK, NEXT_WEEK + timedelta(hours=1))):
            resp = await patient_client.post(
                "/api/v1/appointments",
                json=_appt_payload(patient_user, doctor_profile, slot),
                headers={"Idempotency-Key": str(uuid.uuid4())},
            )
            assert resp.status_code == 201, resp.json()
        assert await _appointment_count(db) == 2

    async def test_missing_key_passes_through(
        self, patient_client, db, patient_user, doctor_profile
    ):
        """No header → normal handler semantics, incl. conflict detection."""
        payload = _appt_payload(patient_user, doctor_profile, NEXT_WEEK)
        resp1 = await patient_client.post("/api/v1/appointments", json=payload)
        assert resp1.status_code == 201

        # A true duplicate POST without a key hits the normal double-booking
        # conflict path — idempotency must not mask it as a replay.
        resp2 = await patient_client.post("/api/v1/appointments", json=payload)
        assert resp2.status_code == 409
        assert resp2.json()["error"]["code"] == "DOCTOR_UNAVAILABLE"
        assert "Idempotent-Replay" not in resp2.headers

        assert (
            await db.execute(select(func.count()).select_from(IdempotencyKey))
        ).scalar_one() == 0

    async def test_same_key_different_body_returns_409(
        self, patient_client, db, patient_user, doctor_profile
    ):
        key = str(uuid.uuid4())
        resp1 = await patient_client.post(
            "/api/v1/appointments",
            json=_appt_payload(patient_user, doctor_profile, NEXT_WEEK),
            headers={"Idempotency-Key": key},
        )
        assert resp1.status_code == 201

        resp2 = await patient_client.post(
            "/api/v1/appointments",
            json=_appt_payload(
                patient_user, doctor_profile, NEXT_WEEK + timedelta(hours=2)
            ),
            headers={"Idempotency-Key": key},
        )
        assert resp2.status_code == 409
        assert resp2.json()["error"]["code"] == "IDEMPOTENCY_MISMATCH"
        assert await _appointment_count(db) == 1

    async def test_in_progress_claim_returns_409(
        self, patient_client, db, patient_user, doctor_profile
    ):
        """A claim row with NULL response = original request still in-flight."""
        key = str(uuid.uuid4())
        db.add(
            IdempotencyKey(
                key=key,
                user_id=patient_user.id,
                endpoint="appointments.create",
                request_hash="x" * 64,
            )
        )
        await db.commit()

        resp = await patient_client.post(
            "/api/v1/appointments",
            json=_appt_payload(patient_user, doctor_profile, NEXT_WEEK),
            headers={"Idempotency-Key": key},
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "IDEMPOTENCY_IN_PROGRESS"
        assert await _appointment_count(db) == 0

    async def test_expired_key_reprocesses(
        self, patient_client, db, patient_user, doctor_profile
    ):
        """Rows older than 24h are lazily deleted — the key can be reused."""
        key = str(uuid.uuid4())
        db.add(
            IdempotencyKey(
                key=key,
                user_id=patient_user.id,
                endpoint="appointments.create",
                request_hash="x" * 64,
                response_json={"stale": True},
                status_code=201,
                created_at=datetime.now(timezone.utc) - timedelta(hours=25),
            )
        )
        await db.commit()

        resp = await patient_client.post(
            "/api/v1/appointments",
            json=_appt_payload(patient_user, doctor_profile, NEXT_WEEK),
            headers={"Idempotency-Key": key},
        )
        assert resp.status_code == 201
        assert "Idempotent-Replay" not in resp.headers
        assert resp.json() != {"stale": True}
        assert await _appointment_count(db) == 1

        # The claim row was refreshed with the new response.
        row = (
            await db.execute(
                select(IdempotencyKey).where(IdempotencyKey.key == key)
            )
        ).scalar_one()
        assert row.response_json == resp.json()
        assert row.created_at > datetime.now(timezone.utc) - timedelta(minutes=5)

    async def test_same_key_different_user_is_independent(
        self, patient_client, db, patient_user, doctor_profile
    ):
        """Keys are scoped (key, user_id, endpoint) — another user's key
        with the same value does not replay this user's response."""
        other = User(
            keycloak_sub=f"patient-{uuid.uuid4()}",
            email="other@test.com",
            full_name="Other Patient",
            role="patient",
        )
        db.add(other)
        await db.commit()
        other_headers = {
            "Authorization": f"Bearer {create_test_token(sub=other.keycloak_sub, email=other.email, name=other.full_name, roles=['patient'])}",
        }

        key = str(uuid.uuid4())
        resp1 = await patient_client.post(
            "/api/v1/appointments",
            json=_appt_payload(patient_user, doctor_profile, NEXT_WEEK),
            headers={"Idempotency-Key": key},
        )
        assert resp1.status_code == 201

        resp2 = await patient_client.post(
            "/api/v1/appointments",
            json=_appt_payload(other, doctor_profile, NEXT_WEEK + timedelta(hours=1)),
            headers={**other_headers, "Idempotency-Key": key},
        )
        assert resp2.status_code == 201, resp2.json()
        assert resp2.json()["id"] != resp1.json()["id"]
        assert "Idempotent-Replay" not in resp2.headers
        assert await _appointment_count(db) == 2


class TestPatientRecordIdempotency:
    async def test_record_create_replay_does_not_duplicate(
        self, patient_client, db, patient_user
    ):
        key = str(uuid.uuid4())
        payload = {"record_type": "lab_report", "title": "Blood Test"}
        headers = {"Idempotency-Key": key}

        resp1 = await patient_client.post(
            "/api/v1/patients/records", json=payload, headers=headers
        )
        assert resp1.status_code == 201, resp1.json()

        resp2 = await patient_client.post(
            "/api/v1/patients/records", json=payload, headers=headers
        )
        assert resp2.status_code == 201
        assert resp2.headers.get("Idempotent-Replay") == "true"
        assert resp2.json() == resp1.json()

        count = (
            await db.execute(
                select(func.count())
                .select_from(MedicalRecord)
                .where(
                    MedicalRecord.patient_id == patient_user.id,
                    MedicalRecord.deleted_at.is_(None),
                )
            )
        ).scalar_one()
        assert count == 1

    async def test_record_create_without_key_creates_each_time(
        self, patient_client, db, patient_user
    ):
        payload = {"record_type": "lab_report", "title": "Blood Test"}
        for _ in range(2):
            resp = await patient_client.post("/api/v1/patients/records", json=payload)
            assert resp.status_code == 201

        count = (
            await db.execute(
                select(func.count())
                .select_from(MedicalRecord)
                .where(
                    MedicalRecord.patient_id == patient_user.id,
                    MedicalRecord.deleted_at.is_(None),
                )
            )
        ).scalar_one()
        assert count == 2
