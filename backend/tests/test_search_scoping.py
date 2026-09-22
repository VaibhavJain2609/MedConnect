"""Additional global-search scoping tests — r11 coverage.

test_search.py covers the happy-path per-role matrix; this file targets the
scoping gaps:
  - doctor access via *approved clinic link* (no authored record)
  - revoked / pending clinic links must NOT grant search visibility
    (accessible_patient_ids_select is called with allow_revoked=False)
  - doctor patient search (type=patient) only returns accessible patients
  - medicine entity (brands/salts in the medicine DB): doctor+admin see it,
    patients never do
  - admin clinic search includes inactive clinics; patient directory doesn't
  - match fields beyond titles (lab test_id, record_type, doctor specialization)
  - suggestions scoping per role
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
from app.models.patient_link import PatientClinicLink
from app.models.user import User
from tests.conftest import create_test_token

pytestmark = pytest.mark.asyncio

SEARCH_URL = "/api/v1/search"
SUGGEST_URL = "/api/v1/search/suggestions"


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


async def make_patient(db: AsyncSession, name: str, email: str | None = None) -> User:
    user = User(
        keycloak_sub=f"sub-{uuid.uuid4()}",
        email=email or f"{uuid.uuid4().hex[:8]}@test.com",
        full_name=name,
        role="patient",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def make_record(
    db: AsyncSession, patient_id, title: str, doctor_id=None,
    record_type: str = "opd_note",
) -> MedicalRecord:
    record = MedicalRecord(
        patient_id=patient_id, doctor_id=doctor_id,
        record_type=record_type, title=title,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def make_lab_result(db: AsyncSession, patient_id, test_name: str,
                          test_id: str | None = None) -> LabResult:
    lab = LabResult(
        test_id=test_id or f"TST-{uuid.uuid4().hex[:8]}",
        patient_id=patient_id,
        test_name=test_name,
        test_category="biochemistry",
        appointment_date=datetime.now(timezone.utc),
        status="completed",
    )
    db.add(lab)
    await db.commit()
    await db.refresh(lab)
    return lab


async def make_prescription(
    db: AsyncSession, patient_id, doctor_id, diagnosis: str
) -> Prescription:
    record = await make_record(
        db, patient_id, f"Rx {diagnosis}", doctor_id=doctor_id,
        record_type="prescription",
    )
    rx = Prescription(
        record_id=record.id, doctor_id=doctor_id, patient_id=patient_id,
        medicines=[{"brand_name": "Zincovit", "dose": "1 tab"}],
        diagnosis=diagnosis,
    )
    db.add(rx)
    await db.commit()
    await db.refresh(rx)
    return rx


async def make_clinic(db: AsyncSession, name: str, is_active: bool = True) -> Clinic:
    clinic = Clinic(name=name, city="Pune", is_active=is_active)
    db.add(clinic)
    await db.commit()
    await db.refresh(clinic)
    return clinic


async def make_membership(db: AsyncSession, clinic_id, user_id) -> ClinicMembership:
    m = ClinicMembership(clinic_id=clinic_id, user_id=user_id, role="doctor")
    db.add(m)
    await db.commit()
    return m


async def make_link(
    db: AsyncSession, patient_id, clinic_id, linked_by, consent_status: str
) -> PatientClinicLink:
    link = PatientClinicLink(
        patient_id=patient_id, clinic_id=clinic_id, linked_by=linked_by,
        consent_status=consent_status,
        consented_at=datetime.now(timezone.utc) - timedelta(days=10),
    )
    db.add(link)
    await db.commit()
    return link


async def link_patient_to_doctors_clinic(
    db: AsyncSession, doctor_user: User, patient: User,
    consent_status: str = "approved",
) -> Clinic:
    """Create a clinic, member it to the doctor, link the patient to it."""
    clinic = await make_clinic(db, f"Clinic {uuid.uuid4().hex[:6]}")
    await make_membership(db, clinic.id, doctor_user.id)
    await make_link(db, patient.id, clinic.id, doctor_user.id, consent_status)
    return clinic


def _ids(results: list[dict]) -> set[str]:
    return {r["id"] for r in results}


# ---------------------------------------------------------------------------
# Doctor scoping via clinic links (no authored records)
# ---------------------------------------------------------------------------


async def test_doctor_sees_record_via_approved_clinic_link(
    doctor_client: AsyncClient, doctor_user: User, doctor_profile: Doctor,
    db: AsyncSession,
):
    """An approved PatientClinicLink (no authored record) makes the patient's
    records searchable."""
    patient = await make_patient(db, "Linked Vita")
    await link_patient_to_doctors_clinic(db, doctor_user, patient, "approved")
    record = await make_record(db, patient.id, "Unique thyroid workup")

    resp = await doctor_client.get(SEARCH_URL, params={"q": "thyroid"})
    assert resp.status_code == 200
    assert str(record.id) in _ids(resp.json()["results"])


async def test_doctor_sees_lab_and_rx_via_approved_clinic_link(
    doctor_client: AsyncClient, doctor_user: User, doctor_profile: Doctor,
    db: AsyncSession,
):
    patient = await make_patient(db, "Linked Vita")
    await link_patient_to_doctors_clinic(db, doctor_user, patient, "approved")
    lab = await make_lab_result(db, patient.id, "Uniquelab Panel")
    rx = await make_prescription(db, patient.id, doctor_profile.id, "Uniquerxitis")

    resp = await doctor_client.get(SEARCH_URL, params={"q": "uniquelab"})
    assert str(lab.id) in _ids(resp.json()["results"])

    resp = await doctor_client.get(SEARCH_URL, params={"q": "uniquerxitis"})
    assert str(rx.id) in _ids(resp.json()["results"])


async def _make_other_doctor(db: AsyncSession) -> Doctor:
    """A second doctor who authored data for the patient — ensures access
    can only come through the clinic link, not via_records."""
    other_user = User(
        keycloak_sub=f"sub-{uuid.uuid4()}", email=f"{uuid.uuid4().hex[:8]}@t.com",
        full_name="Other Doc", role="doctor",
    )
    db.add(other_user)
    await db.flush()
    other_doctor = Doctor(user_id=other_user.id)
    db.add(other_doctor)
    await db.commit()
    return other_doctor


async def test_doctor_revoked_link_hides_patient_entities(
    doctor_client: AsyncClient, doctor_user: User, doctor_profile: Doctor,
    db: AsyncSession,
):
    """Revoked consent grants read-back only of pre-revocation clinical data
    in the patient view — the *search* index uses allow_revoked=False, so a
    revoked link must not surface the patient or their data at all.

    The prescription is authored by a *different* doctor on purpose: an
    authored record would itself grant access via the records path."""
    patient = await make_patient(db, "Revoked Vita")
    await link_patient_to_doctors_clinic(db, doctor_user, patient, "revoked")
    other_doctor = await _make_other_doctor(db)
    record = await make_record(db, patient.id, "Revokescope note")
    lab = await make_lab_result(db, patient.id, "Revokescope panel")
    rx = await make_prescription(db, patient.id, other_doctor.id, "Revokescope dx")

    for q in ("Revokescope", "Revoked Vita"):
        resp = await doctor_client.get(SEARCH_URL, params={"q": q})
        assert resp.status_code == 200
        found = _ids(resp.json()["results"])
        assert str(record.id) not in found
        assert str(lab.id) not in found
        assert str(rx.id) not in found
        assert str(patient.id) not in found


async def test_doctor_pending_link_hides_patient_entities(
    doctor_client: AsyncClient, doctor_user: User, doctor_profile: Doctor,
    db: AsyncSession,
):
    patient = await make_patient(db, "Pending Vita")
    await link_patient_to_doctors_clinic(db, doctor_user, patient, "pending")
    record = await make_record(db, patient.id, "Pendingscope note")

    resp = await doctor_client.get(SEARCH_URL, params={"q": "Pendingscope"})
    assert resp.status_code == 200
    assert str(record.id) not in _ids(resp.json()["results"])

    resp = await doctor_client.get(SEARCH_URL, params={"q": "Pending Vita"})
    assert str(patient.id) not in _ids(resp.json()["results"])


async def test_doctor_patient_search_returns_only_accessible(
    doctor_client: AsyncClient, doctor_user: User, doctor_profile: Doctor,
    db: AsyncSession,
):
    """type=patient: linked patient matches; a stranger with the same name
    does not."""
    linked = await make_patient(db, "Aarav Scopecheck")
    await link_patient_to_doctors_clinic(db, doctor_user, linked, "approved")
    stranger = await make_patient(db, "Aarav Scopecheck")

    resp = await doctor_client.get(
        SEARCH_URL, params={"q": "scopecheck", "type": "patient"}
    )
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert _ids(results) == {str(linked.id)}
    assert results[0]["url"] == f"/doctor/patients/{linked.id}"


async def test_doctor_appointment_search_scoped_to_own(
    doctor_client: AsyncClient, doctor_user: User, doctor_profile: Doctor,
    db: AsyncSession,
):
    """type=appointment returns only the calling doctor's appointments."""
    patient = await make_patient(db, "Appt Patient")
    own = Appointment(
        patient_id=patient.id, doctor_id=doctor_profile.id,
        created_by=doctor_user.id,
        scheduled_at=datetime.now(timezone.utc) + timedelta(days=1),
        type="in-person", status="scheduled", chief_complaint="Uniqueshoulder pain",
    )
    # Another doctor's appointment with the same complaint text.
    other_user = User(
        keycloak_sub=f"sub-{uuid.uuid4()}", email=f"{uuid.uuid4().hex[:8]}@t.com",
        full_name="Other Doc", role="doctor",
    )
    db.add(other_user)
    await db.flush()
    other_doctor = Doctor(user_id=other_user.id)
    db.add(other_doctor)
    await db.flush()
    foreign = Appointment(
        patient_id=patient.id, doctor_id=other_doctor.id,
        created_by=other_user.id,
        scheduled_at=datetime.now(timezone.utc) + timedelta(days=1),
        type="in-person", status="scheduled", chief_complaint="Uniqueshoulder pain",
    )
    db.add_all([own, foreign])
    await db.commit()

    resp = await doctor_client.get(
        SEARCH_URL, params={"q": "uniqueshoulder", "type": "appointment"}
    )
    assert resp.status_code == 200
    assert _ids(resp.json()["results"]) == {str(own.id)}


