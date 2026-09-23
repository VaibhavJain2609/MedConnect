"""Doctor lab orders.

POST   /api/v1/lab-orders                  — create an order (verified doctor)
GET    /api/v1/lab-orders                  — doctor's own orders (?patient_id, ?status)
GET    /api/v1/lab-orders/mine             — patient's own orders
PATCH  /api/v1/lab-orders/{order_id}/status — ordered → completed | cancelled

Patient-access rule (same convention as doctors.py / lab-results ingest):
creating an order is a WRITE, so the doctor must have an active relationship
with the patient — an authored non-deleted MedicalRecord OR an approved
PatientClinicLink with a clinic where the doctor holds an active membership
(``allow_revoked=False``; revoked consent never authorises new writes). When
the ``X-Clinic-Id`` clinic context is present, the clinic-scoped
``check_patient_consent`` write-path guard applies instead.

Status transitions are enforced server-side: only ``ordered`` orders may
transition, to ``completed`` or ``cancelled`` (both terminal). A completion
may attach ``result_record_id`` — a MedicalRecord for the same patient that
the doctor can access.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Literal

from app.database import get_db
from app.dependencies import get_active_clinic, get_verified_doctor, require_patient
from app.models.doctor import Doctor
from app.models.lab_order import LabOrder
from app.models.medical_record import MedicalRecord
from app.models.user import User
from app.services import access_service

router = APIRouter(prefix="/api/v1/lab-orders", tags=["lab-orders"])

TERMINAL_STATUSES = {"completed", "cancelled"}


class LabOrderCreate(BaseModel):
    patient_id: UUID
    test_name: str = Field(min_length=1, max_length=255)
    notes: str | None = None


class LabOrderStatusUpdate(BaseModel):
    status: Literal["completed", "cancelled"]
    result_record_id: UUID | None = None


def _serialize(order: LabOrder, doctor_name: str | None = None) -> dict:
    return {
        "id": str(order.id),
        "patient_id": str(order.patient_id),
        "doctor_id": str(order.doctor_id),
        "clinic_id": str(order.clinic_id) if order.clinic_id else None,
        "test_name": order.test_name,
        "notes": order.notes,
        "status": order.status,
        "result_record_id": str(order.result_record_id) if order.result_record_id else None,
        "doctor_name": doctor_name,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "updated_at": order.updated_at.isoformat() if order.updated_at else None,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_lab_order(
    body: LabOrderCreate,
    doctor_info: tuple[User, Doctor] = Depends(get_verified_doctor),
    db: AsyncSession = Depends(get_db),
    clinic_context: tuple | None = Depends(get_active_clinic),
):
    _, doctor = doctor_info

    patient = await db.get(User, body.patient_id)
    if not patient or patient.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Patient not found"}},
        )

    clinic_id = clinic_context[0] if clinic_context else None
    if clinic_id:
        await access_service.check_patient_consent(
            db, body.patient_id, clinic_id,
            message="Patient has revoked clinic access. Cannot create lab orders.",
        )
    else:
        if not await access_service.doctor_patient_relationship_exists(
            db, doctor.user_id, doctor.id, body.patient_id, allow_revoked=False
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "PATIENT_ACCESS_DENIED", "message": "No relationship with this patient"}},
            )

    order = LabOrder(
        patient_id=body.patient_id,
        doctor_id=doctor.id,
        clinic_id=clinic_id,
        test_name=body.test_name.strip(),
        notes=body.notes,
        status="ordered",
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return _serialize(order)


@router.get("")
async def list_lab_orders(
    patient_id: UUID | None = Query(None),
    order_status: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    doctor_info: tuple[User, Doctor] = Depends(get_verified_doctor),
    db: AsyncSession = Depends(get_db),
):
    _, doctor = doctor_info

    if order_status is not None and order_status not in LabOrder.VALID_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_STATUS",
                    "message": f"status must be one of: {', '.join(LabOrder.VALID_STATUSES)}",
                }
            },
        )

    stmt = (
        select(LabOrder)
        .where(LabOrder.doctor_id == doctor.id, LabOrder.deleted_at.is_(None))
        .order_by(LabOrder.created_at.desc())
        .limit(limit)
    )
    if patient_id is not None:
        stmt = stmt.where(LabOrder.patient_id == patient_id)
    if order_status is not None:
        stmt = stmt.where(LabOrder.status == order_status)

    result = await db.execute(stmt)
    orders = result.scalars().all()
    return {"data": [_serialize(o) for o in orders]}


# NOTE: must be declared before any /{order_id} path so "mine" isn't captured
# by a UUID path parameter.
@router.get("/mine")
async def list_my_lab_orders(
    user: User = Depends(require_patient),
    db: AsyncSession = Depends(get_db),
):
    """Patient-facing list — returns only the caller's own orders."""
    stmt = (
        select(LabOrder, User.full_name.label("doctor_name"))
        .join(Doctor, LabOrder.doctor_id == Doctor.id)
        .join(User, Doctor.user_id == User.id)
        .where(LabOrder.patient_id == user.id, LabOrder.deleted_at.is_(None))
        .order_by(LabOrder.created_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.all()
    return {"data": [_serialize(order, doctor_name=name) for order, name in rows]}


@router.patch("/{order_id}/status")
async def update_lab_order_status(
    order_id: UUID,
    body: LabOrderStatusUpdate,
    doctor_info: tuple[User, Doctor] = Depends(get_verified_doctor),
    db: AsyncSession = Depends(get_db),
):
    _, doctor = doctor_info

    order = await db.get(LabOrder, order_id)
    if not order or order.deleted_at is not None or order.doctor_id != doctor.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Lab order not found"}},
        )

    if order.status != "ordered":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "error": {
                    "code": "INVALID_TRANSITION",
                    "message": f"Cannot transition from '{order.status}' to '{body.status}'",
                }
            },
        )

    if body.status == "cancelled" and body.result_record_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "result_record_id can only be attached when completing an order",
                }
            },
        )

    if body.result_record_id is not None:
        record = await db.get(MedicalRecord, body.result_record_id)
        if not record or record.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "NOT_FOUND", "message": "Result record not found"}},
            )
        if record.patient_id != order.patient_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "RECORD_PATIENT_MISMATCH",
                        "message": "Result record belongs to a different patient",
                    }
                },
            )
        if record.doctor_id != doctor.id and not await access_service.doctor_patient_relationship_exists(
            db, doctor.user_id, doctor.id, record.patient_id, allow_revoked=True
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "FORBIDDEN", "message": "No access to this record"}},
            )

    order.status = body.status
    if body.result_record_id is not None:
        order.result_record_id = body.result_record_id
    await db.commit()
    await db.refresh(order)
    return _serialize(order)
