"""Coverage for the admin doctors router (/api/v1/admin/doctors*).

Covers the admin doctor list with filters (search / specialty / verified),
the specialties dropdown, doctor detail with activity counts, the
verification-state transitions (PUT /{id}/verify approve|reject incl.
notifications + audit trail), admin create/update/delete (incl. the
self-delete guard), and the admin-only gate.
"""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.doctor import Doctor
from app.models.medical_record import MedicalRecord
from app.models.notification import Notification
from app.models.user import User

pytestmark = pytest.mark.asyncio

BASE = "/api/v1/admin/doctors"


async def _make_doctor(
    db: AsyncSession,
    *,
    name: str = "Doc Extra",
    email: str | None = None,
    specialization: str | None = "Cardiology",
    license_number: str | None = None,
    verified: bool = False,
    onboarding_step: str = "pending",
) -> tuple[User, Doctor]:
    user = User(
        id=uuid.uuid4(),
        keycloak_sub=f"doc-{uuid.uuid4()}",
        full_name=name,
        email=email or f"{uuid.uuid4().hex[:8]}@test.com",
        role="doctor",
    )
    db.add(user)
    await db.flush()
    doctor = Doctor(
        id=uuid.uuid4(),
        user_id=user.id,
        specialization=specialization,
        license_number=license_number,
        verified=verified,
        onboarding_step=onboarding_step,
    )
    db.add(doctor)
    await db.commit()
    await db.refresh(doctor)
    return user, doctor


# ---------------------------------------------------------------------------
# GET /doctors — list + filters
# ---------------------------------------------------------------------------


class TestListDoctors:
    async def test_list_shape(self, admin_client, doctor_user, doctor_profile):
        resp = await admin_client.get(BASE)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] == 1
        item = body["doctors"][0]
        assert item["id"] == str(doctor_profile.id)
        assert item["user_id"] == str(doctor_user.id)
        assert item["name"] == "Doctor User"
        assert item["specialization"] == "General Physician"
        assert item["verified"] is True

    async def test_search_by_name_email_license(
        self, admin_client, db, doctor_user, doctor_profile
    ):
        _, d2 = await _make_doctor(
            db, name="Cardio Sam", email="cardio@test.com",
            license_number="LIC-999", specialization="Cardiology",
        )

        by_name = await admin_client.get(BASE, params={"search": "Cardio"})
        assert [d["id"] for d in by_name.json()["doctors"]] == [str(d2.id)]

        by_license = await admin_client.get(BASE, params={"search": "LIC-999"})
        assert [d["id"] for d in by_license.json()["doctors"]] == [str(d2.id)]

        no_match = await admin_client.get(BASE, params={"search": "nobody"})
        assert no_match.json()["total"] == 0

    async def test_specialty_filter(self, admin_client, db, doctor_user, doctor_profile):
        _, d2 = await _make_doctor(db, name="Derm Dana", specialization="Dermatology")
        resp = await admin_client.get(BASE, params={"specialty": "Derm"})
        assert [d["id"] for d in resp.json()["doctors"]] == [str(d2.id)]

    async def test_verified_filter(self, admin_client, db, doctor_user, doctor_profile):
        _, pending = await _make_doctor(db, name="Pending Pete", verified=False)

        verified = await admin_client.get(BASE, params={"verified": "true"})
        assert [d["id"] for d in verified.json()["doctors"]] == [str(doctor_profile.id)]

        unverified = await admin_client.get(BASE, params={"verified": "false"})
        assert [d["id"] for d in unverified.json()["doctors"]] == [str(pending.id)]

    async def test_pagination(self, admin_client, db, doctor_user, doctor_profile):
        for i in range(2):
            await _make_doctor(db, name=f"Doc {i}")
        resp = await admin_client.get(BASE, params={"limit": 2, "page": 2})
        body = resp.json()
        assert body["total"] == 3
        assert body["totalPages"] == 2
        assert len(body["doctors"]) == 1

    async def test_soft_deleted_doctor_excluded(
        self, admin_client, db, doctor_user, doctor_profile
    ):
        doctor_profile.deleted_at = datetime.now(timezone.utc)
        await db.commit()
        resp = await admin_client.get(BASE)
        assert resp.json()["total"] == 0

    async def test_specialties_endpoint(
        self, admin_client, db, doctor_user, doctor_profile
    ):
        await _make_doctor(db, name="Derm Dana", specialization="Dermatology")
        await _make_doctor(db, name="Derm Dave", specialization="Dermatology")
        await _make_doctor(db, name="NoSpec", specialization=None)

        resp = await admin_client.get(f"{BASE}/specialties")
        assert resp.status_code == 200, resp.text
        assert resp.json() == ["Dermatology", "General Physician"]


