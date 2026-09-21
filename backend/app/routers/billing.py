import io
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_doctor, get_current_user, require_admin
from app.models.appointment import Appointment
from app.models.billing import BILLING_STATUSES, PAYMENT_METHODS, Billing, BillingItem
from app.models.clinic import Clinic, ClinicMembership
from app.models.doctor import Doctor
from app.models.user import User
from app.schemas.billing import BillingCreate, BillingListResponse, BillingResponse, BillingUpdate
from app.utils.pdf import fmt_date as _fmt_date

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
        # `items` is a selectin-loaded relationship — populated on every
        # Billing select, and explicitly assigned on the create path.
        "items": [
            {
                "id": str(item.id),
                "description": item.description,
                "quantity": str(item.quantity),
                "unit_amount": str(item.unit_amount),
                "amount": str(item.amount),
            }
            for item in (bill.items or [])
        ],
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


async def _get_member_clinic_ids(db: AsyncSession, user_id: uuid.UUID) -> set[uuid.UUID]:
    """Return IDs of clinics where the user holds an active membership."""
    result = await db.execute(
        select(ClinicMembership.clinic_id).where(
            ClinicMembership.user_id == user_id,
            ClinicMembership.is_active.is_(True),
            ClinicMembership.deleted_at.is_(None),
        )
    )
    return {row[0] for row in result.all()}


async def _require_bill_clinic_access(db: AsyncSession, user: User, bill: Billing) -> None:
    """
    Doctors may only touch bills scoped to a clinic where they hold an active
    membership. Bills without a clinic_id are inaccessible to doctors.
    """
    member_clinic_ids = await _get_member_clinic_ids(db, user.id)
    if bill.clinic_id is None or bill.clinic_id not in member_clinic_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Access denied"}},
        )


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

    # Doctors can only create bills for clinics where they hold a membership
    if current_user.role == "doctor":
        if req.clinic_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "VALIDATION_ERROR", "message": "clinic_id is required"}},
            )
        member_clinic_ids = await _get_member_clinic_ids(db, current_user.id)
        if req.clinic_id not in member_clinic_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "NOT_CLINIC_MEMBER", "message": "Not a member of this clinic"}},
            )

    bill = Billing(
        id=uuid.uuid4(),
        patient_id=req.patient_id,
        clinic_id=req.clinic_id,
        appointment_id=req.appointment_id,
        amount=req.amount if req.amount is not None else Decimal(0),
        status="pending",
        notes=req.notes,
    )

    # Line items: server computes each line amount and the bill total —
    # the model has no tax column, so billing.amount = sum(item amounts)
    # and any client-supplied `amount` is ignored when items are given.
    if req.items:
        line_items: list[BillingItem] = []
        total = Decimal(0)
        for it in req.items:
            line_amount = (it.quantity * it.unit_amount).quantize(Decimal("0.01"))
            total += line_amount
            line_items.append(
                BillingItem(
                    id=uuid.uuid4(),
                    description=it.description,
                    quantity=it.quantity,
                    unit_amount=it.unit_amount,
                    amount=line_amount,
                )
            )
        bill.items = line_items
        bill.amount = total.quantize(Decimal("0.01"))

    db.add(bill)
    await db.flush()
    await db.refresh(bill)

    # Audit the invoice creation — ids/status/amount only, no notes text.
    from app.services.audit_service import log_change
    await log_change(
        db=db,
        table_name="billing",
        record_id=bill.id,
        action="INSERT",
        old_values=None,
        new_values={
            "patient_id": str(bill.patient_id),
            "clinic_id": str(bill.clinic_id) if bill.clinic_id else None,
            "appointment_id": str(bill.appointment_id) if bill.appointment_id else None,
            "status": bill.status,
            "amount": str(bill.amount),
        },
    )

    return await _load_bill_with_names(db, bill)


