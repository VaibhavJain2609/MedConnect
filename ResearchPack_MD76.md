# ResearchPack: Prescription PDF Generation with QR Code (MD-76)

**Date**: 2026-02-26
**Epic**: Prescription Enhancement
**Ticket**: MD-76
**Researcher**: @chief-architect

---

## Executive Summary

This ResearchPack documents the findings for implementing prescription PDF generation with doctor details and QR codes for the MedConnect healthcare platform. The solution will use **ReportLab** for PDF generation and **python-qrcode** for QR code creation, enabling doctors to generate professional, standards-compliant prescription PDFs.

**Quality Score**: 85/100
- Research Completeness: 90/100
- Version Accuracy: 85/100
- Code Examples: 85/100
- Integration Clarity: 80/100

---

## 1. Technology Selection

### 1.1 PDF Generation Library: ReportLab

**Selected**: ReportLab v4.4.10+ (latest stable)

**Rationale**:
- **Programmatic Control**: Low-level API provides precise control over PDF layout, essential for medical documents
- **Table Support**: Built-in table functionality perfect for medicine lists
- **Medical Document Suitability**: Used extensively for invoices, reports, and structured documents
- **Performance**: Fast PDF generation without browser engine overhead
- **Production Ready**: Mature library (20+ years), widely used in healthcare and enterprise

**Alternatives Considered**:
- **WeasyPrint**: HTML/CSS to PDF - rejected because requires HTML templates, slower for data-heavy documents, struggles with complex tables
- **FPDF**: Too basic, lacks advanced table support
- **PyPDF2**: Merging/reading only, not generation

**Installation**:
```bash
pip install reportlab==4.4.10
```

### 1.2 QR Code Library: python-qrcode

**Selected**: qrcode v7.4+ with Pillow support

**Rationale**:
- **Pure Python**: No external dependencies except Pillow
- **ReportLab Compatible**: Can embed PIL images directly
- **Customizable**: Error correction levels, size, colors
- **Well Maintained**: Active development, 10K+ stars on GitHub
- **Simple API**: Quick implementation

**Installation**:
```bash
pip install qrcode[pil]==7.4.2
```

**Why not PyQRCode**: Discontinued, less flexible

---

## 2. Indian Medical Prescription Standards

### 2.1 Regulatory Requirements

Based on Medical Council of India and state medical council guidelines:

**Prescription Format Standards**:
- **Size**: Minimum A5 (14x21cm) or 11x11cm
- **Content**: Generic medicine names in CAPITAL LETTERS
- **Legibility**: Clear, readable fonts (avoid handwriting in digital)
- **Mandatory Fields**:
  - Doctor's name, qualification, registration number
  - Facility/clinic name and address
  - Patient name, age, gender
  - Date of prescription
  - Rx symbol (℞)
  - Medicine name, strength, dosage, duration
  - Total quantity to be supplied
  - Doctor's signature

**Best Practices**:
- Rational prescription (evidence-based)
- Generic names preferred over brand names
- Clear dosage instructions
- No overwriting or alterations

### 2.2 Digital Prescription Additions

For digital/PDF prescriptions:
- QR code linking to digital record (enhances verification)
- Unique prescription ID (audit trail)
- Timestamp (creation date/time)

