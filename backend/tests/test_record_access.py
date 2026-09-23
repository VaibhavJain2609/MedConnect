"""Record access consent endpoints (record_access.py).

Covers:
- Doctor: POST /api/v1/doctors/patients/{patient_id}/record-access —
  auth matrix (401/403/400), clinic membership enforcement, patient-link
  requirement, duplicate pending 409, payload validation 422, happy path 201.
- Doctor: GET .../record-access — null when absent, returns latest consent,
  scoped to the requesting doctor.
- Patient: GET /api/v1/patients/record-access-requests — own requests only,
  doctor/clinic names joined, status filter, doctor role rejected.
- Patient: PUT /api/v1/patients/record-access-requests/{consent_id} —
  approve/reject/revoke state transitions, ownership 404, invalid transitions.
"""

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clinic import Clinic, ClinicMembership
from app.models.doctor import Doctor
from app.models.notification import Notification
from app.models.patient_link import PatientClinicLink
from app.models.record_access import RecordAccessConsent
from app.models.user import User
from tests.conftest import make_auth_header

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def clinic(db: AsyncSession, doctor_user: User) -> Clinic:
    c = Clinic(id=uuid.uuid4(), name="Access Clinic", city="Delhi", created_by=doctor_user.id)
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


@pytest_asyncio.fixture
async def other_clinic(db: AsyncSession, doctor_user: User) -> Clinic:
    c = Clinic(id=uuid.uuid4(), name="Other Clinic", city="Goa", created_by=doctor_user.id)
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


@pytest_asyncio.fixture
async def doctor_membership(db: AsyncSession, clinic: Clinic, doctor_user: User) -> ClinicMembership:
    m = ClinicMembership(
        id=uuid.uuid4(), clinic_id=clinic.id, user_id=doctor_user.id, role="owner", is_active=True
    )
    db.add(m)
    await db.commit()
    return m


