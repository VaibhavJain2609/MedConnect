from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.doctor import Doctor
from app.models.medical_record import MedicalRecord
from app.models.prescription import Prescription
from app.models.user import User
from app.services.notification_service import create_notification
from app.utils.fhir import create_fhir_bundle


async def create_prescription(
    db: AsyncSession,
    doctor_id: UUID,
    patient_id: UUID,
    medicines: list[dict],
    diagnosis: str | None = None,
    notes: str | None = None,
    valid_until: date | None = None,
    clinic_id: UUID | None = None,
) -> Prescription:
    patient_result = await db.execute(
        select(User).where(User.id == patient_id, User.role == "patient", User.deleted_at.is_(None))
    )
    patient = patient_result.scalar_one_or_none()
    if not patient:
        raise ValueError("Patient not found")

    fhir_bundle = create_fhir_bundle(
        record_type="prescription",
        data={"medicines": medicines},
        patient_id=patient_id,
        doctor_id=doctor_id,
    )

    record = MedicalRecord(
        patient_id=patient_id,
        doctor_id=doctor_id,
        record_type="prescription",
        title=f"Prescription — {diagnosis or 'General'}",
        description=notes,
        fhir_bundle=fhir_bundle,
        source="doctor",
        clinic_id=clinic_id,
    )
    db.add(record)
    await db.flush()

    prescription = Prescription(
        record_id=record.id,
        doctor_id=doctor_id,
        patient_id=patient_id,
        medicines=medicines,
        diagnosis=diagnosis,
        notes=notes,
        valid_until=valid_until,
        clinic_id=clinic_id,
    )
    db.add(prescription)
    await db.flush()

    from app.services.audit_service import log_change
    await log_change(
        db=db,
        table_name="prescriptions",
        record_id=prescription.id,
        action="INSERT",
        old_values=None,
        new_values={
            "patient_id": str(patient_id),
            "doctor_id": str(doctor_id),
            "diagnosis": diagnosis,
            "medicines_count": len(medicines),
        },
    )

    # Notify the patient about the new prescription
    doctor_result = await db.execute(
        select(Doctor).where(Doctor.id == doctor_id, Doctor.deleted_at.is_(None))
    )
    doctor = doctor_result.scalar_one_or_none()
    if doctor:
        doctor_user_result = await db.execute(
            select(User).where(User.id == doctor.user_id, User.deleted_at.is_(None))
        )
        doctor_user = doctor_user_result.scalar_one_or_none()
        doctor_name = doctor_user.full_name if doctor_user else "your doctor"
    else:
        doctor_name = "your doctor"

    await create_notification(
        db=db,
        user_id=patient_id,
        notif_type="prescription",
        title=f"New prescription from Dr. {doctor_name}",
        body=f"Diagnosis: {diagnosis or 'See prescription for details'}",
        action_url="/patient/timeline",
    )

    return prescription


async def get_patient_prescriptions(
    db: AsyncSession,
    patient_id: UUID,
    cursor: UUID | None = None,
    limit: int = 20,
) -> tuple[list[Prescription], str | None, bool]:
    stmt = (
        select(Prescription)
        .where(Prescription.patient_id == patient_id, Prescription.deleted_at.is_(None))
        .order_by(Prescription.created_at.desc())
        .limit(limit + 1)
    )

    if cursor:
        cursor_result = await db.execute(
            select(Prescription.created_at).where(Prescription.id == cursor)
        )
        cursor_time = cursor_result.scalar_one_or_none()
        if cursor_time:
            stmt = stmt.where(Prescription.created_at <= cursor_time, Prescription.id != cursor)

    result = await db.execute(stmt)
    items = result.scalars().all()

    has_more = len(items) > limit
    prescriptions = list(items[:limit])
    next_cursor = str(prescriptions[-1].id) if prescriptions and has_more else None

    return prescriptions, next_cursor, has_more
