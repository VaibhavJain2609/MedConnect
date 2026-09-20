"""Tests for appointment booking rules and the status-transition state machine.

Covers:
- The full transition matrix enforced by PUT /api/v1/appointments/{id}/status
- Terminal-state rejection (completed / cancelled / no-show accept no transition)
- The patient-cancel-only rule
- Doctor-ownership enforcement on status updates
- Double-booking conflict detection (409 DOCTOR_UNAVAILABLE)
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.user import User
from tests.conftest import create_test_token

pytestmark = pytest.mark.asyncio

NEXT_WEEK = datetime.now(timezone.utc) + timedelta(days=7)


async def _make_appointment(
    db: AsyncSession,
    *,
    patient_id: uuid.UUID,
    doctor_id: uuid.UUID,
    created_by: uuid.UUID,
    status: str = "scheduled",
    scheduled_at: datetime | None = None,
    duration_minutes: int = 30,
) -> Appointment:
    appt = Appointment(
        id=uuid.uuid4(),
        patient_id=patient_id,
        doctor_id=doctor_id,
        scheduled_at=scheduled_at or NEXT_WEEK,
        duration_minutes=duration_minutes,
        type="in-person",
        status=status,
        created_by=created_by,
    )
    db.add(appt)
    await db.commit()
    await db.refresh(appt)
    return appt


async def _make_other_doctor(db: AsyncSession) -> tuple[User, Doctor, dict]:
    """Create a second doctor (user + profile) and an auth header for them."""
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
    token = create_test_token(
        sub=user.keycloak_sub, email=user.email, name=user.full_name, roles=["doctor"]
    )
    return user, profile, {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Status transition matrix
# ---------------------------------------------------------------------------


class TestStatusTransitions:
    """PUT /api/v1/appointments/{id}/status must enforce STATUS_TRANSITIONS."""

    @pytest.mark.parametrize("target", ["arrived", "cancelled", "no-show"])
    async def test_scheduled_allows(
        self, doctor_client, db, doctor_user, doctor_profile, patient_user, target
    ):
        appt = await _make_appointment(
            db,
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            created_by=doctor_user.id,
            status="scheduled",
        )
        resp = await doctor_client.put(
            f"/api/v1/appointments/{appt.id}/status", json={"status": target}
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == target

    @pytest.mark.parametrize("target", ["in-progress", "completed", "scheduled"])
    async def test_scheduled_rejects(
        self, doctor_client, db, doctor_user, doctor_profile, patient_user, target
    ):
        appt = await _make_appointment(
            db,
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            created_by=doctor_user.id,
            status="scheduled",
        )
        resp = await doctor_client.put(
            f"/api/v1/appointments/{appt.id}/status", json={"status": target}
        )
        # NOTE: HTTPException(422) is remapped to 400 VALIDATION_ERROR by the
        # app's status-code exception handler (MD-395); the INVALID_TRANSITION
        # detail is intentionally swallowed.
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.parametrize("target", ["in-progress", "cancelled"])
    async def test_arrived_allows(
        self, doctor_client, db, doctor_user, doctor_profile, patient_user, target
    ):
        appt = await _make_appointment(
            db,
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            created_by=doctor_user.id,
            status="arrived",
        )
        resp = await doctor_client.put(
            f"/api/v1/appointments/{appt.id}/status", json={"status": target}
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == target

    @pytest.mark.parametrize("target", ["scheduled", "completed", "no-show"])
    async def test_arrived_rejects(
        self, doctor_client, db, doctor_user, doctor_profile, patient_user, target
    ):
        appt = await _make_appointment(
            db,
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            created_by=doctor_user.id,
            status="arrived",
        )
        resp = await doctor_client.put(
            f"/api/v1/appointments/{appt.id}/status", json={"status": target}
        )
        assert resp.status_code == 400  # 422 remapped to 400 VALIDATION_ERROR

    @pytest.mark.parametrize("target", ["completed", "cancelled"])
    async def test_in_progress_allows(
        self, doctor_client, db, doctor_user, doctor_profile, patient_user, target
    ):
        appt = await _make_appointment(
            db,
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            created_by=doctor_user.id,
            status="in-progress",
        )
        resp = await doctor_client.put(
            f"/api/v1/appointments/{appt.id}/status", json={"status": target}
        )
        assert resp.status_code == 200

    @pytest.mark.parametrize("terminal", ["completed", "cancelled", "no-show"])
    @pytest.mark.parametrize(
        "target", ["scheduled", "arrived", "in-progress", "completed", "cancelled", "no-show"]
    )
    async def test_terminal_states_reject_everything(
        self, doctor_client, db, doctor_user, doctor_profile, patient_user, terminal, target
    ):
        appt = await _make_appointment(
            db,
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            created_by=doctor_user.id,
            status=terminal,
        )
        resp = await doctor_client.put(
            f"/api/v1/appointments/{appt.id}/status", json={"status": target}
        )
        # NOTE: HTTPException(422) is remapped to 400 VALIDATION_ERROR by the
        # app's status-code exception handler (MD-395); the INVALID_TRANSITION
        # detail is intentionally swallowed.
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

    async def test_invalid_status_value_returns_400(
        self, doctor_client, db, doctor_user, doctor_profile, patient_user
    ):
        appt = await _make_appointment(
            db,
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            created_by=doctor_user.id,
        )
        resp = await doctor_client.put(
            f"/api/v1/appointments/{appt.id}/status", json={"status": "bogus"}
        )
        assert resp.status_code == 400

    async def test_status_update_nonexistent_appointment_404(self, doctor_client):
        resp = await doctor_client.put(
            f"/api/v1/appointments/{uuid.uuid4()}/status", json={"status": "arrived"}
        )
        assert resp.status_code == 404

    async def test_cancelled_reason_stored(
        self, doctor_client, db, doctor_user, doctor_profile, patient_user
    ):
        appt = await _make_appointment(
            db,
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            created_by=doctor_user.id,
        )
        resp = await doctor_client.put(
            f"/api/v1/appointments/{appt.id}/status",
            json={"status": "cancelled", "cancelled_reason": "Patient requested"},
        )
        assert resp.status_code == 200
        assert resp.json()["cancelled_reason"] == "Patient requested"


# ---------------------------------------------------------------------------
# Patient cancel-only rule
# ---------------------------------------------------------------------------


class TestPatientCancelOnly:
    async def test_patient_can_cancel_own_appointment(
        self, patient_client, db, patient_user, doctor_profile
    ):
        appt = await _make_appointment(
            db,
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            created_by=patient_user.id,
        )
        resp = await patient_client.put(
            f"/api/v1/appointments/{appt.id}/status", json={"status": "cancelled"}
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    @pytest.mark.parametrize("target", ["arrived", "in-progress", "completed", "no-show"])
    async def test_patient_cannot_set_other_statuses(
        self, patient_client, db, patient_user, doctor_profile, target
    ):
        appt = await _make_appointment(
            db,
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            created_by=patient_user.id,
        )
        resp = await patient_client.put(
            f"/api/v1/appointments/{appt.id}/status", json={"status": target}
        )
        assert resp.status_code == 403

    async def test_patient_cannot_cancel_someone_elses_appointment(
        self, patient_client, db, patient_user, doctor_profile
    ):
        other_patient = User(
            keycloak_sub=f"patient-{uuid.uuid4()}",
            email="other-patient@test.com",
            full_name="Other Patient",
            role="patient",
        )
        db.add(other_patient)
        await db.commit()
        appt = await _make_appointment(
            db,
            patient_id=other_patient.id,
            doctor_id=doctor_profile.id,
            created_by=other_patient.id,
        )
        resp = await patient_client.put(
            f"/api/v1/appointments/{appt.id}/status", json={"status": "cancelled"}
        )
        assert resp.status_code == 403

    async def test_doctor_cannot_update_other_doctors_appointment(
        self, doctor_client, client, db, patient_user, doctor_profile
    ):
        appt = await _make_appointment(
            db,
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            created_by=patient_user.id,
        )
        _, _, other_auth = await _make_other_doctor(db)
        resp = await client.put(
            f"/api/v1/appointments/{appt.id}/status",
            json={"status": "arrived"},
            headers=other_auth,
        )
        assert resp.status_code == 403

    async def test_admin_can_update_any_status(
        self, admin_client, db, admin_user, patient_user, doctor_profile
    ):
        appt = await _make_appointment(
            db,
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            created_by=admin_user.id,
        )
        resp = await admin_client.put(
            f"/api/v1/appointments/{appt.id}/status", json={"status": "no-show"}
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Booking rules / conflict detection
# ---------------------------------------------------------------------------


class TestBookingConflicts:
    def _payload(self, patient_user, doctor_profile, scheduled_at: datetime) -> dict:
        return {
            "patient_id": str(patient_user.id),
            "doctor_id": str(doctor_profile.id),
            "scheduled_at": scheduled_at.isoformat(),
            "duration_minutes": 30,
            "type": "in-person",
        }

    async def test_patient_books_own_appointment(
        self, patient_client, db, patient_user, doctor_profile
    ):
        resp = await patient_client.post(
            "/api/v1/appointments",
            json=self._payload(patient_user, doctor_profile, NEXT_WEEK),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "scheduled"
        assert body["patient_id"] == str(patient_user.id)

    async def test_double_booking_same_slot_returns_409(
        self, patient_client, db, patient_user, doctor_profile
    ):
        payload = self._payload(patient_user, doctor_profile, NEXT_WEEK)
        resp1 = await patient_client.post("/api/v1/appointments", json=payload)
        assert resp1.status_code == 201

        resp2 = await patient_client.post("/api/v1/appointments", json=payload)
        assert resp2.status_code == 409
        assert resp2.json()["detail"]["error"]["code"] == "DOCTOR_UNAVAILABLE"

    async def test_overlapping_slot_returns_409(
        self, patient_client, db, patient_user, doctor_profile
    ):
        """A booking 15 minutes into an existing 30-minute slot conflicts."""
        resp1 = await patient_client.post(
            "/api/v1/appointments",
            json=self._payload(patient_user, doctor_profile, NEXT_WEEK),
        )
        assert resp1.status_code == 201

        overlapping = NEXT_WEEK + timedelta(minutes=15)
        resp2 = await patient_client.post(
            "/api/v1/appointments",
            json=self._payload(patient_user, doctor_profile, overlapping),
        )
        assert resp2.status_code == 409

    async def test_adjacent_slot_is_allowed(
        self, patient_client, db, patient_user, doctor_profile
    ):
        """A booking starting exactly when the previous ends does not conflict."""
        resp1 = await patient_client.post(
            "/api/v1/appointments",
            json=self._payload(patient_user, doctor_profile, NEXT_WEEK),
        )
        assert resp1.status_code == 201

        adjacent = NEXT_WEEK + timedelta(minutes=30)
        resp2 = await patient_client.post(
            "/api/v1/appointments",
            json=self._payload(patient_user, doctor_profile, adjacent),
        )
        assert resp2.status_code == 201

    async def test_cancelled_appointment_frees_the_slot(
        self, patient_client, db, patient_user, doctor_profile
    ):
        await _make_appointment(
            db,
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            created_by=patient_user.id,
            status="cancelled",
            scheduled_at=NEXT_WEEK,
        )
        resp = await patient_client.post(
            "/api/v1/appointments",
            json=self._payload(patient_user, doctor_profile, NEXT_WEEK),
        )
        assert resp.status_code == 201

    async def test_patient_cannot_book_for_another_patient(
        self, patient_client, db, patient_user, doctor_profile
    ):
        other_patient = User(
            keycloak_sub=f"patient-{uuid.uuid4()}",
            email="other@test.com",
            full_name="Other Patient",
            role="patient",
        )
        db.add(other_patient)
        await db.commit()

        payload = self._payload(patient_user, doctor_profile, NEXT_WEEK)
        payload["patient_id"] = str(other_patient.id)
        resp = await patient_client.post("/api/v1/appointments", json=payload)
        assert resp.status_code == 403

    async def test_invalid_type_returns_400(
        self, patient_client, db, patient_user, doctor_profile
    ):
        payload = self._payload(patient_user, doctor_profile, NEXT_WEEK)
        payload["type"] = "carrier-pigeon"
        resp = await patient_client.post("/api/v1/appointments", json=payload)
        assert resp.status_code == 400

    async def test_unknown_doctor_returns_404(self, patient_client, patient_user):
        payload = {
            "patient_id": str(patient_user.id),
            "doctor_id": str(uuid.uuid4()),
            "scheduled_at": NEXT_WEEK.isoformat(),
            "type": "in-person",
        }
        resp = await patient_client.post("/api/v1/appointments", json=payload)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Delete (soft-cancel) rules
# ---------------------------------------------------------------------------


class TestDeleteAppointment:
    @pytest.mark.parametrize("terminal", ["completed", "cancelled", "no-show"])
    async def test_cannot_delete_terminal_appointment(
        self, doctor_client, db, doctor_user, doctor_profile, patient_user, terminal
    ):
        appt = await _make_appointment(
            db,
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            created_by=doctor_user.id,
            status=terminal,
        )
        resp = await doctor_client.delete(f"/api/v1/appointments/{appt.id}")
        # HTTPException(422) is remapped to 400 VALIDATION_ERROR
        assert resp.status_code == 400

    async def test_doctor_can_delete_scheduled(
        self, doctor_client, db, doctor_user, doctor_profile, patient_user
    ):
        appt = await _make_appointment(
            db,
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            created_by=doctor_user.id,
        )
        resp = await doctor_client.delete(f"/api/v1/appointments/{appt.id}")
        assert resp.status_code == 204
