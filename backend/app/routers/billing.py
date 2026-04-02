import uuid
from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_doctor, get_current_user, require_admin
from app.models.billing import BILLING_STATUSES, PAYMENT_METHODS, Billing
from app.models.clinic import Clinic
from app.models.user import User
from app.schemas.billing import BillingCreate, BillingListResponse, BillingResponse, BillingUpdate

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _serialize_bill(
    bill: Billing,
    patient_name: str | None = None,
    clinic_name: str | None = None,
) -> dict:
    return {
        "id": str(bill.id),
        "patient_id": str(bill.patient_id),
        "patient_name": patient_name,
        "clinic_id": str(bill.clinic_id) if bill.clinic_id else None,
        "clinic_name": clinic_name,
        "appointment_id": str(bill.appointment_id) if bill.appointment_id else None,
        "amount": str(bill.amount),
        "status": bill.status,
        "payment_method": bill.payment_method,
        "notes": bill.notes,
        "created_at": bill.created_at,
        "updated_at": bill.updated_at,
    }


async def _load_bill_with_names(db: AsyncSession, bill: Billing) -> dict:
    patient_name: str | None = None
    clinic_name: str | None = None

    patient_res = await db.execute(
        select(User.full_name).where(User.id == bill.patient_id)
    )
    patient_name = patient_res.scalar_one_or_none()

    if bill.clinic_id:
        clinic_res = await db.execute(
            select(Clinic.name).where(Clinic.id == bill.clinic_id)
        )
        clinic_name = clinic_res.scalar_one_or_none()

    return _serialize_bill(bill, patient_name, clinic_name)


def _get_or_raise(bill: Billing | None) -> Billing:
    if not bill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Bill not found"}},
        )
    return bill


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_bill(
    req: BillingCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new billing invoice. Requires doctor or admin role."""
    if current_user.role not in ("doctor", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Doctor or admin access required"}},
        )

    # Verify patient exists
    patient_res = await db.execute(
        select(User).where(User.id == req.patient_id, User.deleted_at.is_(None))
    )
    if not patient_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Patient not found"}},
        )

    # Verify clinic exists if provided
    if req.clinic_id:
        clinic_res = await db.execute(
            select(Clinic).where(Clinic.id == req.clinic_id, Clinic.deleted_at.is_(None))
        )
        if not clinic_res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "NOT_FOUND", "message": "Clinic not found"}},
            )

    bill = Billing(
        id=uuid.uuid4(),
        patient_id=req.patient_id,
        clinic_id=req.clinic_id,
        appointment_id=req.appointment_id,
        amount=req.amount,
        status="pending",
        notes=req.notes,
    )
    db.add(bill)
    await db.flush()
    await db.refresh(bill)
    return await _load_bill_with_names(db, bill)


@router.get("")
async def list_bills(
    clinic_id: UUID | None = Query(None),
    patient_id: UUID | None = Query(None),
    bill_status: str | None = Query(None, alias="status"),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List bills with optional filters.
    - admin: can see all bills
    - doctor: can see bills for patients in their clinic (uses clinic_id filter)
    - patient: can only see their own bills
    """
    if bill_status and bill_status not in BILLING_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_STATUS",
                    "message": f"status must be one of: {', '.join(BILLING_STATUSES)}",
                }
            },
        )

    stmt = select(Billing).where(Billing.deleted_at.is_(None))

    if current_user.role == "patient":
        stmt = stmt.where(Billing.patient_id == current_user.id)
    elif current_user.role == "doctor":
        if clinic_id:
            stmt = stmt.where(Billing.clinic_id == clinic_id)
        if patient_id:
            stmt = stmt.where(Billing.patient_id == patient_id)
    else:
        # admin sees all; apply optional filters
        if clinic_id:
            stmt = stmt.where(Billing.clinic_id == clinic_id)
        if patient_id:
            stmt = stmt.where(Billing.patient_id == patient_id)

    if bill_status:
        stmt = stmt.where(Billing.status == bill_status)

    if date_from:
        try:
            from_dt = datetime.combine(date.fromisoformat(date_from), datetime.min.time()).replace(
                tzinfo=timezone.utc
            )
            stmt = stmt.where(Billing.created_at >= from_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "INVALID_DATE", "message": "date_from must be YYYY-MM-DD"}},
            )

    if date_to:
        try:
            to_dt = datetime.combine(date.fromisoformat(date_to), datetime.max.time()).replace(
                tzinfo=timezone.utc
            )
            stmt = stmt.where(Billing.created_at <= to_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "INVALID_DATE", "message": "date_to must be YYYY-MM-DD"}},
            )

    stmt = stmt.order_by(Billing.created_at.desc())
    result = await db.execute(stmt)
    bills = result.scalars().all()

    # Batch load names
    patient_ids = list({b.patient_id for b in bills})
    clinic_ids = list({b.clinic_id for b in bills if b.clinic_id})

    patient_names: dict[uuid.UUID, str] = {}
    if patient_ids:
        pr = await db.execute(select(User.id, User.full_name).where(User.id.in_(patient_ids)))
        patient_names = {row.id: row.full_name for row in pr.all()}

    clinic_names: dict[uuid.UUID, str] = {}
    if clinic_ids:
        cr = await db.execute(select(Clinic.id, Clinic.name).where(Clinic.id.in_(clinic_ids)))
        clinic_names = {row.id: row.name for row in cr.all()}

    data = [
        _serialize_bill(
            b,
            patient_name=patient_names.get(b.patient_id),
            clinic_name=clinic_names.get(b.clinic_id) if b.clinic_id else None,
        )
        for b in bills
    ]
    return {"data": data, "total": len(data)}


@router.get("/{bill_id}")
async def get_bill(
    bill_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a single bill by ID."""
    result = await db.execute(
        select(Billing).where(Billing.id == bill_id, Billing.deleted_at.is_(None))
    )
    bill = _get_or_raise(result.scalar_one_or_none())

    # Access control
    if current_user.role == "patient" and bill.patient_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Access denied"}},
        )

    return await _load_bill_with_names(db, bill)


@router.patch("/{bill_id}")
async def update_bill(
    bill_id: UUID,
    req: BillingUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update billing status and/or payment method. Requires doctor or admin."""
    if current_user.role not in ("doctor", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Doctor or admin access required"}},
        )

    result = await db.execute(
        select(Billing).where(Billing.id == bill_id, Billing.deleted_at.is_(None))
    )
    bill = _get_or_raise(result.scalar_one_or_none())

    if req.status is not None:
        bill.status = req.status
    if req.payment_method is not None:
        bill.payment_method = req.payment_method
    if req.notes is not None:
        bill.notes = req.notes

    await db.flush()
    await db.refresh(bill)
    return await _load_bill_with_names(db, bill)
