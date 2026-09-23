"""Tests for the vitals router (app/routers/vitals.py) — r11 coverage.

Endpoints under test:
  POST /api/v1/patients/vitals                          — patient records a vital
  GET  /api/v1/patients/vitals                          — patient lists own vitals
  GET  /api/v1/doctors/patients/{patient_id}/vitals     — doctor reads patient vitals

Coverage:
  - auth: unauthenticated 401, wrong role 403, unverified doctor 403
  - create: valid types, INVALID_VITAL_TYPE, value bounds, recorded_at/notes,
    abnormal_flag + critical-vital notifications (patient + linked clinic doctors)
  - patient list: self-scope, type/days/limit filters, ordering, soft deletes
  - doctor list: relationship via authored record, approved clinic link,
    X-Clinic-Id consent gate, revoked-link cutoff (with and without header),
    non-member clinic, invalid clinic id
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clinic import Clinic, ClinicMembership
from app.models.doctor import Doctor
from app.models.medical_record import MedicalRecord
from app.models.notification import Notification
from app.models.patient_link import PatientClinicLink
from app.models.user import User
from app.models.vital import PatientVital
from tests.conftest import create_test_token

pytestmark = pytest.mark.asyncio

PATIENT_VITALS_URL = "/api/v1/patients/vitals"


def _doctor_vitals_url(patient_id) -> str:
    return f"/api/v1/doctors/patients/{patient_id}/vitals"


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


async def make_patient(db: AsyncSession, name: str = "Vitals Patient") -> User:
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


async def make_vital(
    db: AsyncSession,
    patient_id,
    vital_type: str = "pulse",
    value: float = 72,
    unit: str = "bpm",
    recorded_at: datetime | None = None,
    recorded_by=None,
    deleted: bool = False,
) -> PatientVital:
    vital = PatientVital(
        id=uuid.uuid4(),
        patient_id=patient_id,
        vital_type=vital_type,
        value=value,
        unit=unit,
        recorded_at=recorded_at or datetime.now(timezone.utc),
        recorded_by=recorded_by or patient_id,
    )
    if deleted:
        vital.deleted_at = datetime.now(timezone.utc)
    db.add(vital)
    await db.commit()
    await db.refresh(vital)
    return vital


async def make_clinic(db: AsyncSession, name: str = "Vitals Clinic") -> Clinic:
    clinic = Clinic(id=uuid.uuid4(), name=name, city="Pune")
    db.add(clinic)
    await db.commit()
    await db.refresh(clinic)
    return clinic


async def make_membership(
    db: AsyncSession, clinic_id, user_id, role: str = "doctor", is_active: bool = True
) -> ClinicMembership:
    m = ClinicMembership(
        id=uuid.uuid4(), clinic_id=clinic_id, user_id=user_id, role=role, is_active=is_active
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


async def make_link(
    db: AsyncSession,
    patient_id,
    clinic_id,
    linked_by,
    consent_status: str = "approved",
    revoked_at: datetime | None = None,
) -> PatientClinicLink:
    link = PatientClinicLink(
        id=uuid.uuid4(),
        patient_id=patient_id,
        clinic_id=clinic_id,
        linked_by=linked_by,
        consent_status=consent_status,
        consented_at=datetime.now(timezone.utc) - timedelta(days=30),
        revoked_at=revoked_at,
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return link


async def make_record(db: AsyncSession, patient_id, doctor_id) -> MedicalRecord:
    record = MedicalRecord(
        patient_id=patient_id,
        doctor_id=doctor_id,
        record_type="opd_note",
        title="Relationship seed",
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def patient_notifications(db: AsyncSession, user_id) -> list[Notification]:
    result = await db.execute(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.deleted_at.is_(None),
        )
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# POST /patients/vitals — auth + validation
# ---------------------------------------------------------------------------


async def test_create_vital_requires_auth(client: AsyncClient):
    resp = await client.post(
        PATIENT_VITALS_URL,
        json={"vital_type": "pulse", "value": 72, "unit": "bpm"},
    )
    assert resp.status_code == 401


async def test_create_vital_rejects_doctor_role(doctor_client: AsyncClient):
    resp = await doctor_client.post(
        PATIENT_VITALS_URL,
        json={"vital_type": "pulse", "value": 72, "unit": "bpm"},
    )
    assert resp.status_code == 403


@pytest.mark.smoke
async def test_create_vital_happy_path(patient_client: AsyncClient, patient_user: User):
    recorded = "2025-01-15T10:30:00+00:00"
    resp = await patient_client.post(
        PATIENT_VITALS_URL,
        json={
            "vital_type": "bp_systolic",
            "value": 120,
            "unit": "mmHg",
            "recorded_at": recorded,
            "notes": "morning reading",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["patient_id"] == str(patient_user.id)
    assert body["vital_type"] == "bp_systolic"
    assert body["value"] == 120.0
    assert body["unit"] == "mmHg"
    assert body["notes"] == "morning reading"
    assert body["recorded_by"] == str(patient_user.id)
    assert body["abnormal_flag"] is False
    assert body["recorded_at"].startswith("2025-01-15")


async def test_create_vital_defaults_recorded_at_now(
    patient_client: AsyncClient, patient_user: User
):
    before = datetime.now(timezone.utc)
    resp = await patient_client.post(
        PATIENT_VITALS_URL, json={"vital_type": "weight_kg", "value": 68.5, "unit": "kg"}
    )
    assert resp.status_code == 201
    recorded_at = datetime.fromisoformat(resp.json()["recorded_at"])
    assert recorded_at >= before - timedelta(seconds=5)


async def test_create_vital_invalid_type(patient_client: AsyncClient):
    resp = await patient_client.post(
        PATIENT_VITALS_URL,
        json={"vital_type": "blood_pressure", "value": 120, "unit": "mmHg"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_VITAL_TYPE"


@pytest.mark.parametrize(
    "vital_type,value",
    [
        ("spo2", 150),       # above hard max 100
        ("spo2", 0),         # below hard min 1
        ("pulse", 5),        # below hard min 10
        ("bp_systolic", 500),  # above hard max 350
        ("glucose_fasting", 0),
    ],
)
async def test_create_vital_out_of_bounds(
    patient_client: AsyncClient, vital_type: str, value: float
):
    """Values outside the clinical bounds fail schema validation (422)."""
    resp = await patient_client.post(
        PATIENT_VITALS_URL,
        json={"vital_type": vital_type, "value": value, "unit": "x"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /patients/vitals — abnormal flag + critical notifications
# ---------------------------------------------------------------------------


async def test_create_vital_critical_high_sets_flag_and_notifies(
    patient_client: AsyncClient, patient_user: User, db: AsyncSession
):
    """bp_systolic > 180 is critical: response flags it and a notification row
    is created for the patient."""
    resp = await patient_client.post(
        PATIENT_VITALS_URL,
        json={"vital_type": "bp_systolic", "value": 200, "unit": "mmHg"},
    )
    assert resp.status_code == 201
    assert resp.json()["abnormal_flag"] is True

    notifications = await patient_notifications(db, patient_user.id)
    assert len(notifications) == 1
    assert notifications[0].title == "Critical Vital Alert"
    assert "critically high" in notifications[0].message
    assert notifications[0].meta["vital_type"] == "bp_systolic"
    assert notifications[0].meta["abnormal_flag"] is True


async def test_create_vital_critical_low_sets_flag(
    patient_client: AsyncClient, patient_user: User, db: AsyncSession
):
    """spo2 < 92 is critically low."""
    resp = await patient_client.post(
        PATIENT_VITALS_URL, json={"vital_type": "spo2", "value": 88, "unit": "%"}
    )
    assert resp.status_code == 201
    assert resp.json()["abnormal_flag"] is True
    notifications = await patient_notifications(db, patient_user.id)
    assert len(notifications) == 1
    assert "critically low" in notifications[0].message


async def test_create_vital_at_threshold_boundary_not_abnormal(
    patient_client: AsyncClient, patient_user: User, db: AsyncSession
):
    """Thresholds are exclusive: exactly 92 spo2 and exactly 180 systolic are
    NOT abnormal."""
    resp = await patient_client.post(
        PATIENT_VITALS_URL, json={"vital_type": "spo2", "value": 92, "unit": "%"}
    )
    assert resp.status_code == 201
    assert resp.json()["abnormal_flag"] is False

    resp = await patient_client.post(
        PATIENT_VITALS_URL,
        json={"vital_type": "bp_systolic", "value": 180, "unit": "mmHg"},
    )
    assert resp.status_code == 201
    assert resp.json()["abnormal_flag"] is False

    assert await patient_notifications(db, patient_user.id) == []


async def test_create_vital_normal_no_notification(
    patient_client: AsyncClient, patient_user: User, db: AsyncSession
):
    resp = await patient_client.post(
        PATIENT_VITALS_URL, json={"vital_type": "pulse", "value": 72, "unit": "bpm"}
    )
    assert resp.status_code == 201
    assert resp.json()["abnormal_flag"] is False
    assert await patient_notifications(db, patient_user.id) == []


async def test_create_vital_untracked_type_never_abnormal(
    patient_client: AsyncClient, patient_user: User, db: AsyncSession
):
    """weight_kg / temperature_c have no critical thresholds — never abnormal."""
    resp = await patient_client.post(
        PATIENT_VITALS_URL, json={"vital_type": "weight_kg", "value": 400, "unit": "kg"}
    )
    assert resp.status_code == 201
    assert resp.json()["abnormal_flag"] is False
    assert await patient_notifications(db, patient_user.id) == []


async def test_critical_vital_notifies_linked_clinic_doctors(
    patient_client: AsyncClient,
    patient_user: User,
    doctor_user: User,
    doctor_profile: Doctor,
    db: AsyncSession,
):
    """Doctors at clinics with an approved PatientClinicLink get alerted."""
    clinic = await make_clinic(db)
    await make_membership(db, clinic.id, doctor_user.id)
    await make_link(db, patient_user.id, clinic.id, linked_by=doctor_user.id)

    resp = await patient_client.post(
        PATIENT_VITALS_URL,
        json={"vital_type": "glucose_fasting", "value": 350, "unit": "mg/dL"},
    )
    assert resp.status_code == 201

    doctor_notes = await patient_notifications(db, doctor_user.id)
    assert len(doctor_notes) == 1
    assert doctor_notes[0].title == "Critical Vital Alert"
    assert doctor_notes[0].meta["patient_id"] == str(patient_user.id)
    assert doctor_notes[0].meta["vital_type"] == "glucose_fasting"
    assert patient_user.full_name in doctor_notes[0].message


async def test_critical_vital_does_not_notify_pending_link_clinic(
    patient_client: AsyncClient,
    patient_user: User,
    doctor_user: User,
    doctor_profile: Doctor,
    db: AsyncSession,
):
    """A pending (not yet approved) clinic link must not leak the alert."""
    clinic = await make_clinic(db)
    await make_membership(db, clinic.id, doctor_user.id)
    await make_link(
        db, patient_user.id, clinic.id, linked_by=doctor_user.id, consent_status="pending"
    )

    resp = await patient_client.post(
        PATIENT_VITALS_URL,
        json={"vital_type": "pulse", "value": 200, "unit": "bpm"},
    )
    assert resp.status_code == 201
    assert resp.json()["abnormal_flag"] is True

    # Only the patient's own notification exists.
    assert await patient_notifications(db, doctor_user.id) == []
    assert len(await patient_notifications(db, patient_user.id)) == 1


# ---------------------------------------------------------------------------
# GET /patients/vitals — patient self list
# ---------------------------------------------------------------------------


async def test_list_vitals_requires_auth(client: AsyncClient):
    resp = await client.get(PATIENT_VITALS_URL)
    assert resp.status_code == 401


async def test_list_vitals_rejects_doctor_role(doctor_client: AsyncClient):
    resp = await doctor_client.get(PATIENT_VITALS_URL)
    assert resp.status_code == 403


async def test_list_vitals_empty(patient_client: AsyncClient):
    resp = await patient_client.get(PATIENT_VITALS_URL)
    assert resp.status_code == 200
    assert resp.json() == {"data": [], "total": 0}


async def test_list_vitals_returns_only_own(
    patient_client: AsyncClient, patient_user: User, db: AsyncSession
):
    mine = await make_vital(db, patient_user.id, vital_type="pulse", value=70)
    other = await make_patient(db, "Other Patient")
    await make_vital(db, other.id, vital_type="pulse", value=140)

    resp = await patient_client.get(PATIENT_VITALS_URL)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["data"][0]["id"] == str(mine.id)
    assert body["data"][0]["patient_id"] == str(patient_user.id)


async def test_list_vitals_type_filter(
    patient_client: AsyncClient, patient_user: User, db: AsyncSession
):
    await make_vital(db, patient_user.id, vital_type="pulse", value=70)
    bp = await make_vital(db, patient_user.id, vital_type="bp_systolic", value=120, unit="mmHg")

    resp = await patient_client.get(PATIENT_VITALS_URL, params={"type": "bp_systolic"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["data"][0]["id"] == str(bp.id)


async def test_list_vitals_invalid_type_filter(patient_client: AsyncClient):
    resp = await patient_client.get(PATIENT_VITALS_URL, params={"type": "bogus"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_VITAL_TYPE"


async def test_list_vitals_days_window(
    patient_client: AsyncClient, patient_user: User, db: AsyncSession
):
    now = datetime.now(timezone.utc)
    recent = await make_vital(db, patient_user.id, recorded_at=now - timedelta(days=5))
    old = await make_vital(db, patient_user.id, recorded_at=now - timedelta(days=60))

    # Default window is 30 days — the 60-day-old reading is excluded.
    resp = await patient_client.get(PATIENT_VITALS_URL)
    ids = [v["id"] for v in resp.json()["data"]]
    assert str(recent.id) in ids
    assert str(old.id) not in ids

    # days=90 brings the old reading back (trends over a longer window).
    resp = await patient_client.get(PATIENT_VITALS_URL, params={"days": 90})
    ids = [v["id"] for v in resp.json()["data"]]
    assert {str(recent.id), str(old.id)} <= set(ids)


async def test_list_vitals_ordered_newest_first(
    patient_client: AsyncClient, patient_user: User, db: AsyncSession
):
    now = datetime.now(timezone.utc)
    oldest = await make_vital(db, patient_user.id, recorded_at=now - timedelta(days=10))
    newest = await make_vital(db, patient_user.id, recorded_at=now - timedelta(days=1))
    mid = await make_vital(db, patient_user.id, recorded_at=now - timedelta(days=5))

    resp = await patient_client.get(PATIENT_VITALS_URL)
    ids = [v["id"] for v in resp.json()["data"]]
    assert ids == [str(newest.id), str(mid.id), str(oldest.id)]


async def test_list_vitals_excludes_soft_deleted(
    patient_client: AsyncClient, patient_user: User, db: AsyncSession
):
    await make_vital(db, patient_user.id, deleted=True)
    alive = await make_vital(db, patient_user.id)

    resp = await patient_client.get(PATIENT_VITALS_URL)
    body = resp.json()
    assert body["total"] == 1
    assert body["data"][0]["id"] == str(alive.id)


async def test_list_vitals_limit(
    patient_client: AsyncClient, patient_user: User, db: AsyncSession
):
    for _ in range(5):
        await make_vital(db, patient_user.id)

    resp = await patient_client.get(PATIENT_VITALS_URL, params={"limit": 2})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 2
    # `total` mirrors the returned row count, not the underlying total.
    assert body["total"] == 2


async def test_list_vitals_abnormal_flag_surfaced(
    patient_client: AsyncClient, patient_user: User, db: AsyncSession
):
    """abnormal_flag is computed on read too, not only at write time."""
    await make_vital(db, patient_user.id, vital_type="pulse", value=170)  # > 150
    await make_vital(db, patient_user.id, vital_type="pulse", value=70)

    resp = await patient_client.get(PATIENT_VITALS_URL, params={"type": "pulse"})
    flags = {v["value"]: v["abnormal_flag"] for v in resp.json()["data"]}
    assert flags == {170.0: True, 70.0: False}


# ---------------------------------------------------------------------------
# GET /doctors/patients/{patient_id}/vitals — auth gates
# ---------------------------------------------------------------------------


async def test_doctor_vitals_requires_auth(client: AsyncClient):
    resp = await client.get(_doctor_vitals_url(uuid.uuid4()))
    assert resp.status_code == 401


async def test_doctor_vitals_rejects_patient_role(
    patient_client: AsyncClient, patient_user: User
):
    resp = await patient_client.get(_doctor_vitals_url(patient_user.id))
    assert resp.status_code == 403


async def test_doctor_vitals_rejects_unverified_doctor(client: AsyncClient, db: AsyncSession):
    """A doctor who hasn't completed verification gets ONBOARDING_INCOMPLETE."""
    user = User(
        keycloak_sub="unverified-doc",
        email="unverified@test.com",
        full_name="Unverified Doc",
        role="doctor",
    )
    db.add(user)
    await db.flush()
    db.add(Doctor(user_id=user.id, verified=False, onboarding_step="pending"))
    await db.commit()

    token = create_test_token(
        sub="unverified-doc", email=user.email, name=user.full_name, roles=["doctor"]
    )
    resp = await client.get(
        _doctor_vitals_url(uuid.uuid4()), headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "ONBOARDING_INCOMPLETE"


async def test_doctor_vitals_no_relationship_403(
    doctor_client: AsyncClient, db: AsyncSession
):
    stranger = await make_patient(db, "Stranger")
    resp = await doctor_client.get(_doctor_vitals_url(stranger.id))
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


# ---------------------------------------------------------------------------
# GET /doctors/patients/{patient_id}/vitals — access paths
# ---------------------------------------------------------------------------


async def test_doctor_vitals_via_authored_record(
    doctor_client: AsyncClient, doctor_profile: Doctor, db: AsyncSession
):
    """Doctor who authored a record for the patient can read vitals (no header)."""
    patient = await make_patient(db)
    await make_record(db, patient.id, doctor_profile.id)
    vital = await make_vital(db, patient.id, vital_type="spo2", value=97, unit="%")

    resp = await doctor_client.get(_doctor_vitals_url(patient.id))
    assert resp.status_code == 200
    body = resp.json()
    assert body["patient_id"] == str(patient.id)
    assert body["total"] == 1
    assert body["data"][0]["id"] == str(vital.id)


async def test_doctor_vitals_via_approved_clinic_link(
    doctor_client: AsyncClient, doctor_user: User, doctor_profile: Doctor, db: AsyncSession
):
    """Approved clinic link alone (no authored record) grants access."""
    patient = await make_patient(db)
    clinic = await make_clinic(db)
    await make_membership(db, clinic.id, doctor_user.id)
    await make_link(db, patient.id, clinic.id, linked_by=doctor_user.id)
    await make_vital(db, patient.id)

    resp = await doctor_client.get(_doctor_vitals_url(patient.id))
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


async def test_doctor_vitals_pending_link_denied(
    doctor_client: AsyncClient, doctor_user: User, doctor_profile: Doctor, db: AsyncSession
):
    """Pending consent does not count as a relationship."""
    patient = await make_patient(db)
    clinic = await make_clinic(db)
    await make_membership(db, clinic.id, doctor_user.id)
    await make_link(
        db, patient.id, clinic.id, linked_by=doctor_user.id, consent_status="pending"
    )

    resp = await doctor_client.get(_doctor_vitals_url(patient.id))
    assert resp.status_code == 403


async def test_doctor_vitals_inactive_membership_denied(
    doctor_client: AsyncClient, doctor_user: User, doctor_profile: Doctor, db: AsyncSession
):
    """Approved link + inactive membership is not a relationship."""
    patient = await make_patient(db)
    clinic = await make_clinic(db)
    await make_membership(db, clinic.id, doctor_user.id, is_active=False)
    await make_link(db, patient.id, clinic.id, linked_by=doctor_user.id)

    resp = await doctor_client.get(_doctor_vitals_url(patient.id))
    assert resp.status_code == 403


async def test_doctor_vitals_revoked_link_cutoff_no_header(
    doctor_client: AsyncClient, doctor_user: User, doctor_profile: Doctor, db: AsyncSession
):
    """Without X-Clinic-Id, a revoked-only link still applies the revoked_at
    cutoff: vitals recorded after revocation must not leak."""
    now = datetime.now(timezone.utc)
    revoked_at = now - timedelta(days=10)

    patient = await make_patient(db)
    clinic = await make_clinic(db)
    await make_membership(db, clinic.id, doctor_user.id)
    await make_link(
        db, patient.id, clinic.id, linked_by=doctor_user.id,
        consent_status="revoked", revoked_at=revoked_at,
    )
    before_revoke = await make_vital(
        db, patient.id, recorded_at=revoked_at - timedelta(days=5)
    )
    after_revoke = await make_vital(
        db, patient.id, recorded_at=revoked_at + timedelta(days=5)
    )

    resp = await doctor_client.get(_doctor_vitals_url(patient.id))
    assert resp.status_code == 200
    ids = [v["id"] for v in resp.json()["data"]]
    assert str(before_revoke.id) in ids
    assert str(after_revoke.id) not in ids


async def test_doctor_vitals_revoked_without_timestamp_denied(
    doctor_client: AsyncClient, doctor_user: User, doctor_profile: Doctor, db: AsyncSession
):
    """A revoked link with revoked_at=NULL is treated as full denial."""
    patient = await make_patient(db)
    clinic = await make_clinic(db)
    await make_membership(db, clinic.id, doctor_user.id)
    await make_link(
        db, patient.id, clinic.id, linked_by=doctor_user.id,
        consent_status="revoked", revoked_at=None,
    )

    resp = await doctor_client.get(_doctor_vitals_url(patient.id))
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "ACCESS_REVOKED"


# ---------------------------------------------------------------------------
# GET /doctors/patients/{patient_id}/vitals — X-Clinic-Id scoping
# ---------------------------------------------------------------------------


async def test_doctor_vitals_clinic_header_approved_link(
    doctor_client: AsyncClient, doctor_user: User, doctor_profile: Doctor, db: AsyncSession
):
    patient = await make_patient(db)
    clinic = await make_clinic(db)
    await make_membership(db, clinic.id, doctor_user.id)
    await make_link(db, patient.id, clinic.id, linked_by=doctor_user.id)
    await make_vital(db, patient.id)

    resp = await doctor_client.get(
        _doctor_vitals_url(patient.id), headers={"X-Clinic-Id": str(clinic.id)}
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


async def test_doctor_vitals_clinic_header_no_link(
    doctor_client: AsyncClient, doctor_user: User, doctor_profile: Doctor, db: AsyncSession
):
    """Clinic member, but the patient never linked to that clinic → 403."""
    patient = await make_patient(db)
    clinic = await make_clinic(db)
    await make_membership(db, clinic.id, doctor_user.id)

    resp = await doctor_client.get(
        _doctor_vitals_url(patient.id), headers={"X-Clinic-Id": str(clinic.id)}
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "CONSENT_REQUIRED"


async def test_doctor_vitals_clinic_header_pending_link(
    doctor_client: AsyncClient, doctor_user: User, doctor_profile: Doctor, db: AsyncSession
):
    patient = await make_patient(db)
    clinic = await make_clinic(db)
    await make_membership(db, clinic.id, doctor_user.id)
    await make_link(
        db, patient.id, clinic.id, linked_by=doctor_user.id, consent_status="pending"
    )

    resp = await doctor_client.get(
        _doctor_vitals_url(patient.id), headers={"X-Clinic-Id": str(clinic.id)}
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "CONSENT_REQUIRED"


async def test_doctor_vitals_clinic_header_revoked_cutoff(
    doctor_client: AsyncClient, doctor_user: User, doctor_profile: Doctor, db: AsyncSession
):
    """With X-Clinic-Id on a revoked link, only pre-revocation vitals show."""
    now = datetime.now(timezone.utc)
    revoked_at = now - timedelta(days=3)

    patient = await make_patient(db)
    clinic = await make_clinic(db)
    await make_membership(db, clinic.id, doctor_user.id)
    await make_link(
        db, patient.id, clinic.id, linked_by=doctor_user.id,
        consent_status="revoked", revoked_at=revoked_at,
    )
    before = await make_vital(db, patient.id, recorded_at=revoked_at - timedelta(days=1))
    after = await make_vital(db, patient.id, recorded_at=revoked_at + timedelta(days=1))

    resp = await doctor_client.get(
        _doctor_vitals_url(patient.id), headers={"X-Clinic-Id": str(clinic.id)}
    )
    assert resp.status_code == 200
    ids = [v["id"] for v in resp.json()["data"]]
    assert str(before.id) in ids
    assert str(after.id) not in ids


async def test_doctor_vitals_clinic_header_non_member(
    doctor_client: AsyncClient, doctor_user: User, doctor_profile: Doctor, db: AsyncSession
):
    """Doctor isn't a member of the named clinic → NOT_CLINIC_MEMBER."""
    patient = await make_patient(db)
    clinic = await make_clinic(db)
    await make_link(db, patient.id, clinic.id, linked_by=doctor_user.id)

    resp = await doctor_client.get(
        _doctor_vitals_url(patient.id), headers={"X-Clinic-Id": str(clinic.id)}
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "NOT_CLINIC_MEMBER"


async def test_doctor_vitals_malformed_clinic_header(doctor_client: AsyncClient):
    resp = await doctor_client.get(
        _doctor_vitals_url(uuid.uuid4()), headers={"X-Clinic-Id": "not-a-uuid"}
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_CLINIC_ID"


# ---------------------------------------------------------------------------
# GET /doctors/patients/{patient_id}/vitals — filters
# ---------------------------------------------------------------------------


async def test_doctor_vitals_type_filter_and_window(
    doctor_client: AsyncClient, doctor_profile: Doctor, db: AsyncSession
):
    patient = await make_patient(db)
    await make_record(db, patient.id, doctor_profile.id)
    now = datetime.now(timezone.utc)
    recent_pulse = await make_vital(db, patient.id, vital_type="pulse", value=70)
    old_pulse = await make_vital(
        db, patient.id, vital_type="pulse", value=80,
        recorded_at=now - timedelta(days=120),
    )
    await make_vital(db, patient.id, vital_type="spo2", value=98, unit="%")

    # type filter
    resp = await doctor_client.get(
        _doctor_vitals_url(patient.id), params={"type": "pulse"}
    )
    assert resp.status_code == 200
    ids = {v["id"] for v in resp.json()["data"]}
    assert ids == {str(recent_pulse.id)}  # doctor default window is 90 days

    # widen the window
    resp = await doctor_client.get(
        _doctor_vitals_url(patient.id), params={"type": "pulse", "days": 180}
    )
    ids = {v["id"] for v in resp.json()["data"]}
    assert ids == {str(recent_pulse.id), str(old_pulse.id)}


async def test_doctor_vitals_invalid_type_filter(
    doctor_client: AsyncClient, doctor_profile: Doctor, db: AsyncSession
):
    patient = await make_patient(db)
    await make_record(db, patient.id, doctor_profile.id)
    resp = await doctor_client.get(
        _doctor_vitals_url(patient.id), params={"type": "bogus"}
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_VITAL_TYPE"


async def test_doctor_vitals_excludes_soft_deleted(
    doctor_client: AsyncClient, doctor_profile: Doctor, db: AsyncSession
):
    patient = await make_patient(db)
    await make_record(db, patient.id, doctor_profile.id)
    await make_vital(db, patient.id, deleted=True)
    alive = await make_vital(db, patient.id)

    resp = await doctor_client.get(_doctor_vitals_url(patient.id))
    assert resp.status_code == 200
    body = resp.json()
    assert [v["id"] for v in body["data"]] == [str(alive.id)]
