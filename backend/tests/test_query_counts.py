"""Query-count regression tests for hot endpoints (R12 N+1 audit).

A ``QueryCounter`` listens to ``before_cursor_execute`` on the test engines
and counts SQL statements issued while a single request is in flight. Each
test seeds a realistic list (~15 rows with relations) and asserts the
request stays under a fixed statement budget — so a future N+1 regression
(one query per row) trips the limit well before production does.

Thresholds were measured against the fixed implementation with 15 seeded
rows; each carries ~2x headroom over the observed count. The interesting
invariant is that counts are *constant* in the row count, not the exact
number — where practical we also assert a 5-row vs 15-row delta of zero.
"""
import contextlib
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment
from app.models.billing import Billing, BillingItem
from app.models.clinic import Clinic, ClinicBranch, ClinicMembership
from app.models.doctor import Doctor
from app.models.medical_record import MedicalRecord
from app.models.notification import Notification, NotificationType
from app.models.queue import QueueEntry
from app.models.user import User
from tests.conftest import create_test_token, engine, medicine_engine

N_ROWS = 15


class QueryCounter:
    """Counts SQL statements on the main + medicine test engines."""

    def __init__(self) -> None:
        self.main = 0
        self.medicine = 0

    def _main(self, conn, cursor, statement, parameters, context, executemany):
        self.main += 1

    def _medicine(self, conn, cursor, statement, parameters, context, executemany):
        self.medicine += 1

    @property
    def total(self) -> int:
        return self.main + self.medicine


@contextlib.contextmanager
def count_queries():
    """Count statements on both test engines for the wrapped block only —
    fixture setup/teardown (create_all/drop_all) runs outside the window."""
    counter = QueryCounter()
    event.listen(engine.sync_engine, "before_cursor_execute", counter._main)
    event.listen(medicine_engine.sync_engine, "before_cursor_execute", counter._medicine)
    try:
        yield counter
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", counter._main)
        event.remove(medicine_engine.sync_engine, "before_cursor_execute", counter._medicine)
        # Logged on teardown so `-s` output shows the observed counts even
        # when the assertion passes.
        print(f"\n[query-count] main={counter.main} medicine={counter.medicine}")


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

async def _make_patient(db: AsyncSession, i: int) -> User:
    u = User(
        keycloak_sub=f"qc-patient-{i}-{uuid.uuid4().hex[:8]}",
        email=f"qc-patient-{i}@test.com",
        full_name=f"QC Patient {i:02d}",
        role="patient",
    )
    db.add(u)
    return u


@pytest_asyncio.fixture
async def clinic_env(db: AsyncSession, doctor_user: User, doctor_profile: Doctor):
    """Clinic + branch + doctor membership + 15 patients with appointments,
    queue entries, records, bills and notifications."""
    clinic = Clinic(name="QC Clinic", city="Pune", is_active=True)
    db.add(clinic)
    await db.flush()
    branch = ClinicBranch(clinic_id=clinic.id, name="Main Branch")
    db.add(branch)
    db.add(
        ClinicMembership(
            clinic_id=clinic.id, user_id=doctor_user.id, role="doctor", is_active=True
        )
    )
    await db.flush()

    now = datetime.now(tz=timezone.utc)
    patients: list[User] = []
    for i in range(N_ROWS):
        patient = await _make_patient(db, i)
        db.add(patient)
        await db.flush()
        patients.append(patient)
        db.add(
            Appointment(
                patient_id=patient.id,
                doctor_id=doctor_profile.id,
                clinic_id=clinic.id,
                branch_id=branch.id,
                scheduled_at=now + timedelta(minutes=30 * (i + 1)),
                duration_minutes=15,
                type="in-person",
                status="scheduled",
                created_by=doctor_user.id,
            )
        )
        db.add(
            QueueEntry(
                clinic_id=clinic.id,
                branch_id=branch.id,
                patient_id=patient.id,
                doctor_id=doctor_profile.id,
                queue_number=i + 1,
                status="waiting",
            )
        )
        db.add(
            MedicalRecord(
                patient_id=patient.id,
                doctor_id=doctor_profile.id,
                record_type="opd_note",
                title=f"QC record {i}",
                description="query-count seed",
            )
        )
        db.add(
            Billing(
                patient_id=patient.id,
                clinic_id=clinic.id,
                amount=100 + i,
                status="pending",
                items=[
                    BillingItem(description="Consult", quantity=1, unit_amount=100 + i, amount=100 + i),
                ],
            )
        )
        db.add(
            Notification(
                user_id=patient.id,
                type=NotificationType.SYSTEM,
                title=f"QC notification {i}",
                message="seed",
            )
        )
    await db.commit()
    return {
        "clinic": clinic,
        "branch": branch,
        "patients": patients,
        "doctor": doctor_profile,
        "doctor_user": doctor_user,
    }


