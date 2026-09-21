"""Coverage for the admin users router (/api/v1/admin/users).

Covers list + filters (search / role / is_active / clinic_id), walk-in
patient creation, user detail with activity counts, the prescriptions and
records sub-lists, update (including role change with Keycloak sync and
doctor-profile provisioning), soft delete, the related-patients lookup, and
the admin-only gate.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.medical_record import MedicalRecord
from app.models.patient_link import PatientClinicLink
from app.models.prescription import Prescription
from app.models.user import User

pytestmark = pytest.mark.asyncio

BASE = "/api/v1/admin/users"


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


async def _make_user(
    db: AsyncSession,
    *,
    full_name: str = "Extra User",
    email: str | None = None,
    phone: str | None = None,
    role: str = "patient",
    is_active: bool = True,
    keycloak_sub: str | None = None,
) -> User:
    user = User(
        id=uuid.uuid4(),
        keycloak_sub=keycloak_sub or f"extra-{uuid.uuid4()}",
        full_name=full_name,
        email=email if email is not None else f"{uuid.uuid4().hex[:8]}@test.com",
        phone=phone,
        role=role,
        is_active=is_active,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def clinic(db: AsyncSession, admin_user: User) -> Clinic:
    c = Clinic(id=uuid.uuid4(), name="Admin Users Clinic", city="Pune", created_by=admin_user.id)
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


async def _link(
    db: AsyncSession, patient_id, clinic_id, linked_by, consent_status: str = "approved"
) -> PatientClinicLink:
    link = PatientClinicLink(
        id=uuid.uuid4(),
        patient_id=patient_id,
        clinic_id=clinic_id,
        linked_by=linked_by,
        consent_status=consent_status,
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return link


async def _record(
    db: AsyncSession, patient_id, doctor_id=None, title: str = "Note"
) -> MedicalRecord:
    rec = MedicalRecord(
        id=uuid.uuid4(),
        patient_id=patient_id,
        doctor_id=doctor_id,
        record_type="opd_note",
        title=title,
        source="manual",
    )
    db.add(rec)
    await db.commit()
    await db.refresh(rec)
    return rec


async def _prescription(
    db: AsyncSession, patient_id, doctor: Doctor, record: MedicalRecord
) -> Prescription:
    rx = Prescription(
        id=uuid.uuid4(),
        record_id=record.id,
        doctor_id=doctor.id,
        patient_id=patient_id,
        medicines=[{"brand_name": "Crocin", "dose": "500mg"}],
        diagnosis="viral fever",
        valid_until=date.today() + timedelta(days=5),
    )
    db.add(rx)
    await db.commit()
    await db.refresh(rx)
    return rx


# ---------------------------------------------------------------------------
# GET /api/v1/admin/users — list + filters
# ---------------------------------------------------------------------------


class TestListUsers:
    async def test_lists_all_users_with_shape(
        self, admin_client, admin_user, patient_user
    ):
        resp = await admin_client.get(BASE)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] == 2
        assert body["page"] == 1 and body["limit"] == 20
        ids = {u["id"] for u in body["data"]}
        assert str(admin_user.id) in ids and str(patient_user.id) in ids
        item = next(u for u in body["data"] if u["id"] == str(patient_user.id))
        assert item["role"] == "patient"
        assert item["is_active"] is True
        assert item["consent_status"] is None  # only set on the clinic_id path

    async def test_search_matches_name_and_email(self, admin_client, db, admin_user):
        zebra = await _make_user(db, full_name="Zebra Unique", email="zebra@test.com")
        by_name = await admin_client.get(BASE, params={"search": "Zebra"})
        assert [u["id"] for u in by_name.json()["data"]] == [str(zebra.id)]
        by_email = await admin_client.get(BASE, params={"search": "zebra@"})
        assert [u["id"] for u in by_email.json()["data"]] == [str(zebra.id)]
        no_match = await admin_client.get(BASE, params={"search": "does-not-exist"})
        assert no_match.json()["total"] == 0

    async def test_role_filter(self, admin_client, admin_user, patient_user, doctor_user):
        resp = await admin_client.get(BASE, params={"role": "patient"})
        body = resp.json()
        assert body["total"] == 1
        assert body["data"][0]["id"] == str(patient_user.id)

        # "all" is treated as no filter
        resp_all = await admin_client.get(BASE, params={"role": "all"})
        assert resp_all.json()["total"] == 3

    async def test_is_active_filter(self, admin_client, db, admin_user):
        inactive = await _make_user(db, is_active=False)
        resp = await admin_client.get(BASE, params={"is_active": "false"})
        assert resp.status_code == 200
        ids = [u["id"] for u in resp.json()["data"]]
        assert str(inactive.id) in ids
        assert str(admin_user.id) not in ids

    async def test_clinic_id_filter_returns_linked_patients_with_consent(
        self, admin_client, db, admin_user, patient_user, doctor_user, clinic
    ):
        await _link(db, patient_user.id, clinic.id, admin_user.id, "approved")
        other = await _make_user(db, full_name="Pending Patient")
        await _link(db, other.id, clinic.id, admin_user.id, "pending")
        # doctor_user has no patient link and role != patient anyway.
        unlinked = await _make_user(db, full_name="Unlinked Patient")

        resp = await admin_client.get(BASE, params={"clinic_id": str(clinic.id)})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] == 2
        by_id = {u["id"]: u for u in body["data"]}
        assert by_id[str(patient_user.id)]["consent_status"] == "approved"
        assert by_id[str(other.id)]["consent_status"] == "pending"
        assert str(unlinked.id) not in by_id

    async def test_clinic_id_filter_search_within_clinic(
        self, admin_client, db, admin_user, patient_user, clinic
    ):
        await _link(db, patient_user.id, clinic.id, admin_user.id, "approved")
        other = await _make_user(db, full_name="Clinic Member Two")
        await _link(db, other.id, clinic.id, admin_user.id, "pending")

        resp = await admin_client.get(
            BASE, params={"clinic_id": str(clinic.id), "search": "Member Two"}
        )
        body = resp.json()
        assert body["total"] == 1
        assert body["data"][0]["id"] == str(other.id)

    async def test_clinic_id_invalid_uuid_400(self, admin_client):
        resp = await admin_client.get(BASE, params={"clinic_id": "not-a-uuid"})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_CLINIC_ID"

    async def test_pagination(self, admin_client, db, admin_user, patient_user):
        await _make_user(db)
        page1 = await admin_client.get(BASE, params={"limit": 1, "page": 1})
        body1 = page1.json()
        assert body1["total"] == 3
        assert body1["totalPages"] == 3
        assert len(body1["data"]) == 1
        page2 = await admin_client.get(BASE, params={"limit": 1, "page": 2})
        assert page2.json()["data"][0]["id"] != body1["data"][0]["id"]

    async def test_soft_deleted_users_excluded(self, admin_client, db, patient_user):
        patient_user.deleted_at = datetime.now(timezone.utc)
        await db.commit()
        resp = await admin_client.get(BASE)
        ids = {u["id"] for u in resp.json()["data"]}
        assert str(patient_user.id) not in ids


# ---------------------------------------------------------------------------
# POST /api/v1/admin/users — walk-in patient creation
# ---------------------------------------------------------------------------


class TestCreatePatient:
    async def test_creates_walkin_patient(self, admin_client, db):
        resp = await admin_client.post(
            BASE,
            json={"full_name": "Walk In", "phone": "9999999999"},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["full_name"] == "Walk In"
        assert body["role"] == "patient"
        assert body["is_active"] is True

        user = await db.scalar(select(User).where(User.id == uuid.UUID(body["id"])))
        assert user is not None
        assert user.keycloak_sub.startswith("walkin:")

    async def test_missing_full_name_422(self, admin_client):
        resp = await admin_client.post(BASE, json={"phone": "1"})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/admin/users/{id} — detail
# ---------------------------------------------------------------------------


class TestGetUserDetail:
    async def test_detail_fields_and_counts(
        self, admin_client, db, patient_user, doctor_user, doctor_profile
    ):
        rec = await _record(db, patient_user.id, doctor_profile.id)
        await _prescription(db, patient_user.id, doctor_profile, rec)

        resp = await admin_client.get(f"{BASE}/{patient_user.id}")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["id"] == str(patient_user.id)
        assert body["role"] == "patient"
        assert body["records_count"] == 1
        assert body["prescriptions_count"] == 1
        assert body["last_visit"] is not None
        assert body["doctor_profile"] is None

    async def test_detail_embeds_doctor_profile(
        self, admin_client, doctor_user, doctor_profile
    ):
        resp = await admin_client.get(f"{BASE}/{doctor_user.id}")
        assert resp.status_code == 200
        profile = resp.json()["doctor_profile"]
        assert profile["id"] == str(doctor_profile.id)
        assert profile["verified"] is True

    async def test_unknown_user_404(self, admin_client):
        resp = await admin_client.get(f"{BASE}/{uuid.uuid4()}")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "NOT_FOUND"

    async def test_soft_deleted_user_404(self, admin_client, db, patient_user):
        patient_user.deleted_at = datetime.now(timezone.utc)
        await db.commit()
        resp = await admin_client.get(f"{BASE}/{patient_user.id}")
        assert resp.status_code == 404

    async def test_invalid_id_returns_4xx_not_500(self, admin_client):
        resp = await admin_client.get(f"{BASE}/not-a-uuid")
        assert resp.status_code in (400, 404, 422)


# ---------------------------------------------------------------------------
# GET /{user_id}/prescriptions and /{user_id}/records
# ---------------------------------------------------------------------------


class TestUserSubLists:
    async def test_prescriptions_list(
        self, admin_client, db, patient_user, doctor_user, doctor_profile
    ):
        rec = await _record(db, patient_user.id, doctor_profile.id)
        rx = await _prescription(db, patient_user.id, doctor_profile, rec)

        resp = await admin_client.get(f"{BASE}/{patient_user.id}/prescriptions")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] == 1
        item = body["data"][0]
        assert item["id"] == str(rx.id)
        assert item["doctor_name"] == "Doctor User"
        assert item["diagnosis"] == "viral fever"
        assert item["medicines"][0]["brand_name"] == "Crocin"

    async def test_prescriptions_unknown_user_404(self, admin_client):
        resp = await admin_client.get(f"{BASE}/{uuid.uuid4()}/prescriptions")
        assert resp.status_code == 404

    async def test_records_list(
        self, admin_client, db, patient_user, doctor_user, doctor_profile
    ):
        rec = await _record(db, patient_user.id, doctor_profile.id, title="Checkup")

        resp = await admin_client.get(f"{BASE}/{patient_user.id}/records")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] == 1
        item = body["data"][0]
        assert item["id"] == str(rec.id)
        assert item["title"] == "Checkup"
        assert item["record_type"] == "opd_note"
        assert item["doctor_name"] == "Doctor User"

    async def test_records_unknown_user_404(self, admin_client):
        resp = await admin_client.get(f"{BASE}/{uuid.uuid4()}/records")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PUT /{user_id} — update incl. role change
# ---------------------------------------------------------------------------


class TestUpdateUser:
    async def test_updates_basic_fields(self, admin_client, db, patient_user):
        resp = await admin_client.put(
            f"{BASE}/{patient_user.id}",
            json={"full_name": "Renamed", "phone": "8888888888", "is_active": False},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["full_name"] == "Renamed"
        assert body["phone"] == "8888888888"
        assert body["is_active"] is False
        await db.refresh(patient_user)
        assert patient_user.full_name == "Renamed"

    async def test_invalid_role_400(self, admin_client, patient_user):
        resp = await admin_client.put(
            f"{BASE}/{patient_user.id}", json={"role": "superadmin"}
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_ROLE"

    async def test_self_modify_400(self, admin_client, admin_user):
        resp = await admin_client.put(
            f"{BASE}/{admin_user.id}", json={"is_active": False}
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "SELF_MODIFY"

    async def test_unknown_user_404(self, admin_client):
        resp = await admin_client.put(
            f"{BASE}/{uuid.uuid4()}", json={"full_name": "Ghost"}
        )
        assert resp.status_code == 404

    async def test_role_change_calls_keycloak_sync(
        self, admin_client, db, patient_user, monkeypatch
    ):
        calls = []

        async def fake_sync(sub, new_role):
            calls.append((sub, new_role))

        monkeypatch.setattr(
            "app.routers.admin.users._sync_keycloak_role", fake_sync
        )
        resp = await admin_client.put(
            f"{BASE}/{patient_user.id}", json={"role": "admin"}
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["role"] == "admin"
        assert calls == [(patient_user.keycloak_sub, "admin")]
        await db.refresh(patient_user)
        assert patient_user.role == "admin"

    async def test_role_change_to_doctor_provisions_profile(
        self, admin_client, db, patient_user, monkeypatch
    ):
        async def fake_sync(sub, new_role):
            return None

        monkeypatch.setattr(
            "app.routers.admin.users._sync_keycloak_role", fake_sync
        )
        resp = await admin_client.put(
            f"{BASE}/{patient_user.id}", json={"role": "doctor"}
        )
        assert resp.status_code == 200, resp.text

        profile = await db.scalar(
            select(Doctor).where(
                Doctor.user_id == patient_user.id, Doctor.deleted_at.is_(None)
            )
        )
        assert profile is not None

        # Second identical change is a no-op — still exactly one profile.
        resp2 = await admin_client.put(
            f"{BASE}/{patient_user.id}", json={"role": "doctor"}
        )
        assert resp2.status_code == 200
        count = await db.scalar(
            select(func.count()).select_from(Doctor).where(
                Doctor.user_id == patient_user.id, Doctor.deleted_at.is_(None)
            )
        )
        assert count == 1

    async def test_walkin_role_change_skips_keycloak(self, admin_client, db):
        """walkin: subs have no Keycloak user — the sync must no-op locally
        (no HTTP call, no mock needed)."""
        walkin = await _make_user(db, keycloak_sub=f"walkin:{uuid.uuid4()}")
        resp = await admin_client.put(f"{BASE}/{walkin.id}", json={"role": "admin"})
        assert resp.status_code == 200, resp.text
        assert resp.json()["role"] == "admin"

    async def test_writes_audit_entry(self, admin_client, db, patient_user):
        from app.models.audit import AuditLog

        resp = await admin_client.put(
            f"{BASE}/{patient_user.id}", json={"full_name": "Audited"}
        )
        assert resp.status_code == 200
        logs = (
            await db.execute(
                select(AuditLog).where(
                    AuditLog.table_name == "users",
                    AuditLog.record_id == patient_user.id,
                    AuditLog.action == "UPDATE",
                )
            )
        ).scalars().all()
        assert len(logs) >= 1
        assert logs[0].new_values.get("full_name") == "Audited"


# ---------------------------------------------------------------------------
# DELETE /{user_id} — soft delete
# ---------------------------------------------------------------------------


class TestDeleteUser:
    async def test_soft_delete(self, admin_client, db, patient_user):
        resp = await admin_client.delete(f"{BASE}/{patient_user.id}")
        assert resp.status_code == 200, resp.text
        assert resp.json()["id"] == str(patient_user.id)

        await db.refresh(patient_user)
        assert patient_user.deleted_at is not None

        # Deleted users disappear from list and detail.
        assert (await admin_client.get(f"{BASE}/{patient_user.id}")).status_code == 404
        listing = await admin_client.get(BASE)
        assert str(patient_user.id) not in {
            u["id"] for u in listing.json()["data"]
        }

    async def test_self_delete_400(self, admin_client, admin_user):
        resp = await admin_client.delete(f"{BASE}/{admin_user.id}")
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "SELF_DELETE"

    async def test_unknown_user_404(self, admin_client):
        resp = await admin_client.delete(f"{BASE}/{uuid.uuid4()}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /{user_id}/related-patients
# ---------------------------------------------------------------------------


class TestRelatedPatients:
    async def test_matches_on_email_and_phone(self, admin_client, db, patient_user):
        sibling_email = await _make_user(db, email=patient_user.email)
        patient_user.phone = "7777777777"
        await db.commit()
        sibling_phone = await _make_user(db, phone="7777777777")
        # Same email but role=doctor — must not be reported as related patient.
        await _make_user(db, email=patient_user.email, role="doctor")

        resp = await admin_client.get(f"{BASE}/{patient_user.id}/related-patients")
        assert resp.status_code == 200, resp.text
        ids = {u["id"] for u in resp.json()["data"]}
        assert str(sibling_email.id) in ids
        assert str(sibling_phone.id) in ids
        assert all(u["id"] != str(patient_user.id) for u in resp.json()["data"])

    async def test_no_contact_info_returns_empty(self, admin_client, db):
        loner = await _make_user(db, email=None, phone=None)
        resp = await admin_client.get(f"{BASE}/{loner.id}/related-patients")
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    async def test_unknown_user_404(self, admin_client):
        resp = await admin_client.get(f"{BASE}/{uuid.uuid4()}/related-patients")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Auth gates
# ---------------------------------------------------------------------------


class TestAdminGate:
    @pytest.mark.parametrize(
        "method,url",
        [
            ("get", BASE),
            ("post", BASE),
            ("get", f"{BASE}/{uuid.uuid4()}"),
            ("put", f"{BASE}/{uuid.uuid4()}"),
            ("delete", f"{BASE}/{uuid.uuid4()}"),
            ("get", f"{BASE}/{uuid.uuid4()}/prescriptions"),
            ("get", f"{BASE}/{uuid.uuid4()}/records"),
            ("get", f"{BASE}/{uuid.uuid4()}/related-patients"),
        ],
    )
    async def test_patient_forbidden(self, patient_client, method, url):
        kwargs = {"json": {"full_name": "x"}} if method in ("post", "put") else {}
        resp = await getattr(patient_client, method)(url, **kwargs)
        assert resp.status_code == 403

    @pytest.mark.parametrize("method", ["get", "post", "put", "delete"])
    async def test_unauthenticated_401(self, client, method):
        url = BASE if method in ("get", "post") else f"{BASE}/{uuid.uuid4()}"
        kwargs = {"json": {"full_name": "x"}} if method in ("post", "put") else {}
        resp = await getattr(client, method)(url, **kwargs)
        assert resp.status_code == 401
