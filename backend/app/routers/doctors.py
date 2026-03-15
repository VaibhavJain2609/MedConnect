import uuid as _uuid
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_active_clinic, get_current_doctor, get_verified_doctor
from app.models.clinic import ClinicMembership
from app.models.doctor import Doctor
from app.models.medical_record import MedicalRecord
from app.models.patient_link import PatientClinicLink
from app.models.user import User
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.prescription import PrescriptionCreate, PrescriptionMedicineItem, PrescriptionResponse
from app.schemas.record import RecordCreate, RecordResponse
from app.schemas.user import DoctorProfileCreate, DoctorProfileResponse
from app.services.prescription_service import create_prescription
from app.services.record_service import create_record, get_doctor_patients, get_patient_timeline


# ---------------------------------------------------------------------------
# Pydantic models for template endpoints
# ---------------------------------------------------------------------------

class PrescriptionTemplateCreate(BaseModel):
    name: str
    medicines: list[PrescriptionMedicineItem]
    diagnosis: Optional[str] = None
    notes: Optional[str] = None


class PrescriptionTemplateResponse(BaseModel):
    id: UUID
    doctor_id: UUID
    name: str
    medicines: list[dict]
    diagnosis: Optional[str]
    notes: Optional[str]
    created_at: str

    class Config:
        from_attributes = True

router = APIRouter(prefix="/api/v1/doctors", tags=["doctors"])


@router.get("/patients")
async def list_patients(
    cursor: UUID | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    doctor_info: tuple[User, Doctor] = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    _, doctor = doctor_info
    patients, next_cursor, has_more = await get_doctor_patients(
        db=db, doctor_id=doctor.id, cursor=cursor, limit=limit
    )
    return PaginatedResponse(
        data=patients,
        pagination=PaginationMeta(next_cursor=next_cursor, has_more=has_more, limit=limit),
    )


@router.get("/patients/search")
async def search_patients(
    q: str = Query(..., min_length=2),
    doctor_info: tuple = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    """
    Search patients by name or phone among the doctor's known patients.
    Known patients = patients with records created by this doctor OR
    patients approved via clinic links for any of the doctor's clinics.
    Returns: [{id, full_name, phone, last_visit_at}]
    """
    from sqlalchemy import select, or_, func, union
    from app.models.clinic import ClinicMembership

    _, doctor = doctor_info

    search_term = f"%{q}%"

    # Sub-query 1: patients who have records created by this doctor
    records_subq = (
        select(
            User.id,
            User.full_name,
            User.phone,
            MedicalRecord.created_at.label("last_visit_at"),
        )
        .join(MedicalRecord, MedicalRecord.patient_id == User.id)
        .where(
            MedicalRecord.doctor_id == doctor.id,
            MedicalRecord.deleted_at.is_(None),
            User.deleted_at.is_(None),
            or_(
                User.full_name.ilike(search_term),
                User.phone.ilike(search_term),
            ),
        )
    )

    # Sub-query 2: patients with approved clinic links for this doctor's clinics
    clinic_subq = (
        select(
            User.id,
            User.full_name,
            User.phone,
            PatientClinicLink.created_at.label("last_visit_at"),
        )
        .join(PatientClinicLink, PatientClinicLink.patient_id == User.id)
        .join(
            ClinicMembership,
            ClinicMembership.clinic_id == PatientClinicLink.clinic_id,
        )
        .where(
            ClinicMembership.user_id == doctor.user_id,
            ClinicMembership.is_active.is_(True),
            ClinicMembership.deleted_at.is_(None),
            PatientClinicLink.consent_status == "approved",
            PatientClinicLink.deleted_at.is_(None),
            User.deleted_at.is_(None),
            or_(
                User.full_name.ilike(search_term),
                User.phone.ilike(search_term),
            ),
        )
    )

    # Combine both sub-queries via UNION
    combined = union(records_subq, clinic_subq).subquery()

    # Select distinct patients with their latest visit
    stmt = (
        select(
            combined.c.id,
            combined.c.full_name,
            combined.c.phone,
            func.max(combined.c.last_visit_at).label("last_visit_at"),
        )
        .group_by(combined.c.id, combined.c.full_name, combined.c.phone)
        .order_by(combined.c.full_name)
        .limit(20)
    )

    result = await db.execute(stmt)
    rows = result.all()

    return {
        "data": [
            {
                "id": str(row.id),
                "full_name": row.full_name,
                "phone": row.phone,
                "last_visit_at": row.last_visit_at.isoformat() if row.last_visit_at else None,
            }
            for row in rows
        ]
    }


@router.get("/patients/{patient_id}/profile")
async def get_patient_profile(
    patient_id: UUID,
    doctor_info: tuple = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    """
    Doctor-facing patient profile endpoint.
    Returns: {id, full_name, phone, email, blood_group, allergies, chronic_conditions}
    """
    from sqlalchemy import select

    _, doctor = doctor_info

    patient_result = await db.execute(
        select(User).where(User.id == patient_id, User.deleted_at.is_(None))
    )
    patient = patient_result.scalar_one_or_none()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Patient not found"}},
        )

    if not await _check_doctor_patient_relationship(db, doctor, patient_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "No relationship with this patient"}},
        )

    return {
        "id": str(patient.id),
        "full_name": patient.full_name,
        "phone": patient.phone,
        "email": patient.email,
        "blood_group": patient.blood_group,
        "allergies": patient.allergies or [],
        "chronic_conditions": patient.chronic_conditions or [],
        "height_cm": patient.height_cm,
        "weight_kg": patient.weight_kg,
    }


