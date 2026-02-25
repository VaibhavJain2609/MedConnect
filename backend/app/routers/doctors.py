from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_doctor
from app.models.doctor import Doctor
from app.models.user import User
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.prescription import PrescriptionCreate, PrescriptionResponse
from app.schemas.prescription_template import TemplateCreate, TemplateResponse, TemplateUpdate
from app.schemas.record import RecordCreate, RecordResponse
from app.schemas.user import DoctorProfileCreate, DoctorProfileResponse
from app.services.prescription_service import create_prescription
from app.services.record_service import create_record, get_doctor_patients, get_patient_timeline
from app.services import template_service

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


# Prescription Templates


@router.post("/templates", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    req: TemplateCreate,
    doctor_info: tuple[User, Doctor] = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    """Create a new prescription template."""
    _, doctor = doctor_info
    try:
        template = await template_service.create_template(
            db=db,
            doctor_id=doctor.id,
            name=req.name,
            medicines=req.medicines,
            diagnosis=req.diagnosis,
            notes=req.notes,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(e)}},
        )
    return template


@router.get("/templates")
async def list_templates(
    cursor: UUID | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    doctor_info: tuple[User, Doctor] = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    """List all templates for the current doctor."""
    _, doctor = doctor_info
    templates, next_cursor, has_more = await template_service.get_doctor_templates(
        db=db, doctor_id=doctor.id, cursor=cursor, limit=limit
    )
    return PaginatedResponse(
        data=templates,
        pagination=PaginationMeta(next_cursor=next_cursor, has_more=has_more, limit=limit),
    )


@router.get("/templates/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: UUID,
    doctor_info: tuple[User, Doctor] = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    """Get a single template by ID."""
    _, doctor = doctor_info
    template = await template_service.get_template(db=db, template_id=template_id, doctor_id=doctor.id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Template not found"}},
        )
    return template


@router.put("/templates/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: UUID,
    req: TemplateUpdate,
    doctor_info: tuple[User, Doctor] = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    """Update a template."""
    _, doctor = doctor_info
    try:
        template = await template_service.update_template(
            db=db,
            template_id=template_id,
            doctor_id=doctor.id,
            name=req.name,
            medicines=req.medicines,
            diagnosis=req.diagnosis,
            notes=req.notes,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND if "not found" in str(e).lower() else status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(e)}},
        )
    return template


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: UUID,
    doctor_info: tuple[User, Doctor] = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    """Delete a template (soft delete)."""
    _, doctor = doctor_info
    try:
        await template_service.delete_template(db=db, template_id=template_id, doctor_id=doctor.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(e)}},
        )
    return None