@router.get("")
async def list_bills(
    clinic_id: UUID | None = Query(None),
    patient_id: UUID | None = Query(None),
    bill_status: str | None = Query(None, alias="status"),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    limit: int = Query(100, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List bills with optional filters.
    - admin: can see all bills
    - doctor: can only see bills for clinics where they hold a membership
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
        # Scope strictly to clinics where the doctor holds a membership
        member_clinic_ids = await _get_member_clinic_ids(db, current_user.id)
        if clinic_id:
            if clinic_id not in member_clinic_ids:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={"error": {"code": "NOT_CLINIC_MEMBER", "message": "Not a member of this clinic"}},
                )
            stmt = stmt.where(Billing.clinic_id == clinic_id)
        else:
            stmt = stmt.where(Billing.clinic_id.in_(member_clinic_ids))
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

    stmt = stmt.order_by(Billing.created_at.desc()).limit(limit)
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
    elif current_user.role == "doctor":
        await _require_bill_clinic_access(db, current_user, bill)

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

    # Doctors can only update bills scoped to their member clinics
    if current_user.role == "doctor":
        await _require_bill_clinic_access(db, current_user, bill)

    old_status = bill.status
    old_payment_method = bill.payment_method

    if req.status is not None:
        bill.status = req.status
    if req.payment_method is not None:
        bill.payment_method = req.payment_method
    if req.notes is not None:
        bill.notes = req.notes

    await db.flush()
    await db.refresh(bill)

    # Audit status/payment-method transitions (old -> new). Notes content is
    # never logged — only that the field was touched.
    old_values: dict = {}
    new_values: dict = {}
    if req.status is not None:
        old_values["status"] = old_status
        new_values["status"] = bill.status
    if req.payment_method is not None:
        old_values["payment_method"] = old_payment_method
        new_values["payment_method"] = bill.payment_method
    if req.notes is not None:
        new_values["notes_updated"] = True
    if old_values or new_values:
        from app.services.audit_service import log_change
        await log_change(
            db=db,
            table_name="billing",
            record_id=bill.id,
            action="UPDATE",
            old_values=old_values or None,
            new_values=new_values or None,
        )

    return await _load_bill_with_names(db, bill)


# ─── Receipt / invoice PDF ────────────────────────────────────────────────────
# Rendering pattern mirrors routers/prescriptions_pdf.py: A4 SimpleDocTemplate,
# Helvetica styles, all user-controlled strings XML-escaped before being
# interpolated into Paragraph markup. fmt_date lives in app.utils.pdf (shared).

def _fmt_amount(value, currency: str) -> str:
    """Format a monetary amount with its currency code (e.g. 'INR 1,250.00')."""
    try:
        return f"{currency} {float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value)


def _item_field(item, *names: str):
    """Read the first non-None field from a dict or an ORM row.

    ``bill.items`` may be a JSONB-style list of dicts (legacy tolerance) or a
    selectin-loaded list of ``BillingItem`` objects — accept both.
    """
    if isinstance(item, dict):
        for name in names:
            if item.get(name) is not None:
                return item[name]
    else:
        for name in names:
            value = getattr(item, name, None)
            if value is not None:
                return value
    return None


def _normalize_line_items(bill: Billing) -> list[dict]:
    """
    Normalize the bill's line items.

    ``Billing.items`` is the ``billing_items`` relationship (BillingItem ORM
    rows); a JSONB-style list of dicts is also tolerated. Accepts the common
    key variants (description/name, quantity/qty, unit_price/unit_amount/
    price, amount). Falls back to a single line derived from the bill's
    notes + amount when no itemized list exists.
    """
    raw_items = getattr(bill, "items", None)
    line_items: list[dict] = []
    if isinstance(raw_items, list):
        for item in raw_items:
            if not isinstance(item, dict) and not isinstance(item, BillingItem):
                continue
            description = _item_field(item, "description", "name") or "Item"
            try:
                qty = float(_item_field(item, "quantity", "qty") or 1)
            except (TypeError, ValueError):
                qty = 1
            unit_price = _item_field(item, "unit_price", "unit_amount", "price")
            if unit_price is None:
                unit_price = _item_field(item, "amount")
            try:
                unit_price = float(unit_price) if unit_price is not None else 0.0
            except (TypeError, ValueError):
                unit_price = 0.0
            amount = _item_field(item, "amount")
            try:
                amount = float(amount) if amount is not None else qty * unit_price
            except (TypeError, ValueError):
                amount = qty * unit_price
            line_items.append(
                {"description": str(description), "quantity": qty, "unit_price": unit_price, "amount": amount}
            )

    if not line_items:
        description = bill.notes or "Medical services"
        line_items = [{"description": description, "quantity": 1, "unit_price": bill.amount, "amount": bill.amount}]

    return line_items


def _watermark(text: str):
    """Return an onPage callback that stamps a light diagonal watermark."""

    def _draw(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica-Bold", 72)
        canvas.setFillColor(colors.HexColor("#E5E7EB"))
        canvas.translate(A4[0] / 2, A4[1] / 2)
        canvas.rotate(45)
        canvas.drawCentredString(0, 0, text)
        canvas.restoreState()

    return _draw


def _build_receipt_pdf(
    *,
    bill: Billing,
    line_items: list[dict],
    currency: str,
    patient_name: str | None,
    clinic_name: str | None,
    doctor_name: str | None,
    paid_at,
) -> bytes:
    """Render the bill as a receipt/invoice PDF and return raw bytes."""
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    base_styles = getSampleStyleSheet()

    style_normal = ParagraphStyle(
        "Normal",
        parent=base_styles["Normal"],
        fontSize=9,
        leading=13,
        fontName="Helvetica",
    )
    style_bold = ParagraphStyle(
        "Bold",
        parent=style_normal,
        fontName="Helvetica-Bold",
    )
    style_heading = ParagraphStyle(
        "Heading",
        parent=base_styles["Normal"],
        fontSize=14,
        leading=18,
        fontName="Helvetica-Bold",
        alignment=1,  # centre
    )
    style_doc_title = ParagraphStyle(
        "DocTitle",
        parent=base_styles["Normal"],
        fontSize=12,
        leading=16,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#4169E1"),
        alignment=1,
    )
    style_label = ParagraphStyle(
        "Label",
        parent=style_normal,
        textColor=colors.HexColor("#6B7280"),
    )
    style_footer = ParagraphStyle(
        "Footer",
        parent=style_normal,
        fontSize=8,
        textColor=colors.HexColor("#9CA3AF"),
        alignment=1,
    )

    page_width = A4[0] - 40 * mm  # usable width
    is_paid = bill.status == "paid"
    doc_word = "RECEIPT" if is_paid else "INVOICE"

    story = []

    # -----------------------------------------------------------------------
    # Header: clinic name + document type
    # -----------------------------------------------------------------------
    if clinic_name:
        story.append(Paragraph(escape(str(clinic_name)), style_heading))
    else:
        story.append(Paragraph("MedConnect", style_heading))
    story.append(Paragraph(doc_word, style_doc_title))
    story.append(Spacer(1, 3 * mm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#374151")))
    story.append(Spacer(1, 4 * mm))

    # -----------------------------------------------------------------------
    # Bill-to / meta row
    # -----------------------------------------------------------------------
    patient_display = escape(str(patient_name)) if patient_name else "—"
    doctor_display = f"Dr. {escape(str(doctor_name))}" if doctor_name else "—"
    meta_left = (
        f'<font color="#6B7280">Billed to: </font><b>{patient_display}</b>'
        f'<br/><font color="#6B7280">Doctor: </font>{doctor_display}'
    )
    meta_right = (
        f'<font color="#6B7280">Date: </font><b>{_fmt_date(bill.created_at)}</b>'
        f'<br/><font color="#6B7280">Status: </font><b>{escape(str(bill.status).capitalize())}</b>'
    )
    meta_table = Table(
        [[Paragraph(meta_left, style_normal), Paragraph(meta_right, style_normal)]],
        colWidths=[page_width * 0.6, page_width * 0.4],
    )
    meta_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ])
    )
    story.append(meta_table)
    story.append(Spacer(1, 5 * mm))

    # -----------------------------------------------------------------------
    # Line items table
    # -----------------------------------------------------------------------
    rows = [[
        Paragraph("<b>#</b>", style_bold),
        Paragraph("<b>Description</b>", style_bold),
        Paragraph("<b>Qty</b>", style_bold),
        Paragraph("<b>Unit Price</b>", style_bold),
        Paragraph("<b>Amount</b>", style_bold),
    ]]
    for idx, item in enumerate(line_items, start=1):
        qty = item["quantity"]
        qty_display = f"{qty:g}" if isinstance(qty, (int, float)) else str(qty)
        rows.append([
            Paragraph(str(idx), style_normal),
            Paragraph(escape(str(item["description"])), style_normal),
            Paragraph(qty_display, style_normal),
            Paragraph(escape(_fmt_amount(item["unit_price"], currency)), style_normal),
            Paragraph(escape(_fmt_amount(item["amount"], currency)), style_normal),
        ])

    # Totals: subtotal = sum of line-item amounts; the bill's `amount` column
    # is the authoritative total (the model has no dedicated tax column, so a
    # "Tax / adjustments" row is only emitted when the two differ).
    try:
        subtotal = sum(float(i["amount"]) for i in line_items)
    except (TypeError, ValueError):
        subtotal = float(bill.amount)
    total = float(bill.amount)
    tax_delta = total - subtotal

    rows.append([
        Paragraph("", style_normal),
        Paragraph("<b>Subtotal</b>", style_bold),
        Paragraph("", style_normal),
        Paragraph("", style_normal),
        Paragraph(f"<b>{escape(_fmt_amount(subtotal, currency))}</b>", style_bold),
    ])
    if abs(tax_delta) > 0.005:
        rows.append([
            Paragraph("", style_normal),
            Paragraph("Tax / adjustments", style_normal),
            Paragraph("", style_normal),
            Paragraph("", style_normal),
            Paragraph(escape(_fmt_amount(tax_delta, currency)), style_normal),
        ])
    rows.append([
        Paragraph("", style_normal),
        Paragraph("<b>Total</b>", style_bold),
        Paragraph("", style_normal),
        Paragraph("", style_normal),
        Paragraph(f"<b>{escape(_fmt_amount(total, currency))}</b>", style_bold),
    ])

    items_table = Table(
        rows,
        colWidths=[
            page_width * 0.05,
            page_width * 0.47,
            page_width * 0.08,
            page_width * 0.20,
            page_width * 0.20,
        ],
        repeatRows=1,
    )
    items_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F9FAFB")),
            ("LINEABOVE", (0, -1), (-1, -1), 1, colors.HexColor("#374151")),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])
    )
    story.append(items_table)
    story.append(Spacer(1, 5 * mm))

    # -----------------------------------------------------------------------
    # Payment details
    # -----------------------------------------------------------------------
    if bill.payment_method:
        story.append(
            Paragraph(
                f"<b>Payment method:</b> {escape(str(bill.payment_method).capitalize())}",
                style_normal,
            )
        )
        story.append(Spacer(1, 2 * mm))
    if is_paid and paid_at:
        story.append(
            Paragraph(f"<b>Paid on:</b> {_fmt_date(paid_at)}", style_normal)
        )
        story.append(Spacer(1, 2 * mm))
    # Skip notes when they were already rendered as the fallback line description
    notes_as_line = len(line_items) == 1 and line_items[0]["description"] == bill.notes
    if bill.notes and not notes_as_line:
        story.append(Paragraph(f"<b>Notes:</b> {escape(str(bill.notes))}", style_normal))
        story.append(Spacer(1, 2 * mm))

    story.append(Spacer(1, 6 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E5E7EB")))
    story.append(Spacer(1, 2 * mm))
    story.append(
        Paragraph(
            f"Bill ID: {bill.id} &nbsp;·&nbsp; Generated on {_fmt_date(date.today())} &nbsp;·&nbsp; MedConnect",
            style_footer,
        )
    )

    stamp = _watermark(doc_word)
    doc.build(story, onFirstPage=stamp, onLaterPages=stamp)
    buffer.seek(0)
    return buffer.read()


@router.get("/{bill_id}/receipt")
async def get_bill_receipt(
    bill_id: str,
    download: bool = Query(False, description="Set to true to force browser download"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate and return a PDF receipt (paid bills) or invoice (unpaid bills).

    Access rules — identical to GET /{bill_id}:
    - Patients can access their own bills.
    - Doctors can access bills for clinics where they hold a membership.
    - Admins can access any bill.

    ``bill_id`` is parsed manually so that a malformed UUID returns 404
    (bill not found) rather than a 422 validation error.
    """
    try:
        bill_uuid = UUID(bill_id)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Bill not found"}},
        )

    result = await db.execute(
        select(Billing).where(Billing.id == bill_uuid, Billing.deleted_at.is_(None))
    )
    bill = _get_or_raise(result.scalar_one_or_none())

    # Access control — mirrors get_bill exactly
    if current_user.role == "patient" and bill.patient_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Access denied"}},
        )
    elif current_user.role == "doctor":
        await _require_bill_clinic_access(db, current_user, bill)

    # Display names
    patient_name = (
        await db.execute(select(User.full_name).where(User.id == bill.patient_id))
    ).scalar_one_or_none()

    clinic_name = None
    if bill.clinic_id:
        clinic_name = (
            await db.execute(select(Clinic.name).where(Clinic.id == bill.clinic_id))
        ).scalar_one_or_none()

    # Doctor name via the linked appointment (bills have no direct doctor FK)
    doctor_name = None
    if bill.appointment_id:
        doctor_name = (
            await db.execute(
                select(User.full_name)
                .select_from(Appointment)
                .join(Doctor, Doctor.id == Appointment.doctor_id)
                .join(User, User.id == Doctor.user_id)
                .where(Appointment.id == bill.appointment_id)
            )
        ).scalar_one_or_none()

    currency = getattr(bill, "currency", None) or "INR"
    # Prefer a dedicated paid_at column when present; otherwise fall back to
    # the last update time for paid bills.
    paid_at = getattr(bill, "paid_at", None) or (bill.updated_at if bill.status == "paid" else None)

    pdf_bytes = _build_receipt_pdf(
        bill=bill,
        line_items=_normalize_line_items(bill),
        currency=currency,
        patient_name=patient_name,
        clinic_name=clinic_name,
        doctor_name=doctor_name,
        paid_at=paid_at,
    )

    kind = "receipt" if bill.status == "paid" else "invoice"
    filename = f"{kind}-{str(bill_id)[:8]}.pdf"
    disposition = f'attachment; filename="{filename}"' if download else f'inline; filename="{filename}"'

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": disposition},
    )