# ---------------------------------------------------------------------------
# Medicine entity
# ---------------------------------------------------------------------------


async def test_doctor_medicine_search_brand_and_salt(
    doctor_client: AsyncClient, sample_brand, sample_salt
):
    """Crocin (brand) and Paracetamol (salt) live in the medicine DB."""
    resp = await doctor_client.get(SEARCH_URL, params={"q": "crocin", "type": "medicine"})
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert _ids(results) == {str(sample_brand.brand_id)}
    assert results[0]["metadata"]["kind"] == "brand"
    assert results[0]["url"] == "/doctor/prescriptions/new"

    resp = await doctor_client.get(
        SEARCH_URL, params={"q": "paracetamol", "type": "medicine"}
    )
    results = resp.json()["results"]
    assert _ids(results) == {str(sample_salt.salt_id)}
    assert results[0]["metadata"]["kind"] == "salt"


async def test_admin_medicine_search(admin_client: AsyncClient, sample_brand):
    resp = await admin_client.get(SEARCH_URL, params={"q": "crocin", "type": "medicine"})
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert _ids(results) == {str(sample_brand.brand_id)}
    assert results[0]["url"] == "/admin/medicines"


async def test_patient_cannot_search_medicines(
    patient_client: AsyncClient, sample_brand
):
    """The patient role intentionally has no medicine-catalog scope."""
    resp = await patient_client.get(SEARCH_URL, params={"q": "crocin"})
    assert resp.status_code == 200
    assert all(r["type"] != "medicine" for r in resp.json()["results"])

    resp = await patient_client.get(
        SEARCH_URL, params={"q": "crocin", "type": "medicine"}
    )
    assert resp.json()["results"] == []


