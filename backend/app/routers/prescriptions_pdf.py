"""
Prescription PDF Generation Endpoint

GET /api/v1/prescriptions/{prescription_id}/pdf

- Doctors can download PDFs for prescriptions they created.
- Patients can download PDFs for their own prescriptions.
- ?download=true  → Content-Disposition: attachment (triggers browser save dialog)
- Default         → Content-Disposition: inline (renders in browser/new tab)
"""

import io
from datetime import date as _date
from uuid import UUID

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
from app.dependencies import get_current_user
from app.models.doctor import Doctor
from app.models.medical_record import MedicalRecord
from app.models.prescription import Prescription
from app.models.user import User

router = APIRouter(prefix="/api/v1/prescriptions", tags=["prescriptions-pdf"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_date(value) -> str:
    """Format a date or datetime to a readable Indian locale string."""
    if value is None:
        return "—"
    if hasattr(value, "date"):
        value = value.date()
    return value.strftime("%d %B %Y")


def _build_pdf(
    *,
    prescription_id: str,
    medicines: list,
    diagnosis: str | None,
    notes: str | None,
    valid_until,
    created_at,
    patient_name: str | None,
    doctor_name: str | None,
    specialization: str | None,
    license_number: str | None,
    facility_name: str | None,
    facility_city: str | None,
) -> bytes:
    """Render the prescription as a PDF and return raw bytes."""
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
    style_subheading = ParagraphStyle(
        "SubHeading",
        parent=base_styles["Normal"],
        fontSize=10,
        leading=14,
        fontName="Helvetica",
        alignment=1,
    )
    style_rx = ParagraphStyle(
        "Rx",
        parent=base_styles["Normal"],
        fontSize=20,
        leading=24,
        fontName="Helvetica-BoldOblique",
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

    story = []

    # -----------------------------------------------------------------------
    # Header: facility / clinic name
    # -----------------------------------------------------------------------
    if facility_name:
        story.append(Paragraph(facility_name, style_heading))
    if facility_city:
        story.append(Paragraph(facility_city, style_subheading))
    if facility_name or facility_city:
        story.append(Spacer(1, 3 * mm))

    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#374151")))
    story.append(Spacer(1, 3 * mm))

    # -----------------------------------------------------------------------
    # Doctor info row
    # -----------------------------------------------------------------------
    doctor_display = f"Dr. {doctor_name}" if doctor_name else "—"
    doctor_left = f"<b>{doctor_display}</b>"
    if specialization:
        doctor_left += f"<br/>{specialization}"

    doctor_right = ""
    if license_number:
        doctor_right = f"Reg. No.: {license_number}"

    doctor_table = Table(
        [[Paragraph(doctor_left, style_normal), Paragraph(doctor_right, style_label)]],
        colWidths=[page_width * 0.65, page_width * 0.35],
    )
    doctor_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ])
    )
    story.append(doctor_table)
    story.append(Spacer(1, 3 * mm))

    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#D1D5DB")))
    story.append(Spacer(1, 4 * mm))

    # -----------------------------------------------------------------------
    # Patient & Date row
    # -----------------------------------------------------------------------
    patient_display = patient_name or "—"
    pt_date_table = Table(
        [[
            Paragraph(f'<font color="#6B7280">Patient: </font><b>{patient_display}</b>', style_normal),
            Paragraph(f'<font color="#6B7280">Date: </font><b>{_fmt_date(created_at)}</b>', style_normal),
        ]],
        colWidths=[page_width * 0.65, page_width * 0.35],
    )
    pt_date_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ])
    )
    story.append(pt_date_table)
    story.append(Spacer(1, 5 * mm))

    # -----------------------------------------------------------------------
    # Rx symbol
    # -----------------------------------------------------------------------
    story.append(Paragraph("Rx", style_rx))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#D1D5DB")))
    story.append(Spacer(1, 4 * mm))

    # -----------------------------------------------------------------------
    # Medicines table
    # -----------------------------------------------------------------------
    if medicines:
        med_header = [
            Paragraph("<b>#</b>", style_bold),
            Paragraph("<b>Medicine</b>", style_bold),
            Paragraph("<b>Dose</b>", style_bold),
            Paragraph("<b>Frequency</b>", style_bold),
            Paragraph("<b>Duration</b>", style_bold),
            Paragraph("<b>Instructions</b>", style_bold),
        ]
        med_rows = [med_header]

        for idx, med in enumerate(medicines, start=1):
            brand = med.get("brand_name") or med.get("name") or "Unknown"
            dose = med.get("dose") or med.get("dosage") or "—"
            freq = med.get("frequency") or "—"
            dur = med.get("duration") or "—"
            route = med.get("route") or ""
            instr_parts = []
            if route:
                instr_parts.append(f"Route: {route}")
            raw_instr = med.get("instructions") or med.get("timing") or med.get("notes") or ""
            if raw_instr:
                instr_parts.append(raw_instr)
            instr = " | ".join(instr_parts) if instr_parts else "—"

            med_rows.append([
                Paragraph(str(idx), style_normal),
                Paragraph(f"<b>{brand}</b>", style_normal),
                Paragraph(dose, style_normal),
                Paragraph(freq, style_normal),
                Paragraph(dur, style_normal),
                Paragraph(instr, style_normal),
            ])

        col_widths = [
            page_width * 0.04,
            page_width * 0.25,
            page_width * 0.12,
            page_width * 0.16,
            page_width * 0.13,
            page_width * 0.30,
        ]
        med_table = Table(med_rows, colWidths=col_widths, repeatRows=1)
        med_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ])
        )
        story.append(med_table)
    else:
        story.append(Paragraph("No medicines listed.", style_label))

    story.append(Spacer(1, 5 * mm))

    # -----------------------------------------------------------------------
    # Diagnosis & Notes
    # -----------------------------------------------------------------------
    if diagnosis:
        story.append(Paragraph(f"<b>Diagnosis:</b> {diagnosis}", style_normal))
        story.append(Spacer(1, 2 * mm))
    if notes:
        story.append(Paragraph(f"<b>Notes:</b> {notes}", style_normal))
        story.append(Spacer(1, 2 * mm))
    if valid_until:
        story.append(Paragraph(f"<b>Valid until:</b> {_fmt_date(valid_until)}", style_normal))
        story.append(Spacer(1, 2 * mm))

    story.append(Spacer(1, 6 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#D1D5DB")))
    story.append(Spacer(1, 4 * mm))

    # -----------------------------------------------------------------------
    # Signature block (right-aligned)
    # -----------------------------------------------------------------------
    sig_text = f"Dr. {doctor_name}" if doctor_name else ""
    sig_table = Table(
        [[Paragraph(sig_text, style_bold)]],
        colWidths=[page_width],
    )
    sig_table.setStyle(
        TableStyle([
            ("ALIGN", (0, 0), (0, 0), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ])
    )
    story.append(sig_table)
    story.append(Spacer(1, 8 * mm))

    sig_line_table = Table(
        [[Paragraph('<font color="#9CA3AF">Signature</font>', style_footer)]],
        colWidths=[50 * mm],
    )
    sig_line_table.setStyle(
        TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("LINEABOVE", (0, 0), (-1, -1), 0.5, colors.HexColor("#9CA3AF")),
        ])
    )

    # Right-align the sig line by wrapping in outer table
    outer_sig = Table(
        [["", sig_line_table]],
        colWidths=[page_width - 50 * mm, 50 * mm],
    )
    outer_sig.setStyle(
        TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ])
    )
    story.append(outer_sig)
    story.append(Spacer(1, 6 * mm))

    # -----------------------------------------------------------------------
    # Footer
    # -----------------------------------------------------------------------
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E5E7EB")))
    story.append(Spacer(1, 2 * mm))
    story.append(
        Paragraph(
            f"Prescription ID: {prescription_id} &nbsp;·&nbsp; Generated on {_fmt_date(_date.today())} &nbsp;·&nbsp; MedConnect",
            style_footer,
        )
    )

    doc.build(story)
    buffer.seek(0)
    return buffer.read()


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get("/{prescription_id}/pdf")
async def get_prescription_pdf(
    prescription_id: UUID,
    download: bool = Query(False, description="Set to true to force browser download"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate and return a PDF for a single prescription.

    Access rules:
    - Doctors can access prescriptions they created.
    - Patients can access their own prescriptions.
    - Admins can access any prescription.
    """

    # Fetch the prescription, its record and patient name in one query
    stmt = (
        select(Prescription, MedicalRecord, User.full_name.label("patient_name"))
        .join(MedicalRecord, MedicalRecord.id == Prescription.record_id)
        .outerjoin(User, User.id == Prescription.patient_id)
        .where(
            Prescription.id == prescription_id,
            Prescription.deleted_at.is_(None),
            MedicalRecord.deleted_at.is_(None),
        )
    )
    result = await db.execute(stmt)
    row = result.first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Prescription not found"}},
        )

    prescription, record, patient_name = row

    # Authorization check
    if current_user.role == "patient":
        if prescription.patient_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "FORBIDDEN", "message": "Access denied"}},
            )
    elif current_user.role == "doctor":
        # Fetch the doctor profile for this user
        doc_result = await db.execute(
            select(Doctor).where(
                Doctor.user_id == current_user.id,
                Doctor.deleted_at.is_(None),
            )
        )
        doctor = doc_result.scalar_one_or_none()
        if not doctor or record.doctor_id != doctor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "FORBIDDEN", "message": "Access denied"}},
            )
    # admin role: no additional check required

    # Fetch the doctor's profile and user for display details
    doc_result = await db.execute(
        select(Doctor).where(Doctor.id == prescription.doctor_id, Doctor.deleted_at.is_(None))
    )
    doctor_profile = doc_result.scalar_one_or_none()

    doctor_user = None
    if doctor_profile:
        du_result = await db.execute(select(User).where(User.id == doctor_profile.user_id))
        doctor_user = du_result.scalar_one_or_none()

    pdf_bytes = _build_pdf(
        prescription_id=str(prescription_id),
        medicines=prescription.medicines if isinstance(prescription.medicines, list) else [],
        diagnosis=prescription.diagnosis,
        notes=prescription.notes,
        valid_until=prescription.valid_until,
        created_at=prescription.created_at,
        patient_name=patient_name,
        doctor_name=doctor_user.full_name if doctor_user else None,
        specialization=doctor_profile.specialization if doctor_profile else None,
        license_number=doctor_profile.license_number if doctor_profile else None,
        facility_name=doctor_profile.facility_name if doctor_profile else None,
        facility_city=doctor_profile.facility_city if doctor_profile else None,
    )

    filename = f"prescription-{str(prescription_id)[:8]}.pdf"
    disposition = f'attachment; filename="{filename}"' if download else f'inline; filename="{filename}"'

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": disposition},
    )