**Sources**:
- [Maharashtra Medical Council Prescription Format](https://maharashtramedicalcouncil.in/Files/PRESCRIPTION%20FORMAT%20FOR%20REGISTRATION%20MEDICAL%20PRACTITIONERS.pdf)
- [Medical Council of India Model Format](https://mcimindia.co.in/Files/Announcements_07072015_Draft%20of%20Model%20Prescription%20Format.pdf)
- [ESIC SOP for Prescription](https://esic.gov.in/attachments/circularfile/5908ac7c71a73d8fe977f930803341ef.pdf)

---

## 3. Existing Codebase Analysis

### 3.1 Prescription Data Model

**File**: `/backend/app/models/prescription.py`

```python
class Prescription(Base):
    id: UUID                          # Prescription ID
    record_id: UUID                   # Links to medical record
    doctor_id: UUID                   # Doctor who prescribed
    patient_id: UUID                  # Patient receiving prescription
    medicines: dict (JSONB)           # List of medicine items
    diagnosis: str | None             # Clinical diagnosis
    notes: str | None                 # Additional instructions
    valid_until: date | None          # Prescription validity
    created_at: datetime              # Timestamp
```

**Medicine Item Schema** (`/backend/app/schemas/prescription.py`):
```python
class MedicineItem(BaseModel):
    name: str                         # Medicine name
    salt: str | None                  # Generic salt/composition
    dosage: str                       # e.g., "500mg"
    frequency: str                    # e.g., "twice daily"
    duration: str                     # e.g., "5 days"
    timing: str | None                # e.g., "after food"
    notes: str | None                 # Additional instructions
```

### 3.2 Doctor Data Model

**File**: `/backend/app/models/doctor.py`

```python
class Doctor(Base):
    id: UUID
    user_id: UUID                     # Links to User table
    specialization: str | None        # e.g., "General Physician"
    license_number: str | None        # Medical registration number
    facility_name: str | None         # Clinic/hospital name
    facility_city: str | None         # Location
    verified: bool                    # Verification status

    # Relationship
    user: User                        # Contains full_name, email, phone
```

### 3.3 User Data Model

**File**: `/backend/app/models/user.py`

```python
class User(Base):
    id: UUID
    email: str | None
    phone: str | None
    full_name: str                    # Patient/Doctor name
    role: str                         # "patient", "doctor", "admin"
```

### 3.4 Existing API Endpoints

**Create Prescription**: `POST /api/v1/doctors/prescriptions`
- Returns: PrescriptionResponse with all fields
- Already implemented in `/backend/app/routers/doctors.py`

**Get Patient Prescriptions**: `GET /api/v1/patients/prescriptions`
- Implemented in `/backend/app/routers/patients.py` (assumed)

**Missing**: PDF download endpoint - **TO BE IMPLEMENTED**

### 3.5 Test Infrastructure

**File**: `/backend/tests/test_prescriptions.py`
- Uses pytest + AsyncClient
- Helper: `create_test_token(sub, email, name, roles)`
- Existing tests: create prescription, patient timeline, patient prescriptions endpoint

**Test Pattern**:
```python
async def test_example(client: AsyncClient):
    doctor_token = create_test_token(...)
    response = await client.post("/api/v1/doctors/prescriptions", ...)
    assert response.status_code == 201
```

---

## 4. ReportLab Implementation Guide

### 4.1 Core Concepts

**Canvas vs Flowables**:
- **Canvas**: Low-level drawing (x, y coordinates) - good for fixed layouts
- **Flowables**: High-level objects (Paragraph, Table, Image) - good for dynamic content
- **Recommended**: Use **SimpleDocTemplate** + **Flowables** for maintainability

### 4.2 Essential Imports

```python
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, Image, PageBreak
)
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
```

### 4.3 Page Setup

```python
from io import BytesIO

# Create PDF in memory (for HTTP response)
buffer = BytesIO()
doc = SimpleDocTemplate(
    buffer,
    pagesize=A4,
    rightMargin=2*cm,
    leftMargin=2*cm,
    topMargin=2*cm,
    bottomMargin=2*cm
)

# A4 size: 210mm x 297mm (8.27" x 11.69")
```

### 4.4 Table Creation (Medicine List)

```python
# Medicine data
data = [
    ['Medicine', 'Dosage', 'Frequency', 'Duration', 'Instructions'],
    ['Amoxicillin 500mg', '500mg', '3 times daily', '5 days', 'After food'],
]

# Create table
table = Table(data, colWidths=[5*cm, 2*cm, 3*cm, 2*cm, 3*cm])

# Style table
table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, 0), 10),
    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
    ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
]))
```

### 4.5 Text Styling

```python
styles = getSampleStyleSheet()

# Custom styles
header_style = ParagraphStyle(
    'CustomHeader',
    parent=styles['Heading1'],
    fontSize=16,
    textColor=colors.HexColor('#1a56db'),
    spaceAfter=12,
    alignment=TA_CENTER
)

body_style = styles['Normal']
```

### 4.6 Building the Document

```python
story = []  # List of flowables

# Add elements
story.append(Paragraph("Clinic Name", header_style))
story.append(Spacer(1, 12))  # 12pt vertical space
story.append(table)

# Generate PDF
doc.build(story)

# Get PDF bytes
pdf_bytes = buffer.getvalue()
buffer.close()
```

**Sources**:
- [ReportLab User Guide](https://www.reportlab.com/docs/reportlab-userguide.pdf)
- [ReportLab Documentation](https://docs.reportlab.com/)
- [Python Assets - Create PDFs with ReportLab](https://pythonassets.com/posts/create-pdf-documents-in-python-with-reportlab/)

---

## 5. QR Code Implementation Guide

### 5.1 Basic QR Code Generation

```python
import qrcode
from io import BytesIO

# Create QR code
qr = qrcode.QRCode(
    version=1,  # 1-40 (1=21x21 matrix)
    error_correction=qrcode.constants.ERROR_CORRECT_M,  # Medium (15%)
    box_size=10,  # Pixels per box
    border=4,     # Boxes of border (minimum 4)
)

# Add data (URL to digital prescription)
qr.add_data('https://medconnect.app/prescriptions/abc-123')
qr.make(fit=True)

# Generate image
img = qr.make_image(fill_color='black', back_color='white')

# Save to bytes for ReportLab
qr_buffer = BytesIO()
img.save(qr_buffer, format='PNG')
qr_buffer.seek(0)
```

### 5.2 Embedding QR in ReportLab

```python
from reportlab.platypus import Image

# Create Image flowable from QR code bytes
qr_image = Image(qr_buffer, width=3*cm, height=3*cm)

# Add to story
story.append(qr_image)
```

### 5.3 QR Code Content Strategy

**URL Format**: `https://medconnect.app/prescriptions/{prescription_id}`

**Data to Encode**:
- Prescription ID (UUID) for verification
- Link to patient portal prescription view
- Could include basic metadata (date, doctor ID) for quick scan

**Error Correction Levels**:
- **L**: 7% recovery - smallest QR
- **M**: 15% recovery - **RECOMMENDED** (balance size/reliability)
- **Q**: 25% recovery - more robust
- **H**: 30% recovery - largest, most reliable

**Sources**:
- [PyPI - qrcode](https://pypi.org/project/qrcode/)
- [GeeksforGeeks - Generate QR Code in Python](https://www.geeksforgeeks.org/python/generate-qr-code-using-qrcode-in-python/)
- [Medium - Exploring QR Code Library](https://medium.com/strategio/exploring-the-qr-code-library-in-python-10f840ac2258)

---

## 6. API Design

### 6.1 New Endpoint

**Endpoint**: `GET /api/v1/prescriptions/{prescription_id}/pdf`

**Purpose**: Generate and download prescription PDF

**Authentication**: Required (doctor or patient who owns the prescription)

**Response**:
- **Content-Type**: `application/pdf`
- **Headers**: `Content-Disposition: attachment; filename="prescription_{id}.pdf"`
- **Body**: Binary PDF data

### 6.2 Authorization Logic

```python
# Allow:
# 1. Doctor who created the prescription
# 2. Patient for whom prescription was created
# 3. Admin (optional)

if current_user.role == "patient":
    if prescription.patient_id != current_user.id:
        raise HTTPException(403, "Not authorized")
elif current_user.role == "doctor":
    if prescription.doctor_id != current_user.doctor_profile.id:
        raise HTTPException(403, "Not authorized")
```

---

## 7. Frontend Integration

### 7.1 Download Button Location

**File**: `/frontend/src/app/doctor/prescriptions/[id]/page.tsx` (to be created or existing)

**Component**:
```tsx
<button
    onClick={() => downloadPDF(prescription.id)}
    className="bg-primary-600 text-white px-4 py-2 rounded-lg"
>
    Download PDF
</button>
```

### 7.2 Download Handler

```typescript
const downloadPDF = async (prescriptionId: string) => {
    try {
        const response = await api.get(
            `/api/v1/prescriptions/${prescriptionId}/pdf`,
            { responseType: 'blob' }  // Important for binary data
        );

        // Create download link
        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', `prescription_${prescriptionId}.pdf`);
        document.body.appendChild(link);
        link.click();
        link.remove();
    } catch (error) {
        console.error('PDF download failed:', error);
    }
};
```

---

## 8. PDF Layout Design

### 8.1 Professional Prescription Layout

```
┌─────────────────────────────────────────┐
│         [CLINIC LOGO/HEADER]            │
│         Dr. Name, Specialization        │
│         License: XXXXXXX                │
│         Facility Name, City             │
├─────────────────────────────────────────┤
│  Patient: Name            Age: XX       │
│  Gender: X/X              Phone: XXXX   │
│  Date: DD/MM/YYYY    ID: #PRESCRIPTION  │
├─────────────────────────────────────────┤
│                                         │
│  Diagnosis: XXXXXXXXXXXX                │
│                                         │
│  ℞  (Rx Symbol)                         │
│                                         │
│  ┌──────────────────────────────────┐  │
│  │ Medicine | Dosage | Freq | Dur   │  │
│  ├──────────────────────────────────┤  │
│  │ Med 1    | 500mg  | 2x   | 5d    │  │
│  │ Med 2    | 250mg  | 3x   | 7d    │  │
│  └──────────────────────────────────┘  │
│                                         │
│  Notes: XXXXXXXXXXXXXXXXXXXX            │
│                                         │
│  Signature: ____________                │
│             Dr. Name                    │
│                                         │
│  [QR CODE]  (Links to digital copy)    │
└─────────────────────────────────────────┘
```

### 8.2 Typography Guidelines

- **Header**: Helvetica-Bold, 16pt
- **Doctor Name**: Helvetica-Bold, 14pt
- **Section Titles**: Helvetica-Bold, 12pt
- **Body Text**: Helvetica, 10pt
- **Medicine Names**: Helvetica-Bold, 10pt (CAPITAL LETTERS)
- **QR Code**: 3cm x 3cm (bottom right)

### 8.3 Color Scheme

- **Primary**: #1a56db (blue for headers)
- **Text**: #000000 (black for content)
- **Table Headers**: Grey background
- **Borders**: Thin black lines

---

## 9. Implementation Checklist

### Backend Tasks
- [ ] Add `reportlab==4.4.10` to requirements.txt
- [ ] Add `qrcode[pil]==7.4.2` to requirements.txt
- [ ] Create `/backend/app/services/pdf_service.py`
- [ ] Implement `generate_prescription_pdf(prescription, doctor, patient)` function
- [ ] Add GET endpoint `/api/v1/prescriptions/{id}/pdf` in routers
- [ ] Implement authorization (doctor/patient only)
- [ ] Add unit tests in `/backend/tests/test_prescription_pdf.py`

### Frontend Tasks
- [ ] Add download button to prescription view page
- [ ] Implement `downloadPDF()` handler with blob response
- [ ] Add error handling for failed downloads
- [ ] Test PDF download in browser

### Testing Tasks
- [ ] Test PDF generation with sample data
- [ ] Test QR code scanning (links to correct prescription)
- [ ] Test authorization (only authorized users can download)
- [ ] Test edge cases (long medicine names, many medicines)
- [ ] Test PDF rendering on mobile devices

---

## 10. Risk Assessment & Mitigation

### Risk 1: Large Medicine Lists Overflow Page
**Mitigation**: Use ReportLab's PageBreak to split across pages

### Risk 2: Missing Doctor/Patient Data
**Mitigation**: Handle None values gracefully, show "N/A" or skip fields

### Risk 3: QR Code URL Changes
**Mitigation**: Use environment variable for base URL (`FRONTEND_URL`)

### Risk 4: PDF Generation Performance
**Mitigation**: ReportLab is fast (<100ms), but consider caching generated PDFs

### Risk 5: Non-ASCII Characters in Names
**Mitigation**: Use UTF-8 encoding, test with non-English names

---

## 11. Success Metrics

- [ ] PDF generates in <500ms
- [ ] QR code scans correctly on mobile devices
- [ ] PDF displays correctly on all major PDF readers
- [ ] All tests passing with >80% coverage
- [ ] Code review approved
- [ ] Jira ticket MD-76 marked as Done

---

## 12. References & Sources

### Documentation
- [ReportLab User Guide](https://www.reportlab.com/docs/reportlab-userguide.pdf)
- [ReportLab Documentation](https://docs.reportlab.com/)
- [PyPI - qrcode](https://pypi.org/project/qrcode/)
- [GeeksforGeeks - Generate QR Code](https://www.geeksforgeeks.org/python/generate-qr-code-using-qrcode-in-python/)

### Medical Standards
- [Maharashtra Medical Council Prescription Format](https://maharashtramedicalcouncil.in/Files/PRESCRIPTION%20FORMAT%20FOR%20REGISTRATION%20MEDICAL%20PRACTITIONERS.pdf)
- [Medical Council of India Model Format](https://mcimindia.co.in/Files/Announcements_07072015_Draft%20of%20Model%20Prescription%20Format.pdf)
- [ESIC SOP for Prescription](https://esic.gov.in/attachments/circularfile/5908ac7c71a73d8fe977f930803341ef.pdf)

### Tutorials
- [Python Assets - ReportLab Tutorial](https://pythonassets.com/posts/create-pdf-documents-in-python-with-reportlab/)
- [Medium - PDF Report Generation](https://medium.com/@AlexanderObregon/creating-pdf-reports-with-python-a53439031117)
- [Medium - QR Code Library](https://medium.com/strategio/exploring-the-qr-code-library-in-python-10f840ac2258)

---

**End of ResearchPack**
**Status**: Ready for Planning Phase ✓
