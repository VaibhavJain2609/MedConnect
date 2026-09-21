"""Coverage for the admin clinics router (/api/v1/admin/clinics).

Covers create/list/detail/update/delete, the admin patient-link endpoint
(POST /{id}/patients), the per-clinic usage metrics endpoint
(GET /{id}/metrics — members, patient links, appointments, today's queue,
branches), and the admin-only gate.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment
from app.models.clinic import Clinic, ClinicBranch, ClinicMembership
from app.models.medical_record import MedicalRecord
from app.models.patient_link import PatientClinicLink
from app.models.queue import QueueEntry
from app.models.user import User

pytestmark = pytest.mark.asyncio

BASE = "/api/v1/admin/clinics"


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def clinic(db: AsyncSession, admin_user: User) -> Clinic:
    c = Clinic(id=uuid.uuid4(), name="Admin Clinic", city="Mumbai", created_by=admin_user.id)
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


async def _make_user(db: AsyncSession, role: str = "patient", name: str = "Member") -> User:
    u = User(
        id=uuid.uuid4(),
        keycloak_sub=f"sub-{uuid.uuid4()}",
        full_name=name,
        email=f"{uuid.uuid4().hex[:8]}@test.com",
        role=role,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def _membership(
    db: AsyncSession, clinic_id, user_id, role: str, is_active: bool = True
) -> ClinicMembership:
    m = ClinicMembership(
        id=uuid.uuid4(),
        clinic_id=clinic_id,
        user_id=user_id,
        role=role,
        is_active=is_active,
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


async def _patient_link(
    db: AsyncSession, clinic_id, patient_id, linked_by, consent_status: str
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
    return link


# ---------------------------------------------------------------------------
# POST / GET list
# ---------------------------------------------------------------------------


_DETAIL_TIMEZONE_BUG = (
    "BUG (report-only): clinic_service.admin_get_clinic_detail never passes "
    "`timezone` to AdminClinicDetailResponse (required on ClinicResponse) → "
    "ValidationError → 500 on POST/GET-detail/PUT /admin/clinics"
)


class TestCreateAndList:
    @pytest.mark.xfail(strict=True, reason=_DETAIL_TIMEZONE_BUG)
    async def test_create_clinic(self, admin_client):
        resp = await admin_client.post(
            BASE,
            json={"name": "New Clinic", "city": "Delhi", "phone": "01123456789"},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["name"] == "New Clinic"
        assert body["city"] == "Delhi"
        assert body["is_active"] is True
        assert body["member_count"] == 0  # admin create has no owner
        assert body["branches"] == []

    async def test_create_missing_name_422(self, admin_client):
        resp = await admin_client.post(BASE, json={"city": "Delhi"})
        assert resp.status_code == 422

    async def test_list_returns_clinics(self, admin_client, clinic):
        resp = await admin_client.get(BASE)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] == 1
        assert body["totalPages"] >= 1
        item = body["data"][0]
        assert item["id"] == str(clinic.id)
        assert item["name"] == "Admin Clinic"
        assert item["member_count"] == 0

    async def test_list_search_and_is_active_filters(
        self, admin_client, db, clinic, admin_user
    ):
        other = Clinic(
            id=uuid.uuid4(), name="Inactive One", is_active=False,
            created_by=admin_user.id,
        )
        db.add(other)
        await db.commit()

        by_search = await admin_client.get(BASE, params={"search": "Admin"})
        assert [c["id"] for c in by_search.json()["data"]] == [str(clinic.id)]

        inactive = await admin_client.get(BASE, params={"is_active": "false"})
        assert [c["id"] for c in inactive.json()["data"]] == [str(other.id)]

        active = await admin_client.get(BASE, params={"is_active": "true"})
        assert [c["id"] for c in active.json()["data"]] == [str(clinic.id)]

    async def test_list_member_count(
        self, admin_client, db, clinic, doctor_user
    ):
        await _membership(db, clinic.id, doctor_user.id, "owner")
        resp = await admin_client.get(BASE)
        item = resp.json()["data"][0]
        assert item["member_count"] == 1


# ---------------------------------------------------------------------------
# GET /{id} detail, PUT, DELETE
# ---------------------------------------------------------------------------


class TestDetailUpdateDelete:
    @pytest.mark.xfail(strict=True, reason=_DETAIL_TIMEZONE_BUG)
    async def test_detail_counts_and_branches(
        self, admin_client, db, clinic, doctor_user, doctor_profile, patient_user
    ):
        await _membership(db, clinic.id, doctor_user.id, "owner")
        branch = ClinicBranch(id=uuid.uuid4(), clinic_id=clinic.id, name="Main")
        rec = MedicalRecord(
            id=uuid.uuid4(),
            patient_id=patient_user.id,
            doctor_id=doctor_profile.id,
            clinic_id=clinic.id,
            record_type="opd_note",
            title="Visit",
        )
        db.add_all([branch, rec])
        await db.commit()

        resp = await admin_client.get(f"{BASE}/{clinic.id}")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["id"] == str(clinic.id)
        assert body["member_count"] == 1
        assert body["record_count"] == 1
        assert body["prescription_count"] == 0
        assert [b["name"] for b in body["branches"]] == ["Main"]

    async def test_detail_unknown_404(self, admin_client):
        resp = await admin_client.get(f"{BASE}/{uuid.uuid4()}")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "NOT_FOUND"

    async def test_detail_invalid_id_422(self, admin_client):
        resp = await admin_client.get(f"{BASE}/not-a-uuid")
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "INVALID_ID"

    @pytest.mark.xfail(strict=True, reason=_DETAIL_TIMEZONE_BUG)
    async def test_update_clinic(self, admin_client, clinic):
        resp = await admin_client.put(
            f"{BASE}/{clinic.id}",
            json={
                "name": "Renamed Clinic",
                "city": "Goa",
                "is_active": False,
                "timezone": "Asia/Kolkata",
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["name"] == "Renamed Clinic"
        assert body["city"] == "Goa"
        assert body["is_active"] is False
        assert body["timezone"] == "Asia/Kolkata"

    async def test_update_invalid_timezone_422(self, admin_client, clinic):
        resp = await admin_client.put(
            f"{BASE}/{clinic.id}", json={"timezone": "Not/AZone"}
        )
        assert resp.status_code == 422

    async def test_update_unknown_404(self, admin_client):
        resp = await admin_client.put(
            f"{BASE}/{uuid.uuid4()}", json={"name": "Ghost"}
        )
        assert resp.status_code == 404

    async def test_update_invalid_id_422(self, admin_client):
        resp = await admin_client.put(f"{BASE}/nope", json={"name": "x"})
        assert resp.status_code == 422

    async def test_delete_soft_deletes(self, admin_client, clinic):
        resp = await admin_client.delete(f"{BASE}/{clinic.id}")
        assert resp.status_code == 204
        assert (await admin_client.get(f"{BASE}/{clinic.id}")).status_code == 404
        # Not listed either.
        listing = await admin_client.get(BASE)
        assert str(clinic.id) not in {c["id"] for c in listing.json()["data"]}

    async def test_delete_unknown_404(self, admin_client):
        resp = await admin_client.delete(f"{BASE}/{uuid.uuid4()}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /{clinic_id}/patients — admin patient link
# ---------------------------------------------------------------------------


class TestAdminAddPatient:
    async def test_link_patient_pending_consent(
        self, admin_client, clinic, patient_user
    ):
        resp = await admin_client.post(
            f"{BASE}/{clinic.id}/patients",
            json={"patient_id": str(patient_user.id)},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["patient_id"] == str(patient_user.id)
        assert body["clinic_id"] == str(clinic.id)
        assert body["consent_status"] == "pending"

    async def test_duplicate_link_409(self, admin_client, db, clinic, patient_user, admin_user):
        await _patient_link(db, clinic.id, patient_user.id, admin_user.id, "approved")
        resp = await admin_client.post(
            f"{BASE}/{clinic.id}/patients",
            json={"patient_id": str(patient_user.id)},
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "DUPLICATE_LINK"

    async def test_unknown_patient_404(self, admin_client, clinic):
        resp = await admin_client.post(
            f"{BASE}/{clinic.id}/patients",
            json={"patient_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 404

    async def test_non_patient_role_404(self, admin_client, clinic, doctor_user):
        resp = await admin_client.post(
            f"{BASE}/{clinic.id}/patients",
            json={"patient_id": str(doctor_user.id)},
        )
        assert resp.status_code == 404

    async def test_invalid_ids_422(self, admin_client, clinic):
        resp = await admin_client.post(
            f"{BASE}/bad-uuid/patients",
            json={"patient_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 422
        resp2 = await admin_client.post(
            f"{BASE}/{clinic.id}/patients",
            json={"patient_id": "bad-uuid"},
        )
        assert resp2.status_code == 422


# ---------------------------------------------------------------------------
# GET /{clinic_id}/metrics — usage metrics
# ---------------------------------------------------------------------------


class TestClinicMetrics:
    async def test_metrics_aggregates(
        self, admin_client, db, clinic, admin_user, doctor_user, doctor_profile, patient_user
    ):
        # Members: 1 owner + 1 doctor active, 1 inactive receptionist.
        await _membership(db, clinic.id, doctor_user.id, "owner")
        doc2 = await _make_user(db, role="doctor", name="Doc Two")
        await _membership(db, clinic.id, doc2.id, "doctor")
        rec_user = await _make_user(db, role="doctor", name="Recep")
        await _membership(db, clinic.id, rec_user.id, "receptionist", is_active=False)

        # Patient links: approved + pending + revoked.
        p2 = await _make_user(db, name="P2")
        p3 = await _make_user(db, name="P3")
        await _patient_link(db, clinic.id, patient_user.id, admin_user.id, "approved")
        await _patient_link(db, clinic.id, p2.id, admin_user.id, "pending")
        await _patient_link(db, clinic.id, p3.id, admin_user.id, "revoked")

        # Appointments: one recent scheduled, one recent completed,
        # one older than 30 days (excluded from last_30d but in total).
        now = datetime.now(timezone.utc)
        db.add_all([
            Appointment(
                id=uuid.uuid4(), patient_id=patient_user.id,
                doctor_id=doctor_profile.id, clinic_id=clinic.id,
                scheduled_at=now - timedelta(days=1), duration_minutes=30,
                type="in-person", status="scheduled", created_by=admin_user.id,
            ),
            Appointment(
                id=uuid.uuid4(), patient_id=p2.id,
                doctor_id=doctor_profile.id, clinic_id=clinic.id,
                scheduled_at=now - timedelta(days=2), duration_minutes=30,
                type="in-person", status="completed", created_by=admin_user.id,
            ),
            Appointment(
                id=uuid.uuid4(), patient_id=p3.id,
                doctor_id=doctor_profile.id, clinic_id=clinic.id,
                scheduled_at=now - timedelta(days=40), duration_minutes=30,
                type="in-person", status="cancelled", created_by=admin_user.id,
            ),
        ])

        # Queue today: one waiting, one completed.
        db.add_all([
            QueueEntry(
                id=uuid.uuid4(), clinic_id=clinic.id, patient_id=patient_user.id,
                queue_number=1, status="waiting",
            ),
            QueueEntry(
                id=uuid.uuid4(), clinic_id=clinic.id, patient_id=p2.id,
                queue_number=2, status="completed",
            ),
        ])

        # One branch.
        db.add(ClinicBranch(id=uuid.uuid4(), clinic_id=clinic.id, name="B1"))
        await db.commit()

        resp = await admin_client.get(f"{BASE}/{clinic.id}/metrics")
        assert resp.status_code == 200, resp.text
        body = resp.json()

        assert body["members"]["total"] == 3
        assert body["members"]["owners"] == 1
        assert body["members"]["doctors"] == 1
        assert body["members"]["receptionists"] == 0  # inactive doesn't count
        assert body["members"]["inactive"] == 1

        assert body["patients"]["total_linked"] == 3
        assert body["patients"]["approved"] == 1
        assert body["patients"]["pending"] == 1
        assert body["patients"]["revoked"] == 1

        assert body["appointments"]["total"] == 3
        assert body["appointments"]["last_30d"] == 2
        assert body["appointments"]["by_status"]["scheduled"] == 1
        assert body["appointments"]["by_status"]["completed"] == 1
        assert body["appointments"]["by_status"]["cancelled"] == 1

        assert body["queue_today"]["waiting"] == 1
        assert body["queue_today"]["completed"] == 1
        assert body["queue_today"]["in_consultation"] == 0

        assert body["branches"] == 1

    async def test_metrics_empty_clinic(self, admin_client, clinic):
        resp = await admin_client.get(f"{BASE}/{clinic.id}/metrics")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["members"]["total"] == 0
        assert body["patients"]["total_linked"] == 0
        assert body["appointments"]["total"] == 0
        assert body["queue_today"] == {
            "waiting": 0, "in_consultation": 0, "completed": 0,
        }
        assert body["branches"] == 0

    async def test_metrics_unknown_404(self, admin_client):
        resp = await admin_client.get(f"{BASE}/{uuid.uuid4()}/metrics")
        assert resp.status_code == 404

    async def test_metrics_invalid_id_422(self, admin_client):
        resp = await admin_client.get(f"{BASE}/bad/metrics")
        assert resp.status_code == 422


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
            ("get", f"{BASE}/{uuid.uuid4()}/metrics"),
            ("post", f"{BASE}/{uuid.uuid4()}/patients"),
        ],
    )
    async def test_patient_forbidden(self, patient_client, method, url):
        kwargs = {"json": {}} if method in ("post", "put") else {}
        resp = await getattr(patient_client, method)(url, **kwargs)
        assert resp.status_code == 403

    @pytest.mark.parametrize("method", ["get", "post"])
    async def test_unauthenticated_401(self, client, method):
        resp = await getattr(client, method)(BASE, **({"json": {}} if method == "post" else {}))
        assert resp.status_code == 401