async def _check_patient_consent(db: AsyncSession, patient_id: UUID, clinic_id: UUID) -> None:
    """Raise 403 if patient has not approved consent for this clinic."""
    from sqlalchemy import select as _select

    result = await db.execute(
        _select(PatientClinicLink).where(
            PatientClinicLink.patient_id == patient_id,
            PatientClinicLink.clinic_id == clinic_id,
            PatientClinicLink.consent_status == "approved",
            PatientClinicLink.deleted_at.is_(None),
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "CONSENT_REQUIRED", "message": "Patient has not approved access for this clinic"}},
        )


async def _check_doctor_patient_relationship(
    db: AsyncSession, doctor: "Doctor", patient_id: UUID
) -> bool:
    """Returns True if doctor has created a record for patient, or shares an approved clinic."""
    from sqlalchemy import select as _select

    # Check 1: doctor has created at least one medical record for this patient
    record_exists = await db.execute(
        _select(MedicalRecord.id)
        .where(
            MedicalRecord.doctor_id == doctor.id,
            MedicalRecord.patient_id == patient_id,
            MedicalRecord.deleted_at.is_(None),
        )
        .limit(1)
    )
    if record_exists.scalar_one_or_none():
        return True

    # Check 2: doctor is a member of a clinic that has an approved PatientClinicLink
    # Note: ClinicMembership links doctor's User (doctor.user_id), not Doctor.id
    shared_clinic = await db.execute(
        _select(ClinicMembership.id)
        .join(PatientClinicLink, PatientClinicLink.clinic_id == ClinicMembership.clinic_id)
        .where(
            ClinicMembership.user_id == doctor.user_id,
            ClinicMembership.is_active.is_(True),
            ClinicMembership.deleted_at.is_(None),
            PatientClinicLink.patient_id == patient_id,
            PatientClinicLink.consent_status == "approved",
            PatientClinicLink.deleted_at.is_(None),
        )
        .limit(1)
    )
    return shared_clinic.scalar_one_or_none() is not None


