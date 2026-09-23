"""Tests for doctor lab orders — app/routers/lab_orders.py.

Endpoints under test:
  POST  /api/v1/lab-orders                    — create (verified doctor only,
                                                relationship required)
  GET   /api/v1/lab-orders                    — doctor list (patient_id/status)
  GET   /api/v1/lab-orders/mine               — patient list (own only)
  PATCH /api/v1/lab-orders/{id}/status        — ordered → completed | cancelled
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.doctor import Doctor
from app.models.medical_record import MedicalRecord
from app.models.user import User
from tests.conftest import create_test_token, grant_doctor_patient_relationship

pytestmark = pytest.mark.asyncio

URL = "/api/v1/lab-orders"


# ---------------------------------------------------------------------------
# Helpers
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


async def make_doctor(
    db: AsyncSession, name: str = "Other Doctor"
) -> tuple[User, Doctor]:
    user = User(
        keycloak_sub=f"sub-{uuid.uuid4()}",
        email=f"{uuid.uuid4().hex[:8]}@test.com",
        full_name=name,
        role="doctor",
    )
    db.add(user)
    await db.flush()
    doctor = Doctor(
        id=uuid.uuid4(),
        user_id=user.id,
        specialization="Pathologist",
        verified=True,
        onboarding_step="completed",
    )
    db.add(doctor)
    await db.commit()
    await db.refresh(user)
    await db.refresh(doctor)
    return user, doctor


def auth_header(user: User) -> dict[str, str]:
    token = create_test_token(
        sub=user.keycloak_sub,
        email=user.email,
        name=user.full_name,
        roles=[user.role],
    )
    return {"Authorization": f"Bearer {token}"}


async def create_order(
    doctor_client: AsyncClient, patient_id: uuid.UUID, test_name: str = "CBC"
) -> dict:
    res = await doctor_client.post(
        URL, json={"patient_id": str(patient_id), "test_name": test_name}
    )
    assert res.status_code == 201, res.text
    return res.json()


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


async def test_create_lab_order(
    doctor_client: AsyncClient, patient_user: User, db: AsyncSession
):
    await grant_doctor_patient_relationship(db, "doctor-123", patient_user.id)
    res = await doctor_client.post(
        URL,
        json={
            "patient_id": str(patient_user.id),
            "test_name": "Lipid Profile",
            "notes": "Fasting required",
        },
    )
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["status"] == "ordered"
    assert data["test_name"] == "Lipid Profile"
    assert data["notes"] == "Fasting required"
    assert data["patient_id"] == str(patient_user.id)
    assert data["result_record_id"] is None


async def test_create_requires_patient_relationship(
    doctor_client: AsyncClient, db: AsyncSession
):
    stranger = await make_patient(db)
    res = await doctor_client.post(
        URL, json={"patient_id": str(stranger.id), "test_name": "CBC"}
    )
    assert res.status_code == 403


async def test_create_patient_not_found(doctor_client: AsyncClient):
    res = await doctor_client.post(
        URL, json={"patient_id": str(uuid.uuid4()), "test_name": "CBC"}
    )
    assert res.status_code == 404


async def test_create_patient_forbidden(
    patient_client: AsyncClient, patient_user: User
):
    res = await patient_client.post(
        URL, json={"patient_id": str(patient_user.id), "test_name": "CBC"}
    )
    assert res.status_code == 403


async def test_create_unauthenticated(client: AsyncClient):
    res = await client.post(
        URL, json={"patient_id": str(uuid.uuid4()), "test_name": "CBC"}
    )
    assert res.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Doctor list
# ---------------------------------------------------------------------------


async def test_doctor_list_filters(
    doctor_client: AsyncClient, patient_user: User, db: AsyncSession
):
    await grant_doctor_patient_relationship(db, "doctor-123", patient_user.id)
    other = await make_patient(db)
    await grant_doctor_patient_relationship(db, "doctor-123", other.id)

    order_a = await create_order(doctor_client, patient_user.id, "CBC")
    order_b = await create_order(doctor_client, other.id, "TSH")

    res = await doctor_client.get(URL)
    assert res.status_code == 200, res.text
    ids = {o["id"] for o in res.json()["data"]}
    assert {order_a["id"], order_b["id"]} <= ids

    res = await doctor_client.get(URL, params={"patient_id": str(patient_user.id)})
    assert res.status_code == 200
    data = res.json()["data"]
    assert [o["id"] for o in data] == [order_a["id"]]

    res = await doctor_client.get(URL, params={"status": "completed"})
    assert res.status_code == 200
    assert res.json()["data"] == []

    res = await doctor_client.get(URL, params={"status": "ordered"})
    assert res.status_code == 200
    assert {o["id"] for o in res.json()["data"]} >= {order_a["id"], order_b["id"]}

    res = await doctor_client.get(URL, params={"status": "bogus"})
    assert res.status_code == 400


async def test_doctor_list_excludes_other_doctors(
    doctor_client: AsyncClient, patient_user: User, db: AsyncSession, client: AsyncClient
):
    await grant_doctor_patient_relationship(db, "doctor-123", patient_user.id)
    own = await create_order(doctor_client, patient_user.id, "CBC")

    # A second doctor with their own relationship to the patient must not see
    # the first doctor's orders.
    other_user, other_doctor = await make_doctor(db)
    db.add(
        MedicalRecord(
            patient_id=patient_user.id,
            doctor_id=other_doctor.id,
            record_type="opd_note",
            title="seed",
        )
    )
    await db.commit()
    res = await client.get(URL, headers=auth_header(other_user))
    assert res.status_code == 200, res.text
    assert own["id"] not in {o["id"] for o in res.json()["data"]}


# ---------------------------------------------------------------------------
# Patient list (own only)
# ---------------------------------------------------------------------------


async def test_patient_list_own_only(
    doctor_user: User,
    doctor_profile: Doctor,
    patient_user: User,
    db: AsyncSession,
    client: AsyncClient,
):
    # NB: doctor_client/patient_client share the same client — a single
    # Authorization header — so this test sets headers explicitly per call.
    doctor_headers = auth_header(doctor_user)
    await grant_doctor_patient_relationship(db, "doctor-123", patient_user.id)
    other = await make_patient(db)
    await grant_doctor_patient_relationship(db, "doctor-123", other.id)

    res = await client.post(
        URL,
        json={"patient_id": str(patient_user.id), "test_name": "HbA1c"},
        headers=doctor_headers,
    )
    assert res.status_code == 201, res.text
    own_order = res.json()
    res = await client.post(
        URL,
        json={"patient_id": str(other.id), "test_name": "Secret Test"},
        headers=doctor_headers,
    )
    assert res.status_code == 201, res.text

    res = await client.get(f"{URL}/mine", headers=auth_header(patient_user))
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert [o["id"] for o in data] == [own_order["id"]]
    assert data[0]["patient_id"] == str(patient_user.id)
    assert data[0]["doctor_name"] == "Doctor User"

    # The other patient sees only their own orders.
    res = await client.get(f"{URL}/mine", headers=auth_header(other))
    assert res.status_code == 200
    ids = {o["id"] for o in res.json()["data"]}
    assert own_order["id"] not in ids
    assert len(ids) == 1


async def test_patient_list_doctor_forbidden(doctor_client: AsyncClient):
    res = await doctor_client.get(f"{URL}/mine")
    assert res.status_code == 403


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------


async def test_complete_order_with_result_record(
    doctor_client: AsyncClient, patient_user: User, db: AsyncSession, doctor_profile: Doctor
):
    await grant_doctor_patient_relationship(db, "doctor-123", patient_user.id)
    order = await create_order(doctor_client, patient_user.id, "CBC")

    record = MedicalRecord(
        patient_id=patient_user.id,
        doctor_id=doctor_profile.id,
        record_type="lab_report",
        title="CBC report",
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    res = await doctor_client.patch(
        f"{URL}/{order['id']}/status",
        json={"status": "completed", "result_record_id": str(record.id)},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == "completed"
    assert data["result_record_id"] == str(record.id)


async def test_cancel_order(
    doctor_client: AsyncClient, patient_user: User, db: AsyncSession
):
    await grant_doctor_patient_relationship(db, "doctor-123", patient_user.id)
    order = await create_order(doctor_client, patient_user.id, "X-Ray")
    res = await doctor_client.patch(
        f"{URL}/{order['id']}/status", json={"status": "cancelled"}
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "cancelled"


async def test_invalid_transitions(
    doctor_client: AsyncClient, patient_user: User, db: AsyncSession
):
    await grant_doctor_patient_relationship(db, "doctor-123", patient_user.id)
    order = await create_order(doctor_client, patient_user.id, "CBC")

    # completed → cancelled is not allowed (terminal state)
    res = await doctor_client.patch(
        f"{URL}/{order['id']}/status", json={"status": "completed"}
    )
    assert res.status_code == 200
    res = await doctor_client.patch(
        f"{URL}/{order['id']}/status", json={"status": "cancelled"}
    )
    assert res.status_code == 422

    # 'ordered' is not a valid target status (schema-level rejection)
    other_order = await create_order(doctor_client, patient_user.id, "TSH")
    res = await doctor_client.patch(
        f"{URL}/{other_order['id']}/status", json={"status": "ordered"}
    )
    assert res.status_code == 422

    # result_record_id on cancellation is rejected
    res = await doctor_client.patch(
        f"{URL}/{other_order['id']}/status",
        json={"status": "cancelled", "result_record_id": str(uuid.uuid4())},
    )
    assert res.status_code == 400


async def test_result_record_must_belong_to_order_patient(
    doctor_client: AsyncClient, patient_user: User, db: AsyncSession, doctor_profile: Doctor
):
    await grant_doctor_patient_relationship(db, "doctor-123", patient_user.id)
    other = await make_patient(db)
    order = await create_order(doctor_client, patient_user.id, "CBC")

    record = MedicalRecord(
        patient_id=other.id,
        doctor_id=doctor_profile.id,
        record_type="lab_report",
        title="Other patient report",
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    res = await doctor_client.patch(
        f"{URL}/{order['id']}/status",
        json={"status": "completed", "result_record_id": str(record.id)},
    )
    assert res.status_code == 400

    res = await doctor_client.patch(
        f"{URL}/{order['id']}/status",
        json={"status": "completed", "result_record_id": str(uuid.uuid4())},
    )
    assert res.status_code == 404


async def test_status_update_scoped_to_ordering_doctor(
    doctor_client: AsyncClient, patient_user: User, db: AsyncSession, client: AsyncClient
):
    await grant_doctor_patient_relationship(db, "doctor-123", patient_user.id)
    order = await create_order(doctor_client, patient_user.id, "CBC")

    other_user, _ = await make_doctor(db)
    res = await client.patch(
        f"{URL}/{order['id']}/status",
        json={"status": "cancelled"},
        headers=auth_header(other_user),
    )
    assert res.status_code == 404

    # Patients cannot transition orders either.
    res = await client.patch(
        f"{URL}/{order['id']}/status",
        json={"status": "cancelled"},
        headers=auth_header(patient_user),
    )
    assert res.status_code == 403