# ---------------------------------------------------------------------------
# GET /doctors/{id} — detail
# ---------------------------------------------------------------------------


class TestDoctorDetail:
    async def test_detail_with_counts(
        self, admin_client, db, doctor_user, doctor_profile, patient_user
    ):
        db.add(
            MedicalRecord(
                id=uuid.uuid4(),
                patient_id=patient_user.id,
                doctor_id=doctor_profile.id,
                record_type="opd_note",
                title="Visit",
            )
        )
        await db.commit()

        resp = await admin_client.get(f"{BASE}/{doctor_profile.id}")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["id"] == str(doctor_profile.id)
        assert body["user_id"] == str(doctor_user.id)
        assert body["name"] == "Doctor User"
        assert body["email"] == "doctor@test.com"
        assert body["verified"] is True
        assert body["is_active"] is True
        assert body["records_count"] == 1
        assert body["prescriptions_count"] == 0

    async def test_unknown_404(self, admin_client):
        resp = await admin_client.get(f"{BASE}/{uuid.uuid4()}")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "NOT_FOUND"


# ---------------------------------------------------------------------------
# PUT /doctors/{id}/verify — approve / reject transitions
# ---------------------------------------------------------------------------


class TestVerifyDoctor:
    async def test_approve_sets_verified_and_notifies(
        self, admin_client, db, doctor_user
    ):
        _, doctor = await _make_doctor(db, name="Pending Pete", verified=False)

        resp = await admin_client.put(
            f"{BASE}/{doctor.id}/verify",
            json={"action": "approve"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["verified"] is True
        assert "approved" in resp.json()["message"]

        await db.refresh(doctor)
        assert doctor.verified is True

        notif = await db.scalar(
            select(Notification).where(Notification.user_id == doctor.user_id)
        )
        assert notif is not None
        assert notif.title == "Verification Approved"
        assert notif.action_url == "/doctor/dashboard"

    async def test_reject_clears_verified_with_reason(
        self, admin_client, db, doctor_user, doctor_profile
    ):
        resp = await admin_client.put(
            f"{BASE}/{doctor_profile.id}/verify",
            json={"action": "reject", "reason": "license blurry"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["verified"] is False
        assert "rejected" in resp.json()["message"]

        await db.refresh(doctor_profile)
        assert doctor_profile.verified is False

        notif = await db.scalar(
            select(Notification).where(Notification.user_id == doctor_user.id)
        )
        assert notif.title == "Verification Rejected"
        assert "license blurry" in notif.message

    async def test_verify_writes_audit_entry(
        self, admin_client, db, doctor_user
    ):
        _, doctor = await _make_doctor(db, verified=False)
        resp = await admin_client.put(
            f"{BASE}/{doctor.id}/verify",
            json={"action": "approve", "reason": "docs ok"},
        )
        assert resp.status_code == 200
        log = await db.scalar(
            select(AuditLog).where(
                AuditLog.table_name == "doctors",
                AuditLog.record_id == doctor.id,
                AuditLog.action == "UPDATE",
            )
        )
        assert log is not None
        assert log.old_values == {"verified": False}
        assert log.new_values["verified"] is True
        assert log.new_values["action"] == "approve"

    async def test_invalid_action_422(self, admin_client, doctor_profile):
        resp = await admin_client.put(
            f"{BASE}/{doctor_profile.id}/verify",
            json={"action": "suspend"},
        )
        assert resp.status_code == 422

    async def test_unknown_doctor_404(self, admin_client):
        resp = await admin_client.put(
            f"{BASE}/{uuid.uuid4()}/verify", json={"action": "approve"}
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /doctors — admin create
# ---------------------------------------------------------------------------


class TestCreateDoctor:
    async def test_create_doctor(self, admin_client, db):
        resp = await admin_client.post(
            BASE,
            json={
                "name": "New Doc",
                "email": "newdoc@test.com",
                "specialization": "ENT",
                "license_number": "LIC-1",
                "verified": True,
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["name"] == "New Doc"
        assert body["specialization"] == "ENT"
        assert body["verified"] is True

        user = await db.scalar(select(User).where(User.id == uuid.UUID(body["user_id"])))
        assert user.role == "doctor"
        assert user.keycloak_sub.startswith("walkin:")

    async def test_full_name_alias_accepted(self, admin_client):
        resp = await admin_client.post(BASE, json={"full_name": "Alias Doc"})
        assert resp.status_code == 201
        assert resp.json()["name"] == "Alias Doc"

    async def test_missing_name_400(self, admin_client):
        resp = await admin_client.post(BASE, json={"email": "x@y.z"})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# PUT /doctors/{id} — update incl. suspend via is_active
# ---------------------------------------------------------------------------


class TestUpdateDoctor:
    async def test_update_profile_and_user_fields(
        self, admin_client, db, doctor_user, doctor_profile
    ):
        resp = await admin_client.put(
            f"{BASE}/{doctor_profile.id}",
            json={
                "name": "Doc Renamed",
                "specialization": "Neurology",
                "license_number": "LIC-7",
                "facility_city": "Chennai",
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["name"] == "Doc Renamed"
        assert body["specialization"] == "Neurology"
        assert body["license_number"] == "LIC-7"

        await db.refresh(doctor_user)
        await db.refresh(doctor_profile)
        assert doctor_user.full_name == "Doc Renamed"
        assert doctor_profile.specialization == "Neurology"

    async def test_suspend_via_is_active(
        self, admin_client, db, doctor_user, doctor_profile
    ):
        resp = await admin_client.put(
            f"{BASE}/{doctor_profile.id}", json={"is_active": False}
        )
        assert resp.status_code == 200
        await db.refresh(doctor_user)
        assert doctor_user.is_active is False
        # Detail reflects the suspended state.
        detail = await admin_client.get(f"{BASE}/{doctor_profile.id}")
        assert detail.json()["is_active"] is False

    async def test_verify_flag_via_update(
        self, admin_client, db, doctor_user, doctor_profile
    ):
        resp = await admin_client.put(
            f"{BASE}/{doctor_profile.id}", json={"verified": False}
        )
        assert resp.status_code == 200
        await db.refresh(doctor_profile)
        assert doctor_profile.verified is False

    async def test_unknown_404(self, admin_client):
        resp = await admin_client.put(
            f"{BASE}/{uuid.uuid4()}", json={"name": "Ghost"}
        )
        assert resp.status_code == 404

    async def test_doctor_with_deleted_user_404(
        self, admin_client, db, doctor_user, doctor_profile
    ):
        doctor_user.deleted_at = datetime.now(timezone.utc)
        await db.commit()
        resp = await admin_client.put(
            f"{BASE}/{doctor_profile.id}", json={"name": "Ghost"}
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /doctors/{id}
# ---------------------------------------------------------------------------


class TestDeleteDoctor:
    async def test_soft_deletes_doctor_and_user(
        self, admin_client, db, doctor_user, doctor_profile
    ):
        resp = await admin_client.delete(f"{BASE}/{doctor_profile.id}")
        assert resp.status_code == 200, resp.text
        assert resp.json()["id"] == str(doctor_profile.id)

        await db.refresh(doctor_profile)
        await db.refresh(doctor_user)
        assert doctor_profile.deleted_at is not None
        assert doctor_user.deleted_at is not None
        assert doctor_user.is_active is False

        assert (await admin_client.get(f"{BASE}/{doctor_profile.id}")).status_code == 404
        assert (await admin_client.get(BASE)).json()["total"] == 0

    async def test_self_delete_guard(
        self, admin_client, db, admin_user
    ):
        """An admin who also has a doctor profile cannot delete it — doing so
        would deactivate their own user account."""
        own_profile = Doctor(
            id=uuid.uuid4(), user_id=admin_user.id, verified=True,
        )
        db.add(own_profile)
        await db.commit()

        resp = await admin_client.delete(f"{BASE}/{own_profile.id}")
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "SELF_DELETE"

    async def test_unknown_404(self, admin_client):
        resp = await admin_client.delete(f"{BASE}/{uuid.uuid4()}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Auth gates
# ---------------------------------------------------------------------------


class TestAdminGate:
    @pytest.mark.parametrize(
        "method,url",
        [
            ("get", BASE),
            ("get", f"{BASE}/specialties"),
            ("post", BASE),
            ("get", f"{BASE}/{uuid.uuid4()}"),
            ("put", f"{BASE}/{uuid.uuid4()}"),
            ("put", f"{BASE}/{uuid.uuid4()}/verify"),
            ("delete", f"{BASE}/{uuid.uuid4()}"),
        ],
    )
    async def test_patient_forbidden(self, patient_client, method, url):
        kwargs = {"json": {}} if method in ("post", "put") else {}
        resp = await getattr(patient_client, method)(url, **kwargs)
        assert resp.status_code == 403

    async def test_doctor_forbidden(self, doctor_client):
        resp = await doctor_client.get(BASE)
        assert resp.status_code == 403

    @pytest.mark.parametrize("method", ["get", "post"])
    async def test_unauthenticated_401(self, client, method):
        resp = await getattr(client, method)(BASE, **({"json": {}} if method == "post" else {}))
        assert resp.status_code == 401
