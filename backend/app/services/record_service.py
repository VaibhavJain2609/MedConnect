from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.doctor import Doctor
from app.models.medical_record import MedicalRecord
from app.models.user import User
from app.utils.fhir import create_fhir_bundle


async def create_record(
    db: AsyncSession,
    patient_id: UUID,
    doctor_id: UUID | None,
    record_type: str,
    title: str,
    description: str | None = None,
    fhir_bundle: dict | None = None,
    clinic_id: UUID | None = None,
    document_url: str | None = None,
    source: str = "doctor",
) -> MedicalRecord:
    patient = await db.execute(
        select(User).where(User.id == patient_id, User.role == "patient", User.deleted_at.is_(None))
    )
    if not patient.scalar_one_or_none():
        raise ValueError("Patient not found")

    if fhir_bundle is None:
        fhir_bundle = create_fhir_bundle(
            record_type=record_type,
            data={"description": description or ""},
            patient_id=patient_id,
            doctor_id=doctor_id,
        )

    record = MedicalRecord(
        patient_id=patient_id,
        doctor_id=doctor_id,
        record_type=record_type,
        title=title,
        description=description,
        fhir_bundle=fhir_bundle,
        source=source,
        clinic_id=clinic_id,
        document_url=document_url,
    )
    db.add(record)
    await db.flush()

    from app.services.audit_service import log_change
    await log_change(
        db=db,
        table_name="medical_records",
        record_id=record.id,
        action="INSERT",
        old_values=None,
        new_values={
            "record_type": record_type,
            "patient_id": str(patient_id),
            "doctor_id": str(doctor_id) if doctor_id else None,
            "title": title,
        },
    )

    return record


async def get_patient_timeline(
    db: AsyncSession,
    patient_id: UUID,
    record_type: str | None = None,
    query: str | None = None,
    cursor: UUID | None = None,
    limit: int = 20,
    doctor_id: UUID | None = None,
) -> tuple[list[dict], str | None, bool]:
    from app.models.prescription import Prescription

    stmt = (
        select(MedicalRecord, User.full_name.label("doctor_name"), Prescription)
        .outerjoin(Doctor, and_(MedicalRecord.doctor_id == Doctor.id, Doctor.deleted_at.is_(None)))
        .outerjoin(User, and_(Doctor.user_id == User.id, User.deleted_at.is_(None)))
        .outerjoin(Prescription, and_(
            Prescription.record_id == MedicalRecord.id,
            Prescription.deleted_at.is_(None)
        ))
        .where(
            MedicalRecord.patient_id == patient_id,
            MedicalRecord.deleted_at.is_(None),
        )
    )

    if doctor_id:
        stmt = stmt.where(MedicalRecord.doctor_id == doctor_id)

    if record_type:
        stmt = stmt.where(MedicalRecord.record_type == record_type)

    if query:
        search_filter = func.to_tsvector(
            "english",
            func.coalesce(MedicalRecord.title, "") + " " + func.coalesce(MedicalRecord.description, ""),
        ).match(query)
        stmt = stmt.where(search_filter)

    if cursor:
        cursor_record = await db.execute(
            select(MedicalRecord.created_at).where(MedicalRecord.id == cursor)
        )
        cursor_time = cursor_record.scalar_one_or_none()
        if cursor_time:
            stmt = stmt.where(
                and_(MedicalRecord.created_at <= cursor_time, MedicalRecord.id != cursor)
            )

    stmt = stmt.order_by(MedicalRecord.created_at.desc()).limit(limit + 1)

    result = await db.execute(stmt)
    rows = result.all()

    has_more = len(rows) > limit
    items = rows[:limit]

    records = []
    for row in items:
        record = row[0]
        doctor_name = row[1]
        prescription = row[2]

        record_data = {
            "id": str(record.id),
            "record_type": record.record_type,
            "title": record.title,
            "source": record.source,
            "doctor_id": str(record.doctor_id) if record.doctor_id else None,
            "doctor_name": doctor_name,
            "document_url": record.document_url,
            "created_at": record.created_at.isoformat(),
        }

        # Include prescription data for prescription records
        if prescription:
            record_data["prescription"] = {
                "medicines": prescription.medicines,
                "diagnosis": prescription.diagnosis,
                "notes": prescription.notes,
                "valid_until": prescription.valid_until.isoformat() if prescription.valid_until else None,
            }

        records.append(record_data)

    next_cursor = str(items[-1][0].id) if items and has_more else None
    return records, next_cursor, has_more


async def get_record_detail(
    db: AsyncSession,
    record_id: UUID,
    user_id: UUID,
    user_role: str,
) -> MedicalRecord | None:
    stmt = select(MedicalRecord).where(
        MedicalRecord.id == record_id,
        MedicalRecord.deleted_at.is_(None),
    )

    if user_role == "patient":
        stmt = stmt.where(MedicalRecord.patient_id == user_id)
    elif user_role == "doctor":
        doctor_result = await db.execute(
            select(Doctor.id).where(Doctor.user_id == user_id, Doctor.deleted_at.is_(None))
        )
        doctor_id = doctor_result.scalar_one_or_none()
        if doctor_id:
            stmt = stmt.where(MedicalRecord.doctor_id == doctor_id)
        else:
            return None

    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_doctor_patients(
    db: AsyncSession,
    doctor_id: UUID,
    cursor: UUID | None = None,
    limit: int = 20,
) -> tuple[list[dict], str | None, bool]:
    from sqlalchemy import union
    from app.models.clinic import ClinicMembership
    from app.models.patient_link import PatientClinicLink

    # doctor.user_id — needed for ClinicMembership lookup
    doctor_user_subq = select(Doctor.user_id).where(Doctor.id == doctor_id).scalar_subquery()

    # Sub-query 1: patients who have records created by this doctor
    records_stmt = (
        select(User.id, User.full_name, User.email, User.phone)
        .join(MedicalRecord, MedicalRecord.patient_id == User.id)
        .join(Doctor, MedicalRecord.doctor_id == Doctor.id)
        .where(
            Doctor.id == doctor_id,
            MedicalRecord.deleted_at.is_(None),
            User.deleted_at.is_(None),
        )
    )

    # Sub-query 2: patients with approved clinic links for any of the doctor's clinics
    clinic_stmt = (
        select(User.id, User.full_name, User.email, User.phone)
        .join(PatientClinicLink, PatientClinicLink.patient_id == User.id)
        .join(ClinicMembership, ClinicMembership.clinic_id == PatientClinicLink.clinic_id)
        .where(
            ClinicMembership.user_id == doctor_user_subq,
            ClinicMembership.is_active.is_(True),
            ClinicMembership.deleted_at.is_(None),
            PatientClinicLink.consent_status == "approved",
            PatientClinicLink.deleted_at.is_(None),
            User.deleted_at.is_(None),
        )
    )

    combined = union(records_stmt, clinic_stmt).subquery()

    stmt = (
        select(combined.c.id, combined.c.full_name, combined.c.email, combined.c.phone)
        .order_by(combined.c.full_name)
        .limit(limit + 1)
    )

    result = await db.execute(stmt)
    rows = result.all()

    has_more = len(rows) > limit
    items = rows[:limit]

    patients = [
        {
            "id": str(row.id),
            "full_name": row.full_name,
            "email": row.email,
            "phone": row.phone,
        }
        for row in items
    ]

    next_cursor = str(items[-1].id) if items and has_more else None
    return patients, next_cursor, has_more
