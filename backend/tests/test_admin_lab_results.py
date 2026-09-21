"""Coverage for the admin lab results router (/api/v1/admin/lab-results).

Covers the categories endpoint (declared before /{id} to avoid shadowing),
list + filters (search / status / test_category / date), detail, create with
generated test_id, update with status validation, soft delete, and the
admin-only gate.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lab_result import LabResult
from app.models.user import User

pytestmark = pytest.mark.asyncio

BASE = "/api/v1/admin/lab-results"
APPT_DATE = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()


async def _lab_result(
    db: AsyncSession,
    *,
    patient_id,
    doctor_id=None,
    test_id: str,
    test_name: str = "CBC",
    test_category: str | None = "Hematology",
    status: str = "pending",
    appointment_date: datetime | None = None,
) -> LabResult:
    lr = LabResult(
        id=uuid.uuid4(),
        test_id=test_id,
        patient_id=patient_id,
        doctor_id=doctor_id,
        test_name=test_name,
        test_category=test_category,
        appointment_date=appointment_date or datetime.now(timezone.utc),
        status=status,
    )
    db.add(lr)
    await db.commit()
    await db.refresh(lr)
    return lr


# ---------------------------------------------------------------------------
# GET /categories + GET "" list
# ---------------------------------------------------------------------------


class TestCategoriesAndList:
    async def test_categories_distinct_sorted(
        self, admin_client, db, patient_user
    ):
        await _lab_result(db, patient_id=patient_user.id, test_id="T1", test_category="Hematology")
        await _lab_result(db, patient_id=patient_user.id, test_id="T2", test_category="Biochemistry")
        await _lab_result(db, patient_id=patient_user.id, test_id="T3", test_category="Hematology")
        await _lab_result(db, patient_id=patient_user.id, test_id="T4", test_category=None)

        resp = await admin_client.get(f"{BASE}/categories")
        assert resp.status_code == 200, resp.text
        assert resp.json() == ["Biochemistry", "Hematology"]

    async def test_list_returns_results_with_names(
        self, admin_client, db, patient_user, doctor_user
    ):
        lr = await _lab_result(
            db, patient_id=patient_user.id, doctor_id=doctor_user.id, test_id="T1"
        )
        resp = await admin_client.get(BASE)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] == 1
        item = body["results"][0]
        assert item["id"] == str(lr.id)
        assert item["test_id"] == "T1"
        assert item["patient_name"] == "Patient User"
        assert item["doctor_name"] == "Doctor User"
        assert item["status"] == "pending"

    async def test_list_search_by_patient_and_test_name(
        self, admin_client, db, patient_user
    ):
        await _lab_result(db, patient_id=patient_user.id, test_id="T1", test_name="Lipid Panel")
        other_patient = User(
            id=uuid.uuid4(), keycloak_sub=f"p-{uuid.uuid4()}",
            full_name="Someone Else", role="patient",
        )
        db.add(other_patient)
        await db.commit()
        await _lab_result(db, patient_id=other_patient.id, test_id="T2", test_name="CBC")

        by_patient = await admin_client.get(BASE, params={"search": "Patient User"})
        assert [r["test_id"] for r in by_patient.json()["results"]] == ["T1"]

        by_test = await admin_client.get(BASE, params={"search": "Lipid"})
        assert [r["test_id"] for r in by_test.json()["results"]] == ["T1"]

    async def test_list_status_and_category_filters(
        self, admin_client, db, patient_user
    ):
        await _lab_result(db, patient_id=patient_user.id, test_id="T1", status="completed")
        await _lab_result(
            db, patient_id=patient_user.id, test_id="T2",
            status="pending", test_category="Biochemistry",
        )

        done = await admin_client.get(BASE, params={"status": "completed"})
        assert [r["test_id"] for r in done.json()["results"]] == ["T1"]

        bio = await admin_client.get(BASE, params={"test_category": "Biochemistry"})
        assert [r["test_id"] for r in bio.json()["results"]] == ["T2"]

    async def test_list_date_filter(self, admin_client, db, patient_user):
        day = datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc)
        await _lab_result(db, patient_id=patient_user.id, test_id="T1", appointment_date=day)
        await _lab_result(
            db, patient_id=patient_user.id, test_id="T2",
            appointment_date=datetime(2026, 3, 16, 10, 0, tzinfo=timezone.utc),
        )

        resp = await admin_client.get(BASE, params={"date": "2026-03-15"})
        assert [r["test_id"] for r in resp.json()["results"]] == ["T1"]

    async def test_list_invalid_date_400(self, admin_client):
        resp = await admin_client.get(BASE, params={"date": "15-03-2026"})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_DATE"

    async def test_list_pagination(self, admin_client, db, patient_user):
        for i in range(3):
            await _lab_result(db, patient_id=patient_user.id, test_id=f"T{i}")
        resp = await admin_client.get(BASE, params={"limit": 2, "page": 2})
        body = resp.json()
        assert body["total"] == 3
        assert body["totalPages"] == 2
        assert len(body["results"]) == 1


# ---------------------------------------------------------------------------
# GET /{id} detail
# ---------------------------------------------------------------------------


class TestDetail:
    async def test_get_detail(self, admin_client, db, patient_user):
        lr = await _lab_result(db, patient_id=patient_user.id, test_id="T1")
        resp = await admin_client.get(f"{BASE}/{lr.id}")
        assert resp.status_code == 200, resp.text
        assert resp.json()["id"] == str(lr.id)
        assert resp.json()["patient_name"] == "Patient User"

    async def test_unknown_404(self, admin_client):
        resp = await admin_client.get(f"{BASE}/{uuid.uuid4()}")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "NOT_FOUND"

    async def test_invalid_id_422(self, admin_client):
        resp = await admin_client.get(f"{BASE}/not-a-uuid")
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "INVALID_ID"


# ---------------------------------------------------------------------------
# POST create
# ---------------------------------------------------------------------------


class TestCreate:
    async def test_create_generates_test_id(self, admin_client, patient_user):
        resp = await admin_client.post(
            BASE,
            json={
                "patient_id": str(patient_user.id),
                "test_name": "HbA1c",
                "test_category": "Biochemistry",
                "appointment_date": APPT_DATE,
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        year = datetime.now(timezone.utc).year
        assert body["test_id"] == f"LAB-{year}-00001"
        assert body["status"] == "pending"
        assert body["patient_name"] == "Patient User"

    async def test_test_id_increments(self, admin_client, db, patient_user):
        await _lab_result(db, patient_id=patient_user.id, test_id="X")
        resp = await admin_client.post(
            BASE,
            json={
                "patient_id": str(patient_user.id),
                "test_name": "CBC",
                "appointment_date": APPT_DATE,
            },
        )
        assert resp.status_code == 201
        assert resp.json()["test_id"].endswith("-00002")

    async def test_unknown_patient_404(self, admin_client):
        resp = await admin_client.post(
            BASE,
            json={
                "patient_id": str(uuid.uuid4()),
                "test_name": "CBC",
                "appointment_date": APPT_DATE,
            },
        )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "PATIENT_NOT_FOUND"

    async def test_unknown_doctor_404(self, admin_client, patient_user):
        resp = await admin_client.post(
            BASE,
            json={
                "patient_id": str(patient_user.id),
                "doctor_id": str(uuid.uuid4()),
                "test_name": "CBC",
                "appointment_date": APPT_DATE,
            },
        )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "DOCTOR_NOT_FOUND"

    async def test_missing_required_fields_422(self, admin_client):
        resp = await admin_client.post(BASE, json={"test_name": "CBC"})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# PUT update
# ---------------------------------------------------------------------------


class TestUpdate:
    async def test_update_status_and_results(
        self, admin_client, db, patient_user
    ):
        lr = await _lab_result(db, patient_id=patient_user.id, test_id="T1")
        resp = await admin_client.put(
            f"{BASE}/{lr.id}",
            json={
                "status": "completed",
                "result_value": "5.4",
                "result_unit": "%",
                "normal_range": "4.0-5.6",
                "abnormal_flag": False,
                "notes": "within range",
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "completed"
        assert body["result_value"] == "5.4"
        assert body["result_unit"] == "%"
        assert body["normal_range"] == "4.0-5.6"

        await db.refresh(lr)
        assert lr.status == "completed"

    async def test_invalid_status_400(self, admin_client, db, patient_user):
        lr = await _lab_result(db, patient_id=patient_user.id, test_id="T1")
        resp = await admin_client.put(
            f"{BASE}/{lr.id}", json={"status": "bogus"}
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_STATUS"

    async def test_unknown_doctor_404(self, admin_client, db, patient_user):
        lr = await _lab_result(db, patient_id=patient_user.id, test_id="T1")
        resp = await admin_client.put(
            f"{BASE}/{lr.id}", json={"doctor_id": str(uuid.uuid4())}
        )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "DOCTOR_NOT_FOUND"

    async def test_unknown_result_404(self, admin_client):
        resp = await admin_client.put(
            f"{BASE}/{uuid.uuid4()}", json={"status": "completed"}
        )
        assert resp.status_code == 404

    async def test_invalid_id_422(self, admin_client):
        resp = await admin_client.put(f"{BASE}/nope", json={"status": "pending"})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------


class TestDelete:
    async def test_soft_delete(self, admin_client, db, patient_user):
        lr = await _lab_result(db, patient_id=patient_user.id, test_id="T1")
        resp = await admin_client.delete(f"{BASE}/{lr.id}")
        assert resp.status_code == 204

        await db.refresh(lr)
        assert lr.deleted_at is not None

        assert (await admin_client.get(f"{BASE}/{lr.id}")).status_code == 404
        listing = await admin_client.get(BASE)
        assert listing.json()["total"] == 0

    async def test_delete_unknown_404(self, admin_client):
        resp = await admin_client.delete(f"{BASE}/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_delete_invalid_id_422(self, admin_client):
        resp = await admin_client.delete(f"{BASE}/nope")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Auth gates
# ---------------------------------------------------------------------------


class TestAdminGate:
    @pytest.mark.parametrize(
        "method,url",
        [
            ("get", BASE),
            ("get", f"{BASE}/categories"),
            ("post", BASE),
            ("get", f"{BASE}/{uuid.uuid4()}"),
            ("put", f"{BASE}/{uuid.uuid4()}"),
            ("delete", f"{BASE}/{uuid.uuid4()}"),
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
