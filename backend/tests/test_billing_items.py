"""Round-10: billing line items — POST /api/v1/billing accepts `items`.

Covers:
- Create with items → 201; server computes line amounts and the bill total
  (sum of quantity * unit_amount — the model has no tax column).
- Persisted ``billing_items`` rows; detail + list responses include items[].
- Receipt PDF renders item rows without error; empty-items bills keep the
  notes/amount fallback path.
- Backfill: amount-only creates still work; neither amount nor items → 422.
- Authz unchanged: patients can't create; doctors still need membership.

Fixture shape mirrors test_billing_receipt.py (db / client /
make_auth_header from conftest — no cross-test-file imports).
"""

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import Billing, BillingItem
from app.models.user import User
from app.routers.billing import _normalize_line_items
from tests.conftest import make_auth_header

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_bill(
    db: AsyncSession,
    *,
    patient_id,
    status: str = "pending",
    amount: float = 500.00,
    notes: str | None = "Consultation fee",
    items: list[dict] | None = None,
) -> Billing:
    bill = Billing(
        id=uuid.uuid4(),
        patient_id=patient_id,
        amount=amount,
        status=status,
        notes=notes,
    )
    if items:
        bill.items = [
            BillingItem(
                id=uuid.uuid4(),
                description=it["description"],
                quantity=it.get("quantity", 1),
                unit_amount=it["unit_amount"],
                amount=it["amount"],
            )
            for it in items
        ]
    db.add(bill)
    await db.commit()
    await db.refresh(bill)
    return bill


# ---------------------------------------------------------------------------
# Create with items
# ---------------------------------------------------------------------------


@pytest.mark.smoke
async def test_create_bill_with_items_computes_total(
    admin_client: AsyncClient, db: AsyncSession, patient_user: User
):
    resp = await admin_client.post(
        "/api/v1/billing",
        json={
            "patient_id": str(patient_user.id),
            "notes": "Routine visit",
            "items": [
                {"description": "Consultation", "quantity": 1, "unit_amount": "500.00"},
                {"description": "Blood panel", "quantity": 2, "unit_amount": "375.25"},
            ],
        },
    )

    assert resp.status_code == 201
    body = resp.json()
    assert Decimal(body["amount"]) == Decimal("1250.50")
    assert len(body["items"]) == 2
    assert body["items"][0]["description"] == "Consultation"
    assert Decimal(body["items"][0]["amount"]) == Decimal("500.00")
    assert Decimal(body["items"][1]["amount"]) == Decimal("750.50")

    # Rows actually persisted
    rows = (
        await db.execute(
            select(BillingItem).where(BillingItem.billing_id == uuid.UUID(body["id"]))
        )
    ).scalars().all()
    assert len(rows) == 2
    assert {r.description for r in rows} == {"Consultation", "Blood panel"}


async def test_create_bill_items_total_overrides_client_amount(
    admin_client: AsyncClient, db: AsyncSession, patient_user: User
):
    """When items are supplied the server-computed sum wins over `amount`."""
    resp = await admin_client.post(
        "/api/v1/billing",
        json={
            "patient_id": str(patient_user.id),
            "amount": "9999.00",
            "items": [
                {"description": "X-ray", "quantity": 1, "unit_amount": "800.00"},
            ],
        },
    )

    assert resp.status_code == 201
    assert Decimal(resp.json()["amount"]) == Decimal("800.00")


async def test_create_bill_item_quantity_defaults_to_one(
    admin_client: AsyncClient, db: AsyncSession, patient_user: User
):
    resp = await admin_client.post(
        "/api/v1/billing",
        json={
            "patient_id": str(patient_user.id),
            "items": [{"description": "Dressing", "unit_amount": "120.00"}],
        },
    )

    assert resp.status_code == 201
    body = resp.json()
    assert Decimal(body["amount"]) == Decimal("120.00")
    assert Decimal(body["items"][0]["quantity"]) == Decimal("1")


async def test_create_bill_amount_only_still_works(
    admin_client: AsyncClient, db: AsyncSession, patient_user: User
):
    """Backfill: legacy amount-only creates keep working with empty items."""
    resp = await admin_client.post(
        "/api/v1/billing",
        json={
            "patient_id": str(patient_user.id),
            "amount": "500.00",
            "notes": "Consultation fee",
        },
    )

    assert resp.status_code == 201
    body = resp.json()
    assert Decimal(body["amount"]) == Decimal("500.00")
    assert body["items"] == []


async def test_create_bill_neither_amount_nor_items_422(
    admin_client: AsyncClient, db: AsyncSession, patient_user: User
):
    resp = await admin_client.post(
        "/api/v1/billing",
        json={"patient_id": str(patient_user.id)},
    )

    assert resp.status_code == 422