@router.get("/patients/{patient_id}/prescriptions")
async def get_patient_prescriptions(
    patient_id: UUID,
    doctor_info: tuple[User, Doctor] = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=100),
    clinic_context: tuple | None = Depends(get_active_clinic),
):
    """
    Get prescriptions for a patient scoped to the active clinic.
    Respects record_sharing_mode:
      - per_clinic: see all clinic doctors' prescriptions
      - per_doctor: see only own prescriptions
    Falls back to own-only if no clinic context.
    Requires approved PatientClinicLink consent when clinic context is active.
    """
    from sqlalchemy import select, or_
    from app.models.clinic import Clinic
    from app.models.medical_record import MedicalRecord
    from app.models.prescription import Prescription

    _, doctor = doctor_info

    filter_conditions = [MedicalRecord.doctor_id == doctor.id]

    if clinic_context:
        clinic_id, _ = clinic_context
        await _check_patient_consent(db, patient_id, clinic_id)
        # Get clinic sharing mode
        clinic_result = await db.execute(
            select(Clinic).where(Clinic.id == clinic_id, Clinic.deleted_at.is_(None))
        )
        clinic = clinic_result.scalar_one_or_none()

        if clinic and clinic.record_sharing_mode == "per_clinic":
            # Include all doctors who are members of this clinic
            clinic_doctor_ids_stmt = (
                select(Doctor.id)
                .join(ClinicMembership, ClinicMembership.user_id == Doctor.user_id)
                .where(
                    ClinicMembership.clinic_id == clinic_id,
                    ClinicMembership.is_active.is_(True),
                    ClinicMembership.deleted_at.is_(None),
                    Doctor.deleted_at.is_(None),
                )
            )
            clinic_doctor_ids = await db.execute(clinic_doctor_ids_stmt)
            ids = [row[0] for row in clinic_doctor_ids]
            if ids:
                filter_conditions = [MedicalRecord.doctor_id.in_(ids)]

    stmt = (
        select(MedicalRecord, Prescription, User.full_name.label("doctor_name"))
        .join(Prescription, Prescription.record_id == MedicalRecord.id)
        .outerjoin(Doctor, MedicalRecord.doctor_id == Doctor.id)
        .outerjoin(User, Doctor.user_id == User.id)
        .where(
            MedicalRecord.patient_id == patient_id,
            MedicalRecord.record_type == "prescription",
            MedicalRecord.deleted_at.is_(None),
            Prescription.deleted_at.is_(None),
            or_(*filter_conditions),
        )
        .order_by(MedicalRecord.created_at.desc())
        .limit(limit)
    )

    result = await db.execute(stmt)
    rows = result.all()

    from datetime import date as _date
    prescriptions = [
        {
            "id": str(rx.id),
            "record_id": str(rec.id),
            "medicines": rx.medicines,
            "diagnosis": rx.diagnosis,
            "notes": rx.notes,
            "valid_until": rx.valid_until.isoformat() if rx.valid_until else None,
            "is_expired": bool(rx.valid_until and rx.valid_until < _date.today()),
            "created_at": rx.created_at.isoformat(),
            "doctor_name": doc_name,
        }
        for rec, rx, doc_name in rows
    ]

    return {"data": prescriptions, "total": len(prescriptions), "patient_id": str(patient_id)}


@router.get("/patients/{patient_id}/records")
async def patient_records(
    patient_id: UUID,
    type: str | None = Query(None),
    cursor: UUID | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    doctor_info: tuple[User, Doctor] = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
    clinic_context: tuple | None = Depends(get_active_clinic),
):
    _, doctor = doctor_info
    if clinic_context:
        clinic_id, _ = clinic_context
        await _check_patient_consent(db, patient_id, clinic_id)
    else:
        if not await _check_doctor_patient_relationship(db, doctor, patient_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "FORBIDDEN", "message": "No relationship with this patient"}},
            )
    records, next_cursor, has_more = await get_patient_timeline(
        db=db, patient_id=patient_id, record_type=type, cursor=cursor, limit=limit
    )
    return PaginatedResponse(
        data=records,
        pagination=PaginationMeta(next_cursor=next_cursor, has_more=has_more, limit=limit),
    )


