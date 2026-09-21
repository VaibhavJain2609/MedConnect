"""Round-10 coverage for the patient-clinic link router.

Covers:
- GET  /api/v1/patients/link-code — create/reuse/rotate, patient-only gate.
- POST /api/v1/clinics/{id}/link-patient — redeem a link code as a verified
  clinic member: happy path, code consumption, duplicate 409, revoked-link
  reactivation, expired/unknown/malformed codes, membership + verification
  gates.
- GET  /api/v1/patients/clinic-links — patient's own link list + isolation.
- PUT  /api/v1/patients/clinic-links/{id}/consent — approve/revoke/restore
  lifecycle, ownership, notification to the linking doctor.
- GET  /api/v1/clinics/{id}/patients — clinic-side list, consent_only
  filtering + PII masking, membership gate.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clinic import Clinic, ClinicMembership
from app.models.doctor import Doctor
from app.models.notification import Notification
from app.models.patient_link import PatientClinicLink, PatientLinkCode
from app.models.user import User
from tests.conftest import make_auth_header

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def clinic(db: AsyncSession, doctor_user: User) -> Clinic:
    c = Clinic(id=uuid.uuid4(), name="Link Clinic", city="Delhi", created_by=doctor_user.id)
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


@pytest_asyncio.fixture
async def second_clinic(db: AsyncSession, doctor_user: User) -> Clinic:
    c = Clinic(id=uuid.uuid4(), name="Second Clinic", city="Goa", created_by=doctor_user.id)
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


async def _membership(
    db: AsyncSession, clinic_id, user_id, role: str = "owner"
) -> ClinicMembership:
    m = ClinicMembership(
        id=uuid.uuid4(), clinic_id=clinic_id, user_id=user_id, role=role, is_active=True
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


@pytest_asyncio.fixture
async def owner_membership(db: AsyncSession, clinic: Clinic, doctor_user: User):
    return await _membership(db, clinic.id, doctor_user.id, "owner")


async def _link_code(
    db: AsyncSession, patient_id, code: str = "LINKCODE01", expired: bool = False
) -> PatientLinkCode:
    lc = PatientLinkCode(
        id=uuid.uuid4(),
        patient_id=patient_id,
        code=code,
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=-1 if expired else 1),
    )
    db.add(lc)
    await db.commit()
    await db.refresh(lc)
    return lc


async def _link(
    db: AsyncSession,
    patient_id,
    clinic_id,
    linked_by,
    status: str = "pending",
) -> PatientClinicLink:
    link = PatientClinicLink(
        id=uuid.uuid4(),
        patient_id=patient_id,
        clinic_id=clinic_id,
        linked_by=linked_by,
        consent_status=status,
        consented_at=datetime.now(timezone.utc) if status == "approved" else None,
        revoked_at=datetime.now(timezone.utc) if status == "revoked" else None,
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return link


async def _make_doctor(
    db: AsyncSession,
    *,
    with_profile: bool = True,
    email: str | None = None,
) -> tuple[User, Doctor | None, dict]:
    user = User(
        keycloak_sub=f"doctor-{uuid.uuid4()}",
        email=email or f"{uuid.uuid4().hex[:8]}@test.com",
        full_name="Other Doctor",
        role="doctor",
    )
    db.add(user)
    await db.flush()
    profile = None
    if with_profile:
        profile = Doctor(
            id=uuid.uuid4(), user_id=user.id, verified=True, onboarding_step="completed"
        )
        db.add(profile)
    await db.commit()
    return user, profile, make_auth_header(user, roles=["doctor"])


async def _make_patient(db: AsyncSession, email: str | None = None) -> tuple[User, dict]:
    user = User(
        keycloak_sub=f"patient-{uuid.uuid4()}",
        email=email or f"{uuid.uuid4().hex[:8]}@test.com",
        full_name="Other Patient",
        role="patient",
    )
    db.add(user)
    await db.commit()
    return user, make_auth_header(user)


# ---------------------------------------------------------------------------
# GET /patients/link-code
# ---------------------------------------------------------------------------


class TestLinkCode:
    async def test_creates_code(self, patient_client):
        resp = await patient_client.get("/api/v1/patients/link-code")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert len(body["code"]) == 10
        expires = datetime.fromisoformat(body["expires_at"])
        assert expires > datetime.now(timezone.utc)

    async def test_code_is_stable_until_expiry(self, patient_client):
        first = await patient_client.get("/api/v1/patients/link-code")
        second = await patient_client.get("/api/v1/patients/link-code")
        assert first.json()["code"] == second.json()["code"]

    async def test_consumed_code_regenerates(
        self, client, db, clinic, owner_membership, doctor_user, doctor_profile, patient_user
    ):
        """Once a clinic consumes a code, the patient's next /link-code
        request must mint a fresh one."""
        resp = await client.get(
            "/api/v1/patients/link-code", headers=make_auth_header(patient_user)
        )
        original = resp.json()["code"]

        doctor_auth = make_auth_header(doctor_user, roles=["doctor"])
        linked = await client.post(
            f"/api/v1/clinics/{clinic.id}/link-patient",
            json={"code": original},
            headers=doctor_auth,
        )
        assert linked.status_code == 201

        again = await client.get(
            "/api/v1/patients/link-code", headers=make_auth_header(patient_user)
        )
        assert again.status_code == 200
        assert again.json()["code"] != original

    async def test_requires_patient_role(self, doctor_client):
        resp = await doctor_client.get("/api/v1/patients/link-code")
        assert resp.status_code == 403

    async def test_requires_auth(self, client):
        resp = await client.get("/api/v1/patients/link-code")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /clinics/{id}/link-patient
# ---------------------------------------------------------------------------


class TestLinkPatient:
    async def test_happy_path_consumes_code(
        self, doctor_client, db, clinic, owner_membership, doctor_user, patient_user
    ):
        code = await _link_code(db, patient_user.id)
        resp = await doctor_client.post(
            f"/api/v1/clinics/{clinic.id}/link-patient", json={"code": code.code}
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["consent_status"] == "pending"
        assert body["patient_id"] == str(patient_user.id)
        assert body["patient_name"] == "Patient User"

        link = await db.scalar(
            select(PatientClinicLink).where(
                PatientClinicLink.patient_id == patient_user.id,
                PatientClinicLink.clinic_id == clinic.id,
            )
        )
        assert link is not None
        assert link.consent_status == "pending"
        assert link.linked_by == doctor_user.id

        await db.refresh(code)
        assert code.deleted_at is not None  # consumed

    async def test_code_is_single_use(
        self,
        doctor_client,
        db,
        clinic,
        second_clinic,
        owner_membership,
        doctor_user,
        patient_user,
    ):
        """A consumed code cannot establish a second link at another clinic."""
        await _membership(db, second_clinic.id, doctor_user.id, "doctor")
        code = await _link_code(db, patient_user.id)

        first = await doctor_client.post(
            f"/api/v1/clinics/{clinic.id}/link-patient", json={"code": code.code}
        )
        assert first.status_code == 201

        second = await doctor_client.post(
            f"/api/v1/clinics/{second_clinic.id}/link-patient",
            json={"code": code.code},
        )
        assert second.status_code == 404
        assert second.json()["error"]["code"] == "INVALID_CODE"

    async def test_duplicate_link_409(
        self, client, db, clinic, owner_membership, doctor_user, doctor_profile, patient_user
    ):
        doctor_auth = make_auth_header(doctor_user, roles=["doctor"])
        code = await _link_code(db, patient_user.id)
        first = await client.post(
            f"/api/v1/clinics/{clinic.id}/link-patient",
            json={"code": code.code},
            headers=doctor_auth,
        )
        assert first.status_code == 201

        # Patient generates a fresh code; re-linking the same clinic conflicts.
        new_code_resp = await client.get(
            "/api/v1/patients/link-code", headers=make_auth_header(patient_user)
        )
        second = await client.post(
            f"/api/v1/clinics/{clinic.id}/link-patient",
            json={"code": new_code_resp.json()["code"]},
            headers=doctor_auth,
        )
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "ALREADY_LINKED"

    async def test_revoked_link_reactivated_as_pending(
        self, doctor_client, db, clinic, owner_membership, doctor_user, patient_user
    ):
        await _link(
            db, patient_user.id, clinic.id, doctor_user.id, status="revoked"
        )
        code = await _link_code(db, patient_user.id)
        resp = await doctor_client.post(
            f"/api/v1/clinics/{clinic.id}/link-patient", json={"code": code.code}
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["consent_status"] == "pending"

        link = await db.scalar(
            select(PatientClinicLink).where(
                PatientClinicLink.patient_id == patient_user.id,
                PatientClinicLink.clinic_id == clinic.id,
            )
        )
        assert link.consent_status == "pending"
        assert link.revoked_at is None
        assert link.consented_at is None

    async def test_receptionist_member_can_link(
        self, doctor_client, db, clinic, doctor_user, patient_user
    ):
        """Any active clinic membership (incl. receptionist) may initiate a
        link — the code is patient-issued and consent is still pending."""
        await _membership(db, clinic.id, doctor_user.id, "receptionist")
        code = await _link_code(db, patient_user.id)
        resp = await doctor_client.post(
            f"/api/v1/clinics/{clinic.id}/link-patient", json={"code": code.code}
        )
        assert resp.status_code == 201

    async def test_non_member_403(self, client, db, clinic, patient_user):
        _, _, outsider_auth = await _make_doctor(db)
        code = await _link_code(db, patient_user.id)
        resp = await client.post(
            f"/api/v1/clinics/{clinic.id}/link-patient",
            json={"code": code.code},
            headers=outsider_auth,
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "NOT_CLINIC_MEMBER"

    async def test_invalid_clinic_id_422(
        self, doctor_client, db, owner_membership, patient_user
    ):
        await _link_code(db, patient_user.id)
        resp = await doctor_client.post(
            "/api/v1/clinics/not-a-uuid/link-patient", json={"code": "LINKCODE01"}
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "INVALID_ID"

    async def test_unknown_code_404(
        self, doctor_client, clinic, owner_membership
    ):
        resp = await doctor_client.post(
            f"/api/v1/clinics/{clinic.id}/link-patient", json={"code": "NOSUCHCODE"}
        )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "INVALID_CODE"

    async def test_malformed_code_404(
        self, doctor_client, clinic, owner_membership
    ):
        for bad in ("", "!!!###", "a" * 64):
            resp = await doctor_client.post(
                f"/api/v1/clinics/{clinic.id}/link-patient", json={"code": bad}
            )
            assert resp.status_code == 404, bad
            assert resp.json()["error"]["code"] == "INVALID_CODE"

    async def test_expired_code_400(
        self, doctor_client, db, clinic, owner_membership, patient_user
    ):
        await _link_code(db, patient_user.id, code="OLDCODE99", expired=True)
        resp = await doctor_client.post(
            f"/api/v1/clinics/{clinic.id}/link-patient", json={"code": "OLDCODE99"}
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "EXPIRED_CODE"

    async def test_patient_cannot_link(self, patient_client, clinic):
        resp = await patient_client.post(
            f"/api/v1/clinics/{clinic.id}/link-patient", json={"code": "WHATEVER00"}
        )
        assert resp.status_code == 403

    async def test_unverified_doctor_403(self, client, db, clinic, patient_user):
        """Doctor role but no verified/completed profile → ONBOARDING_INCOMPLETE."""
        user = User(
            keycloak_sub=f"doctor-{uuid.uuid4()}",
            email="unverified@test.com",
            full_name="Unverified Doc",
            role="doctor",
        )
        db.add(user)
        await db.flush()
        db.add(Doctor(id=uuid.uuid4(), user_id=user.id, verified=False))
        await db.commit()

        await _link_code(db, patient_user.id)
        resp = await client.post(
            f"/api/v1/clinics/{clinic.id}/link-patient",
            json={"code": "LINKCODE01"},
            headers=make_auth_header(user, roles=["doctor"]),
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "ONBOARDING_INCOMPLETE"

    async def test_doctor_without_profile_404(self, client, db, clinic, patient_user):
        _, _, auth = await _make_doctor(db, with_profile=False)  # no profile row
        await _link_code(db, patient_user.id)
        resp = await client.post(
            f"/api/v1/clinics/{clinic.id}/link-patient",
            json={"code": "LINKCODE01"},
            headers=auth,
        )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "NOT_FOUND"

    async def test_unauthenticated_401(self, client, clinic):
        resp = await client.post(
            f"/api/v1/clinics/{clinic.id}/link-patient", json={"code": "WHATEVER00"}
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /patients/clinic-links (patient side)
# ---------------------------------------------------------------------------


class TestPatientLinkList:
    async def test_lists_own_links(
        self, patient_client, db, clinic, doctor_user, patient_user
    ):
        link = await _link(
            db, patient_user.id, clinic.id, doctor_user.id, status="approved"
        )
        resp = await patient_client.get("/api/v1/patients/clinic-links")
        assert resp.status_code == 200, resp.text
        rows = resp.json()["data"]
        assert len(rows) == 1
        assert rows[0]["id"] == str(link.id)
        assert rows[0]["clinic_name"] == "Link Clinic"
        assert rows[0]["clinic_city"] == "Delhi"
        assert rows[0]["consent_status"] == "approved"
        assert rows[0]["consented_at"] is not None

    async def test_links_isolated_per_patient(
        self, patient_client, db, clinic, doctor_user, patient_user
    ):
        other_patient, _ = await _make_patient(db)
        await _link(db, other_patient.id, clinic.id, doctor_user.id, status="approved")
        resp = await patient_client.get("/api/v1/patients/clinic-links")
        assert resp.json()["data"] == []

    async def test_revoked_link_still_visible_to_patient(
        self, patient_client, db, clinic, doctor_user, patient_user
    ):
        """The patient should see revoked links in their own list (transparency)."""
        await _link(db, patient_user.id, clinic.id, doctor_user.id, status="revoked")
        resp = await patient_client.get("/api/v1/patients/clinic-links")
        rows = resp.json()["data"]
        assert len(rows) == 1
        assert rows[0]["consent_status"] == "revoked"

    async def test_requires_patient_role(self, doctor_client):
        resp = await doctor_client.get("/api/v1/patients/clinic-links")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# PUT /patients/clinic-links/{id}/consent
# ---------------------------------------------------------------------------


class TestConsent:
    async def test_approve_sets_consented_at(
        self, patient_client, db, clinic, doctor_user, patient_user
    ):
        link = await _link(db, patient_user.id, clinic.id, doctor_user.id)
        resp = await patient_client.put(
            f"/api/v1/patients/clinic-links/{link.id}/consent",
            json={"action": "approved"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["consent_status"] == "approved"
        await db.refresh(link)
        assert link.consented_at is not None
        assert link.revoked_at is None

    async def test_revoke_drops_clinic_access(
        self, client, db, clinic, owner_membership, doctor_user, doctor_profile, patient_user
    ):
        link = await _link(
            db, patient_user.id, clinic.id, doctor_user.id, status="approved"
        )
        doctor_auth = make_auth_header(doctor_user, roles=["doctor"])
        before = await client.get(
            f"/api/v1/clinics/{clinic.id}/patients", headers=doctor_auth
        )
        assert before.json()["total"] == 1

        resp = await client.put(
            f"/api/v1/patients/clinic-links/{link.id}/consent",
            json={"action": "revoked"},
            headers=make_auth_header(patient_user),
        )
        assert resp.status_code == 200
        assert resp.json()["consent_status"] == "revoked"
        await db.refresh(link)
        assert link.revoked_at is not None

        after = await client.get(
            f"/api/v1/clinics/{clinic.id}/patients", headers=doctor_auth
        )
        assert after.json()["total"] == 0

    async def test_reapprove_restores_access(
        self, client, db, clinic, owner_membership, doctor_user, doctor_profile, patient_user
    ):
        link = await _link(
            db, patient_user.id, clinic.id, doctor_user.id, status="revoked"
        )
        resp = await client.put(
            f"/api/v1/patients/clinic-links/{link.id}/consent",
            json={"action": "approved"},
            headers=make_auth_header(patient_user),
        )
        assert resp.status_code == 200
        assert resp.json()["consent_status"] == "approved"

        listing = await client.get(
            f"/api/v1/clinics/{clinic.id}/patients",
            headers=make_auth_header(doctor_user, roles=["doctor"]),
        )
        assert listing.json()["total"] == 1
        assert listing.json()["data"][0]["patient_id"] == str(patient_user.id)

    async def test_invalid_action_400(
        self, patient_client, db, clinic, doctor_user, patient_user
    ):
        link = await _link(db, patient_user.id, clinic.id, doctor_user.id)
        resp = await patient_client.put(
            f"/api/v1/patients/clinic-links/{link.id}/consent",
            json={"action": "pending"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_ACTION"

    async def test_other_patients_link_404(
        self, patient_client, db, clinic, doctor_user
    ):
        other_patient, _ = await _make_patient(db)
        link = await _link(db, other_patient.id, clinic.id, doctor_user.id)
        resp = await patient_client.put(
            f"/api/v1/patients/clinic-links/{link.id}/consent",
            json={"action": "approved"},
        )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "NOT_FOUND"

    async def test_invalid_link_id_422(self, patient_client):
        resp = await patient_client.put(
            "/api/v1/patients/clinic-links/not-a-uuid/consent",
            json={"action": "approved"},
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "INVALID_ID"

    async def test_consent_notifies_linking_doctor(
        self, patient_client, db, clinic, doctor_user, patient_user
    ):
        link = await _link(db, patient_user.id, clinic.id, doctor_user.id)
        resp = await patient_client.put(
            f"/api/v1/patients/clinic-links/{link.id}/consent",
            json={"action": "approved"},
        )
        assert resp.status_code == 200
        notif = await db.scalar(
            select(Notification).where(Notification.user_id == doctor_user.id)
        )
        assert notif is not None
        assert "approved" in notif.title
        assert notif.action_url == "/doctor/patients/link"

    async def test_requires_patient_role(
        self, doctor_client, db, clinic, doctor_user, patient_user
    ):
        link = await _link(db, patient_user.id, clinic.id, doctor_user.id)
        resp = await doctor_client.put(
            f"/api/v1/patients/clinic-links/{link.id}/consent",
            json={"action": "approved"},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /clinics/{id}/patients (clinic side)
# ---------------------------------------------------------------------------


class TestClinicPatientList:
    async def test_approved_link_shows_pii(
        self, doctor_client, db, clinic, owner_membership, doctor_user, patient_user
    ):
        await _link(db, patient_user.id, clinic.id, doctor_user.id, status="approved")
        resp = await doctor_client.get(f"/api/v1/clinics/{clinic.id}/patients")
        assert resp.status_code == 200, resp.text
        rows = resp.json()["data"]
        assert resp.json()["total"] == 1
        assert rows[0]["patient_id"] == str(patient_user.id)
        assert rows[0]["full_name"] == "Patient User"
        assert rows[0]["email"] == "patient@test.com"

    async def test_pending_masked_with_consent_only_false(
        self, doctor_client, db, clinic, owner_membership, doctor_user, patient_user
    ):
        link = await _link(db, patient_user.id, clinic.id, doctor_user.id, status="pending")
        resp = await doctor_client.get(
            f"/api/v1/clinics/{clinic.id}/patients?consent_only=false"
        )
        assert resp.status_code == 200
        rows = resp.json()["data"]
        assert len(rows) == 1
        assert rows[0]["link_id"] == str(link.id)
        assert rows[0]["consent_status"] == "pending"
        # PII masked until consent is approved
        assert rows[0]["patient_id"] is None
        assert rows[0]["full_name"] is None
        assert rows[0]["email"] is None

    async def test_non_member_403(self, client, db, clinic):
        _, _, outsider_auth = await _make_doctor(db)
        resp = await client.get(
            f"/api/v1/clinics/{clinic.id}/patients", headers=outsider_auth
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "NOT_CLINIC_MEMBER"

    async def test_invalid_clinic_id_422(self, doctor_client):
        resp = await doctor_client.get("/api/v1/clinics/not-a-uuid/patients")
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "INVALID_ID"

    async def test_patient_forbidden(self, patient_client, clinic):
        resp = await patient_client.get(f"/api/v1/clinics/{clinic.id}/patients")
        assert resp.status_code == 403

    async def test_unauthenticated_401(self, client, clinic):
        resp = await client.get(f"/api/v1/clinics/{clinic.id}/patients")
        assert resp.status_code == 401