def _auth(user: User, roles: list[str] | None = None) -> dict[str, str]:
    return {
        "Authorization": "Bearer "
        + create_test_token(
            sub=user.keycloak_sub,
            email=user.email,
            name=user.full_name,
            roles=roles or [user.role],
        )
    }


# ---------------------------------------------------------------------------
# List endpoints — count must be constant in the number of rows
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_appointments_list_doctor_query_count(client, db, doctor_user, doctor_profile, clinic_env):
    with count_queries() as qc:
        resp = await client.get("/api/v1/appointments", headers=_auth(doctor_user, ["doctor"]))
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["data"]) == N_ROWS
    # auth + doctor profile + count + page + 4 batched name lookups
    assert qc.main <= 10, f"doctor appointments list ran {qc.main} queries"


@pytest.mark.asyncio
async def test_appointments_list_patient_query_count(client, db, patient_user, doctor_profile, clinic_env):
    # Give the patient 15 appointments of their own.
    now = datetime.now(tz=timezone.utc)
    for i in range(N_ROWS):
        db.add(
            Appointment(
                patient_id=patient_user.id,
                doctor_id=doctor_profile.id,
                clinic_id=clinic_env["clinic"].id,
                branch_id=clinic_env["branch"].id,
                scheduled_at=now + timedelta(minutes=30 * (i + 1)),
                duration_minutes=15,
                type="in-person",
                status="scheduled",
                created_by=patient_user.id,
            )
        )
    await db.commit()

    with count_queries() as qc:
        resp = await client.get("/api/v1/appointments", headers=_auth(patient_user))
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["data"]) == N_ROWS
    assert qc.main <= 10, f"patient appointments list ran {qc.main} queries"


@pytest.mark.asyncio
async def test_queue_list_query_count(client, db, doctor_user, clinic_env):
    clinic = clinic_env["clinic"]
    headers = {**_auth(doctor_user, ["doctor"]), "X-Clinic-Id": str(clinic.id)}
    with count_queries() as qc:
        resp = await client.get("/api/v1/queue", headers=headers)
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["data"]) == N_ROWS
    # auth + membership + page + batched patient names + batched doctor names
    assert qc.main <= 8, f"queue list ran {qc.main} queries"


@pytest.mark.asyncio
async def test_notifications_list_query_count(client, db, patient_user, clinic_env):
    for i in range(N_ROWS):
        db.add(
            Notification(
                user_id=patient_user.id,
                type=NotificationType.SYSTEM,
                title=f"Note {i}",
                message="seed",
            )
        )
    await db.commit()

    with count_queries() as qc:
        resp = await client.get("/api/v1/notifications", headers=_auth(patient_user))
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["notifications"]) == N_ROWS
    # auth + total count + unread count + page
    assert qc.main <= 6, f"notifications list ran {qc.main} queries"


@pytest.mark.asyncio
async def test_patient_records_query_count(client, db, patient_user, doctor_profile, clinic_env):
    for i in range(N_ROWS):
        db.add(
            MedicalRecord(
                patient_id=patient_user.id,
                doctor_id=doctor_profile.id,
                record_type="opd_note",
                title=f"QC patient record {i}",
            )
        )
    await db.commit()

    with count_queries() as qc:
        resp = await client.get("/api/v1/patients/records", headers=_auth(patient_user))
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["data"]) == N_ROWS
    # auth + single joined timeline query (doctor name + prescription via JOINs)
    assert qc.main <= 5, f"patient records list ran {qc.main} queries"