@router.post("/records", response_model=RecordResponse, status_code=status.HTTP_201_CREATED)
async def create_medical_record(
    req: RecordCreate,
    doctor_info: tuple[User, Doctor] = Depends(get_verified_doctor),
    db: AsyncSession = Depends(get_db),
    clinic_context: tuple | None = Depends(get_active_clinic),
):
    if not req.patient_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "VALIDATION_ERROR", "message": "patient_id is required"}},
        )
    _, doctor = doctor_info
    clinic_id = clinic_context[0] if clinic_context else None
    if clinic_id:
        await _check_patient_consent(db, req.patient_id, clinic_id)
    else:
        if not await _check_doctor_patient_relationship(db, doctor, req.patient_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "PATIENT_ACCESS_DENIED", "message": "No relationship with this patient"}},
            )
    try:
        record = await create_record(
            db=db,
            patient_id=req.patient_id,
            doctor_id=doctor.id,
            record_type=req.record_type,
            title=req.title,
            description=req.description,
            fhir_bundle=req.fhir_bundle,
            clinic_id=clinic_id,
            document_url=req.document_url,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(e)}},
        )
    return record


@router.get("/records/{record_id}/amendments")
async def list_record_amendments(
    record_id: UUID,
    doctor_info=Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    """
    List all amendment records that point back to record_id via amended_from_id.
    Returns them in ascending created_at order (oldest amendment first).
    """
    from sqlalchemy import select

    # Verify original record exists
    original = await db.get(MedicalRecord, record_id)
    if not original or original.deleted_at:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Record not found"}},
        )

    stmt = (
        select(MedicalRecord)
        .where(
            MedicalRecord.amended_from_id == record_id,
            MedicalRecord.deleted_at.is_(None),
        )
        .order_by(MedicalRecord.created_at.asc())
    )
    result = await db.execute(stmt)
    amendments = result.scalars().all()

    return {
        "data": [
            {
                "id": str(a.id),
                "patient_id": str(a.patient_id),
                "doctor_id": str(a.doctor_id) if a.doctor_id else None,
                "record_type": a.record_type,
                "title": a.title,
                "description": a.description,
                "fhir_bundle": a.fhir_bundle,
                "source": a.source,
                "amended_from_id": str(a.amended_from_id),
                "created_at": a.created_at.isoformat(),
                "updated_at": a.updated_at.isoformat(),
            }
            for a in amendments
        ],
        "total": len(amendments),
        "original_record_id": str(record_id),
    }


@router.post("/records/{record_id}/amend", response_model=RecordResponse, status_code=status.HTTP_201_CREATED)
async def amend_record(
    record_id: UUID,
    req: RecordCreate,
    doctor_info=Depends(get_verified_doctor),
    db: AsyncSession = Depends(get_db),
    clinic_context=Depends(get_active_clinic),
):
    """
    Create an amendment of an existing medical record.
    The original record is preserved; the new record links back via amended_from_id.
    """
    # Verify original record exists
    original = await db.get(MedicalRecord, record_id)
    if not original or original.deleted_at:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Original record not found"}},
        )

    _, doctor = doctor_info
    clinic_id = clinic_context[0] if clinic_context else None

    if clinic_id:
        await _check_patient_consent(db, original.patient_id, clinic_id)
    else:
        if not await _check_doctor_patient_relationship(db, doctor, original.patient_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "PATIENT_ACCESS_DENIED", "message": "No relationship with this patient"}},
            )

    from app.utils.fhir import create_fhir_bundle

    fhir_bundle = req.fhir_bundle or create_fhir_bundle(
        record_type=req.record_type or original.record_type,
        data={"description": req.description or ""},
        patient_id=original.patient_id,
        doctor_id=doctor.id,
    )

    amended = MedicalRecord(
        id=_uuid.uuid4(),
        patient_id=original.patient_id,
        doctor_id=doctor.id,
        record_type=req.record_type or original.record_type,
        title=req.title,
        description=req.description,
        fhir_bundle=fhir_bundle,
        clinic_id=clinic_id,
        amended_from_id=record_id,
        source="amended",
    )
    db.add(amended)
    await db.flush()

    from app.services.audit_service import log_change
    await log_change(
        db=db,
        table_name="medical_records",
        record_id=amended.id,
        action="INSERT",
        old_values=None,
        new_values={
            "record_type": amended.record_type,
            "patient_id": str(amended.patient_id),
            "doctor_id": str(doctor.id),
            "title": amended.title,
            "amended_from_id": str(record_id),
        },
    )

    return amended


