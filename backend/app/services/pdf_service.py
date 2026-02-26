"""PDF generation service for prescriptions."""
from datetime import datetime
from io import BytesIO
from uuid import UUID

import qrcode
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.config import settings
from app.models.doctor import Doctor
from app.models.prescription import Prescription
from app.models.user import User


def generate_qr_code(prescription_id: UUID) -> BytesIO:
    """
    Generate QR code linking to prescription.

    Args:
        prescription_id: Prescription UUID

    Returns:
        BytesIO buffer containing QR code PNG
    """
    # Construct URL to digital prescription
    qr_url = f"{settings.FRONTEND_URL}/prescriptions/{prescription_id}"

    # Create QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_url)
    qr.make(fit=True)

    # Generate image
    img = qr.make_image(fill_color='black', back_color='white')

    # Save to buffer
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer


def generate_prescription_pdf(
    prescription: Prescription,
    doctor: Doctor,
    doctor_user: User,
    patient: User,
) -> BytesIO:
    """
    Generate prescription PDF with doctor details and QR code.

    Args:
        prescription: Prescription object
        doctor: Doctor profile object
        doctor_user: User object for doctor
        patient: User object for patient

    Returns:
        BytesIO buffer containing PDF
    """
    buffer = BytesIO()

    # Create PDF document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=1.5*cm,
        bottomMargin=2*cm,
        title=f"Prescription_{prescription.id}"
    )

    # Styles
    styles = getSampleStyleSheet()

    # Custom styles
    clinic_header_style = ParagraphStyle(
        'ClinicHeader',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1a56db'),
        alignment=TA_CENTER,
        spaceAfter=6,
        fontName='Helvetica-Bold'
    )

    doctor_info_style = ParagraphStyle(
        'DoctorInfo',
        parent=styles['Normal'],
        fontSize=11,
        alignment=TA_CENTER,
        spaceAfter=3,
    )

    section_header_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.black,
        spaceAfter=6,
        spaceBefore=12,
        fontName='Helvetica-Bold'
    )

    rx_style = ParagraphStyle(
        'RxSymbol',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1a56db'),
        spaceAfter=12,
        spaceBefore=12,
    )

    body_style = styles['Normal']
    body_style.fontSize = 10

    # Story (list of flowables)
    story = []

    # === HEADER SECTION ===
    facility_name = doctor.facility_name or "Medical Clinic"
    story.append(Paragraph(facility_name.upper(), clinic_header_style))

    doctor_name = f"Dr. {doctor_user.full_name}"
    story.append(Paragraph(doctor_name, doctor_info_style))

    if doctor.specialization:
        story.append(Paragraph(doctor.specialization, doctor_info_style))

    doctor_details = f"Registration No: {doctor.license_number or 'N/A'}"
    if doctor.facility_city:
        doctor_details += f" | {doctor.facility_city}"
    story.append(Paragraph(doctor_details, doctor_info_style))

    if doctor_user.phone:
        story.append(Paragraph(f"Contact: {doctor_user.phone}", doctor_info_style))

    story.append(Spacer(1, 12))

    # Horizontal line
    line_table = Table([['']], colWidths=[17*cm])
    line_table.setStyle(TableStyle([
        ('LINEABOVE', (0, 0), (-1, 0), 1, colors.black),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 12))

    # === PATIENT INFO SECTION ===
    patient_data = [
        ['Patient Name:', patient.full_name, 'Date:', prescription.created_at.strftime('%d/%m/%Y')],
        ['Contact:', patient.phone or 'N/A', 'Prescription ID:', f"#{str(prescription.id)[:8]}"],
    ]

    patient_table = Table(patient_data, colWidths=[3*cm, 6*cm, 3*cm, 5*cm])
    patient_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(patient_table)
    story.append(Spacer(1, 12))

    # === DIAGNOSIS ===
    if prescription.diagnosis:
        story.append(Paragraph('<b>Diagnosis:</b>', body_style))
        story.append(Paragraph(prescription.diagnosis, body_style))
        story.append(Spacer(1, 12))

    # === RX SYMBOL ===
    story.append(Paragraph('℞', rx_style))

    # === MEDICINES TABLE ===
    story.append(Paragraph('<b>PRESCRIPTION</b>', section_header_style))

    # Table headers
    medicine_data = [
        ['Medicine Name', 'Dosage', 'Frequency', 'Duration', 'Instructions']
    ]

    # Add medicine rows
    medicines_list = prescription.medicines if isinstance(prescription.medicines, list) else []
    for med in medicines_list:
        medicine_name = med.get('name', 'N/A').upper()
        dosage = med.get('dosage', '')
        frequency = med.get('frequency', '')
        duration = med.get('duration', '')

        # Combine timing and notes
        instructions = []
        if med.get('timing'):
            instructions.append(med['timing'])
        if med.get('notes'):
            instructions.append(med['notes'])
        instruction_text = ', '.join(instructions) if instructions else '-'

        medicine_data.append([
            medicine_name,
            dosage,
            frequency,
            duration,
            instruction_text
        ])

    medicine_table = Table(medicine_data, colWidths=[5*cm, 2.5*cm, 3*cm, 2.5*cm, 4*cm])
    medicine_table.setStyle(TableStyle([
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e5e7eb')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),

        # Data rows
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),

        # Medicine name column bold
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),

        # Grid
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(medicine_table)
    story.append(Spacer(1, 18))

    # === NOTES ===
    if prescription.notes:
        story.append(Paragraph('<b>Additional Instructions:</b>', body_style))
        story.append(Paragraph(prescription.notes, body_style))
        story.append(Spacer(1, 18))

    # === SIGNATURE SECTION ===
    signature_data = [
        ['', ''],
        ['Signature: ____________________', ''],
        [f'Dr. {doctor_user.full_name}', ''],
    ]

    signature_table = Table(signature_data, colWidths=[10*cm, 7*cm])
    signature_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (0, -1), 10),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(signature_table)
    story.append(Spacer(1, 12))

    # === QR CODE ===
    qr_buffer = generate_qr_code(prescription.id)
    qr_image = Image(qr_buffer, width=3*cm, height=3*cm)

    qr_data = [
        ['Scan for digital copy', qr_image],
    ]
    qr_table = Table(qr_data, colWidths=[10*cm, 3*cm])
    qr_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (0, 0), 9),
        ('TEXTCOLOR', (0, 0), (0, 0), colors.grey),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(qr_table)

    # Build PDF
    doc.build(story)

    # Get PDF bytes
    buffer.seek(0)
    return buffer
