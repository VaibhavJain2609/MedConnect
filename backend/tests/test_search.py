"""Tests for the role-aware global search endpoints (r9 search scope).

Covers:
  - response contract (results[] with type/id/title/subtitle/url)
  - per-role authz scoping for every searchable entity
  - new entity types: lab_result, prescription; extended: record, clinic,
    appointment
  - ordering, empty queries, type filter, unauthenticated access
  - the dedicated 30/min rate limit on /api/v1/search
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment
from app.models.clinic import Clinic, ClinicMembership
from app.models.doctor import Doctor
from app.models.lab_result import LabResult
from app.models.medical_record import MedicalRecord
from app.models.prescription import Prescription
from app.models.user import User
from tests.conftest import create_test_token


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

async def make_patient(db: AsyncSession, name: str, email: str) -> User:
    user = User(
        keycloak_sub=f"sub-{uuid.uuid4()}",
        email=email,
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
    doctor_id=None,
    record_type: str = "opd_note",
    description: str | None = None,
    created_at: datetime | None = None,
) -> MedicalRecord:
    record = MedicalRecord(
        patient_id=patient_id,
        doctor_id=doctor_id,
        record_type=record_type,
        title=title,
        description=description,
    )
    if created_at is not None:
        record.created_at = created_at
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def make_lab_result(
    db: AsyncSession,
    patient_id,
    test_name: str,
    test_category: str | None = None,
    status: str = "completed",
    days_ago: int = 0,
) -> LabResult:
    lab = LabResult(
        test_id=f"TST-{uuid.uuid4().hex[:8]}",
        patient_id=patient_id,
        test_name=test_name,
        test_category=test_category,
        appointment_date=datetime.now(timezone.utc) - timedelta(days=days_ago),
        status=status,
    )
    db.add(lab)
    await db.commit()
    await db.refresh(lab)
    return lab


async def make_prescription(
    db: AsyncSession,
    patient_id,
    doctor_id,
    diagnosis: str,
    medicines: list[dict],
) -> Prescription:
    record = await make_record(
        db, patient_id, f"Prescription — {diagnosis}", doctor_id=doctor_id,
        record_type="prescription",
    )
    rx = Prescription(
        record_id=record.id,
        doctor_id=doctor_id,
        patient_id=patient_id,
        medicines=medicines,
        diagnosis=diagnosis,
    )
    db.add(rx)
    await db.commit()
    await db.refresh(rx)
    return rx


async def make_clinic(
    db: AsyncSession, name: str, city: str = "Pune", is_active: bool = True
) -> Clinic:
    clinic = Clinic(name=name, city=city, is_active=is_active)
    db.add(clinic)
    await db.commit()
    await db.refresh(clinic)
    return clinic


async def make_membership(db: AsyncSession, clinic_id, user_id) -> ClinicMembership:
    m = ClinicMembership(clinic_id=clinic_id, user_id=user_id, role="doctor")
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


async def make_appointment(
    db: AsyncSession,
    patient_id,
    doctor_id,
    created_by,
    chief_complaint: str | None = None,
) -> Appointment:
    appt = Appointment(
        patient_id=patient_id,
        doctor_id=doctor_id,
        created_by=created_by,
        scheduled_at=datetime.now(timezone.utc) + timedelta(days=1),
        type="in-person",
        status="scheduled",
        chief_complaint=chief_complaint,
    )
    db.add(appt)
    await db.commit()
    await db.refresh(appt)
    return appt


def _types(results: list[dict]) -> set[str]:
    return {r["type"] for r in results}


# ---------------------------------------------------------------------------
# Contract / plumbing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/search", params={"q": "foo"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_missing_query_is_422(patient_client: AsyncClient):
    resp = await patient_client.get("/api/v1/search")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_response_contract(patient_client: AsyncClient, patient_user: User):
    resp = await patient_client.get("/api/v1/search", params={"q": "anything"})
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"results", "total", "query", "took_ms"}
    assert body["query"] == "anything"
    assert isinstance(body["results"], list)
    assert body["total"] == 0


@pytest.mark.asyncio
async def test_no_match_returns_empty(patient_client: AsyncClient, db: AsyncSession):
    other = await make_patient(db, "Ramesh Gupta", "ramesh@test.com")
    await make_record(db, other.id, "Blood panel follow-up")

    resp = await patient_client.get("/api/v1/search", params={"q": "zzz-no-match"})
    assert resp.status_code == 200
    assert resp.json()["results"] == []
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_invalid_type_falls_back_to_all(patient_client: AsyncClient, db: AsyncSession, patient_user: User):
    await make_record(db, patient_user.id, "Annual checkup")

    resp = await patient_client.get("/api/v1/search", params={"q": "checkup", "type": "bogus"})
    assert resp.status_code == 200
    assert _types(resp.json()["results"]) == {"record"}


# ---------------------------------------------------------------------------
# Patient role — own data only
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_patient_finds_own_record(patient_client: AsyncClient, db: AsyncSession, patient_user: User):
    record = await make_record(db, patient_user.id, "Fever consultation notes")

    resp = await patient_client.get("/api/v1/search", params={"q": "fever"})
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert _types(results) == {"record"}
    assert results[0]["id"] == str(record.id)
    assert results[0]["url"] == f"/patient/records/{record.id}"
    for key in ("id", "type", "title", "subtitle", "url"):
        assert key in results[0]


@pytest.mark.asyncio
async def test_patient_cannot_see_other_patients_records(
    patient_client: AsyncClient, db: AsyncSession
):
    other = await make_patient(db, "Other Patient", "other@test.com")
    await make_record(db, other.id, "Confidential fever notes")

    resp = await patient_client.get("/api/v1/search", params={"q": "fever"})
    assert resp.status_code == 200
    assert resp.json()["results"] == []


@pytest.mark.asyncio
async def test_patient_finds_own_lab_result(
    patient_client: AsyncClient, db: AsyncSession, patient_user: User
):
    lab = await make_lab_result(
        db, patient_user.id, "Lipid Profile", test_category="biochemistry"
    )

    resp = await patient_client.get("/api/v1/search", params={"q": "lipid"})
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert _types(results) == {"lab_result"}
    assert results[0]["id"] == str(lab.id)
    assert results[0]["url"] == "/patient/lab-results"
    assert "biochemistry" in results[0]["subtitle"]


@pytest.mark.asyncio
async def test_patient_cannot_see_other_patients_lab_results(
    patient_client: AsyncClient, db: AsyncSession
):
    other = await make_patient(db, "Other Patient", "other@test.com")
    await make_lab_result(db, other.id, "Lipid Profile")

    resp = await patient_client.get("/api/v1/search", params={"q": "lipid"})
    assert resp.status_code == 200
    assert resp.json()["results"] == []


@pytest.mark.asyncio
async def test_patient_finds_own_prescription_by_medicine_name(
    patient_client: AsyncClient, db: AsyncSession, patient_user: User, doctor_profile: Doctor
):
    rx = await make_prescription(
        db,
        patient_user.id,
        doctor_profile.id,
        diagnosis="Viral fever",
        medicines=[
            {"brand_name": "Crocin Advance", "dose": "500mg", "frequency": "BD", "duration": "5 days"}
        ],
    )

    resp = await patient_client.get("/api/v1/search", params={"q": "crocin"})
    assert resp.status_code == 200
    results = resp.json()["results"]
    rx_hits = [r for r in results if r["type"] == "prescription"]
    assert len(rx_hits) == 1
    assert rx_hits[0]["id"] == str(rx.id)
    # Patient-facing URL goes through the backing medical record
    assert rx_hits[0]["url"] == f"/patient/records/{rx.record_id}"
    assert "Crocin Advance" in rx_hits[0]["subtitle"]


@pytest.mark.asyncio
async def test_patient_prescription_search_by_diagnosis(
    patient_client: AsyncClient, db: AsyncSession, patient_user: User, doctor_profile: Doctor
):
    rx = await make_prescription(
        db, patient_user.id, doctor_profile.id,
        diagnosis="Acute bronchitis",
        medicines=[{"brand_name": "Amoxil", "dose": "250mg", "frequency": "TDS", "duration": "7 days"}],
    )
    resp = await patient_client.get(
        "/api/v1/search", params={"q": "bronchitis", "type": "prescription"}
    )
    assert resp.status_code == 200
    assert [r["id"] for r in resp.json()["results"]] == [str(rx.id)]


@pytest.mark.asyncio
async def test_patient_cannot_see_other_patients_prescriptions(
    patient_client: AsyncClient, db: AsyncSession, doctor_profile: Doctor
):
    other = await make_patient(db, "Other Patient", "other@test.com")
    await make_prescription(
        db, other.id, doctor_profile.id, diagnosis="Viral fever",
        medicines=[{"brand_name": "Crocin", "dose": "500mg", "frequency": "BD", "duration": "5 days"}],
    )

    resp = await patient_client.get("/api/v1/search", params={"q": "crocin"})
    assert resp.status_code == 200
    assert all(r["type"] != "prescription" for r in resp.json()["results"])


@pytest.mark.asyncio
async def test_patient_searches_own_appointments_by_doctor_name(
    patient_client: AsyncClient,
    db: AsyncSession,
    patient_user: User,
    doctor_user: User,
    doctor_profile: Doctor,
):
    appt = await make_appointment(
        db, patient_user.id, doctor_profile.id, patient_user.id,
        chief_complaint="Knee pain",
    )
    other = await make_patient(db, "Other Patient", "other@test.com")
    await make_appointment(
        db, other.id, doctor_profile.id, other.id, chief_complaint="Knee pain",
    )

    # Match by complaint
    resp = await patient_client.get("/api/v1/search", params={"q": "knee"})
    results = resp.json()["results"]
    assert _types(results) == {"appointment"}
    assert results[0]["id"] == str(appt.id)
    assert results[0]["url"] == "/patient/appointments"
    assert "Dr." in results[0]["title"]

    # Match by doctor's display name
    resp = await patient_client.get("/api/v1/search", params={"q": "Doctor User"})
    assert any(r["id"] == str(appt.id) for r in resp.json()["results"])


@pytest.mark.asyncio
async def test_patient_searches_clinic_directory(
    patient_client: AsyncClient, db: AsyncSession
):
    clinic = await make_clinic(db, "Sunrise Multispeciality", city="Pune")
    inactive = await make_clinic(db, "Sunrise Closed Wing", is_active=False)

    resp = await patient_client.get("/api/v1/search", params={"q": "sunrise"})
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert _types(results) == {"clinic"}
    ids = {r["id"] for r in results}
    assert str(clinic.id) in ids
    assert str(inactive.id) not in ids  # inactive clinics hidden from patients
    assert results[0]["url"] == "/patient/clinics"


@pytest.mark.asyncio
async def test_patient_cannot_search_users_or_doctors(
    patient_client: AsyncClient, db: AsyncSession
):
    await make_patient(db, "Searchable Patient", "searchable@test.com")

    resp = await patient_client.get("/api/v1/search", params={"q": "searchable"})
    assert resp.status_code == 200
    assert not (_types(resp.json()["results"]) & {"patient", "doctor"})


@pytest.mark.asyncio
async def test_soft_deleted_records_excluded(
    patient_client: AsyncClient, db: AsyncSession, patient_user: User
):
    record = await make_record(db, patient_user.id, "Deleted fever note")
    record.deleted_at = datetime.now(timezone.utc)
    await db.commit()

    resp = await patient_client.get("/api/v1/search", params={"q": "fever"})
    assert resp.json()["results"] == []


# ---------------------------------------------------------------------------
# Doctor role — accessible patients via access_service
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_doctor_finds_accessible_patient_records(
    doctor_client: AsyncClient, db: AsyncSession, doctor_profile: Doctor
):
    patient = await make_patient(db, "Linked Patient", "linked@test.com")
    # The authored record both grants the relationship AND is searchable.
    record = await make_record(
        db, patient.id, "Diabetes management plan", doctor_id=doctor_profile.id
    )

    resp = await doctor_client.get("/api/v1/search", params={"q": "diabetes"})
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert _types(results) == {"record"}
    assert results[0]["id"] == str(record.id)
    assert results[0]["url"] == f"/doctor/patients/{patient.id}"
    assert "Linked Patient" in results[0]["subtitle"]


@pytest.mark.asyncio
async def test_doctor_cannot_see_unrelated_patient_records(
    doctor_client: AsyncClient, db: AsyncSession
):
    stranger = await make_patient(db, "Stranger Patient", "stranger@test.com")
    await make_record(db, stranger.id, "Diabetes management plan")  # no doctor_id

    resp = await doctor_client.get("/api/v1/search", params={"q": "diabetes"})
    assert resp.status_code == 200
    assert resp.json()["results"] == []


@pytest.mark.asyncio
async def test_doctor_finds_accessible_patient_lab_results(
    doctor_client: AsyncClient, db: AsyncSession, doctor_profile: Doctor
):
    patient = await make_patient(db, "Linked Patient", "linked@test.com")
    # Grant the relationship via an authored record (the lab itself was
    # ordered elsewhere — still visible through the patient relationship).
    await make_record(db, patient.id, "Relationship seed", doctor_id=doctor_profile.id)
    lab = await make_lab_result(db, patient.id, "HbA1c", test_category="biochemistry")
    stranger = await make_patient(db, "Stranger", "stranger@test.com")
    await make_lab_result(db, stranger.id, "HbA1c")

    resp = await doctor_client.get("/api/v1/search", params={"q": "hba1c", "type": "lab_result"})
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert [r["id"] for r in results] == [str(lab.id)]
    assert results[0]["url"] == f"/doctor/patients/{patient.id}"


@pytest.mark.asyncio
async def test_doctor_finds_accessible_patient_prescriptions(
    doctor_client: AsyncClient, db: AsyncSession, doctor_profile: Doctor
):
    patient = await make_patient(db, "Linked Patient", "linked@test.com")
    rx = await make_prescription(
        db, patient.id, doctor_profile.id, diagnosis="Hypertension",
        medicines=[{"brand_name": "Amlong", "dose": "5mg", "frequency": "OD", "duration": "1 month"}],
    )
    stranger = await make_patient(db, "Stranger", "stranger@test.com")
    # A prescription authored by a different doctor for an unrelated patient.
    other_user = User(keycloak_sub=f"sub-{uuid.uuid4()}", email="od@t.com", full_name="Other Doc", role="doctor")
    db.add(other_user)
    await db.flush()
    other_doctor = Doctor(user_id=other_user.id)
    db.add(other_doctor)
    await db.flush()
    await make_prescription(
        db, stranger.id, other_doctor.id, diagnosis="Hypertension",
        medicines=[{"brand_name": "Amlong", "dose": "5mg", "frequency": "OD", "duration": "1 month"}],
    )

    resp = await doctor_client.get(
        "/api/v1/search", params={"q": "amlong", "type": "prescription"}
    )
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert [r["id"] for r in results] == [str(rx.id)]
    assert results[0]["url"] == f"/doctor/prescriptions/{rx.id}"


@pytest.mark.asyncio
async def test_doctor_searches_member_clinics_only(
    doctor_client: AsyncClient, db: AsyncSession, doctor_user: User
):
    mine = await make_clinic(db, "Sunrise Member Clinic")
    await make_membership(db, mine.id, doctor_user.id)
    await make_clinic(db, "Sunrise Other Clinic")

    resp = await doctor_client.get("/api/v1/search", params={"q": "sunrise", "type": "clinic"})
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert [r["id"] for r in results] == [str(mine.id)]
    assert results[0]["url"] == "/doctor/clinic"


@pytest.mark.asyncio
async def test_doctor_without_profile_gets_no_patient_data(
    client: AsyncClient, db: AsyncSession
):
    """A doctor-role user with no Doctor profile must not see patient data."""
    user = User(
        keycloak_sub="doc-no-profile", email="np@t.com",
        full_name="No Profile", role="doctor",
    )
    db.add(user)
    await db.commit()

    patient = await make_patient(db, "Linked Patient", "linked@test.com")
    await make_record(db, patient.id, "Diabetes plan")
    await make_lab_result(db, patient.id, "HbA1c")

    token = create_test_token(sub="doc-no-profile", email="np@t.com",
                              name="No Profile", roles=["doctor"])
    resp = await client.get(
        "/api/v1/search", params={"q": "a"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert all(
        r["type"] not in {"patient", "record", "lab_result", "prescription"}
        for r in resp.json()["results"]
    )


# ---------------------------------------------------------------------------
# Admin role — broad visibility
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_sees_all_entity_types(
    admin_client: AsyncClient, db: AsyncSession
):
    patient = await make_patient(db, "Admin Target Patient", "target@test.com")
    doctor_user = User(
        keycloak_sub=f"sub-{uuid.uuid4()}", email="doc@t.com",
        full_name="Admin Target Doctor", role="doctor",
    )
    db.add(doctor_user)
    await db.flush()
    doctor = Doctor(user_id=doctor_user.id, specialization="Cardiology")
    db.add(doctor)
    await db.flush()
    clinic = await make_clinic(db, "Admin Target Clinic")
    appt = await make_appointment(db, patient.id, doctor.id, patient.id,
                                  chief_complaint="Admin Target complaint")
    record = await make_record(db, patient.id, "Admin Target record",
                               doctor_id=doctor.id)
    lab = await make_lab_result(db, patient.id, "Admin Target Panel")
    rx = await make_prescription(
        db, patient.id, doctor.id, diagnosis="Admin Target dx",
        medicines=[{"brand_name": "Targetol", "dose": "10mg", "frequency": "OD", "duration": "7 days"}],
    )

    resp = await admin_client.get("/api/v1/search", params={"q": "Admin Target"})
    assert resp.status_code == 200
    types = _types(resp.json()["results"])
    assert {"patient", "doctor", "clinic", "appointment", "record", "lab_result", "prescription"} <= types

    by_id = {r["id"]: r for r in resp.json()["results"]}
    assert by_id[str(lab.id)]["url"] == "/admin/lab-results"
    assert by_id[str(rx.id)]["url"] == f"/admin/users/{patient.id}"
    assert by_id[str(record.id)]["url"] == f"/admin/users/{patient.id}"
    assert by_id[str(clinic.id)]["url"] == f"/admin/clinics/{clinic.id}"
    assert by_id[str(appt.id)]["url"] == "/admin/appointments"


@pytest.mark.asyncio
async def test_type_filter_lab_result(admin_client: AsyncClient, db: AsyncSession):
    patient = await make_patient(db, "Filter Patient", "filter@test.com")
    await make_lab_result(db, patient.id, "Thyroid Profile")
    await make_record(db, patient.id, "Thyroid consult")

    resp = await admin_client.get(
        "/api/v1/search", params={"q": "thyroid", "type": "lab_result"}
    )
    assert resp.status_code == 200
    assert _types(resp.json()["results"]) == {"lab_result"}


# ---------------------------------------------------------------------------
# Ordering + suggestions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_records_ordered_newest_first(
    patient_client: AsyncClient, db: AsyncSession, patient_user: User
):
    older = await make_record(
        db, patient_user.id, "Fever note A",
        created_at=datetime.now(timezone.utc) - timedelta(days=5),
    )
    newer = await make_record(db, patient_user.id, "Fever note B")

    resp = await patient_client.get("/api/v1/search", params={"q": "fever"})
    ids = [r["id"] for r in resp.json()["results"]]
    assert ids == [str(newer.id), str(older.id)]


@pytest.mark.asyncio
async def test_suggestions_include_new_types(
    patient_client: AsyncClient, db: AsyncSession, patient_user: User
):
    await make_lab_result(db, patient_user.id, "Vitamin D Assay")
    await make_record(db, patient_user.id, "Vitamin deficiency consult")

    resp = await patient_client.get("/api/v1/search/suggestions", params={"q": "vitamin"})
    assert resp.status_code == 200
    suggestions = resp.json()["suggestions"]
    assert "Vitamin D Assay" in suggestions
    assert "Vitamin deficiency consult" in suggestions


@pytest.mark.asyncio
async def test_suggestions_dedup_and_limit(
    patient_client: AsyncClient, db: AsyncSession, patient_user: User
):
    for i in range(5):
        await make_lab_result(db, patient_user.id, "Duplicate Test Name")

    resp = await patient_client.get(
        "/api/v1/search/suggestions", params={"q": "duplicate", "limit": 5}
    )
    assert resp.status_code == 200
    assert resp.json()["suggestions"] == ["Duplicate Test Name"]


# ---------------------------------------------------------------------------
# Rate limiting — /api/v1/search has a dedicated 30/min bucket
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_endpoint_rate_limited_at_30(
    patient_client: AsyncClient,
):
    """The 31st search request in a minute is rejected with 429.

    conftest swaps Redis for fakeredis, so real counters apply.
    """
    last = None
    for _ in range(30):
        last = await patient_client.get("/api/v1/search", params={"q": "x"})
        assert last.status_code == 200
    resp = await patient_client.get("/api/v1/search", params={"q": "x"})
    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert "30" in resp.json()["error"]["message"]
    assert "retry-after" in resp.headers


@pytest.mark.asyncio
async def test_search_suggestions_rate_limited_at_30(patient_client: AsyncClient):
    for _ in range(30):
        resp = await patient_client.get("/api/v1/search/suggestions", params={"q": "x"})
        assert resp.status_code == 200
    resp = await patient_client.get("/api/v1/search/suggestions", params={"q": "x"})
    assert resp.status_code == 429
