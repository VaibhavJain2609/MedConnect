"""
Encounter (visit) summary PDF endpoint

GET /api/v1/encounters/{encounter_id}/summary-pdf

- Doctors can download summaries for encounters they authored (and clinic
  owner/admin members can download summaries for their clinic's encounters).
- Patients can download summaries of their own encounters.
- Admins can download any encounter summary.
- ?download=true  → Content-Disposition: attachment (triggers browser save dialog)
- Default         → Content-Disposition: inline (renders in browser/new tab)
"""

import io
from datetime import datetime, timezone
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
from app.dependencies import get_current_user
from app.models.appointment import Appointment
from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.encounter import Encounter
from app.models.prescription import Prescription
from app.models.user import User
from app.routers.encounters import (
    _get_doctor_for_user,
    _is_clinic_admin_for_encounter,
)
from app.utils.pdf import fmt_date as _fmt_date

router = APIRouter(prefix="/api/v1/encounters", tags=["encounters-pdf"])

# Canonical labels for known vitals_snapshot keys (mirrors the doctor UI);
# unknown keys are prettified (snake_case → Title Case).
VITAL_LABELS = {
    "bp_systolic": "BP Systolic (mmHg)",
    "bp_diastolic": "BP Diastolic (mmHg)",
    "pulse": "Pulse (bpm)",
    "spo2": "SpO2 (%)",
    "temperature_c": "Temperature (°C)",
    "weight_kg": "Weight (kg)",
    "height_cm": "Height (cm)",
    "respiratory_rate": "Resp. Rate (/min)",
}

_APPOINTMENT_TYPE_LABELS = {
    "in-person": "In-person Visit",
    "teleconsult": "Teleconsult",
    "follow-up": "Follow-up Visit",
}


def _vital_label(key: str) -> str:
    if key in VITAL_LABELS:
        return VITAL_LABELS[key]
    return str(key).replace("_", " ").title()