# ---------------------------------------------------------------------------
# Clinics — role differences
# ---------------------------------------------------------------------------


async def test_admin_clinic_search_includes_inactive(
    admin_client: AsyncClient, db: AsyncSession
):
    """Admin sees inactive clinics; the patient directory hides them."""
    inactive = await make_clinic(db, "Closedwing Clinic", is_active=False)
    active = await make_clinic(db, "Closedwing Annex", is_active=True)

    resp = await admin_client.get(SEARCH_URL, params={"q": "closedwing", "type": "clinic"})
    assert _ids(resp.json()["results"]) == {str(inactive.id), str(active.id)}


async def test_patient_clinic_search_excludes_inactive(
    patient_client: AsyncClient, db: AsyncSession
):
    inactive = await make_clinic(db, "Hiddenwing Clinic", is_active=False)
    active = await make_clinic(db, "Hiddenwing Annex", is_active=True)

    resp = await patient_client.get(SEARCH_URL, params={"q": "hiddenwing"})
    assert _ids(resp.json()["results"]) == {str(active.id)}


# ---------------------------------------------------------------------------
# Match fields beyond titles
# ---------------------------------------------------------------------------


async def test_lab_result_matches_test_id(
    patient_client: AsyncClient, patient_user: User, db: AsyncSession
):
    lab = await make_lab_result(
        db, patient_user.id, test_name="CBC", test_id="TST-UNIQUE99"
    )
    resp = await patient_client.get(SEARCH_URL, params={"q": "unique99"})
    assert resp.status_code == 200
    assert str(lab.id) in _ids(resp.json()["results"])