@pytest.mark.asyncio
async def test_doctor_patients_query_count(client, db, doctor_user, doctor_profile, clinic_env):
    with count_queries() as qc:
        resp = await client.get(
            "/api/v1/doctors/patients", headers=_auth(doctor_user, ["doctor"])
        )
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["data"]) == N_ROWS
    # auth + doctor profile + single accessible-patients query
    assert qc.main <= 6, f"doctor patients list ran {qc.main} queries"


@pytest.mark.asyncio
async def test_billing_list_query_count(client, db, admin_user, clinic_env):
    with count_queries() as qc:
        resp = await client.get("/api/v1/billing", headers=_auth(admin_user, ["admin"]))
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["data"]) == N_ROWS
    # auth + page (+ selectin items) + batched patient names + clinic names
    assert qc.main <= 8, f"billing list ran {qc.main} queries"


@pytest.mark.asyncio
async def test_search_records_query_count(client, db, admin_user, clinic_env):
    with count_queries() as qc:
        resp = await client.get(
            "/api/v1/search", params={"q": "QC record", "type": "record"},
            headers=_auth(admin_user, ["admin"]),
        )
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["results"]) == N_ROWS
    # auth + count + page (patient name joined inline)
    assert qc.main <= 5, f"record search ran {qc.main} queries"


# ---------------------------------------------------------------------------
# GET /api/v1/uploads/{key} — doctor auth path previously ran
# _doctor_has_patient_relationship (up to 3 queries) per referencing record.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_serve_denied_query_count(client, db, doctor_user, doctor_profile, clinic_env):
    """A doctor with NO relationship to the referencing records' patients gets
    403 — but the authorization scan must be a constant number of queries,
    not ~3 per record."""
    key = f"{uuid.uuid4()}/scan.pdf"
    other_doctor_user = User(
        keycloak_sub=f"qc-other-doc-{uuid.uuid4().hex[:8]}",
        email="other-doc@test.com",
        full_name="Other Doc",
        role="doctor",
    )
    db.add(other_doctor_user)
    await db.flush()
    other_doctor = Doctor(user_id=other_doctor_user.id)
    db.add(other_doctor)
    await db.flush()
    # 8 records (fresh patients the requesting doctor has NO relationship
    # with — clinic_env patients are already linked via authored records)
    # all referencing the same object key; no clinic links.
    for i in range(8):
        stranger = await _make_patient(db, 100 + i)
        db.add(stranger)
        await db.flush()
        db.add(
            MedicalRecord(
                patient_id=stranger.id,
                doctor_id=other_doctor.id,
                record_type="lab_report",
                title=f"scan {i}",
                document_url=key,
            )
        )
    await db.commit()

    with count_queries() as qc:
        resp = await client.get(
            f"/api/v1/uploads/{key}", headers=_auth(doctor_user, ["doctor"])
        )
    assert resp.status_code == 403, resp.text
    # auth + license-doc check + records-by-key + doctor profile +
    # constant-size batched relationship checks (was ~3 x 8 = 24 before fix)
    assert qc.main <= 12, f"upload auth scan ran {qc.main} queries"


# ---------------------------------------------------------------------------
# POST /api/v1/doctors/prescriptions — the clinical safety gate resolved each
# medicine item with up to ~4 medicine-DB queries (brand by id / exact name /
# prefix + salts + salt_id get). Now batched: ~5 queries for any item count.
# ---------------------------------------------------------------------------


async def _seed_catalog(medicine_db: AsyncSession, n_brands: int = 8):
    """N brands on one manufacturer, each composed of one distinct salt."""
    from app.models.medicine.commercial import Brand, BrandComposition, Manufacturer
    from app.models.medicine.salts import Salt, SaltStrength

    mfr = Manufacturer(manufacturer_name="QC Pharma")
    medicine_db.add(mfr)
    await medicine_db.flush()
    brands = []
    for i in range(n_brands):
        salt = Salt(salt_name=f"QCSalt{i}")
        medicine_db.add(salt)
        await medicine_db.flush()
        strength = SaltStrength(
            salt_id=salt.salt_id, strength_value=100 + i, strength_unit="mg"
        )
        medicine_db.add(strength)
        await medicine_db.flush()
        brand = Brand(
            brand_name=f"QCBrand{i}", manufacturer_id=mfr.manufacturer_id
        )
        medicine_db.add(brand)
        await medicine_db.flush()
        medicine_db.add(
            BrandComposition(
                brand_id=brand.brand_id,
                salt_strength_id=strength.salt_strength_id,
                sequence=1,
            )
        )
        brands.append((brand, salt))
    await medicine_db.commit()
    return brands