def _build_pdf(
    *,
    encounter_id: str,
    created_at,
    visit_type: str,
    clinic_name: str | None,
    facility_name: str | None,
    facility_city: str | None,
    patient_name: str | None,
    doctor_name: str | None,
    specialization: str | None,
    subjective: str | None,
    objective: str | None,
    assessment: str | None,
    plan: str | None,
    vitals_snapshot: dict | None,
    medicines: list,
) -> bytes:
    """Render the encounter visit summary as a PDF and return raw bytes."""
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
    style_section = ParagraphStyle(
        "Section",
        parent=style_normal,
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#374151"),
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
    # Header: clinic / facility name + document title
    # -----------------------------------------------------------------------
    # All user-controlled strings interpolated into Paragraph markup are
    # XML-escaped to prevent markup injection via ReportLab's paragraph parser.
    header_name = clinic_name or facility_name
    if header_name:
        story.append(Paragraph(escape(str(header_name)), style_heading))
    if facility_city:
        story.append(Paragraph(escape(str(facility_city)), style_subheading))
    if header_name or facility_city:
        story.append(Spacer(1, 2 * mm))

    story.append(Paragraph("Visit Summary", style_subheading))
    story.append(Spacer(1, 2 * mm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#374151")))
    story.append(Spacer(1, 4 * mm))

    # -----------------------------------------------------------------------
    # Patient / Doctor / Date / Visit type row
    # -----------------------------------------------------------------------
    patient_display = escape(str(patient_name)) if patient_name else "—"
    doctor_display = f"Dr. {escape(str(doctor_name))}" if doctor_name else "—"
    if specialization:
        doctor_display += f"<br/><font color='#6B7280'>{escape(str(specialization))}</font>"

    info_table = Table(
        [
            [
                Paragraph(f'<font color="#6B7280">Patient: </font><b>{patient_display}</b>', style_normal),
                Paragraph(f'<font color="#6B7280">Date: </font><b>{_fmt_date(created_at)}</b>', style_normal),
            ],
            [
                Paragraph(f'<font color="#6B7280">Doctor: </font><b>{doctor_display}</b>', style_normal),
                Paragraph(f'<font color="#6B7280">Visit type: </font><b>{escape(visit_type)}</b>', style_normal),
            ],
        ],
        colWidths=[page_width * 0.65, page_width * 0.35],
    )
    info_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ])
    )
    story.append(info_table)
    story.append(Spacer(1, 4 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#D1D5DB")))
    story.append(Spacer(1, 4 * mm))

    # -----------------------------------------------------------------------
    # Vitals snapshot table
    # -----------------------------------------------------------------------
    if vitals_snapshot:
        story.append(Paragraph("Vitals", style_section))
        story.append(Spacer(1, 1.5 * mm))

        vital_rows = [[
            Paragraph("<b>Measurement</b>", style_bold),
            Paragraph("<b>Value</b>", style_bold),
        ]]
        for key, value in vitals_snapshot.items():
            vital_rows.append([
                Paragraph(escape(_vital_label(key)), style_normal),
                Paragraph(escape(str(value)), style_normal),
            ])

        vitals_table = Table(
            vital_rows,
            colWidths=[page_width * 0.45, page_width * 0.55],
            repeatRows=1,
        )
        vitals_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ])
        )
        story.append(vitals_table)
        story.append(Spacer(1, 4 * mm))

    # -----------------------------------------------------------------------
    # SOAP sections
    # -----------------------------------------------------------------------
    story.append(Paragraph("Clinical Notes (SOAP)", style_section))
    story.append(Spacer(1, 1.5 * mm))

    for label, text in (
        ("Subjective", subjective),
        ("Objective", objective),
        ("Assessment", assessment),
        ("Plan", plan),
    ):
        story.append(Paragraph(f"<b>{label}</b>", style_normal))
        if text:
            story.append(Paragraph(escape(str(text)).replace("\n", "<br/>"), style_normal))
        else:
            story.append(Paragraph('<font color="#9CA3AF"><i>Not recorded</i></font>', style_normal))
        story.append(Spacer(1, 2 * mm))

    # -----------------------------------------------------------------------
    # Linked prescription medicines
    # -----------------------------------------------------------------------
    if medicines:
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph("Prescription", style_section))
        story.append(Spacer(1, 1.5 * mm))

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
            brand = escape(str(med.get("brand_name") or med.get("name") or "Unknown"))
            dose = escape(str(med.get("dose") or med.get("dosage") or "—"))
            freq = escape(str(med.get("frequency") or "—"))
            dur = escape(str(med.get("duration") or "—"))
            route = med.get("route") or ""
            instr_parts = []
            if route:
                instr_parts.append(f"Route: {escape(str(route))}")
            raw_instr = med.get("instructions") or med.get("timing") or med.get("notes") or ""
            if raw_instr:
                instr_parts.append(escape(str(raw_instr)))
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

    # -----------------------------------------------------------------------
    # Footer: generated-at + record id
    # -----------------------------------------------------------------------
    story.append(Spacer(1, 6 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E5E7EB")))
    story.append(Spacer(1, 2 * mm))
    generated_at = datetime.now(timezone.utc).strftime("%d %B %Y %H:%M UTC")
    story.append(
        Paragraph(
            f"Encounter ID: {escape(encounter_id)} &nbsp;·&nbsp; Generated on {generated_at} &nbsp;·&nbsp; MedConnect",
            style_footer,
        )
    )

    doc.build(story)
    buffer.seek(0)
    return buffer.read()


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get("/{encounter_id}/summary-pdf")
async def get_encounter_summary_pdf(
    encounter_id: UUID,
    download: bool = Query(False, description="Set to true to force browser download"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate and return a PDF visit summary for a single encounter.

    Access rules — identical to GET /api/v1/encounters/{encounter_id}:
    - The authoring doctor.
    - The patient the encounter belongs to.
    - An owner/admin member of the encounter's clinic.
    - An admin.
    """
    result = await db.execute(
        select(Encounter).where(
            Encounter.id == encounter_id,
            Encounter.deleted_at.is_(None),
        )
    )
    enc = result.scalar_one_or_none()
    if enc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Encounter not found"}},
        )

    # Authorization — mirrors get_encounter exactly
    allowed = False
    if current_user.role == "admin":
        allowed = True
    elif current_user.role == "patient":
        allowed = enc.patient_id == current_user.id
    elif current_user.role == "doctor":
        doctor = await _get_doctor_for_user(db, current_user)
        if doctor is not None and enc.doctor_id == doctor.id:
            allowed = True
        elif await _is_clinic_admin_for_encounter(db, current_user, enc):
            allowed = True

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Access denied"}},
        )

    # Display names
    patient_name = (
        await db.execute(select(User.full_name).where(User.id == enc.patient_id))
    ).scalar_one_or_none()

    doctor_name = (
        await db.execute(
            select(User.full_name)
            .join(Doctor, Doctor.user_id == User.id)
            .where(Doctor.id == enc.doctor_id)
        )
    ).scalar_one_or_none()

    clinic_name = None
    if enc.clinic_id:
        clinic_name = (
            await db.execute(select(Clinic.name).where(Clinic.id == enc.clinic_id))
        ).scalar_one_or_none()

    # Doctor profile details (facility fallback + specialization)
    doctor_profile = (
        await db.execute(
            select(Doctor).where(Doctor.id == enc.doctor_id, Doctor.deleted_at.is_(None))
        )
    ).scalar_one_or_none()

    # Visit type + linked prescription via the appointment
    visit_type = "Walk-in"
    medicines: list = []
    if enc.appointment_id:
        appointment = (
            await db.execute(
                select(Appointment).where(
                    Appointment.id == enc.appointment_id,
                    Appointment.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if appointment is not None:
            visit_type = _APPOINTMENT_TYPE_LABELS.get(
                appointment.type, appointment.type.replace("-", " ").title()
            )

        # A prescription linked to the same appointment is the visit's Rx —
        # encounters and prescriptions share appointment_id as the join key.
        rx = (
            await db.execute(
                select(Prescription)
                .where(
                    Prescription.appointment_id == enc.appointment_id,
                    Prescription.deleted_at.is_(None),
                )
                .order_by(Prescription.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if rx is not None and isinstance(rx.medicines, list):
            medicines = rx.medicines

    pdf_bytes = _build_pdf(
        encounter_id=str(encounter_id),
        created_at=enc.created_at,
        visit_type=visit_type,
        clinic_name=clinic_name,
        facility_name=doctor_profile.facility_name if doctor_profile else None,
        facility_city=doctor_profile.facility_city if doctor_profile else None,
        patient_name=patient_name,
        doctor_name=doctor_name,
        specialization=doctor_profile.specialization if doctor_profile else None,
        subjective=enc.subjective,
        objective=enc.objective,
        assessment=enc.assessment,
        plan=enc.plan,
        vitals_snapshot=enc.vitals_snapshot if isinstance(enc.vitals_snapshot, dict) else None,
        medicines=medicines,
    )

    filename = f"visit-summary-{str(encounter_id)[:8]}.pdf"
    disposition = f'attachment; filename="{filename}"' if download else f'inline; filename="{filename}"'

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": disposition},
    )