async def _link(db: AsyncSession, patient: User, clinic: Clinic, linked_by: User, status: str = "approved") -> PatientClinicLink:
    link = PatientClinicLink(
        id=uuid.uuid4(),
        patient_id=patient.id,
        clinic_id=clinic.id,
        linked_by=linked_by.id,
        consent_status=status,
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return link


async def _make_patient(db: AsyncSession, email: str) -> User:
    u = User(keycloak_sub=f"patient-{uuid.uuid4()}", email=email, full_name="Extra Patient", role="patient")
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def _make_verified_doctor(db: AsyncSession, email: str) -> tuple[User, Doctor]:
    u = User(keycloak_sub=f"doctor-{uuid.uuid4()}", email=email, full_name="Extra Doctor", role="doctor")
    db.add(u)
    await db.flush()
    d = Doctor(
        id=uuid.uuid4(), user_id=u.id, specialization="Cardiology",
        verified=True, onboarding_step="completed",
    )
    db.add(d)
    await db.commit()
    await db.refresh(u)
    await db.refresh(d)
    return u, d


def _clinic_header(clinic: Clinic) -> dict[str, str]:
    return {"X-Clinic-Id": str(clinic.id)}


async def _request_access(client, doctor: User, clinic: Clinic, patient_id, **kwargs) -> "httpx.Response":
    body = {"purpose": "ongoing care", "access_duration_days": 30}
    body.update(kwargs)
    return await client.post(
        f"/api/v1/doctors/patients/{patient_id}/record-access",
        json=body,
        headers={**make_auth_header(doctor), **_clinic_header(clinic)},
    )


# ---------------------------------------------------------------------------
# POST /doctors/patients/{patient_id}/record-access
# ---------------------------------------------------------------------------


class TestRequestAccess:
    async def test_unauthenticated_401(self, client, patient_user, clinic):
        resp = await client.post(
            f"/api/v1/doctors/patients/{patient_user.id}/record-access",
            json={},
            headers=_clinic_header(clinic),
        )
        assert resp.status_code == 401

    async def test_patient_role_403(self, client, db, patient_user, clinic, doctor_user, doctor_profile):
        await _link(db, patient_user, clinic, doctor_user)
        resp = await client.post(
            f"/api/v1/doctors/patients/{patient_user.id}/record-access",
            json={},
            headers={**make_auth_header(patient_user), **_clinic_header(clinic)},
        )
        assert resp.status_code == 403

    async def test_unverified_doctor_403(self, client, db, patient_user, clinic):
        u = User(keycloak_sub=f"doctor-{uuid.uuid4()}", email="unv@test.com", full_name="Unverified", role="doctor")
        db.add(u)
        await db.flush()
        db.add(Doctor(id=uuid.uuid4(), user_id=u.id, verified=False, onboarding_step="pending"))
        await _link(db, patient_user, clinic, u)
        await db.commit()
        resp = await client.post(
            f"/api/v1/doctors/patients/{patient_user.id}/record-access",
            json={},
            headers={**make_auth_header(u), **_clinic_header(clinic)},
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "ONBOARDING_INCOMPLETE"

    async def test_missing_clinic_header_400(self, client, db, patient_user, doctor_user, doctor_profile, clinic):
        await _link(db, patient_user, clinic, doctor_user)
        resp = await client.post(
            f"/api/v1/doctors/patients/{patient_user.id}/record-access",
            json={},
            headers=make_auth_header(doctor_user),
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "MISSING_CLINIC"

    async def test_nonmember_clinic_403(
        self, client, db, patient_user, doctor_user, doctor_profile, clinic, other_clinic
    ):
        # Doctor belongs to `clinic`, not `other_clinic`.
        await _link(db, patient_user, other_clinic, doctor_user)
        resp = await client.post(
            f"/api/v1/doctors/patients/{patient_user.id}/record-access",
            json={},
            headers={**make_auth_header(doctor_user), **_clinic_header(other_clinic)},
        )
        assert resp.status_code == 403

    async def test_patient_not_linked_403(
        self, client, db, patient_user, doctor_user, doctor_profile, clinic, doctor_membership
    ):
        resp = await _request_access(client, doctor_user, clinic, patient_user.id)
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "NOT_LINKED"

    async def test_pending_link_not_enough_403(
        self, client, db, patient_user, doctor_user, doctor_profile, clinic, doctor_membership
    ):
        await _link(db, patient_user, clinic, doctor_user, status="pending")
        resp = await _request_access(client, doctor_user, clinic, patient_user.id)
        assert resp.status_code == 403

    async def test_success_201_and_notifies_patient(
        self, client, db, patient_user, doctor_user, doctor_profile, clinic, doctor_membership
    ):
        await _link(db, patient_user, clinic, doctor_user)
        resp = await _request_access(client, doctor_user, clinic, patient_user.id)
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["status"] == "pending"
        assert body["purpose"] == "ongoing care"
        assert body["access_duration_days"] == 30
        assert body["expires_at"] is None
        assert body["consented_at"] is None

        notif = (
            await db.execute(
                select(Notification).where(
                    Notification.user_id == patient_user.id,
                    Notification.type == "system",
                )
            )
        ).scalars().first()
        assert notif is not None
        assert "record access" in notif.title.lower()

    async def test_duplicate_pending_409(
        self, client, db, patient_user, doctor_user, doctor_profile, clinic, doctor_membership
    ):
        await _link(db, patient_user, clinic, doctor_user)
        first = await _request_access(client, doctor_user, clinic, patient_user.id)
        assert first.status_code == 201
        second = await _request_access(client, doctor_user, clinic, patient_user.id)
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "PENDING_REQUEST_EXISTS"

    @pytest.mark.parametrize("days", [0, -5, 366])
    async def test_invalid_duration_422(
        self, client, db, patient_user, doctor_user, doctor_profile, clinic, doctor_membership, days
    ):
        await _link(db, patient_user, clinic, doctor_user)
        resp = await _request_access(
            client, doctor_user, clinic, patient_user.id, access_duration_days=days
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /doctors/patients/{patient_id}/record-access
# ---------------------------------------------------------------------------


class TestGetConsentStatus:
    async def test_null_when_none(self, client, patient_user, doctor_user, doctor_profile):
        resp = await client.get(
            f"/api/v1/doctors/patients/{patient_user.id}/record-access",
            headers=make_auth_header(doctor_user),
        )
        assert resp.status_code == 200
        assert resp.json() is None

    async def test_returns_latest_consent(
        self, client, db, patient_user, doctor_user, doctor_profile, clinic, doctor_membership
    ):
        await _link(db, patient_user, clinic, doctor_user)
        created = await _request_access(client, doctor_user, clinic, patient_user.id)
        consent_id = created.json()["id"]

        resp = await client.get(
            f"/api/v1/doctors/patients/{patient_user.id}/record-access",
            headers=make_auth_header(doctor_user),
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == consent_id
        assert resp.json()["status"] == "pending"

    async def test_scoped_to_requesting_doctor(
        self, client, db, patient_user, doctor_user, doctor_profile, clinic, doctor_membership
    ):
        await _link(db, patient_user, clinic, doctor_user)
        await _request_access(client, doctor_user, clinic, patient_user.id)

        other_user, _ = await _make_verified_doctor(db, "other-doc@test.com")
        resp = await client.get(
            f"/api/v1/doctors/patients/{patient_user.id}/record-access",
            headers=make_auth_header(other_user),
        )
        assert resp.status_code == 200
        assert resp.json() is None


# ---------------------------------------------------------------------------
# GET /patients/record-access-requests
# ---------------------------------------------------------------------------


class TestPatientListRequests:
    async def test_doctor_role_403(self, client, doctor_user, doctor_profile):
        resp = await client.get(
            "/api/v1/patients/record-access-requests",
            headers=make_auth_header(doctor_user),
        )
        assert resp.status_code == 403

    async def test_unauthenticated_401(self, client):
        resp = await client.get("/api/v1/patients/record-access-requests")
        assert resp.status_code == 401

    async def test_empty(self, client, patient_user):
        resp = await client.get(
            "/api/v1/patients/record-access-requests",
            headers=make_auth_header(patient_user),
        )
        assert resp.status_code == 200
        assert resp.json() == {"data": []}

    async def test_lists_own_with_names(
        self, client, db, patient_user, doctor_user, doctor_profile, clinic, doctor_membership
    ):
        await _link(db, patient_user, clinic, doctor_user)
        await _request_access(client, doctor_user, clinic, patient_user.id)

        resp = await client.get(
            "/api/v1/patients/record-access-requests",
            headers=make_auth_header(patient_user),
        )
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["doctor_name"] == doctor_user.full_name
        assert data[0]["doctor_specialization"] == doctor_profile.specialization
        assert data[0]["clinic_name"] == clinic.name
        assert data[0]["status"] == "pending"

    async def test_excludes_other_patients(
        self, client, db, patient_user, doctor_user, doctor_profile, clinic, doctor_membership
    ):
        other_patient = await _make_patient(db, "other@test.com")
        await _link(db, other_patient, clinic, doctor_user)
        await _request_access(client, doctor_user, clinic, other_patient.id)

        resp = await client.get(
            "/api/v1/patients/record-access-requests",
            headers=make_auth_header(patient_user),
        )
        assert resp.json() == {"data": []}

    async def test_status_filter(
        self, client, db, patient_user, doctor_user, doctor_profile, clinic, doctor_membership
    ):
        await _link(db, patient_user, clinic, doctor_user)
        created = await _request_access(client, doctor_user, clinic, patient_user.id)
        consent_id = created.json()["id"]
        # Approve it so there is one approved + (after re-request is blocked) only that row.
        await client.put(
            f"/api/v1/patients/record-access-requests/{consent_id}",
            json={"action": "approved"},
            headers=make_auth_header(patient_user),
        )

        resp = await client.get(
            "/api/v1/patients/record-access-requests?status=pending",
            headers=make_auth_header(patient_user),
        )
        assert resp.json() == {"data": []}
        resp = await client.get(
            "/api/v1/patients/record-access-requests?status=approved",
            headers=make_auth_header(patient_user),
        )
        assert len(resp.json()["data"]) == 1


# ---------------------------------------------------------------------------
# PUT /patients/record-access-requests/{consent_id}
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def pending_consent(
    client, db, patient_user, doctor_user, doctor_profile, clinic, doctor_membership
) -> RecordAccessConsent:
    await _link(db, patient_user, clinic, doctor_user)
    resp = await _request_access(client, doctor_user, clinic, patient_user.id)
    assert resp.status_code == 201
    consent = (
        await db.execute(
            select(RecordAccessConsent).where(RecordAccessConsent.id == uuid.UUID(resp.json()["id"]))
        )
    ).scalar_one()
    return consent


class TestActOnRequest:
    async def test_doctor_role_403(self, client, doctor_user, doctor_profile, pending_consent):
        resp = await client.put(
            f"/api/v1/patients/record-access-requests/{pending_consent.id}",
            json={"action": "approved"},
            headers=make_auth_header(doctor_user),
        )
        assert resp.status_code == 403

    async def test_not_found_404(self, client, patient_user):
        resp = await client.put(
            f"/api/v1/patients/record-access-requests/{uuid.uuid4()}",
            json={"action": "approved"},
            headers=make_auth_header(patient_user),
        )
        assert resp.status_code == 404

    async def test_other_patients_consent_404(self, client, db, pending_consent):
        other_patient = await _make_patient(db, "intruder@test.com")
        resp = await client.put(
            f"/api/v1/patients/record-access-requests/{pending_consent.id}",
            json={"action": "approved"},
            headers=make_auth_header(other_patient),
        )
        assert resp.status_code == 404

    async def test_approve_sets_expiry(self, client, db, patient_user, pending_consent):
        resp = await client.put(
            f"/api/v1/patients/record-access-requests/{pending_consent.id}",
            json={"action": "approved"},
            headers=make_auth_header(patient_user),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "approved"
        assert body["consented_at"] is not None
        expires = datetime.fromisoformat(body["expires_at"])
        consented = datetime.fromisoformat(body["consented_at"])
        assert (expires - consented).days == pending_consent.access_duration_days

    async def test_reject(self, client, patient_user, pending_consent):
        resp = await client.put(
            f"/api/v1/patients/record-access-requests/{pending_consent.id}",
            json={"action": "rejected"},
            headers=make_auth_header(patient_user),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"
        assert resp.json()["expires_at"] is None

    async def test_revoke_pending_400(self, client, patient_user, pending_consent):
        resp = await client.put(
            f"/api/v1/patients/record-access-requests/{pending_consent.id}",
            json={"action": "revoked"},
            headers=make_auth_header(patient_user),
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_ACTION"

    async def test_revoke_after_approve(self, client, patient_user, pending_consent):
        await client.put(
            f"/api/v1/patients/record-access-requests/{pending_consent.id}",
            json={"action": "approved"},
            headers=make_auth_header(patient_user),
        )
        resp = await client.put(
            f"/api/v1/patients/record-access-requests/{pending_consent.id}",
            json={"action": "revoked"},
            headers=make_auth_header(patient_user),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "revoked"

    async def test_invalid_action_422(self, client, patient_user, pending_consent):
        resp = await client.put(
            f"/api/v1/patients/record-access-requests/{pending_consent.id}",
            json={"action": "explode"},
            headers=make_auth_header(patient_user),
        )
        assert resp.status_code == 422

    async def test_decision_notifies_doctor(self, client, db, patient_user, doctor_user, pending_consent):
        await client.put(
            f"/api/v1/patients/record-access-requests/{pending_consent.id}",
            json={"action": "approved"},
            headers=make_auth_header(patient_user),
        )
        notif = (
            await db.execute(
                select(Notification).where(Notification.user_id == doctor_user.id)
            )
        ).scalars().first()
        assert notif is not None
        assert "approved" in notif.title.lower()