@router.post("/prescriptions", response_model=PrescriptionResponse, status_code=status.HTTP_201_CREATED)
async def create_rx(
    req: PrescriptionCreate,
    doctor_info: tuple[User, Doctor] = Depends(get_verified_doctor),
    db: AsyncSession = Depends(get_db),
    clinic_context: tuple | None = Depends(get_active_clinic),
):
    _, doctor = doctor_info
    # clinic_id: prefer X-Clinic-Id header (existing context); fall back to body field
    clinic_id = (clinic_context[0] if clinic_context else None) or req.clinic_id
    branch_id = req.branch_id
    if clinic_id:
        await _check_patient_consent(db, req.patient_id, clinic_id)
    else:
        if not await _check_doctor_patient_relationship(db, doctor, req.patient_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "PATIENT_ACCESS_DENIED", "message": "No relationship with this patient"}},
            )
    try:
        prescription = await create_prescription(
            db=db,
            doctor_id=doctor.id,
            patient_id=req.patient_id,
            medicines=[m.model_dump() for m in req.medicines],
            diagnosis=req.diagnosis,
            notes=req.notes,
            valid_until=req.valid_until,
            clinic_id=clinic_id,
            branch_id=branch_id,
            appointment_id=req.appointment_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(e)}},
        )
    return prescription


