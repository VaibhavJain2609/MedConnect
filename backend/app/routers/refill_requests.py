"""
Prescription refill / renewal request endpoints.

- POST /api/v1/prescriptions/{id}/refill-request  — patient requests a refill
- GET  /api/v1/prescriptions/refill-requests/mine — patient's own requests
- GET  /api/v1/prescriptions/refill-requests      — doctor's list (clinic-scoped
      when X-Clinic-Id is present, otherwise requests on the doctor's own
      prescriptions); filterable by ?status=
- POST /api/v1/refill-requests/{id}/respond       — doctor approves/declines

Approving creates a NEW prescription cloned from the original's medicines via
the existing create flow (which also notifies the patient). Declining notifies
the patient with the doctor's response note.
"""

from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import (
    get_active_clinic,
    get_current_doctor,
    get_verified_doctor,
    require_patient,
)
from app.models.doctor import Doctor
from app.models.prescription import Prescription
from app.models.prescription_refill import PrescriptionRefillRequest
from app.models.user import User
from app.schemas.prescription_refill import RefillRequestCreate, RefillRespondRequest
from app.services import access_service
from app.services.notification_service import create_notification
from app.services.prescription_service import create_prescription

router = APIRouter(prefix="/api/v1", tags=["refill-requests"])

VALID_STATUSES = {"pending", "approved", "declined"}


def _err(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message}},
    )


def _serialize(
    rr: PrescriptionRefillRequest,
    *,
    patient_name: str | None = None,
    rx: Prescription | None = None,
) -> dict:
    return {
        "id": str(rr.id),
        "prescription_id": str(rr.prescription_id),
        "patient_id": str(rr.patient_id),
        "patient_name": patient_name,
        "doctor_id": str(rr.doctor_id),
        "clinic_id": str(rr.clinic_id) if rr.clinic_id else None,
        "note": rr.note,
        "status": rr.status,
        "response_note": rr.response_note,
        "new_prescription_id": str(rr.new_prescription_id) if rr.new_prescription_id else None,
        "responded_at": rr.responded_at.isoformat() if rr.responded_at else None,
        "created_at": rr.created_at.isoformat() if rr.created_at else None,
        # Original prescription context (doctor list view)
        "medicines": rx.medicines if rx else None,
        "diagnosis": rx.diagnosis if rx else None,
        "valid_until": rx.valid_until.isoformat() if rx and rx.valid_until else None,
        "prescribed_at": rx.created_at.isoformat() if rx and rx.created_at else None,
    }


# ---------------------------------------------------------------------------
# Patient endpoints
# ---------------------------------------------------------------------------


