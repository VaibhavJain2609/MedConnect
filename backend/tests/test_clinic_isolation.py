"""Tests for clinic-scoped authorization and patient–clinic link isolation.

Covers:
- X-Clinic-Id enforcement: members pass, non-members get 403 NOT_CLINIC_MEMBER
- Revoked/pending consent hides patients from the clinic patient list
- Patient link-code lifecycle: valid link, unknown code, expired code
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clinic import Clinic, ClinicMembership
from app.models.doctor import Doctor
from app.models.patient_link import PatientClinicLink, PatientLinkCode
from app.models.user import User
from tests.conftest import create_test_token, make_auth_header

pytestmark = pytest.mark.asyncio

NEXT_WEEK = datetime.now(timezone.utc) + timedelta(days=7)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def clinic(db: AsyncSession, doctor_user: User) -> Clinic:
    clinic = Clinic(
        id=uuid.uuid4(),
        name="Test Clinic",
        city="Mumbai",
        created_by=doctor_user.id,
    )
    db.add(clinic)
    await db.commit()
    await db.refresh(clinic)
    return clinic


@pytest_asyncio.fixture
async def clinic_membership(
    db: AsyncSession, clinic: Clinic, doctor_user: User
) -> ClinicMembership:
    membership = ClinicMembership(
        id=uuid.uuid4(),
        clinic_id=clinic.id,
        user_id=doctor_user.id,
        role="owner",
        is_active=True,
    )
    db.add(membership)
    await db.commit()
    await db.refresh(membership)
    return membership


@pytest_asyncio.fixture
async def approved_link(
    db: AsyncSession, clinic: Clinic, doctor_user: User, patient_user: User
) -> PatientClinicLink:
    link = PatientClinicLink(
        id=uuid.uuid4(),
        patient_id=patient_user.id,
        clinic_id=clinic.id,
        linked_by=doctor_user.id,
        consent_status="approved",
        consented_at=datetime.now(timezone.utc),
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return link


async def _make_other_doctor(db: AsyncSession) -> tuple[User, Doctor, dict]:
    """Create a second doctor (user + profile) with no clinic memberships."""
    user = User(
        keycloak_sub=f"doctor-{uuid.uuid4()}",
        email="outsider@test.com",
        full_name="Outside Doctor",
        role="doctor",
    )
    db.add(user)
    await db.flush()
    profile = Doctor(id=uuid.uuid4(), user_id=user.id, verified=True, onboarding_step="completed")
    db.add(profile)
    await db.commit()
    token = create_test_token(
        sub=user.keycloak_sub, email=user.email, name=user.full_name, roles=["doctor"]
    )
    return user, profile, {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# X-Clinic-Id membership enforcement
# ---------------------------------------------------------------------------


class TestClinicMembershipEnforcement:
    async def test_member_can_list_clinic_patients(
        self, doctor_client, clinic, clinic_membership, approved_link, patient_user
    ):
        resp = await doctor_client.get(f"/api/v1/clinics/{clinic.id}/patients")
        assert resp.status_code == 200
        ids = [row["patient_id"] for row in resp.json()["data"]]
        assert str(patient_user.id) in ids

    async def test_non_member_cannot_list_clinic_patients(
        self, client, db, clinic, approved_link
    ):
        _, _, outsider_auth = await _make_other_doctor(db)
        resp = await client.get(
            f"/api/v1/clinics/{clinic.id}/patients", headers=outsider_auth
        )
        assert resp.status_code == 403

    async def test_member_x_clinic_id_accepted(
        self, doctor_client, clinic, clinic_membership
    ):
        """A clinic member can book a guest appointment under the clinic."""
        resp = await doctor_client.post(
            "/api/v1/appointments/guest",
            json={
                "patient_name": "Walk In",
                "patient_phone": "+919999999999",
                "scheduled_at": NEXT_WEEK.isoformat(),
                "type": "in-person",
            },
            headers={"X-Clinic-Id": str(clinic.id)},
        )
        assert resp.status_code == 201

    async def test_non_member_x_clinic_id_rejected(
        self, client, db, clinic, clinic_membership
    ):
        """A doctor who is not a clinic member gets 403 NOT_CLINIC_MEMBER."""
        _, _, outsider_auth = await _make_other_doctor(db)
        resp = await client.post(
            "/api/v1/appointments/guest",
            json={
                "patient_name": "Walk In",
                "patient_phone": "+919999999999",
                "scheduled_at": NEXT_WEEK.isoformat(),
                "type": "in-person",
            },
            headers={**outsider_auth, "X-Clinic-Id": str(clinic.id)},
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "NOT_CLINIC_MEMBER"

    async def test_missing_x_clinic_id_rejected(self, doctor_client):
        """Endpoints requiring clinic context reject requests without the header."""
        resp = await doctor_client.post(
            "/api/v1/appointments/guest",
            json={
                "patient_name": "Walk In",
                "patient_phone": "+919999999999",
                "scheduled_at": NEXT_WEEK.isoformat(),
                "type": "in-person",
            },
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "MISSING_CLINIC"

    async def test_malformed_x_clinic_id_rejected(self, doctor_client):
        resp = await doctor_client.post(
            "/api/v1/appointments/guest",
            json={
                "patient_name": "Walk In",
                "patient_phone": "+919999999999",
                "scheduled_at": NEXT_WEEK.isoformat(),
                "type": "in-person",
            },
            headers={"X-Clinic-Id": "not-a-uuid"},
        )
        # HTTPException(422) is remapped to 400 VALIDATION_ERROR
        assert resp.status_code == 400

    async def test_inactive_membership_rejected(
        self, client, db, clinic, doctor_user, doctor_profile
    ):
        """A deactivated membership must not grant access."""
        inactive = ClinicMembership(
            id=uuid.uuid4(),
            clinic_id=clinic.id,
            user_id=doctor_user.id,
            role="doctor",
            is_active=False,
        )
        db.add(inactive)
        await db.commit()

        resp = await client.get(
            f"/api/v1/clinics/{clinic.id}/patients",
            headers=make_auth_header(doctor_user, roles=["doctor"]),
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Consent-driven visibility
# ---------------------------------------------------------------------------


class TestConsentVisibility:
    async def test_revoked_consent_hides_patient_from_clinic_list(
        self,
        client,
        db,
        clinic,
        clinic_membership,
        approved_link,
        doctor_user,
        patient_user,
        doctor_profile,
    ):
        doctor_auth = make_auth_header(doctor_user, roles=["doctor"])
        patient_auth = make_auth_header(patient_user)

        # Sanity: patient visible while consent is approved
        before = await client.get(
            f"/api/v1/clinics/{clinic.id}/patients", headers=doctor_auth
        )
        assert before.status_code == 200
        assert str(patient_user.id) in [
            row["patient_id"] for row in before.json()["data"]
        ]

        # Patient revokes consent through the consent endpoint
        revoke = await client.put(
            f"/api/v1/patients/clinic-links/{approved_link.id}/consent",
            json={"action": "revoked"},
            headers=patient_auth,
        )
        assert revoke.status_code == 200
        assert revoke.json()["consent_status"] == "revoked"

        # Revoked patient no longer appears in the clinic's patient list
        after = await client.get(
            f"/api/v1/clinics/{clinic.id}/patients", headers=doctor_auth
        )
        assert after.status_code == 200
        assert str(patient_user.id) not in [
            row["patient_id"] for row in after.json()["data"]
        ]

    async def test_pending_consent_hides_patient_from_clinic_list(
        self, doctor_client, db, clinic, clinic_membership, doctor_user, patient_user,
        doctor_profile,
    ):
        link = PatientClinicLink(
            id=uuid.uuid4(),
            patient_id=patient_user.id,
            clinic_id=clinic.id,
            linked_by=doctor_user.id,
            consent_status="pending",
        )
        db.add(link)
        await db.commit()

        listing = await doctor_client.get(f"/api/v1/clinics/{clinic.id}/patients")
        assert listing.status_code == 200
        ids = [row["patient_id"] for row in listing.json()["data"]]
        assert str(patient_user.id) not in ids

    async def test_pending_link_visible_with_consent_only_false(
        self, doctor_client, db, clinic, clinic_membership, doctor_user, patient_user,
        doctor_profile,
    ):
        link = PatientClinicLink(
            id=uuid.uuid4(),
            patient_id=patient_user.id,
            clinic_id=clinic.id,
            linked_by=doctor_user.id,
            consent_status="pending",
        )
        db.add(link)
        await db.commit()

        listing = await doctor_client.get(
            f"/api/v1/clinics/{clinic.id}/patients?consent_only=false"
        )
        assert listing.status_code == 200
        rows = listing.json()["data"]
        assert len(rows) == 1
        assert rows[0]["patient_id"] is None  # identity masked until consent is approved


# ---------------------------------------------------------------------------
# Patient link codes
# ---------------------------------------------------------------------------


class TestLinkCodes:
    async def test_patient_gets_link_code(self, patient_client):
        resp = await patient_client.get("/api/v1/patients/link-code")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["code"]) == 10
        assert "expires_at" in body

    async def test_expired_code_rotates_on_get(
        self, patient_client, db, patient_user
    ):
        stale = PatientLinkCode(
            id=uuid.uuid4(),
            patient_id=patient_user.id,
            code="STALECODE1",
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        db.add(stale)
        await db.commit()

        resp = await patient_client.get("/api/v1/patients/link-code")
        assert resp.status_code == 200
        assert resp.json()["code"] != "STALECODE1"

    async def test_member_links_patient_with_valid_code(
        self, doctor_client, db, clinic, clinic_membership, patient_user
    ):
        code = PatientLinkCode(
            id=uuid.uuid4(),
            patient_id=patient_user.id,
            code="VALIDCODE1",
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
        db.add(code)
        await db.commit()

        resp = await doctor_client.post(
            f"/api/v1/clinics/{clinic.id}/link-patient", json={"code": "validcode1"}
        )
        assert resp.status_code == 201
        assert resp.json()["consent_status"] == "pending"
        assert resp.json()["patient_id"] == str(patient_user.id)

    async def test_expired_code_rejected(
        self, doctor_client, db, clinic, clinic_membership, patient_user
    ):
        code = PatientLinkCode(
            id=uuid.uuid4(),
            patient_id=patient_user.id,
            code="EXPIRED123",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        db.add(code)
        await db.commit()

        resp = await doctor_client.post(
            f"/api/v1/clinics/{clinic.id}/link-patient", json={"code": "EXPIRED123"}
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "EXPIRED_CODE"

    async def test_unknown_code_returns_404(
        self, doctor_client, clinic, clinic_membership
    ):
        resp = await doctor_client.post(
            f"/api/v1/clinics/{clinic.id}/link-patient", json={"code": "NOSUCHCODE"}
        )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "INVALID_CODE"

    async def test_non_member_cannot_link_patient(
        self, client, db, clinic, patient_user
    ):
        _, _, outsider_auth = await _make_other_doctor(db)
        code = PatientLinkCode(
            id=uuid.uuid4(),
            patient_id=patient_user.id,
            code="VALIDCODE2",
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
        db.add(code)
        await db.commit()

        resp = await client.post(
            f"/api/v1/clinics/{clinic.id}/link-patient",
            json={"code": "VALIDCODE2"},
            headers=outsider_auth,
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "NOT_CLINIC_MEMBER"
