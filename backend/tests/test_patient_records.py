"""Tests for the patient-facing records surface in app/routers/patients.py.

Endpoints under test:
  GET  /api/v1/patients/records                 — own records list (filters, cursor)
  POST /api/v1/patients/records                 — patient self-upload
  GET  /api/v1/patients/records/{id}            — record detail
  GET  /api/v1/patients/records/export          — FHIR R4 bundle download
  GET  /api/v1/patients/lab-results[/{id}]      — own lab results list/detail

Record-version chains are covered in test_records.py.
"""
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.doctor import Doctor
from app.models.lab_result import LabResult
from app.models.medical_record import MedicalRecord
from app.models.prescription import Prescription
from app.models.user import User

pytestmark = pytest.mark.asyncio

RECORDS_URL = "/api/v1/patients/records"
LAB_RESULTS_URL = "/api/v1/patients/lab-results"


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


async def make_patient(db: AsyncSession, name: str = "Other Patient") -> User:
    user = User(
        keycloak_sub=f"sub-{uuid.uuid4()}",
        email=f"{uuid.uuid4().hex[:8]}@test.com",
        full_name=name,
        role="patient",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def make_record(
    db: AsyncSession,
    patient_id,
    title: str,
    record_type: str = "lab_report",
    description: str | None = None,
    source: str = "doctor",
    doctor_id=None,
    created_at: datetime | None = None,
    deleted: bool = False,
) -> MedicalRecord:
    record = MedicalRecord(
        patient_id=patient_id,
        doctor_id=doctor_id,
        record_type=record_type,
        title=title,
        description=description,
        source=source,
    )
    if created_at is not None:
        record.created_at = created_at
    if deleted:
        record.deleted_at = datetime.now(timezone.utc)
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def make_lab_result(
    db: AsyncSession,
    patient_id,
    test_name: str = "CBC",
    test_category: str = "hematology",
    doctor_id=None,
) -> LabResult:
    lab = LabResult(
        test_id=f"TST-{uuid.uuid4().hex[:8]}",
        patient_id=patient_id,
        doctor_id=doctor_id,
        test_name=test_name,
        test_category=test_category,
        appointment_date=datetime.now(timezone.utc),
        status="completed",
        result_value="5.6",
        result_unit="x10^6/uL",
        normal_range="4.5-5.5",
        abnormal_flag=True,
    )
    db.add(lab)
    await db.commit()
    await db.refresh(lab)
    return lab


# ---------------------------------------------------------------------------
# GET /patients/records — list
# ---------------------------------------------------------------------------


async def test_records_list_requires_auth(client: AsyncClient):
    resp = await client.get(RECORDS_URL)
    assert resp.status_code == 401


async def test_records_list_rejects_doctor_role(doctor_client: AsyncClient):
    resp = await doctor_client.get(RECORDS_URL)
    assert resp.status_code == 403


async def test_records_list_empty(patient_client: AsyncClient):
    resp = await patient_client.get(RECORDS_URL)
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"] == []
    assert body["pagination"]["has_more"] is False
    assert body["pagination"]["next_cursor"] is None


async def test_records_list_returns_only_own(
    patient_client: AsyncClient, patient_user: User, db: AsyncSession
):
    mine = await make_record(db, patient_user.id, "My lab report")
    other = await make_patient(db)
    await make_record(db, other.id, "Someone else's report")

    resp = await patient_client.get(RECORDS_URL)
    assert resp.status_code == 200
    ids = [r["id"] for r in resp.json()["data"]]
    assert ids == [str(mine.id)]


async def test_records_list_type_filter(
    patient_client: AsyncClient, patient_user: User, db: AsyncSession
):
    await make_record(db, patient_user.id, "Blood work", record_type="lab_report")
    imaging = await make_record(
        db, patient_user.id, "Chest X-ray", record_type="imaging"
    )

    resp = await patient_client.get(RECORDS_URL, params={"type": "imaging"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert [r["id"] for r in data] == [str(imaging.id)]
    assert data[0]["record_type"] == "imaging"


async def test_records_list_text_search(
    patient_client: AsyncClient, patient_user: User, db: AsyncSession
):
    await make_record(db, patient_user.id, "Annual physical", description="all clear")
    hit = await make_record(
        db, patient_user.id, "Cardiology referral", description="murmur evaluation"
    )

    resp = await patient_client.get(RECORDS_URL, params={"q": "murmur"})
    assert resp.status_code == 200
    assert [r["id"] for r in resp.json()["data"]] == [str(hit.id)]


async def test_records_list_cursor_pagination(
    patient_client: AsyncClient, patient_user: User, db: AsyncSession
):
    now = datetime.now(timezone.utc)
    records = []
    for i in range(3):
        records.append(
            await make_record(
                db, patient_user.id, f"Record {i}",
                created_at=now - timedelta(days=i),
            )
        )

    resp = await patient_client.get(RECORDS_URL, params={"limit": 2})
    assert resp.status_code == 200
    page1 = resp.json()
    assert len(page1["data"]) == 2
    assert page1["pagination"]["has_more"] is True
    cursor = page1["pagination"]["next_cursor"]
    assert cursor is not None

    resp = await patient_client.get(RECORDS_URL, params={"limit": 2, "cursor": cursor})
    assert resp.status_code == 200
    page2 = resp.json()
    assert len(page2["data"]) == 1
    assert page2["pagination"]["has_more"] is False
    assert page2["pagination"]["next_cursor"] is None

    all_ids = [r["id"] for r in page1["data"]] + [r["id"] for r in page2["data"]]
    assert set(all_ids) == {str(r.id) for r in records}


async def test_records_list_excludes_soft_deleted(
    patient_client: AsyncClient, patient_user: User, db: AsyncSession
):
    await make_record(db, patient_user.id, "Deleted record", deleted=True)
    alive = await make_record(db, patient_user.id, "Live record")

    resp = await patient_client.get(RECORDS_URL)
    assert [r["id"] for r in resp.json()["data"]] == [str(alive.id)]


async def test_records_list_includes_doctor_name_and_prescription(
    patient_client: AsyncClient,
    patient_user: User,
    doctor_profile: Doctor,
    db: AsyncSession,
):
    """List items surface the authoring doctor's name and embedded
    prescription payload for prescription records."""
    record = await make_record(
        db, patient_user.id, "Rx for fever", record_type="prescription",
        doctor_id=doctor_profile.id,
    )
    rx = Prescription(
        record_id=record.id,
        doctor_id=doctor_profile.id,
        patient_id=patient_user.id,
        medicines=[{"brand_name": "Crocin", "dose": "500mg"}],
        diagnosis="Viral fever",
    )
    db.add(rx)
    await db.commit()

    resp = await patient_client.get(RECORDS_URL)
    item = resp.json()["data"][0]
    assert item["doctor_name"] == "Doctor User"
    assert item["prescription"]["diagnosis"] == "Viral fever"
    assert item["prescription"]["medicines"][0]["brand_name"] == "Crocin"


# ---------------------------------------------------------------------------
# POST /patients/records — self-upload
# ---------------------------------------------------------------------------


async def test_create_record_requires_auth(client: AsyncClient):
    resp = await client.post(
        RECORDS_URL, json={"record_type": "lab_report", "title": "CBC"}
    )
    assert resp.status_code == 401


async def test_create_record_rejects_doctor_role(doctor_client: AsyncClient):
    resp = await doctor_client.post(
        RECORDS_URL, json={"record_type": "lab_report", "title": "CBC"}
    )
    assert resp.status_code == 403


async def test_create_record_happy_path(
    patient_client: AsyncClient, patient_user: User
):
    resp = await patient_client.post(
        RECORDS_URL,
        json={
            "record_type": "lab_report",
            "title": "Home lab results",
            "description": "Uploaded PDF report",
            "document_url": "abc123/report.pdf",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["patient_id"] == str(patient_user.id)
    assert body["record_type"] == "lab_report"
    assert body["title"] == "Home lab results"
    assert body["source"] == "patient_uploaded"
    assert body["doctor_id"] is None
    assert body["document_url"] == "abc123/report.pdf"
    assert body["fhir_bundle"] is not None


@pytest.mark.parametrize("record_type", ["opd_note", "prescription", "other", "bogus"])
async def test_create_record_rejects_doctor_only_types(
    patient_client: AsyncClient, record_type: str
):
    """Patients may only self-upload the lab/imaging/discharge subset."""
    resp = await patient_client.post(
        RECORDS_URL, json={"record_type": record_type, "title": "Nope"}
    )
    assert resp.status_code == 422


@pytest.mark.parametrize(
    "document_url",
    [
        "javascript:alert(1)",
        "http://example.com/report.pdf",  # only https allowed
        "/absolute/path.pdf",
        "dir/../escape.pdf",
        "not a url with spaces",
    ],
)
async def test_create_record_rejects_unsafe_document_url(
    patient_client: AsyncClient, document_url: str
):
    resp = await patient_client.post(
        RECORDS_URL,
        json={
            "record_type": "imaging",
            "title": "Scan",
            "document_url": document_url,
        },
    )
    assert resp.status_code == 422


async def test_create_record_accepts_https_document_url(patient_client: AsyncClient):
    resp = await patient_client.post(
        RECORDS_URL,
        json={
            "record_type": "discharge_summary",
            "title": "Discharge",
            "document_url": "https://files.example.com/discharge.pdf",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["document_url"] == "https://files.example.com/discharge.pdf"


async def test_create_record_missing_title_422(patient_client: AsyncClient):
    resp = await patient_client.post(
        RECORDS_URL, json={"record_type": "lab_report"}
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /patients/records/{record_id} — detail
# ---------------------------------------------------------------------------


async def test_get_record_detail_own(
    patient_client: AsyncClient, patient_user: User, db: AsyncSession
):
    record = await make_record(
        db, patient_user.id, "My record", description="details here"
    )
    resp = await patient_client.get(f"{RECORDS_URL}/{record.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(record.id)
    assert body["title"] == "My record"
    assert body["description"] == "details here"
    assert body["source"] == "doctor"


async def test_get_record_detail_other_patient_404(
    patient_client: AsyncClient, db: AsyncSession
):
    other = await make_patient(db)
    record = await make_record(db, other.id, "Not yours")
    resp = await patient_client.get(f"{RECORDS_URL}/{record.id}")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


async def test_get_record_detail_nonexistent_404(patient_client: AsyncClient):
    resp = await patient_client.get(f"{RECORDS_URL}/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_get_record_detail_soft_deleted_404(
    patient_client: AsyncClient, patient_user: User, db: AsyncSession
):
    record = await make_record(db, patient_user.id, "Gone", deleted=True)
    resp = await patient_client.get(f"{RECORDS_URL}/{record.id}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /patients/records/export — FHIR bundle
# ---------------------------------------------------------------------------


async def test_export_records_fhir_bundle(
    patient_client: AsyncClient, patient_user: User, db: AsyncSession
):
    await make_record(db, patient_user.id, "Exported record")
    other = await make_patient(db)
    await make_record(db, other.id, "Not exported")

    resp = await patient_client.get(f"{RECORDS_URL}/export", params={"format": "json"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/fhir+json")
    assert "attachment" in resp.headers["content-disposition"]
    assert "medconnect-records-" in resp.headers["content-disposition"]

    bundle = resp.json()
    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "collection"
    # Entry 0 is the Patient resource; only the caller's records follow.
    assert bundle["entry"][0]["resource"]["resourceType"] == "Patient"
    titles = json.dumps(bundle["entry"])
    assert "Exported record" in titles
    assert "Not exported" not in titles


async def test_export_records_rejects_non_json_format(patient_client: AsyncClient):
    resp = await patient_client.get(f"{RECORDS_URL}/export", params={"format": "csv"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_export_records_requires_auth(client: AsyncClient):
    resp = await client.get(f"{RECORDS_URL}/export")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /patients/lab-results — list + detail
# ---------------------------------------------------------------------------


async def test_lab_results_list_only_own(
    patient_client: AsyncClient, patient_user: User, db: AsyncSession
):
    mine = await make_lab_result(db, patient_user.id, test_name="HbA1c")
    other = await make_patient(db)
    await make_lab_result(db, other.id, test_name="HbA1c")

    resp = await patient_client.get(LAB_RESULTS_URL)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert [r["id"] for r in data] == [str(mine.id)]
    assert data[0]["test_name"] == "HbA1c"
    assert data[0]["abnormal_flag"] is True


async def test_lab_results_category_filter(
    patient_client: AsyncClient, patient_user: User, db: AsyncSession
):
    await make_lab_result(db, patient_user.id, test_name="CBC", test_category="hematology")
    biochem = await make_lab_result(
        db, patient_user.id, test_name="Lipid", test_category="biochemistry"
    )

    resp = await patient_client.get(
        LAB_RESULTS_URL, params={"category": "biochemistry"}
    )
    assert [r["id"] for r in resp.json()["data"]] == [str(biochem.id)]


async def test_lab_result_detail_own(
    patient_client: AsyncClient, patient_user: User, doctor_user: User, db: AsyncSession
):
    lab = await make_lab_result(db, patient_user.id, doctor_id=doctor_user.id)
    resp = await patient_client.get(f"{LAB_RESULTS_URL}/{lab.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(lab.id)
    assert body["doctor_name"] == doctor_user.full_name
    assert body["result_value"] == "5.6"


async def test_lab_result_detail_other_patient_404(
    patient_client: AsyncClient, db: AsyncSession
):
    other = await make_patient(db)
    lab = await make_lab_result(db, other.id)
    resp = await patient_client.get(f"{LAB_RESULTS_URL}/{lab.id}")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


async def test_lab_result_detail_nonexistent_404(patient_client: AsyncClient):
    resp = await patient_client.get(f"{LAB_RESULTS_URL}/{uuid.uuid4()}")
    assert resp.status_code == 404
