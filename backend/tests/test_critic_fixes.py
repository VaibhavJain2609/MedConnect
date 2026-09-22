"""Regression tests for round-3 critic findings.

Covers:
- teleconsult meeting URLs are deterministic per appointment (mc-<uuid hex>)
- revoked clinic consent blocks NEW appointment/encounter writes
- naive scheduled_at is coerced to UTC instead of 500ing
- prescription safety gate flags unresolved free-text items (checked=False)
- admin appointment-request approve/reject endpoints exist and work
- encounters reject non-patient targets and cancelled appointments
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment
from app.models.clinic import Clinic, ClinicMembership
from app.models.doctor import Doctor
from app.models.patient_link import PatientClinicLink
from app.models.user import User
from tests.conftest import create_test_token

pytestmark = pytest.mark.asyncio

FUTURE = datetime.now(timezone.utc) + timedelta(days=3)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def clinic(db: AsyncSession, doctor_user: User) -> Clinic:
    c = Clinic(id=uuid.uuid4(), name="Critic Clinic", city="Pune", created_by=doctor_user.id)
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


@pytest_asyncio.fixture
async def membership(db: AsyncSession, clinic: Clinic, doctor_user: User) -> ClinicMembership:
    m = ClinicMembership(
        id=uuid.uuid4(), clinic_id=clinic.id, user_id=doctor_user.id,
        role="owner", is_active=True,
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


@pytest_asyncio.fixture
async def revoked_link(
    db: AsyncSession, clinic: Clinic, doctor_user: User, patient_user: User
) -> PatientClinicLink:
    link = PatientClinicLink(
        id=uuid.uuid4(),
        patient_id=patient_user.id,
        clinic_id=clinic.id,
        linked_by=doctor_user.id,
        consent_status="revoked",
        consented_at=datetime.now(timezone.utc) - timedelta(days=10),
        revoked_at=datetime.now(timezone.utc),
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return link


@pytest_asyncio.fixture
async def appointment(db: AsyncSession, doctor_profile: Doctor, patient_user: User, admin_user: User) -> Appointment:
    a = Appointment(
        id=uuid.uuid4(),
        patient_id=patient_user.id,
        doctor_id=doctor_profile.id,
        scheduled_at=FUTURE,
        duration_minutes=30,
        type="in-person",
        status="scheduled",
        created_by=admin_user.id,
    )
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return a


# ---------------------------------------------------------------------------
# Teleconsult meeting URL determinism
# ---------------------------------------------------------------------------


class TestMeetingUrlDeterminism:
    async def test_meeting_url_deterministic_per_appointment(
        self, doctor_client, doctor_profile, patient_user, db
    ):
        """Room name is mc-<appointment UUID hex> — one stable room per
        appointment (idempotent across create/status transitions/regenerate).
        Access is enforced at the API layer: the URL only reaches the
        patient, the doctor, clinic members, and admins."""
        from tests.conftest import grant_doctor_patient_relationship

        await grant_doctor_patient_relationship(db, "doctor-123", patient_user.id)
        res = await doctor_client.post(
            "/api/v1/appointments",
            json={
                "patient_id": str(patient_user.id),
                "doctor_id": str(doctor_profile.id),
                "scheduled_at": FUTURE.isoformat(),
                "duration_minutes": 30,
                "type": "teleconsult",
            },
        )
        assert res.status_code == 201, res.text
        body = res.json()
        expected = f"mc-{uuid.UUID(body['id']).hex}"
        assert body["meeting_url"]
        assert body["meeting_url"].endswith(expected)
        assert body["teleconsult_url"] == body["meeting_url"]


# ---------------------------------------------------------------------------
# Revoked consent blocks new writes
# ---------------------------------------------------------------------------


class TestRevokedConsentWrites:
    async def test_doctor_cannot_book_after_revoke(
        self, doctor_client, doctor_profile, patient_user, clinic, membership, revoked_link
    ):
        res = await doctor_client.post(
            "/api/v1/appointments",
            json={
                "patient_id": str(patient_user.id),
                "doctor_id": str(doctor_profile.id),
                "clinic_id": str(clinic.id),
                "scheduled_at": FUTURE.isoformat(),
                "duration_minutes": 30,
                "type": "in-person",
            },
        )
        assert res.status_code == 403
        assert res.json()["error"]["code"] == "PATIENT_ACCESS_DENIED"

    async def test_doctor_cannot_create_encounter_after_revoke(
        self, doctor_client, patient_user, clinic, membership, revoked_link
    ):
        res = await doctor_client.post(
            "/api/v1/encounters",
            json={
                "patient_id": str(patient_user.id),
                "clinic_id": str(clinic.id),
                "subjective": "test",
            },
        )
        assert res.status_code == 403
        assert res.json()["error"]["code"] == "PATIENT_ACCESS_DENIED"


# ---------------------------------------------------------------------------
# Naive datetime coercion (no 500)
# ---------------------------------------------------------------------------


class TestNaiveDatetime:
    async def test_naive_scheduled_at_is_coerced(
        self, patient_client, patient_user, doctor_profile
    ):
        res = await patient_client.post(
            "/api/v1/appointments",
            json={
                "patient_id": str(patient_user.id),
                "doctor_id": str(doctor_profile.id),
                "scheduled_at": FUTURE.strftime("%Y-%m-%dT%H:%M:%S"),  # no offset
                "duration_minutes": 30,
                "type": "in-person",
            },
        )
        assert res.status_code == 201, res.text


# ---------------------------------------------------------------------------
# Safety gate: unresolved items surface instead of silent all-clear
# ---------------------------------------------------------------------------


class TestSafetyGateUnresolved:
    async def test_free_text_item_flags_unresolved(
        self, doctor_client, doctor_profile, patient_user, db
    ):
        from tests.conftest import grant_doctor_patient_relationship

        await grant_doctor_patient_relationship(db, "doctor-123", patient_user.id)
        res = await doctor_client.post(
            "/api/v1/doctors/prescriptions",
            json={
                "patient_id": str(patient_user.id),
                "medicines": [
                    {"brand_name": "Totally Compounded Nonexistent XYZ", "dose": "5mg",
                     "frequency": "OD", "duration": "7 days"}
                ],
            },
        )
        assert res.status_code == 201, res.text
        safety = res.json()["safety"]
        assert safety["checked"] is False
        kinds = [a["kind"] for a in safety["alerts"]]
        assert "unresolved_item" in kinds


# ---------------------------------------------------------------------------
# Admin appointment-request approve/reject
# ---------------------------------------------------------------------------


class TestAppointmentRequests:
    async def test_approve_and_reject(self, admin_client, appointment, patient_user):
        approve = await admin_client.post(
            f"/api/v1/admin/appointment-requests/{appointment.id}/approve"
        )
        assert approve.status_code == 200, approve.text

        reject = await admin_client.post(
            f"/api/v1/admin/appointment-requests/{appointment.id}/reject",
            json={"reason": "Doctor unavailable"},
        )
        # already approved once — status still 'scheduled', so reject works
        assert reject.status_code == 200, reject.text
        assert reject.json()["status"] == "cancelled"

        # terminal — further actions rejected
        again = await admin_client.post(
            f"/api/v1/admin/appointment-requests/{appointment.id}/approve"
        )
        assert again.status_code == 409


# ---------------------------------------------------------------------------
# Encounter guards
# ---------------------------------------------------------------------------


class TestEncounterGuards:
    async def test_encounter_rejects_non_patient_target(
        self, doctor_client, doctor_profile, doctor_user
    ):
        res = await doctor_client.post(
            "/api/v1/encounters",
            json={"patient_id": str(doctor_user.id), "subjective": "x"},
        )
        assert res.status_code == 404

    async def test_cancelled_appointment_grants_no_relationship(
        self, doctor_client, doctor_profile, patient_user, db
    ):
        appt = Appointment(
            id=uuid.uuid4(),
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            scheduled_at=FUTURE,
            duration_minutes=30,
            type="in-person",
            status="cancelled",
            created_by=doctor_profile.user_id,
        )
        db.add(appt)
        await db.commit()

        res = await doctor_client.post(
            "/api/v1/encounters",
            json={
                "patient_id": str(patient_user.id),
                "appointment_id": str(appt.id),
                "subjective": "x",
            },
        )
        assert res.status_code == 403
        assert res.json()["error"]["code"] == "PATIENT_ACCESS_DENIED"


# ---------------------------------------------------------------------------
# Notification channel preference keys (sms/whatsapp were silently dropped)
# ---------------------------------------------------------------------------


class TestChannelPrefs:
    async def test_sms_whatsapp_prefs_roundtrip(self, patient_client):
        res = await patient_client.put(
            "/api/v1/notifications/preferences",
            json={"sms_notifications": True, "whatsapp_notifications": True},
        )
        assert res.status_code == 200, res.text
        prefs = res.json()  # PUT returns the merged prefs dict directly
        assert prefs["sms_notifications"] is True
        assert prefs["whatsapp_notifications"] is True

        got = await patient_client.get("/api/v1/notifications/preferences")
        assert got.json()["sms_notifications"] is True


# ---------------------------------------------------------------------------
# Maintenance-mode middleware (platform settings actually enforced)
# ---------------------------------------------------------------------------


class TestMaintenanceMode:
    async def test_503_when_enabled_and_admin_exempt(self, client, monkeypatch):
        from app.main import MaintenanceModeMiddleware

        async def _on(self):
            return True

        monkeypatch.setattr(MaintenanceModeMiddleware, "_maintenance_on", _on)
        res = await client.get("/api/v1/notifications")
        assert res.status_code == 503
        assert res.json()["error"]["code"] == "MAINTENANCE_MODE"

        # admin namespace + auth are exempt so admins can still work
        res2 = await client.get("/api/v1/auth/me")
        assert res2.status_code != 503

    async def test_passes_when_disabled(self, client, monkeypatch):
        from app.main import MaintenanceModeMiddleware

        async def _off(self):
            return False

        monkeypatch.setattr(MaintenanceModeMiddleware, "_maintenance_on", _off)
        # Not 503'd by the gate — 401/200/etc. depending on auth state
        res = await client.get("/api/v1/notifications")
        assert res.status_code != 503


class TestPlatformSettingsService:
    async def test_get_setting_reads_row(self, db: AsyncSession):
        import uuid as _uuid
        from app.models.platform_setting import PlatformSetting
        from app.services import platform_settings

        db.add(
            PlatformSetting(
                id=_uuid.uuid4(), key="maintenance_mode",
                value={"enabled": True},
            )
        )
        await db.commit()
        assert await platform_settings.get_setting(db, "maintenance_mode") == {
            "enabled": True
        }
        assert await platform_settings.get_setting(db, "nonexistent") is None
