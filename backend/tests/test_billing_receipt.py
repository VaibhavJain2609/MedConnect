"""Round-7: GET /api/v1/billing/{bill_id}/receipt — PDF receipt/invoice.

Covers:
- Owner (patient) gets a 200 PDF with %PDF magic; paid bills are named
  ``receipt-*.pdf``, unpaid bills ``invoice-*.pdf`` (?download=true flips the
  Content-Disposition to attachment).
- Wrong patient → 403; doctor without clinic membership → 403; doctor with
  membership → 200; admin → 200.
- Missing bill / malformed UUID → 404; unauthenticated → 401.

Fixture shape mirrors test_r6_staff_booking.py (db / client /
make_auth_header from conftest — no cross-test-file imports).
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import Billing
from app.models.clinic import Clinic, ClinicMembership
from app.models.user import User
from tests.conftest import make_auth_header

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


async def _make_bill(
    db: AsyncSession,
    *,
    patient_id,
    clinic_id=None,
    status: str = "paid",
    amount: float = 1250.00,
    payment_method: str | None = "cash",
    notes: str | None = "Consultation fee",
) -> Billing:
    bill = Billing(
        id=uuid.uuid4(),
        patient_id=patient_id,
        clinic_id=clinic_id,
        amount=amount,
        status=status,
        payment_method=payment_method,
        notes=notes,
    )
    db.add(bill)
    await db.commit()
    await db.refresh(bill)
    return bill


@pytest_asyncio.fixture
async def other_patient(db: AsyncSession) -> User:
    user = User(
        keycloak_sub="patient-456",
        email="other-patient@test.com",
        full_name="Other Patient",
        role="patient",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def clinic(db: AsyncSession) -> Clinic:
    c = Clinic(id=uuid.uuid4(), name="Receipt Clinic", city="Delhi")
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


async def _membership(db: AsyncSession, clinic_id, user_id, role: str) -> ClinicMembership:
    m = ClinicMembership(
        id=uuid.uuid4(), clinic_id=clinic_id, user_id=user_id,
        role=role, is_active=True,
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


async def test_receipt_paid_bill_returns_pdf(
    client: AsyncClient, db: AsyncSession, patient_user: User
):
    bill = await _make_bill(db, patient_id=patient_user.id, status="paid")

    resp = await client.get(
        f"/api/v1/billing/{bill.id}/receipt",
        headers=make_auth_header(patient_user),
    )

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:5] == b"%PDF-"
    disposition = resp.headers["content-disposition"]
    assert "receipt-" in disposition
    assert "inline" in disposition


async def test_receipt_pending_bill_is_invoice(
    client: AsyncClient, db: AsyncSession, patient_user: User
):
    bill = await _make_bill(db, patient_id=patient_user.id, status="pending", payment_method=None)

    resp = await client.get(
        f"/api/v1/billing/{bill.id}/receipt",
        headers=make_auth_header(patient_user),
    )

    assert resp.status_code == 200
    assert resp.content[:5] == b"%PDF-"
    assert "invoice-" in resp.headers["content-disposition"]


async def test_receipt_download_true_forces_attachment(
    client: AsyncClient, db: AsyncSession, patient_user: User
):
    bill = await _make_bill(db, patient_id=patient_user.id, status="paid")

    resp = await client.get(
        f"/api/v1/billing/{bill.id}/receipt?download=true",
        headers=make_auth_header(patient_user),
    )

    assert resp.status_code == 200
    assert "attachment" in resp.headers["content-disposition"]


async def test_receipt_escape_heavy_notes_does_not_500(
    client: AsyncClient, db: AsyncSession, patient_user: User
):
    """User-controlled markup (<b>, & etc.) must be escaped, not crash ReportLab."""
    bill = await _make_bill(
        db,
        patient_id=patient_user.id,
        status="paid",
        notes='Consult <b>bold</b> & "quoted" <img src="x">',
    )

    resp = await client.get(
        f"/api/v1/billing/{bill.id}/receipt",
        headers=make_auth_header(patient_user),
    )

    assert resp.status_code == 200
    assert resp.content[:5] == b"%PDF-"


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------


async def test_receipt_other_patient_forbidden(
    client: AsyncClient, db: AsyncSession, patient_user: User, other_patient: User
):
    bill = await _make_bill(db, patient_id=patient_user.id)

    resp = await client.get(
        f"/api/v1/billing/{bill.id}/receipt",
        headers=make_auth_header(other_patient),
    )

    assert resp.status_code == 403


async def test_receipt_doctor_member_allowed(
    client: AsyncClient,
    db: AsyncSession,
    patient_user: User,
    doctor_user: User,
    clinic: Clinic,
):
    await _membership(db, clinic.id, doctor_user.id, "doctor")
    bill = await _make_bill(db, patient_id=patient_user.id, clinic_id=clinic.id)

    resp = await client.get(
        f"/api/v1/billing/{bill.id}/receipt",
        headers=make_auth_header(doctor_user),
    )

    assert resp.status_code == 200
    assert resp.content[:5] == b"%PDF-"


async def test_receipt_doctor_non_member_forbidden(
    client: AsyncClient,
    db: AsyncSession,
    patient_user: User,
    doctor_user: User,
    clinic: Clinic,
):
    """Doctor holds no membership for the bill's clinic → 403."""
    bill = await _make_bill(db, patient_id=patient_user.id, clinic_id=clinic.id)

    resp = await client.get(
        f"/api/v1/billing/{bill.id}/receipt",
        headers=make_auth_header(doctor_user),
    )

    assert resp.status_code == 403


async def test_receipt_admin_allowed(
    client: AsyncClient, db: AsyncSession, patient_user: User, admin_user: User
):
    bill = await _make_bill(db, patient_id=patient_user.id)

    resp = await client.get(
        f"/api/v1/billing/{bill.id}/receipt",
        headers=make_auth_header(admin_user),
    )

    assert resp.status_code == 200
    assert resp.content[:5] == b"%PDF-"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


async def test_receipt_missing_bill_404(
    client: AsyncClient, db: AsyncSession, patient_user: User
):
    resp = await client.get(
        f"/api/v1/billing/{uuid.uuid4()}/receipt",
        headers=make_auth_header(patient_user),
    )

    assert resp.status_code == 404


async def test_receipt_invalid_uuid_404(
    client: AsyncClient, db: AsyncSession, patient_user: User
):
    resp = await client.get(
        "/api/v1/billing/not-a-uuid/receipt",
        headers=make_auth_header(patient_user),
    )

    assert resp.status_code == 404


async def test_receipt_unauthenticated_401(client: AsyncClient, db: AsyncSession):
    resp = await client.get(f"/api/v1/billing/{uuid.uuid4()}/receipt")

    assert resp.status_code == 401
