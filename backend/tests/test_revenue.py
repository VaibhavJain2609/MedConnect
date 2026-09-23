"""Revenue reporting endpoints (/api/v1/revenue/*).

Covers:
- Auth matrix: unauthenticated 401; non-admin without clinic context 403;
  non-member / non-owner membership / inactive membership 403;
  admin 200; clinic owner and clinic-admin members 200.
- Daily revenue: sums only paid bills for the day, excludes other days and
  soft-deleted rows, optional clinic_id scoping, invalid date 400.
- Monthly revenue: per-day breakdown + totals, query validation 422.
- Unpaid invoices: pending-only list with patient/clinic names, totals,
  clinic scoping.
"""

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import Billing
from app.models.clinic import Clinic, ClinicMembership
from app.models.user import User
from tests.conftest import make_auth_header

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def clinic(db: AsyncSession, doctor_user: User) -> Clinic:
    c = Clinic(id=uuid.uuid4(), name="Revenue Clinic", city="Pune", created_by=doctor_user.id)
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


@pytest_asyncio.fixture
async def other_clinic(db: AsyncSession, doctor_user: User) -> Clinic:
    c = Clinic(id=uuid.uuid4(), name="Other Clinic", city="Goa", created_by=doctor_user.id)
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


async def _membership(db: AsyncSession, clinic: Clinic, user: User, role: str, active: bool = True) -> ClinicMembership:
    m = ClinicMembership(
        id=uuid.uuid4(), clinic_id=clinic.id, user_id=user.id, role=role, is_active=active
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


async def _make_bill(
    db: AsyncSession,
    patient_id,
    amount: float,
    status: str = "paid",
    clinic_id=None,
    created_at: datetime | None = None,
    deleted_at: datetime | None = None,
    payment_method: str = "cash",
) -> Billing:
    bill = Billing(
        id=uuid.uuid4(),
        patient_id=patient_id,
        clinic_id=clinic_id,
        amount=amount,
        status=status,
        payment_method=payment_method,
    )
    if created_at is not None:
        bill.created_at = created_at
    if deleted_at is not None:
        bill.deleted_at = deleted_at
    db.add(bill)
    await db.commit()
    await db.refresh(bill)
    return bill


DAY = datetime(2024, 3, 15, 10, 0, 0, tzinfo=timezone.utc)
OTHER_DAY = datetime(2024, 3, 16, 10, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Auth matrix
# ---------------------------------------------------------------------------


class TestRevenueAuth:
    async def test_unauthenticated_401(self, client):
        resp = await client.get("/api/v1/revenue/daily", params={"date": "2024-03-15"})
        assert resp.status_code == 401

    @pytest.mark.parametrize("path", ["/daily", "/monthly", "/unpaid"])
    async def test_non_admin_without_clinic_id_403(self, client, patient_user, path):
        params = {"date": "2024-03-15"} if path == "/daily" else (
            {"year": 2024, "month": 3} if path == "/monthly" else {}
        )
        resp = await client.get(
            f"/api/v1/revenue{path}", params=params, headers=make_auth_header(patient_user)
        )
        assert resp.status_code == 403

    async def test_clinic_id_but_not_member_403(self, client, patient_user, clinic):
        resp = await client.get(
            "/api/v1/revenue/daily",
            params={"date": "2024-03-15", "clinic_id": str(clinic.id)},
            headers=make_auth_header(patient_user),
        )
        assert resp.status_code == 403

    async def test_member_with_non_owner_role_403(self, client, db, doctor_user, clinic):
        # A plain 'doctor' membership is not enough — owner/admin required.
        await _membership(db, clinic, doctor_user, role="doctor")
        resp = await client.get(
            "/api/v1/revenue/daily",
            params={"date": "2024-03-15", "clinic_id": str(clinic.id)},
            headers=make_auth_header(doctor_user),
        )
        assert resp.status_code == 403

    async def test_inactive_membership_403(self, client, db, doctor_user, clinic):
        await _membership(db, clinic, doctor_user, role="owner", active=False)
        resp = await client.get(
            "/api/v1/revenue/daily",
            params={"date": "2024-03-15", "clinic_id": str(clinic.id)},
            headers=make_auth_header(doctor_user),
        )
        assert resp.status_code == 403

    async def test_owner_of_other_clinic_403(self, client, db, doctor_user, clinic, other_clinic):
        # Owner of `clinic` cannot query revenue for `other_clinic`.
        await _membership(db, clinic, doctor_user, role="owner")
        resp = await client.get(
            "/api/v1/revenue/daily",
            params={"date": "2024-03-15", "clinic_id": str(other_clinic.id)},
            headers=make_auth_header(doctor_user),
        )
        assert resp.status_code == 403

    @pytest.mark.parametrize("role", ["owner", "admin"])
    async def test_clinic_owner_and_admin_members_200(self, client, db, doctor_user, clinic, role):
        await _membership(db, clinic, doctor_user, role=role)
        resp = await client.get(
            "/api/v1/revenue/daily",
            params={"date": "2024-03-15", "clinic_id": str(clinic.id)},
            headers=make_auth_header(doctor_user),
        )
        assert resp.status_code == 200

    @pytest.mark.parametrize(
        "path",
        [
            "/daily",
            # REAL BUG: /monthly always 500s — func.date_trunc() is emitted 3x
            # (SELECT/GROUP BY/ORDER BY) with distinct bound params, so Postgres
            # raises GroupingError "column billing.created_at must appear in the
            # GROUP BY clause". See revenue.py monthly_revenue().
            pytest.param(
                "/monthly",
                marks=pytest.mark.xfail(
                    strict=True,
                    reason="BUG: monthly revenue 500s — date_trunc GROUP BY param mismatch",
                ),
            ),
            "/unpaid",
        ],
    )
    async def test_admin_all_endpoints_200(self, client, admin_user, path):
        params = {"date": "2024-03-15"} if path == "/daily" else (
            {"year": 2024, "month": 3} if path == "/monthly" else {}
        )
        resp = await client.get(
            f"/api/v1/revenue{path}", params=params, headers=make_auth_header(admin_user)
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Daily revenue
# ---------------------------------------------------------------------------


class TestDailyRevenue:
    async def test_sums_paid_only(self, client, db, admin_user, patient_user):
        await _make_bill(db, patient_user.id, 500.0, "paid", created_at=DAY)
        await _make_bill(db, patient_user.id, 250.0, "paid", created_at=DAY)
        await _make_bill(db, patient_user.id, 999.0, "pending", created_at=DAY)
        await _make_bill(db, patient_user.id, 999.0, "cancelled", created_at=DAY)

        resp = await client.get(
            "/api/v1/revenue/daily",
            params={"date": "2024-03-15"},
            headers=make_auth_header(admin_user),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["date"] == "2024-03-15"
        assert float(body["total_paid"]) == 750.0
        assert body["bill_count"] == 2

    async def test_excludes_other_days_and_soft_deleted(self, client, db, admin_user, patient_user):
        await _make_bill(db, patient_user.id, 100.0, "paid", created_at=DAY)
        await _make_bill(db, patient_user.id, 400.0, "paid", created_at=OTHER_DAY)
        await _make_bill(
            db, patient_user.id, 300.0, "paid",
            created_at=DAY, deleted_at=datetime(2024, 3, 20, tzinfo=timezone.utc),
        )

        resp = await client.get(
            "/api/v1/revenue/daily",
            params={"date": "2024-03-15"},
            headers=make_auth_header(admin_user),
        )
        body = resp.json()
        assert float(body["total_paid"]) == 100.0
        assert body["bill_count"] == 1

    async def test_clinic_scoping(self, client, db, doctor_user, patient_user, clinic, other_clinic):
        await _membership(db, clinic, doctor_user, role="owner")
        await _make_bill(db, patient_user.id, 200.0, "paid", clinic_id=clinic.id, created_at=DAY)
        await _make_bill(db, patient_user.id, 800.0, "paid", clinic_id=other_clinic.id, created_at=DAY)
        await _make_bill(db, patient_user.id, 50.0, "paid", clinic_id=None, created_at=DAY)

        resp = await client.get(
            "/api/v1/revenue/daily",
            params={"date": "2024-03-15", "clinic_id": str(clinic.id)},
            headers=make_auth_header(doctor_user),
        )
        body = resp.json()
        assert float(body["total_paid"]) == 200.0
        assert body["bill_count"] == 1

    async def test_invalid_date_400(self, client, admin_user):
        resp = await client.get(
            "/api/v1/revenue/daily",
            params={"date": "not-a-date"},
            headers=make_auth_header(admin_user),
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_DATE"

    async def test_missing_date_422(self, client, admin_user):
        resp = await client.get("/api/v1/revenue/daily", headers=make_auth_header(admin_user))
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Monthly revenue
# ---------------------------------------------------------------------------


class TestMonthlyRevenue:
    # REAL BUG: every successful /revenue/monthly call 500s — the endpoint
    # emits func.date_trunc() three separate times (SELECT, GROUP BY,
    # ORDER BY), each with its own bound parameter, so Postgres does not
    # recognise the SELECT expression in GROUP BY → GroupingError → 500.
    # revenue.py monthly_revenue(). Not fixed here per task instructions.
    @pytest.mark.xfail(
        strict=True,
        reason="BUG: /revenue/monthly 500s — date_trunc GROUP BY param mismatch",
    )
    async def test_breakdown_and_totals(self, client, db, admin_user, patient_user):
        await _make_bill(db, patient_user.id, 100.0, "paid", created_at=DAY)
        await _make_bill(db, patient_user.id, 200.0, "paid", created_at=DAY)
        await _make_bill(db, patient_user.id, 300.0, "paid", created_at=OTHER_DAY)
        await _make_bill(db, patient_user.id, 999.0, "pending", created_at=DAY)

        resp = await client.get(
            "/api/v1/revenue/monthly",
            params={"year": 2024, "month": 3},
            headers=make_auth_header(admin_user),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["year"] == 2024 and body["month"] == 3
        assert float(body["total_paid"]) == 600.0
        assert body["bill_count"] == 3
        assert len(body["daily_breakdown"]) == 2
        assert body["daily_breakdown"][0]["date"] == "2024-03-15"
        assert body["daily_breakdown"][1]["date"] == "2024-03-16"

    @pytest.mark.xfail(
        strict=True,
        reason="BUG: /revenue/monthly 500s — date_trunc GROUP BY param mismatch",
    )
    async def test_empty_month(self, client, admin_user):
        resp = await client.get(
            "/api/v1/revenue/monthly",
            params={"year": 2024, "month": 6},
            headers=make_auth_header(admin_user),
        )
        body = resp.json()
        assert body["bill_count"] == 0
        assert float(body["total_paid"]) == 0.0
        assert body["daily_breakdown"] == []

    @pytest.mark.parametrize(
        "params",
        [
            {"year": 2024, "month": 13},
            {"year": 2024, "month": 0},
            {"year": 1999, "month": 3},
            {"year": 2101, "month": 3},
            {"month": 3},   # missing year
            {"year": 2024},  # missing month
        ],
    )
    async def test_query_validation_422(self, client, admin_user, params):
        resp = await client.get(
            "/api/v1/revenue/monthly", params=params, headers=make_auth_header(admin_user)
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Unpaid invoices
# ---------------------------------------------------------------------------


class TestUnpaid:
    async def test_lists_pending_with_names_and_total(
        self, client, db, admin_user, patient_user, clinic
    ):
        await _make_bill(db, patient_user.id, 120.0, "pending", clinic_id=clinic.id, created_at=DAY)
        await _make_bill(db, patient_user.id, 80.0, "pending", clinic_id=None, created_at=OTHER_DAY)
        await _make_bill(db, patient_user.id, 500.0, "paid", created_at=DAY)
        await _make_bill(
            db, patient_user.id, 700.0, "pending",
            created_at=DAY, deleted_at=datetime(2024, 3, 20, tzinfo=timezone.utc),
        )

        resp = await client.get("/api/v1/revenue/unpaid", headers=make_auth_header(admin_user))
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert float(body["total_unpaid_amount"]) == 200.0
        first = body["data"][0]
        assert first["patient_id"] == str(patient_user.id)
        assert first["patient_name"] == patient_user.full_name
        assert first["status"] == "pending"
        clinic_rows = [b for b in body["data"] if b["clinic_id"] == str(clinic.id)]
        assert clinic_rows and clinic_rows[0]["clinic_name"] == clinic.name

    async def test_empty(self, client, admin_user):
        resp = await client.get("/api/v1/revenue/unpaid", headers=make_auth_header(admin_user))
        body = resp.json()
        assert body["total"] == 0
        assert body["data"] == []
        assert float(body["total_unpaid_amount"]) == 0.0

    async def test_clinic_scoping(self, client, db, doctor_user, patient_user, clinic, other_clinic):
        await _membership(db, clinic, doctor_user, role="owner")
        await _make_bill(db, patient_user.id, 150.0, "pending", clinic_id=clinic.id)
        await _make_bill(db, patient_user.id, 450.0, "pending", clinic_id=other_clinic.id)

        resp = await client.get(
            "/api/v1/revenue/unpaid",
            params={"clinic_id": str(clinic.id)},
            headers=make_auth_header(doctor_user),
        )
        body = resp.json()
        assert body["total"] == 1
        assert float(body["total_unpaid_amount"]) == 150.0
        assert body["data"][0]["clinic_id"] == str(clinic.id)
