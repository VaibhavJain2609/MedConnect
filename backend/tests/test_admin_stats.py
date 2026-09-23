"""Admin dashboard stats + admin list endpoints (app/routers/admin/stats.py).

Covers:
- Auth matrix across all GET endpoints: 401 unauthenticated, 403 patient,
  403 doctor, 200 admin.
- GET /api/v1/admin/stats — entity counts + trend fields.
- Trend endpoints — cumulative shape, seeded rows reflected.
- /stats/record-types, /stats/patient-statistics.
- /appointment-requests feed + approve/reject transitions
  (404, 422, 409, notification + status effects).
- /patients and /appointments admin lists — pagination + filters.
- /appointments/departments + /visits/departments.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.medical_record import MedicalRecord
from app.models.notification import Notification
from app.models.prescription import Prescription
from app.models.user import User
from tests.conftest import make_auth_header

pytestmark = pytest.mark.asyncio

BASE = "/api/v1/admin"

GET_ENDPOINTS = [
    "/stats",
    "/stats/patient-trend",
    "/stats/record-trend",
    "/stats/prescription-trend",
    "/stats/doctor-trend",
    "/stats/record-types",
    "/stats/patient-statistics",
    "/appointment-requests",
    "/patients",
    "/appointments",
    "/appointments/departments",
    "/visits/departments",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_patient(db: AsyncSession, email: str, name: str = "Stats Patient", active: bool = True) -> User:
    u = User(
        keycloak_sub=f"patient-{uuid.uuid4()}", email=email, full_name=name,
        role="patient", is_active=active,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def _make_record(
    db: AsyncSession, patient_id, doctor_id, record_type: str = "opd_note", title: str = "Rec"
) -> MedicalRecord:
    r = MedicalRecord(
        patient_id=patient_id, doctor_id=doctor_id, record_type=record_type, title=title
    )
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return r


async def _make_prescription(db: AsyncSession, record: MedicalRecord, doctor_id, patient_id) -> Prescription:
    p = Prescription(
        record_id=record.id, doctor_id=doctor_id, patient_id=patient_id, medicines=[]
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


async def _make_appointment(
    db: AsyncSession,
    patient: User,
    doctor: Doctor,
    status: str = "scheduled",
    scheduled_at: datetime | None = None,
    appt_type: str = "in-person",
) -> Appointment:
    a = Appointment(
        id=uuid.uuid4(),
        patient_id=patient.id,
        doctor_id=doctor.id,
        scheduled_at=scheduled_at or datetime.now(timezone.utc) + timedelta(days=1),
        type=appt_type,
        status=status,
        created_by=patient.id,
    )
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return a


# ---------------------------------------------------------------------------
# Auth matrix
# ---------------------------------------------------------------------------


class TestAdminAuthMatrix:
    @pytest.mark.parametrize("path", GET_ENDPOINTS)
    async def test_unauthenticated_401(self, client, path):
        resp = await client.get(f"{BASE}{path}")
        assert resp.status_code == 401

    @pytest.mark.parametrize("path", GET_ENDPOINTS)
    async def test_patient_403(self, client, patient_user, path):
        resp = await client.get(f"{BASE}{path}", headers=make_auth_header(patient_user))
        assert resp.status_code == 403

    @pytest.mark.parametrize("path", GET_ENDPOINTS)
    async def test_doctor_403(self, client, doctor_user, doctor_profile, path):
        resp = await client.get(f"{BASE}{path}", headers=make_auth_header(doctor_user))
        assert resp.status_code == 403

    @pytest.mark.parametrize("path", GET_ENDPOINTS)
    async def test_admin_200(self, client, admin_user, path):
        resp = await client.get(f"{BASE}{path}", headers=make_auth_header(admin_user))
        assert resp.status_code == 200, f"{path}: {resp.text}"


# ---------------------------------------------------------------------------
# GET /stats
# ---------------------------------------------------------------------------


class TestDashboardStats:
    async def test_counts_and_keys(self, client, db, admin_user, patient_user, doctor_user, doctor_profile):
        await _make_record(db, patient_user.id, doctor_profile.id)

        resp = await client.get(f"{BASE}/stats", headers=make_auth_header(admin_user))
        assert resp.status_code == 200
        body = resp.json()
        # patient_user is the only patient; doctor_profile the only doctor
        assert body["total_patients"] == 1
        assert body["total_doctors"] == 1
        assert body["verified_doctors"] == 1
        assert body["unverified_doctors"] == 0
        assert body["total_records"] == 1
        assert body["total_prescriptions"] == 0
        assert body["total_medicines"] == 0
        for key in ("patient_trend", "record_trend", "prescription_trend", "doctor_trend"):
            assert isinstance(body[key], (int, float))

    async def test_empty_db_zeros(self, client, admin_user):
        resp = await client.get(f"{BASE}/stats", headers=make_auth_header(admin_user))
        body = resp.json()
        assert body["total_patients"] == 0
        assert body["total_doctors"] == 0
        assert body["total_records"] == 0

    async def test_date_range_params_accepted(self, client, admin_user):
        resp = await client.get(
            f"{BASE}/stats",
            params={"start_date": "2024-01-01", "end_date": "2024-01-31"},
            headers=make_auth_header(admin_user),
        )
        assert resp.status_code == 200

    async def test_garbage_dates_fall_back_to_defaults(self, client, admin_user):
        resp = await client.get(
            f"{BASE}/stats",
            params={"start_date": "banana", "end_date": "also-bad"},
            headers=make_auth_header(admin_user),
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Trend endpoints
# ---------------------------------------------------------------------------


class TestTrends:
    async def test_patient_trend_shape_and_baseline(self, client, db, admin_user, patient_user):
        resp = await client.get(
            f"{BASE}/stats/patient-trend",
            params={"start_date": "2024-01-01", "end_date": "2024-01-07"},
            headers=make_auth_header(admin_user),
        )
        assert resp.status_code == 200
        trend = resp.json()["trend"]
        assert len(trend) == 7
        assert trend[0]["date"] == "2024-01-01"
        assert trend[-1]["date"] == "2024-01-07"
        # patient_user was created today — outside the Jan-2024 window, so
        # the whole window reads the post-window baseline of 0.
        assert all(p["value"] == 0 for p in trend)

    async def test_patient_trend_counts_todays_signup(self, client, admin_user, patient_user):
        today = datetime.now().date()
        start = today - timedelta(days=2)
        resp = await client.get(
            f"{BASE}/stats/patient-trend",
            params={"start_date": start.isoformat(), "end_date": today.isoformat()},
            headers=make_auth_header(admin_user),
        )
        trend = resp.json()["trend"]
        assert len(trend) == 3
        # Cumulative: last point includes the patient created today.
        assert trend[-1]["value"] == 1
        assert trend[-1]["value"] >= trend[0]["value"]

    async def test_record_and_prescription_trends(
        self, client, db, admin_user, patient_user, doctor_user, doctor_profile
    ):
        record = await _make_record(db, patient_user.id, doctor_profile.id)
        await _make_prescription(db, record, doctor_profile.id, patient_user.id)

        today = datetime.now().date()
        params = {
            "start_date": (today - timedelta(days=1)).isoformat(),
            "end_date": today.isoformat(),
        }
        rec = await client.get(
            f"{BASE}/stats/record-trend", params=params, headers=make_auth_header(admin_user)
        )
        assert rec.json()["trend"][-1]["value"] == 1
        rx = await client.get(
            f"{BASE}/stats/prescription-trend", params=params, headers=make_auth_header(admin_user)
        )
        assert rx.json()["trend"][-1]["value"] == 1

    async def test_doctor_trend(self, client, db, admin_user, doctor_user, doctor_profile):
        today = datetime.now().date()
        resp = await client.get(
            f"{BASE}/stats/doctor-trend",
            params={
                "start_date": (today - timedelta(days=1)).isoformat(),
                "end_date": today.isoformat(),
            },
            headers=make_auth_header(admin_user),
        )
        assert resp.json()["trend"][-1]["value"] == 1

    async def test_default_window_is_30_days(self, client, admin_user):
        resp = await client.get(
            f"{BASE}/stats/patient-trend", headers=make_auth_header(admin_user)
        )
        assert len(resp.json()["trend"]) == 30


# ---------------------------------------------------------------------------
# Record types + patient statistics
# ---------------------------------------------------------------------------


class TestBreakdowns:
    async def test_record_types_grouped(
        self, client, db, admin_user, patient_user, doctor_user, doctor_profile
    ):
        await _make_record(db, patient_user.id, doctor_profile.id, record_type="opd_note")
        await _make_record(db, patient_user.id, doctor_profile.id, record_type="opd_note")
        await _make_record(db, patient_user.id, doctor_profile.id, record_type="lab_report")

        resp = await client.get(f"{BASE}/stats/record-types", headers=make_auth_header(admin_user))
        types = {row["type"]: row["count"] for row in resp.json()["record_types"]}
        assert types == {"opd_note": 2, "lab_report": 1}

    async def test_record_types_excludes_soft_deleted(
        self, client, db, admin_user, patient_user, doctor_user, doctor_profile
    ):
        record = await _make_record(db, patient_user.id, doctor_profile.id)
        record.deleted_at = datetime.now(timezone.utc)
        await db.commit()

        resp = await client.get(f"{BASE}/stats/record-types", headers=make_auth_header(admin_user))
        assert resp.json() == {"record_types": []}

    async def test_patient_statistics_shape(self, client, admin_user, patient_user):
        resp = await client.get(
            f"{BASE}/stats/patient-statistics", headers=make_auth_header(admin_user)
        )
        stats = resp.json()["statistics"]
        assert len(stats) == 7
        assert {"date", "new_patients", "returning_patients"} <= set(stats[0])
        assert stats[-1]["new_patients"] == 1


# ---------------------------------------------------------------------------
# Appointment requests feed + approve/reject
# ---------------------------------------------------------------------------


class TestAppointmentRequests:
    async def test_feed_returns_joined_names(
        self, client, db, admin_user, patient_user, doctor_user, doctor_profile
    ):
        await _make_appointment(db, patient_user, doctor_profile)
        resp = await client.get(f"{BASE}/appointment-requests", headers=make_auth_header(admin_user))
        reqs = resp.json()["requests"]
        assert len(reqs) == 1
        assert reqs[0]["patient_name"] == patient_user.full_name
        assert reqs[0]["doctor_name"] == doctor_user.full_name
        assert reqs[0]["department"] == doctor_profile.specialization
        assert reqs[0]["status"] == "scheduled"

    async def test_feed_respects_limit(
        self, client, db, admin_user, patient_user, doctor_user, doctor_profile
    ):
        for _ in range(3):
            await _make_appointment(db, patient_user, doctor_profile)
        resp = await client.get(
            f"{BASE}/appointment-requests?limit=2", headers=make_auth_header(admin_user)
        )
        assert len(resp.json()["requests"]) == 2

    async def test_feed_excludes_soft_deleted(
        self, client, db, admin_user, patient_user, doctor_user, doctor_profile
    ):
        appt = await _make_appointment(db, patient_user, doctor_profile)
        appt.deleted_at = datetime.now(timezone.utc)
        await db.commit()
        resp = await client.get(f"{BASE}/appointment-requests", headers=make_auth_header(admin_user))
        assert resp.json() == {"requests": []}

    async def test_approve_success_notifies_patient(
        self, client, db, admin_user, patient_user, doctor_user, doctor_profile
    ):
        appt = await _make_appointment(db, patient_user, doctor_profile)
        resp = await client.post(
            f"{BASE}/appointment-requests/{appt.id}/approve",
            headers=make_auth_header(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json() == {"id": str(appt.id), "status": "scheduled"}

        notif = (
            await db.execute(
                select(Notification).where(Notification.user_id == patient_user.id)
            )
        ).scalars().first()
        assert notif is not None
        assert "approved" in notif.title.lower() or "confirmed" in notif.title.lower()

    async def test_approve_requires_admin(
        self, client, db, patient_user, doctor_user, doctor_profile
    ):
        appt = await _make_appointment(db, patient_user, doctor_profile)
        resp = await client.post(
            f"{BASE}/appointment-requests/{appt.id}/approve",
            headers=make_auth_header(patient_user),
        )
        assert resp.status_code == 403

    async def test_approve_not_found_404(self, client, admin_user):
        resp = await client.post(
            f"{BASE}/appointment-requests/{uuid.uuid4()}/approve",
            headers=make_auth_header(admin_user),
        )
        assert resp.status_code == 404

    async def test_approve_invalid_id_422(self, client, admin_user):
        resp = await client.post(
            f"{BASE}/appointment-requests/not-a-uuid/approve",
            headers=make_auth_header(admin_user),
        )
        assert resp.status_code == 422

    async def test_approve_non_scheduled_409(
        self, client, db, admin_user, patient_user, doctor_user, doctor_profile
    ):
        appt = await _make_appointment(db, patient_user, doctor_profile, status="completed")
        resp = await client.post(
            f"{BASE}/appointment-requests/{appt.id}/approve",
            headers=make_auth_header(admin_user),
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "INVALID_STATE"

    async def test_reject_cancels_with_default_reason(
        self, client, db, admin_user, patient_user, doctor_user, doctor_profile
    ):
        appt = await _make_appointment(db, patient_user, doctor_profile)
        resp = await client.post(
            f"{BASE}/appointment-requests/{appt.id}/reject",
            headers=make_auth_header(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json() == {"id": str(appt.id), "status": "cancelled"}
        await db.refresh(appt)
        assert appt.status == "cancelled"
        assert appt.cancelled_reason == "Rejected by clinic administration"

    async def test_reject_custom_reason(
        self, client, db, admin_user, patient_user, doctor_user, doctor_profile
    ):
        appt = await _make_appointment(db, patient_user, doctor_profile)
        resp = await client.post(
            f"{BASE}/appointment-requests/{appt.id}/reject",
            json={"reason": "Doctor on leave"},
            headers=make_auth_header(admin_user),
        )
        assert resp.status_code == 200
        await db.refresh(appt)
        assert appt.cancelled_reason == "Doctor on leave"

    async def test_reject_already_cancelled_409(
        self, client, db, admin_user, patient_user, doctor_user, doctor_profile
    ):
        appt = await _make_appointment(db, patient_user, doctor_profile, status="cancelled")
        resp = await client.post(
            f"{BASE}/appointment-requests/{appt.id}/reject",
            headers=make_auth_header(admin_user),
        )
        assert resp.status_code == 409

    async def test_reject_not_found_404(self, client, admin_user):
        resp = await client.post(
            f"{BASE}/appointment-requests/{uuid.uuid4()}/reject",
            headers=make_auth_header(admin_user),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Admin patient / appointment lists
# ---------------------------------------------------------------------------


class TestAdminPatientList:
    async def test_pagination_shape(self, client, db, admin_user):
        for i in range(3):
            await _make_patient(db, f"p{i}@test.com", name=f"Page Patient {i}")
        resp = await client.get(
            f"{BASE}/patients?page=1&limit=2", headers=make_auth_header(admin_user)
        )
        body = resp.json()
        assert body["total"] == 3
        assert body["page"] == 1
        assert body["limit"] == 2
        assert body["totalPages"] == 2
        assert len(body["patients"]) == 2

    async def test_only_patients_listed(self, client, db, admin_user, doctor_user, doctor_profile):
        resp = await client.get(f"{BASE}/patients", headers=make_auth_header(admin_user))
        emails = [p["email"] for p in resp.json()["patients"]]
        assert doctor_user.email not in emails
        assert admin_user.email not in emails

    async def test_search_filters_by_name(self, client, db, admin_user):
        await _make_patient(db, "alice@test.com", name="Alice Wonder")
        await _make_patient(db, "bob@test.com", name="Bob Builder")
        resp = await client.get(
            f"{BASE}/patients?search=alice", headers=make_auth_header(admin_user)
        )
        body = resp.json()
        assert body["total"] == 1
        assert body["patients"][0]["name"] == "Alice Wonder"

    async def test_status_filter(self, client, db, admin_user):
        await _make_patient(db, "active@test.com", name="Active P", active=True)
        await _make_patient(db, "inactive@test.com", name="Inactive P", active=False)
        resp = await client.get(
            f"{BASE}/patients?status=inactive", headers=make_auth_header(admin_user)
        )
        body = resp.json()
        assert body["total"] == 1
        assert body["patients"][0]["status"] == "inactive"


class TestAdminAppointmentList:
    async def test_list_with_names_and_pagination(
        self, client, db, admin_user, patient_user, doctor_user, doctor_profile
    ):
        await _make_appointment(db, patient_user, doctor_profile)
        resp = await client.get(f"{BASE}/appointments", headers=make_auth_header(admin_user))
        body = resp.json()
        assert body["total"] == 1
        row = body["appointments"][0]
        assert row["patient_name"] == patient_user.full_name
        assert row["doctor_name"] == doctor_user.full_name
        assert row["status"] == "scheduled"
        assert row["type"] == "in-person"

    async def test_status_filter(
        self, client, db, admin_user, patient_user, doctor_user, doctor_profile
    ):
        await _make_appointment(db, patient_user, doctor_profile, status="scheduled")
        await _make_appointment(db, patient_user, doctor_profile, status="cancelled")
        resp = await client.get(
            f"{BASE}/appointments?status=cancelled", headers=make_auth_header(admin_user)
        )
        body = resp.json()
        assert body["total"] == 1
        assert body["appointments"][0]["status"] == "cancelled"

    async def test_department_filter(
        self, client, db, admin_user, patient_user, doctor_user, doctor_profile
    ):
        await _make_appointment(db, patient_user, doctor_profile)
        resp = await client.get(
            f"{BASE}/appointments?department=General Physician",
            headers=make_auth_header(admin_user),
        )
        assert resp.json()["total"] == 1
        resp = await client.get(
            f"{BASE}/appointments?department=Neurology",
            headers=make_auth_header(admin_user),
        )
        assert resp.json()["total"] == 0

    async def test_date_filter(
        self, client, db, admin_user, patient_user, doctor_user, doctor_profile
    ):
        target = datetime.now(timezone.utc) + timedelta(days=5)
        await _make_appointment(db, patient_user, doctor_profile, scheduled_at=target)
        await _make_appointment(
            db, patient_user, doctor_profile, scheduled_at=target + timedelta(days=10)
        )
        resp = await client.get(
            f"{BASE}/appointments?date={target.date().isoformat()}",
            headers=make_auth_header(admin_user),
        )
        assert resp.json()["total"] == 1

    async def test_search_by_patient_name(
        self, client, db, admin_user, doctor_user, doctor_profile
    ):
        alice = await _make_patient(db, "alice2@test.com", name="Alice Unique")
        bob = await _make_patient(db, "bob2@test.com", name="Bob Plain")
        await _make_appointment(db, alice, doctor_profile)
        await _make_appointment(db, bob, doctor_profile)
        resp = await client.get(
            f"{BASE}/appointments?search=Unique", headers=make_auth_header(admin_user)
        )
        body = resp.json()
        assert body["total"] == 1
        assert body["appointments"][0]["patient_name"] == "Alice Unique"


# ---------------------------------------------------------------------------
# Department lists
# ---------------------------------------------------------------------------


class TestDepartments:
    async def test_appointment_departments(self, client, db, admin_user, doctor_user, doctor_profile):
        resp = await client.get(
            f"{BASE}/appointments/departments", headers=make_auth_header(admin_user)
        )
        assert resp.json() == ["General Physician"]

    async def test_visit_departments(
        self, client, db, admin_user, patient_user, doctor_user, doctor_profile
    ):
        await _make_record(db, patient_user.id, doctor_profile.id, record_type="opd_note")
        await _make_record(db, patient_user.id, doctor_profile.id, record_type="discharge_summary")
        resp = await client.get(
            f"{BASE}/visits/departments", headers=make_auth_header(admin_user)
        )
        assert sorted(resp.json()) == ["discharge_summary", "opd_note"]
