import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.clinic import Clinic, ClinicMembership
from app.models.notification import Notification
from app.models.patient_link import PatientClinicLink
from app.models.prescription import Prescription
from tests.conftest import create_test_token, verify_provisioned_doctor


async def _provision_user(client: AsyncClient, *, email: str, name: str, roles: list[str]) -> tuple[str, str]:
    """Hit /auth/me to auto-provision a user; return (token, user_id)."""
    sub = str(uuid.uuid4())
    token = create_test_token(sub=sub, email=email, name=name, roles=roles)
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    return token, me.json()["id"]


async def _make_clinic(db, *, user_id: str, role: str = "owner", name: str = "Test Clinic") -> Clinic:
    clinic = Clinic(name=name)
    db.add(clinic)
    await db.flush()
    db.add(
        ClinicMembership(
            clinic_id=clinic.id,
            user_id=uuid.UUID(str(user_id)),
            role=role,
        )
    )
    await db.commit()
    await db.refresh(clinic)
    return clinic


def _auth(token: str, clinic_id: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if clinic_id:
        headers["X-Clinic-Id"] = str(clinic_id)
    return headers


async def setup_clinic_scenario(client: AsyncClient, db):
    """Patient + verified doctor + clinic membership + clinic-scoped prescription.

    Returns (patient_token, patient_id, doctor_token, doctor_user_id, clinic, rx_id).
    """
    patient_token, patient_id = await _provision_user(
        client, email="patient@refill.com", name="Refill Patient", roles=["patient"]
    )
    doctor_sub = str(uuid.uuid4())
    doctor_token = create_test_token(
        sub=doctor_sub, email="doctor@refill.com", name="Dr. Refill", roles=["doctor"]
    )
    me = await client.get("/api/v1/auth/me", headers=_auth(doctor_token))
    doctor_user_id = me.json()["id"]
    await verify_provisioned_doctor(db, doctor_sub)

    clinic = await _make_clinic(db, user_id=doctor_user_id)

    # Clinic-scoped writes require an approved patient→clinic consent link.
    db.add(
        PatientClinicLink(
            patient_id=uuid.UUID(patient_id),
            clinic_id=clinic.id,
            linked_by=uuid.UUID(doctor_user_id),
            consent_status="approved",
        )
    )
    await db.commit()

    rx_resp = await client.post(
        "/api/v1/doctors/prescriptions",
        json={
            "patient_id": patient_id,
            "medicines": [
                {
                    "brand_name": "Metformin 500mg",
                    "dose": "500mg",
                    "frequency": "twice daily",
                    "duration": "30 days",
                }
            ],
            "diagnosis": "Type 2 Diabetes",
            "notes": "With meals",
        },
        headers=_auth(doctor_token, clinic.id),
    )
    assert rx_resp.status_code == 201, rx_resp.text
    return patient_token, patient_id, doctor_token, doctor_user_id, clinic, rx_resp.json()["id"]


@pytest.mark.asyncio
async def test_request_refill_creates_pending_and_notifies_doctor(client: AsyncClient, db):
    patient_token, patient_id, doctor_token, doctor_user_id, clinic, rx_id = (
        await setup_clinic_scenario(client, db)
    )

    resp = await client.post(
        f"/api/v1/prescriptions/{rx_id}/refill-request",
        json={"note": "Running low, please refill"},
        headers=_auth(patient_token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "pending"
    assert body["prescription_id"] == rx_id
    assert body["clinic_id"] == str(clinic.id)
    assert body["note"] == "Running low, please refill"

    # Prescribing doctor's user account got a notification
    notifs = (
        await db.execute(
            select(Notification).where(Notification.user_id == uuid.UUID(doctor_user_id))
        )
    ).scalars().all()
    assert any("Refill request" in n.title for n in notifs)


@pytest.mark.asyncio
async def test_double_request_rejected(client: AsyncClient, db):
    patient_token, patient_id, doctor_token, doctor_user_id, clinic, rx_id = (
        await setup_clinic_scenario(client, db)
    )

    first = await client.post(
        f"/api/v1/prescriptions/{rx_id}/refill-request",
        json={},
        headers=_auth(patient_token),
    )
    assert first.status_code == 201

    second = await client.post(
        f"/api/v1/prescriptions/{rx_id}/refill-request",
        json={},
        headers=_auth(patient_token),
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "REFILL_ALREADY_PENDING"


@pytest.mark.asyncio
async def test_request_refill_other_patients_prescription_denied(client: AsyncClient, db):
    _, _, _, _, _, rx_id = await setup_clinic_scenario(client, db)
    other_token, _ = await _provision_user(
        client, email="other@refill.com", name="Other Patient", roles=["patient"]
    )
    resp = await client.post(
        f"/api/v1/prescriptions/{rx_id}/refill-request",
        json={},
        headers=_auth(other_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_request_refill_missing_prescription_404(client: AsyncClient, db):
    patient_token, _ = await _provision_user(
        client, email="p@refill.com", name="P", roles=["patient"]
    )
    resp = await client.post(
        f"/api/v1/prescriptions/{uuid.uuid4()}/refill-request",
        json={},
        headers=_auth(patient_token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_approve_creates_new_prescription_and_notifies_patient(client: AsyncClient, db):
    patient_token, patient_id, doctor_token, doctor_user_id, clinic, rx_id = (
        await setup_clinic_scenario(client, db)
    )

    req = await client.post(
        f"/api/v1/prescriptions/{rx_id}/refill-request",
        json={"note": "please refill"},
        headers=_auth(patient_token),
    )
    request_id = req.json()["id"]

    # Doctor sees it in the clinic-scoped list
    listing = await client.get(
        "/api/v1/prescriptions/refill-requests?status=pending",
        headers=_auth(doctor_token, clinic.id),
    )
    assert listing.status_code == 200, listing.text
    items = listing.json()["data"]
    assert len(items) == 1
    assert items[0]["id"] == request_id
    assert items[0]["patient_name"] == "Refill Patient"
    assert items[0]["medicines"][0]["brand_name"] == "Metformin 500mg"

    resp = await client.post(
        f"/api/v1/refill-requests/{request_id}/respond",
        json={"action": "approve", "note": "Refilled for 30 days"},
        headers=_auth(doctor_token, clinic.id),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "approved"
    assert body["new_prescription_id"]

    # A new prescription now exists for the patient, cloned from the original
    rxs = (
        await db.execute(
            select(Prescription).where(
                Prescription.patient_id == uuid.UUID(patient_id),
                Prescription.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    assert len(rxs) == 2
    new_rx = next(r for r in rxs if str(r.id) == body["new_prescription_id"])
    assert new_rx.medicines[0]["brand_name"] == "Metformin 500mg"
    assert new_rx.diagnosis == "Type 2 Diabetes"
    assert new_rx.clinic_id == clinic.id

    # Patient was notified (create_prescription notifies on issue)
    notifs = (
        await db.execute(
            select(Notification).where(Notification.user_id == uuid.UUID(patient_id))
        )
    ).scalars().all()
    assert any("prescription" in n.title.lower() for n in notifs)

    # Responding again is a conflict
    again = await client.post(
        f"/api/v1/refill-requests/{request_id}/respond",
        json={"action": "approve"},
        headers=_auth(doctor_token, clinic.id),
    )
    assert again.status_code == 409


@pytest.mark.asyncio
async def test_decline_notifies_patient(client: AsyncClient, db):
    patient_token, patient_id, doctor_token, doctor_user_id, clinic, rx_id = (
        await setup_clinic_scenario(client, db)
    )

    req = await client.post(
        f"/api/v1/prescriptions/{rx_id}/refill-request",
        json={},
        headers=_auth(patient_token),
    )
    request_id = req.json()["id"]

    resp = await client.post(
        f"/api/v1/refill-requests/{request_id}/respond",
        json={"action": "decline", "note": "Please book a follow-up visit first"},
        headers=_auth(doctor_token, clinic.id),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "declined"
    assert resp.json()["response_note"] == "Please book a follow-up visit first"
    assert resp.json()["new_prescription_id"] is None

    notifs = (
        await db.execute(
            select(Notification).where(Notification.user_id == uuid.UUID(patient_id))
        )
    ).scalars().all()
    assert any("declined" in n.title.lower() for n in notifs)

    # Patient can see resolved status in their own list
    mine = await client.get(
        "/api/v1/prescriptions/refill-requests/mine", headers=_auth(patient_token)
    )
    assert mine.status_code == 200
    assert mine.json()["data"][0]["status"] == "declined"


@pytest.mark.asyncio
async def test_cross_clinic_doctor_cannot_respond_or_list(client: AsyncClient, db):
    patient_token, patient_id, doctor_token, doctor_user_id, clinic, rx_id = (
        await setup_clinic_scenario(client, db)
    )
    req = await client.post(
        f"/api/v1/prescriptions/{rx_id}/refill-request",
        json={},
        headers=_auth(patient_token),
    )
    request_id = req.json()["id"]

    # Second verified doctor who belongs to a DIFFERENT clinic
    other_sub = str(uuid.uuid4())
    other_token = create_test_token(
        sub=other_sub, email="other-doc@refill.com", name="Dr. Other", roles=["doctor"]
    )
    me = await client.get("/api/v1/auth/me", headers=_auth(other_token))
    other_user_id = me.json()["id"]
    await verify_provisioned_doctor(db, other_sub)
    other_clinic = await _make_clinic(db, user_id=other_user_id, name="Other Clinic")

    # Cannot respond — not a member of the prescribing clinic
    resp = await client.post(
        f"/api/v1/refill-requests/{request_id}/respond",
        json={"action": "approve"},
        headers=_auth(other_token, other_clinic.id),
    )
    assert resp.status_code == 403

    # Their clinic-scoped list does not include the request
    listing = await client.get(
        "/api/v1/prescriptions/refill-requests",
        headers=_auth(other_token, other_clinic.id),
    )
    assert listing.status_code == 200
    assert listing.json()["data"] == []

    # The original doctor's list still shows it pending
    listing2 = await client.get(
        "/api/v1/prescriptions/refill-requests",
        headers=_auth(doctor_token, clinic.id),
    )
    assert [r["id"] for r in listing2.json()["data"]] == [request_id]


@pytest.mark.asyncio
async def test_expired_prescription_still_requestable(client: AsyncClient, db):
    patient_token, patient_id, doctor_token, doctor_user_id, clinic, rx_id = (
        await setup_clinic_scenario(client, db)
    )
    # Force the prescription into the past
    rx = await db.get(Prescription, uuid.UUID(rx_id))
    import datetime as _dt

    rx.valid_until = _dt.date.today() - _dt.timedelta(days=10)
    await db.commit()

    resp = await client.post(
        f"/api/v1/prescriptions/{rx_id}/refill-request",
        json={},
        headers=_auth(patient_token),
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "pending"