@router.get("/prescriptions")
async def list_prescriptions(
    limit: int = Query(50, ge=1, le=100),
    cursor: UUID | None = Query(None),
    doctor_info: tuple[User, Doctor] = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all prescriptions created by the logged-in doctor.
    Returns medical records of type 'prescription' with patient info.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload
    from app.models.medical_record import MedicalRecord

    _, doctor = doctor_info

    # Build query for prescription records created by this doctor
    stmt = (
        select(MedicalRecord)
        .options(joinedload(MedicalRecord.patient))
        .where(
            MedicalRecord.doctor_id == doctor.id,
            MedicalRecord.record_type == "prescription",
            MedicalRecord.deleted_at.is_(None),
        )
        .order_by(MedicalRecord.created_at.desc())
        .limit(limit + 1)
    )

    if cursor:
        cursor_result = await db.execute(
            select(MedicalRecord.created_at).where(MedicalRecord.id == cursor)
        )
        cursor_time = cursor_result.scalar_one_or_none()
        if cursor_time:
            stmt = stmt.where(
                MedicalRecord.created_at <= cursor_time,
                MedicalRecord.id != cursor
            )

    result = await db.execute(stmt)
    records = result.unique().scalars().all()

    has_more = len(records) > limit
    records_list = list(records[:limit])
    next_cursor = str(records_list[-1].id) if records_list and has_more else None

    # Format response with patient names
    data = []
    for record in records_list:
        data.append({
            "id": str(record.id),
            "patient_id": str(record.patient_id),
            "patient_name": record.patient.full_name if record.patient else None,
            "record_type": record.record_type,
            "title": record.title,
            "description": record.description,
            "fhir_bundle": record.fhir_bundle,
            "source": record.source,
            "created_at": record.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
        })

    return PaginatedResponse(
        data=data,
        pagination=PaginationMeta(next_cursor=next_cursor, has_more=has_more, limit=limit),
    )


@router.get("/profile", response_model=DoctorProfileResponse)
async def get_profile(
    doctor_info: tuple[User, Doctor] = Depends(get_current_doctor),
):
    _, doctor = doctor_info
    return doctor


@router.put("/profile", response_model=DoctorProfileResponse)
async def update_profile(
    req: DoctorProfileCreate,
    doctor_info: tuple[User, Doctor] = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    _, doctor = doctor_info
    if req.specialization is not None:
        doctor.specialization = req.specialization
    if req.license_number is not None:
        doctor.license_number = req.license_number
    if req.facility_name is not None:
        doctor.facility_name = req.facility_name
    if req.facility_city is not None:
        doctor.facility_city = req.facility_city
    await db.flush()
    return doctor


# ---------------------------------------------------------------------------
# MD-246: Single prescription GET endpoint (for print view)
# ---------------------------------------------------------------------------

@router.get("/prescriptions/{prescription_id}")
async def get_prescription(
    prescription_id: UUID,
    doctor_info: tuple = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a single prescription with patient and doctor info (for print view).
    """
    from sqlalchemy import select, or_
    from app.models.prescription import Prescription

    user, doctor = doctor_info

    stmt = (
        select(Prescription, MedicalRecord, User.full_name.label("patient_name"))
        .join(MedicalRecord, MedicalRecord.id == Prescription.record_id)
        .outerjoin(User, User.id == Prescription.patient_id)
        .where(
            Prescription.id == prescription_id,
            Prescription.deleted_at.is_(None),
            MedicalRecord.deleted_at.is_(None),
            MedicalRecord.doctor_id == doctor.id,
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

    doctor_user_stmt = select(User).where(User.id == doctor.user_id)
    doctor_user_result = await db.execute(doctor_user_stmt)
    doctor_user = doctor_user_result.scalar_one_or_none()

    from datetime import date as _date
    return {
        "id": str(prescription.id),
        "record_id": str(record.id),
        "medicines": prescription.medicines,
        "diagnosis": prescription.diagnosis,
        "notes": prescription.notes,
        "valid_until": prescription.valid_until.isoformat() if prescription.valid_until else None,
        "is_expired": bool(prescription.valid_until and prescription.valid_until < _date.today()),
        "created_at": prescription.created_at.isoformat(),
        "patient_id": str(prescription.patient_id),
        "patient_name": patient_name,
        "doctor": {
            "name": doctor_user.full_name if doctor_user else None,
            "specialization": doctor.specialization,
            "license_number": doctor.license_number,
            "facility_name": doctor.facility_name,
            "facility_city": doctor.facility_city,
        },
    }


# ---------------------------------------------------------------------------
# MD-247: Prescription template endpoints
# ---------------------------------------------------------------------------

@router.post("/prescription-templates", response_model=PrescriptionTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_prescription_template(
    req: PrescriptionTemplateCreate,
    doctor_info: tuple = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    """Create a new prescription template for quick reuse."""
    from app.models.prescription import PrescriptionTemplate

    _, doctor = doctor_info

    template = PrescriptionTemplate(
        doctor_id=doctor.id,
        name=req.name,
        medicines=[m.model_dump() for m in req.medicines],
        diagnosis=req.diagnosis,
        notes=req.notes,
    )
    db.add(template)
    await db.flush()

    return {
        "id": template.id,
        "doctor_id": template.doctor_id,
        "name": template.name,
        "medicines": template.medicines,
        "diagnosis": template.diagnosis,
        "notes": template.notes,
        "created_at": template.created_at.isoformat(),
    }


@router.get("/prescription-templates")
async def list_prescription_templates(
    doctor_info: tuple = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    """List all prescription templates for the logged-in doctor."""
    from sqlalchemy import select
    from app.models.prescription import PrescriptionTemplate

    _, doctor = doctor_info

    stmt = (
        select(PrescriptionTemplate)
        .where(
            PrescriptionTemplate.doctor_id == doctor.id,
            PrescriptionTemplate.deleted_at.is_(None),
        )
        .order_by(PrescriptionTemplate.created_at.desc())
    )

    result = await db.execute(stmt)
    templates = result.scalars().all()

    return {
        "data": [
            {
                "id": str(t.id),
                "doctor_id": str(t.doctor_id),
                "name": t.name,
                "medicines": t.medicines,
                "diagnosis": t.diagnosis,
                "notes": t.notes,
                "created_at": t.created_at.isoformat(),
            }
            for t in templates
        ]
    }


@router.delete("/prescription-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prescription_template(
    template_id: UUID,
    doctor_info: tuple = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a prescription template."""
    from sqlalchemy import select
    from datetime import datetime, timezone
    from app.models.prescription import PrescriptionTemplate

    _, doctor = doctor_info

    stmt = select(PrescriptionTemplate).where(
        PrescriptionTemplate.id == template_id,
        PrescriptionTemplate.doctor_id == doctor.id,
        PrescriptionTemplate.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Template not found"}},
        )

    template.deleted_at = datetime.now(timezone.utc)
    await db.flush()
    return None