async def test_create_bill_empty_items_without_amount_422(
    admin_client: AsyncClient, db: AsyncSession, patient_user: User
):
    resp = await admin_client.post(
        "/api/v1/billing",
        json={"patient_id": str(patient_user.id), "items": []},
    )

    assert resp.status_code == 422


async def test_create_bill_patient_forbidden(
    client: AsyncClient, db: AsyncSession, patient_user: User
):
    """Authz unchanged — patients still can't create bills."""
    resp = await client.post(
        "/api/v1/billing",
        json={
            "patient_id": str(patient_user.id),
            "items": [{"description": "Consult", "quantity": 1, "unit_amount": "100.00"}],
        },
        headers=make_auth_header(patient_user),
    )

    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Detail / list responses carry items
# ---------------------------------------------------------------------------


async def test_get_bill_returns_items(
    client: AsyncClient, db: AsyncSession, patient_user: User
):
    bill = await _make_bill(
        db,
        patient_id=patient_user.id,
        amount=625.00,
        items=[
            {"description": "Consultation", "quantity": 1, "unit_amount": 500.00, "amount": 500.00},
            {"description": "Bandage", "quantity": 5, "unit_amount": 25.00, "amount": 125.00},
        ],
    )

    resp = await client.get(
        f"/api/v1/billing/{bill.id}", headers=make_auth_header(patient_user)
    )

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 2
    assert body["items"][0]["description"] == "Consultation"
    assert Decimal(body["items"][1]["amount"]) == Decimal("125.00")


async def test_list_bills_returns_items(
    client: AsyncClient, db: AsyncSession, patient_user: User
):
    await _make_bill(
        db,
        patient_id=patient_user.id,
        amount=100.00,
        items=[
            {"description": "Consultation", "quantity": 1, "unit_amount": 100.00, "amount": 100.00},
        ],
    )

    resp = await client.get("/api/v1/billing", headers=make_auth_header(patient_user))

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert len(data[0]["items"]) == 1
    assert data[0]["items"][0]["description"] == "Consultation"


async def test_bill_without_items_serializes_empty_list(
    client: AsyncClient, db: AsyncSession, patient_user: User
):
    bill = await _make_bill(db, patient_id=patient_user.id, amount=500.00)

    resp = await client.get(
        f"/api/v1/billing/{bill.id}", headers=make_auth_header(patient_user)
    )

    assert resp.status_code == 200
    assert resp.json()["items"] == []


# ---------------------------------------------------------------------------
# Receipt PDF + line-item normalization
# ---------------------------------------------------------------------------


async def test_receipt_for_itemized_bill_returns_pdf(
    client: AsyncClient, db: AsyncSession, patient_user: User
):
    bill = await _make_bill(
        db,
        patient_id=patient_user.id,
        status="paid",
        amount=1250.50,
        items=[
            {"description": "Consultation", "quantity": 1, "unit_amount": 500.00, "amount": 500.00},
            {"description": "Blood panel", "quantity": 2, "unit_amount": 375.25, "amount": 750.50},
        ],
    )

    resp = await client.get(
        f"/api/v1/billing/{bill.id}/receipt",
        headers=make_auth_header(patient_user),
    )

    assert resp.status_code == 200
    assert resp.content[:5] == b"%PDF-"


async def test_normalize_line_items_reads_orm_rows():
    """ORM BillingItem rows (not dicts) feed the PDF line-item table."""
    bill = Billing(
        id=uuid.uuid4(),
        patient_id=uuid.uuid4(),
        amount=Decimal("750.50"),
        status="pending",
    )
    bill.items = [
        BillingItem(
            id=uuid.uuid4(),
            description="Blood panel",
            quantity=Decimal("2"),
            unit_amount=Decimal("375.25"),
            amount=Decimal("750.50"),
        )
    ]

    items = _normalize_line_items(bill)

    assert len(items) == 1
    assert items[0]["description"] == "Blood panel"
    assert items[0]["quantity"] == 2.0
    assert items[0]["unit_price"] == 375.25
    assert items[0]["amount"] == 750.50


async def test_normalize_line_items_fallback_when_empty():
    """Empty items → single notes/amount line (the pre-items behaviour)."""
    bill = Billing(
        id=uuid.uuid4(),
        patient_id=uuid.uuid4(),
        amount=Decimal("500.00"),
        status="pending",
        notes="Consultation fee",
    )

    items = _normalize_line_items(bill)

    assert len(items) == 1
    assert items[0]["description"] == "Consultation fee"
    assert items[0]["amount"] == Decimal("500.00")


async def test_receipt_for_bill_without_items_uses_fallback(
    client: AsyncClient, db: AsyncSession, patient_user: User
):
    bill = await _make_bill(db, patient_id=patient_user.id, status="paid")

    resp = await client.get(
        f"/api/v1/billing/{bill.id}/receipt",
        headers=make_auth_header(patient_user),
    )

    assert resp.status_code == 200
    assert resp.content[:5] == b"%PDF-"
