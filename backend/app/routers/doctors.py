from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_active_clinic, get_current_doctor
from app.models.clinic import ClinicMembership
from app.models.doctor import Doctor
from app.models.patient_link import PatientClinicLink
from app.models.user import User
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.prescription import PrescriptionCreate, PrescriptionResponse
from app.schemas.record import RecordCreate, RecordResponse
from app.schemas.user import DoctorProfileCreate, DoctorProfileResponse
from app.services.prescription_service import create_prescription
from app.services.record_service import create_record, get_doctor_patients, get_patient_timeline

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

    prescriptions = [
        {
            "id": str(rx.id),
            "record_id": str(rec.id),
            "medicines": rx.medicines,
            "diagnosis": rx.diagnosis,
            "notes": rx.notes,
            "valid_until": rx.valid_until.isoformat() if rx.valid_until else None,
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
    doctor_info: tuple[User, Doctor] = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
    clinic_context: tuple | None = Depends(get_active_clinic),
):
    _, doctor = doctor_info
    clinic_id = clinic_context[0] if clinic_context else None
    if clinic_id:
        await _check_patient_consent(db, req.patient_id, clinic_id)
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
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(e)}},
        )
    return record


@router.post("/prescriptions", response_model=PrescriptionResponse, status_code=status.HTTP_201_CREATED)
async def create_rx(
    req: PrescriptionCreate,
    doctor_info: tuple[User, Doctor] = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
    clinic_context: tuple | None = Depends(get_active_clinic),
):
    _, doctor = doctor_info
    clinic_id = clinic_context[0] if clinic_context else None
    if clinic_id:
        await _check_patient_consent(db, req.patient_id, clinic_id)
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