@router.post("/prescriptions/{prescription_id}/refill-request", status_code=status.HTTP_201_CREATED)
async def request_refill(
    prescription_id: UUID,
    req: RefillRequestCreate,
    user: User = Depends(require_patient),
    db: AsyncSession = Depends(get_db),
):
    """Request a refill/renewal of one of the patient's own prescriptions.

    Any non-deleted prescription is requestable — including expired ones,
    which is the common refill case. A second request while one is still
    pending is rejected (409), and a partial unique index enforces it.
    """
    result = await db.execute(
        select(Prescription).where(
            Prescription.id == prescription_id,
            Prescription.deleted_at.is_(None),
        )
    )
    rx = result.scalar_one_or_none()
    if not rx:
        raise _err(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Prescription not found")
    if rx.patient_id != user.id:
        raise _err(status.HTTP_403_FORBIDDEN, "FORBIDDEN", "Not your prescription")

    pending = await db.execute(
        select(PrescriptionRefillRequest.id).where(
            PrescriptionRefillRequest.prescription_id == rx.id,
            PrescriptionRefillRequest.status == "pending",
            PrescriptionRefillRequest.deleted_at.is_(None),
        )
    )
    if pending.scalar_one_or_none() is not None:
        raise _err(
            status.HTTP_409_CONFLICT,
            "REFILL_ALREADY_PENDING",
            "A refill request for this prescription is already pending",
        )

    rr = PrescriptionRefillRequest(
        prescription_id=rx.id,
        patient_id=user.id,
        doctor_id=rx.doctor_id,
        clinic_id=rx.clinic_id,
        note=req.note,
    )
    db.add(rr)
    try:
        await db.flush()
    except IntegrityError:
        # Lost a race against the partial unique index — a pending request
        # was created concurrently.
        await db.rollback()
        raise _err(
            status.HTTP_409_CONFLICT,
            "REFILL_ALREADY_PENDING",
            "A refill request for this prescription is already pending",
        )

    # Notify the prescribing doctor (their User account) about the request.
    doctor = await db.get(Doctor, rx.doctor_id)
    if doctor and doctor.deleted_at is None:
        await create_notification(
            db=db,
            user_id=doctor.user_id,
            notif_type="prescription",
            title=f"Refill request from {user.full_name or 'a patient'}",
            body=req.note or "A patient has requested a prescription refill.",
            action_url="/doctor/refill-requests",
            metadata={"refill_request_id": str(rr.id), "prescription_id": str(rx.id)},
        )

    return _serialize(rr)


@router.get("/prescriptions/refill-requests/mine")
async def my_refill_requests(
    user: User = Depends(require_patient),
    db: AsyncSession = Depends(get_db),
):
    """List the current patient's refill requests (newest first, capped)."""
    result = await db.execute(
        select(PrescriptionRefillRequest)
        .where(
            PrescriptionRefillRequest.patient_id == user.id,
            PrescriptionRefillRequest.deleted_at.is_(None),
        )
        .order_by(PrescriptionRefillRequest.created_at.desc())
        .limit(200)
    )
    return {"data": [_serialize(rr) for rr in result.scalars().all()]}


# ---------------------------------------------------------------------------
# Doctor endpoints
# ---------------------------------------------------------------------------


@router.get("/prescriptions/refill-requests")
async def list_refill_requests(
    status_filter: str | None = Query(None, alias="status"),
    doctor_info: tuple[User, Doctor] = Depends(get_current_doctor),
    clinic_ctx: tuple | None = Depends(get_active_clinic),
    db: AsyncSession = Depends(get_db),
):
    """List refill requests for the doctor.

    With an X-Clinic-Id header: requests scoped to that clinic (receptionist
    memberships are excluded — refill requests expose clinical detail).
    Without it: requests on prescriptions this doctor authored.
    """
    _, doctor = doctor_info

    if status_filter is not None and status_filter not in VALID_STATUSES:
        raise _err(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "INVALID_STATUS",
            f"status must be one of: {', '.join(sorted(VALID_STATUSES))}",
        )

    stmt = (
        select(PrescriptionRefillRequest, Prescription, User.full_name.label("patient_name"))
        .join(Prescription, Prescription.id == PrescriptionRefillRequest.prescription_id)
        .join(User, User.id == PrescriptionRefillRequest.patient_id)
        .where(PrescriptionRefillRequest.deleted_at.is_(None))
        .order_by(PrescriptionRefillRequest.created_at.desc())
        .limit(200)
    )

    if clinic_ctx:
        clinic_id, membership_role = clinic_ctx
        if membership_role == "receptionist":
            raise _err(
                status.HTTP_403_FORBIDDEN,
                "RECEPTIONIST_NO_CLINICAL_ACCESS",
                "Receptionists cannot view refill requests",
            )
        stmt = stmt.where(PrescriptionRefillRequest.clinic_id == clinic_id)
    else:
        stmt = stmt.where(PrescriptionRefillRequest.doctor_id == doctor.id)

    if status_filter:
        stmt = stmt.where(PrescriptionRefillRequest.status == status_filter)

    result = await db.execute(stmt)
    return {
        "data": [
            _serialize(rr, patient_name=patient_name, rx=rx)
            for rr, rx, patient_name in result.all()
        ]
    }


@router.post("/refill-requests/{request_id}/respond")
async def respond_refill_request(
    request_id: UUID,
    req: RefillRespondRequest,
    doctor_info: tuple[User, Doctor] = Depends(get_verified_doctor),
    db: AsyncSession = Depends(get_db),
):
    """Approve or decline a refill request.

    Authorization: for clinic-scoped requests, the responding doctor must
    hold an active owner/admin/doctor membership in the prescribing clinic;
    for non-clinic prescriptions, only the original prescriber may respond.

    Approve issues a NEW prescription cloned from the original's medicines
    (valid_until is extended by the original course length). The patient is
    notified in both cases via the notification service.
    """
    user, doctor = doctor_info

    result = await db.execute(
        select(PrescriptionRefillRequest).where(
            PrescriptionRefillRequest.id == request_id,
            PrescriptionRefillRequest.deleted_at.is_(None),
        )
    )
    rr = result.scalar_one_or_none()
    if not rr:
        raise _err(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Refill request not found")
    if rr.status != "pending":
        raise _err(
            status.HTTP_409_CONFLICT,
            "REFILL_ALREADY_RESOLVED",
            "This refill request has already been resolved",
        )

    if rr.clinic_id:
        # Only the prescribing clinic's clinical staff may respond.
        await access_service.require_membership_role(
            db, user, rr.clinic_id, allowed_roles={"owner", "admin", "doctor"}
        )
    elif rr.doctor_id != doctor.id:
        raise _err(status.HTTP_403_FORBIDDEN, "FORBIDDEN", "Only the prescribing doctor can respond")

    if req.action == "approve":
        rx = await db.get(Prescription, rr.prescription_id)
        if not rx or rx.deleted_at is not None:
            raise _err(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Original prescription not found")

        if rr.clinic_id:
            await access_service.check_patient_consent(
                db, rr.patient_id, rr.clinic_id,
                message="Patient has revoked clinic access. Cannot issue a refill.",
            )

        # Extend validity by the original course length when it had one.
        new_valid_until: date | None = None
        if rx.valid_until and rx.created_at:
            course_days = (rx.valid_until - rx.created_at.date()).days
            new_valid_until = date.today() + timedelta(days=max(course_days, 1))

        try:
            new_rx = await create_prescription(
                db=db,
                doctor_id=doctor.id,
                patient_id=rr.patient_id,
                medicines=rx.medicines if isinstance(rx.medicines, list) else [],
                diagnosis=rx.diagnosis,
                notes=req.note or rx.notes,
                valid_until=new_valid_until,
                clinic_id=rr.clinic_id,
                branch_id=rx.branch_id,
            )
        except ValueError as e:
            raise _err(status.HTTP_400_BAD_REQUEST, "VALIDATION_ERROR", str(e))

        rr.status = "approved"
        rr.new_prescription_id = new_rx.id
        # create_prescription already notifies the patient of the new rx.
    else:
        rr.status = "declined"
        await create_notification(
            db=db,
            user_id=rr.patient_id,
            notif_type="prescription",
            title="Refill request declined",
            body=req.note or "Your prescription refill request was declined.",
            action_url="/patient/medications",
            metadata={"refill_request_id": str(rr.id), "prescription_id": str(rr.prescription_id)},
        )

    rr.response_note = req.note
    rr.responded_by_id = doctor.id
    rr.responded_at = datetime.now(timezone.utc)
    await db.flush()

    return _serialize(rr)