async def test_record_matches_record_type(
    patient_client: AsyncClient, patient_user: User, db: AsyncSession
):
    """record_type is a match field: searching 'imaging' finds imaging
    records even when the title doesn't contain the word."""
    record = await make_record(
        db, patient_user.id, "Chest scan report", record_type="imaging"
    )
    resp = await patient_client.get(SEARCH_URL, params={"q": "imaging"})
    assert str(record.id) in _ids(resp.json()["results"])


async def test_admin_doctor_search_matches_specialization(
    admin_client: AsyncClient, db: AsyncSession
):
    doc_user = User(
        keycloak_sub=f"sub-{uuid.uuid4()}", email=f"{uuid.uuid4().hex[:8]}@t.com",
        full_name="Plain Name", role="doctor",
    )
    db.add(doc_user)
    await db.flush()
    doctor = Doctor(user_id=doc_user.id, specialization="Neurosurgeonix")
    db.add(doctor)
    await db.commit()

    resp = await admin_client.get(
        SEARCH_URL, params={"q": "neurosurgeonix", "type": "doctor"}
    )
    assert _ids(resp.json()["results"]) == {str(doctor.id)}


# ---------------------------------------------------------------------------
# limit / offset
# ---------------------------------------------------------------------------


async def test_limit_applies_per_entity_type(
    admin_client: AsyncClient, db: AsyncSession
):
    """limit caps rows *per* type — a type='record' query with limit=1
    returns a single record even if more match."""
    patient = await make_patient(db, "Limit Target")
    await make_record(db, patient.id, "Limittag one")
    await make_record(db, patient.id, "Limittag two")

    resp = await admin_client.get(
        SEARCH_URL, params={"q": "limittag", "type": "record", "limit": 1}
    )
    results = resp.json()["results"]
    assert len(results) == 1
    # `total` is the full match count, not the page size.
    assert resp.json()["total"] == 2


# ---------------------------------------------------------------------------
# Suggestions scoping
# ---------------------------------------------------------------------------


async def test_suggestions_requires_auth(client: AsyncClient):
    resp = await client.get(SUGGEST_URL, params={"q": "x"})
    assert resp.status_code == 401


async def test_suggestions_doctor_excludes_inaccessible_patients_data(
    doctor_client: AsyncClient, doctor_user: User, doctor_profile: Doctor,
    db: AsyncSession,
):
    """Doctor suggestions pull from accessible patients' labs/rx only."""
    linked = await make_patient(db, "Sugg Linked")
    await link_patient_to_doctors_clinic(db, doctor_user, linked, "approved")
    stranger = await make_patient(db, "Sugg Stranger")

    await make_lab_result(db, linked.id, "Suggestscope Visible Panel")
    await make_lab_result(db, stranger.id, "Suggestscope Hidden Panel")

    resp = await doctor_client.get(SUGGEST_URL, params={"q": "suggestscope"})
    assert resp.status_code == 200
    suggestions = resp.json()["suggestions"]
    assert "Suggestscope Visible Panel" in suggestions
    assert "Suggestscope Hidden Panel" not in suggestions


async def test_suggestions_admin_sees_doctors_and_clinics(
    admin_client: AsyncClient, db: AsyncSession
):
    doc_user = User(
        keycloak_sub=f"sub-{uuid.uuid4()}", email=f"{uuid.uuid4().hex[:8]}@t.com",
        full_name="Suggestable Doctor", role="doctor",
    )
    db.add(doc_user)
    await db.flush()
    db.add(Doctor(user_id=doc_user.id))
    await make_clinic(db, "Suggestable Clinic")

    resp = await admin_client.get(SUGGEST_URL, params={"q": "suggestable"})
    assert resp.status_code == 200
    suggestions = resp.json()["suggestions"]
    assert "Suggestable Doctor" in suggestions
    assert "Suggestable Clinic" in suggestions


async def test_suggestions_patient_only_own_data(
    patient_client: AsyncClient, patient_user: User, db: AsyncSession
):
    other = await make_patient(db, "Other")
    await make_lab_result(db, patient_user.id, "Ownscope Mine")
    await make_lab_result(db, other.id, "Ownscope Theirs")

    resp = await patient_client.get(SUGGEST_URL, params={"q": "ownscope"})
    suggestions = resp.json()["suggestions"]
    assert "Ownscope Mine" in suggestions
    assert "Ownscope Theirs" not in suggestions
