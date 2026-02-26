from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_doctor
from app.models.doctor import Doctor
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


@router.get("/patients/{patient_id}/prescriptions")
async def get_patient_prescriptions(
    patient_id: UUID,
    doctor_info: tuple[User, Doctor] = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=100),
):
    """
    Get prescriptions for a specific patient that were created by:
    - The current doctor (same doctor_id), OR
    - Doctors from the same facility (same facility_name and facility_city)

    This ensures doctors can only see prescriptions from their own practice/facility.
    """
    from sqlalchemy import select, or_, and_
    from sqlalchemy.orm import joinedload
    from app.models.medical_record import MedicalRecord
    from app.models.prescription import Prescription

    _, doctor = doctor_info

    # Build filter conditions:
    # 1. Same doctor, OR
    # 2. Same facility (if facility_name is set)
    filter_conditions = [MedicalRecord.doctor_id == doctor.id]

    if doctor.facility_name and doctor.facility_city:
        # Also include prescriptions from other doctors at the same facility
        facility_doctors_stmt = (
            select(Doctor.id)
            .where(
                Doctor.facility_name == doctor.facility_name,
                Doctor.facility_city == doctor.facility_city,
                Doctor.deleted_at.is_(None),
            )
        )
        facility_doctor_ids = await db.execute(facility_doctors_stmt)
        facility_doctor_ids = [row[0] for row in facility_doctor_ids]

        if facility_doctor_ids:
            filter_conditions.append(MedicalRecord.doctor_id.in_(facility_doctor_ids))

    # Query prescriptions
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

    # Format response
    prescriptions = []
    for row in rows:
        record = row[0]
        prescription = row[1]
        doctor_name = row[2]

        prescriptions.append({
            "id": str(prescription.id),
            "record_id": str(record.id),
            "medicines": prescription.medicines,
            "diagnosis": prescription.diagnosis,
            "notes": prescription.notes,
            "valid_until": prescription.valid_until.isoformat() if prescription.valid_until else None,
            "created_at": prescription.created_at.isoformat(),
            "doctor_name": doctor_name,
        })

    return {
        "data": prescriptions,
        "total": len(prescriptions),
        "patient_id": str(patient_id),
    }


@router.get("/patients/{patient_id}/records")
async def patient_records(
    patient_id: UUID,
    type: str | None = Query(None),
    cursor: UUID | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    doctor_info: tuple[User, Doctor] = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    _, doctor = doctor_info
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
):
    _, doctor = doctor_info
    try:
        record = await create_record(
            db=db,
            patient_id=req.patient_id,
            doctor_id=doctor.id,
            record_type=req.record_type,
            title=req.title,
            description=req.description,
            fhir_bundle=req.fhir_bundle,
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
):
    _, doctor = doctor_info
    try:
        prescription = await create_prescription(
            db=db,
            doctor_id=doctor.id,
            patient_id=req.patient_id,
            medicines=[m.model_dump() for m in req.medicines],
            diagnosis=req.diagnosis,
            notes=req.notes,
            valid_until=req.valid_until,
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
