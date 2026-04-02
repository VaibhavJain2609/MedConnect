from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_active_clinic, get_current_user, require_admin
from app.models.billing import Billing
from app.models.clinic import Clinic, ClinicMembership
from app.models.user import User
from app.schemas.billing import (
    DailyRevenueResponse,
    MonthlyRevenueResponse,
    UnpaidSummaryResponse,
)

router = APIRouter(prefix="/api/v1/revenue", tags=["revenue"])


# ─── Authorization helper ─────────────────────────────────────────────────────

async def _require_admin_or_clinic_owner(
    current_user: User,
    clinic_id: UUID | None,
    db: AsyncSession,
) -> None:
    """
    Allow access if:
      - user is admin, OR
      - user is a clinic owner/admin for the specified clinic_id
    """
    if current_user.role == "admin":
        return

    if clinic_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "FORBIDDEN",
                    "message": "Admin role required, or provide clinic_id if you are a clinic owner/admin",
                }
            },
        )

    membership_res = await db.execute(
        select(ClinicMembership).where(
            ClinicMembership.clinic_id == clinic_id,
            ClinicMembership.user_id == current_user.id,
            ClinicMembership.role.in_(("owner", "admin")),
            ClinicMembership.is_active.is_(True),
            ClinicMembership.deleted_at.is_(None),
        )
    )
    if not membership_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "FORBIDDEN",
                    "message": "Clinic owner or admin role required",
                }
            },
        )


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/daily")
async def daily_revenue(
    date_param: str = Query(..., alias="date", description="YYYY-MM-DD"),
    clinic_id: UUID | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return total revenue (sum of paid bills) for a single day.
    Requires admin or clinic owner role.
    """
    await _require_admin_or_clinic_owner(current_user, clinic_id, db)

    try:
        target_date = date.fromisoformat(date_param)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_DATE", "message": "date must be YYYY-MM-DD"}},
        )

    day_start = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=timezone.utc)
    day_end = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59, tzinfo=timezone.utc)

    stmt = select(
        func.coalesce(func.sum(Billing.amount), 0).label("total_paid"),
        func.count(Billing.id).label("bill_count"),
    ).where(
        Billing.status == "paid",
        Billing.deleted_at.is_(None),
        Billing.created_at >= day_start,
        Billing.created_at <= day_end,
    )
    if clinic_id:
        stmt = stmt.where(Billing.clinic_id == clinic_id)

    result = await db.execute(stmt)
    row = result.one()

    return {
        "date": date_param,
        "total_paid": str(row.total_paid),
        "bill_count": row.bill_count,
    }


@router.get("/monthly")
async def monthly_revenue(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    clinic_id: UUID | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return total revenue for a calendar month with per-day breakdown.
    Requires admin or clinic owner role.
    """
    await _require_admin_or_clinic_owner(current_user, clinic_id, db)

    import calendar
    last_day = calendar.monthrange(year, month)[1]

    month_start = datetime(year, month, 1, 0, 0, 0, tzinfo=timezone.utc)
    month_end = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)

    # Aggregate per day
    stmt = select(
        func.date_trunc("day", Billing.created_at).label("day"),
        func.coalesce(func.sum(Billing.amount), 0).label("total_paid"),
        func.count(Billing.id).label("bill_count"),
    ).where(
        Billing.status == "paid",
        Billing.deleted_at.is_(None),
        Billing.created_at >= month_start,
        Billing.created_at <= month_end,
    ).group_by(
        func.date_trunc("day", Billing.created_at)
    ).order_by(
        func.date_trunc("day", Billing.created_at)
    )
    if clinic_id:
        stmt = stmt.where(Billing.clinic_id == clinic_id)

    result = await db.execute(stmt)
    rows = result.all()

    daily_breakdown = [
        {
            "date": row.day.date().isoformat(),
            "total_paid": str(row.total_paid),
            "bill_count": row.bill_count,
        }
        for row in rows
    ]

    total_paid = sum(Decimal(d["total_paid"]) for d in daily_breakdown)
    total_count = sum(d["bill_count"] for d in daily_breakdown)

    return {
        "year": year,
        "month": month,
        "total_paid": str(total_paid),
        "bill_count": total_count,
        "daily_breakdown": daily_breakdown,
    }


@router.get("/unpaid")
async def unpaid_invoices(
    clinic_id: UUID | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all pending (unpaid) invoices with total unpaid amount.
    Requires admin or clinic owner role.
    """
    await _require_admin_or_clinic_owner(current_user, clinic_id, db)

    stmt = select(Billing).where(
        Billing.status == "pending",
        Billing.deleted_at.is_(None),
    ).order_by(Billing.created_at.asc())

    if clinic_id:
        stmt = stmt.where(Billing.clinic_id == clinic_id)

    result = await db.execute(stmt)
    bills = result.scalars().all()

    # Batch load patient/clinic names
    patient_ids = list({b.patient_id for b in bills})
    clinic_ids = list({b.clinic_id for b in bills if b.clinic_id})

    from app.models.user import User as UserModel
    from app.models.clinic import Clinic as ClinicModel

    patient_names: dict = {}
    if patient_ids:
        pr = await db.execute(select(UserModel.id, UserModel.full_name).where(UserModel.id.in_(patient_ids)))
        patient_names = {row.id: row.full_name for row in pr.all()}

    clinic_names: dict = {}
    if clinic_ids:
        cr = await db.execute(select(ClinicModel.id, ClinicModel.name).where(ClinicModel.id.in_(clinic_ids)))
        clinic_names = {row.id: row.name for row in cr.all()}

    data = [
        {
            "id": str(b.id),
            "patient_id": str(b.patient_id),
            "patient_name": patient_names.get(b.patient_id),
            "clinic_id": str(b.clinic_id) if b.clinic_id else None,
            "clinic_name": clinic_names.get(b.clinic_id) if b.clinic_id else None,
            "appointment_id": str(b.appointment_id) if b.appointment_id else None,
            "amount": str(b.amount),
            "status": b.status,
            "payment_method": b.payment_method,
            "notes": b.notes,
            "created_at": b.created_at,
            "updated_at": b.updated_at,
        }
        for b in bills
    ]

    total_unpaid = sum(Decimal(d["amount"]) for d in data)

    return {
        "data": data,
        "total": len(data),
        "total_unpaid_amount": str(total_unpaid),
    }