@pytest.mark.asyncio
async def test_resolve_items_batched(medicine_db):
    """Service-level: resolve_items must run a constant number of queries
    regardless of item count (was ~3-4 per item)."""
    from app.services.clinical_safety_service import resolve_items

    brands = await _seed_catalog(medicine_db, n_brands=8)
    medicines = [
        {
            "brand_name": brand.brand_name,
            "brand_id": str(brand.brand_id),
            "salt_id": str(salt.salt_id),
            "dose": "1 tab",
            "frequency": "BD",
            "duration": "7 days",
        }
        for brand, salt in brands
    ]
    # One unresolvable item exercises the prefix-match fallback path.
    medicines.append(
        {"brand_name": "NoSuchBrandXYZ", "dose": "1", "frequency": "OD", "duration": "1 day"}
    )

    with count_queries() as qc:
        resolved = await resolve_items(medicine_db, medicines)
    assert len(resolved) == len(medicines)
    assert all(r.brand is not None for r in resolved[:-1])
    assert resolved[-1].brand is None and not resolved[-1].salts
    # brand_id batch + brand_name batch + prefix fallback + salts batch
    # + salt_id batch — constant, independent of the 9 items.
    assert qc.medicine <= 8, f"resolve_items ran {qc.medicine} medicine-DB queries"


@pytest.mark.asyncio
async def test_create_prescription_query_count(
    client, db, medicine_db, doctor_user, doctor_profile, clinic_env
):
    """End-to-end: POST /doctors/prescriptions with 8 medicine items."""
    brands = await _seed_catalog(medicine_db, n_brands=8)
    patient = clinic_env["patients"][0]
    # Doctor↔patient relationship via an authored record already exists
    # (clinic_env seeds one per patient).
    payload = {
        "patient_id": str(patient.id),
        "medicines": [
            {
                "brand_name": brand.brand_name,
                "brand_id": str(brand.brand_id),
                "salt_id": str(salt.salt_id),
                "dose": "1 tab",
                "frequency": "BD",
                "duration": "7 days",
            }
            for brand, salt in brands
        ],
        "diagnosis": "QC diagnosis",
    }
    with count_queries() as qc:
        resp = await client.post(
            "/api/v1/doctors/prescriptions",
            json=payload,
            headers=_auth(doctor_user, ["doctor"]),
        )
    assert resp.status_code == 201, resp.text
    # Medicine DB: ~4 batched resolution + interactions + active-therapy
    # brand/salt lookups + contraindications + audit insert.
    assert qc.medicine <= 12, f"prescription create ran {qc.medicine} medicine-DB queries"
    assert qc.main <= 15, f"prescription create ran {qc.main} main-DB queries"


# ---------------------------------------------------------------------------
# Scaling invariant: list endpoints must NOT grow with row count.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notifications_list_scales_flat(client, db, patient_user):
    """5 rows vs 15 rows must issue the same number of statements."""
    from app import dependencies as _deps

    counts = []
    for n in (5, 15):
        # wipe prior seeds
        await db.execute(Notification.__table__.delete())
        for i in range(n):
            db.add(
                Notification(
                    user_id=patient_user.id,
                    type=NotificationType.SYSTEM,
                    title=f"n{i}",
                    message="seed",
                )
            )
        await db.commit()
        # _user_cache has a 30s TTL and persists across requests inside a
        # test — clear it so both iterations pay the same auth lookup.
        _deps._user_cache.clear()
        with count_queries() as qc:
            resp = await client.get("/api/v1/notifications", headers=_auth(patient_user))
        assert resp.status_code == 200
        counts.append(qc.main)
    assert counts[0] == counts[1], f"query count grew with rows: {counts}"
