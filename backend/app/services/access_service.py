"""
Centralized doctor↔patient access rules.

This rule previously existed as five divergent inline copies
(appointments.py, encounters.py, doctors.py, uploads.py, record_service.py)
and caused real authorization bugs. All doctor↔patient access decisions
must go through this module.

Core rule: a doctor may access a patient if
  - the doctor authored at least one non-deleted MedicalRecord for the
    patient, OR
  - the doctor's user holds an active ClinicMembership at a clinic that has
    a PatientClinicLink for the patient with consent_status='approved'
    (or 'revoked' as well when ``allow_revoked=True``).

``allow_revoked=False`` restricts the clinic-link path to ``approved`` —
revoked consent must never authorize NEW writes (appointments, encounters,
prescriptions, records); it only preserves reads of pre-revocation data.
"""
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import Select, select, union
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clinic import ClinicMembership
from app.models.medical_record import MedicalRecord
from app.models.patient_link import PatientClinicLink
from app.models.user import User


def _allowed_consent_statuses(allow_revoked: bool) -> list[str]:
    return ["approved", "revoked"] if allow_revoked else ["approved"]


def accessible_patient_ids_select(
    doctor_user_id,
    doctor_id: UUID | None = None,
    allow_revoked: bool = True,
) -> Select:
    """SQL select of patient_ids a doctor may access.

    Set-based form of the doctor↔patient rule, for queries that list or
    filter accessible patients (e.g. ``User.id.in_(...)``).

    ``doctor_user_id`` may be a UUID or a scalar subquery/expression.
    ``doctor_id`` is optional: when None, only the clinic-link path applies
    (a caller without a Doctor profile cannot have authored records).
    """
    via_links = (
        select(PatientClinicLink.patient_id.label("patient_id"))
        .join(
            ClinicMembership,
            PatientClinicLink.clinic_id == ClinicMembership.clinic_id,
        )
        .where(
            ClinicMembership.user_id == doctor_user_id,
            ClinicMembership.is_active.is_(True),
            ClinicMembership.deleted_at.is_(None),
            PatientClinicLink.consent_status.in_(_allowed_consent_statuses(allow_revoked)),
            PatientClinicLink.deleted_at.is_(None),
        )
    )
    if doctor_id is None:
        return via_links

    via_records = select(MedicalRecord.patient_id.label("patient_id")).where(
        MedicalRecord.doctor_id == doctor_id,
        MedicalRecord.deleted_at.is_(None),
    )
    combined = union(via_records, via_links).subquery()
    return select(combined.c.patient_id)


async def doctor_patient_relationship_exists(
    db: AsyncSession,
    doctor_user_id: UUID,
    doctor_id: UUID | None,
    patient_id: UUID,
    allow_revoked: bool = True,
) -> bool:
    """True if the doctor may access this patient (see module docstring).

    ``allow_revoked=False`` restricts the clinic-link path to ``approved`` —
    use it for any endpoint that creates NEW data for the patient.
    """
    if doctor_id is not None:
        record_exists = await db.execute(
            select(MedicalRecord.id)
            .where(
                MedicalRecord.doctor_id == doctor_id,
                MedicalRecord.patient_id == patient_id,
                MedicalRecord.deleted_at.is_(None),
            )
            .limit(1)
        )
        if record_exists.scalar_one_or_none() is not None:
            return True

    shared_clinic = await db.execute(
        select(ClinicMembership.id)
        .join(PatientClinicLink, PatientClinicLink.clinic_id == ClinicMembership.clinic_id)
        .where(
            ClinicMembership.user_id == doctor_user_id,
            ClinicMembership.is_active.is_(True),
            ClinicMembership.deleted_at.is_(None),
            PatientClinicLink.patient_id == patient_id,
            PatientClinicLink.consent_status.in_(_allowed_consent_statuses(allow_revoked)),
            PatientClinicLink.deleted_at.is_(None),
        )
        .limit(1)
    )
    return shared_clinic.scalar_one_or_none() is not None


async def resolve_patient_consent(
    db: AsyncSession, patient_id: UUID, clinic_id: UUID
) -> PatientClinicLink | None:
    """Resolve the PatientClinicLink between a patient and a clinic.

    - approved link  → returns None (full live access, no cutoff)
    - revoked link   → returns the link so callers can apply revoked_at as a
                       date cutoff (read-only access to pre-revocation data)
    - no link / pending → raises 403 CONSENT_REQUIRED

    Callers that receive a non-None return value must restrict data to
    records created at or before link.revoked_at.
    """
    result = await db.execute(
        select(PatientClinicLink).where(
            PatientClinicLink.patient_id == patient_id,
            PatientClinicLink.clinic_id == clinic_id,
            PatientClinicLink.deleted_at.is_(None),
        )
    )
    link = result.scalar_one_or_none()

    if link is None or link.consent_status == "pending":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "CONSENT_REQUIRED", "message": "Patient has not approved access for this clinic"}},
        )

    if link.consent_status == "revoked":
        return link  # caller must apply revoked_at cutoff

    return None  # approved — full live access


async def check_patient_consent(
    db: AsyncSession,
    patient_id: UUID,
    clinic_id: UUID,
    message: str = "Patient has revoked clinic access",
) -> None:
    """Write-path guard for clinic-scoped patient access.

    Raises 403 CONSENT_REQUIRED when there is no approved link (missing or
    pending), and 403 ACCESS_REVOKED when consent has been revoked. Use this
    before creating new data; read paths that need the revoked_at cutoff
    should call ``resolve_patient_consent`` instead.
    """
    revoked_link = await resolve_patient_consent(db, patient_id, clinic_id)
    if revoked_link is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "ACCESS_REVOKED", "message": message}},
        )


async def get_membership_role(
    db: AsyncSession, user_id: UUID, clinic_id: UUID
) -> str | None:
    """Return the user's active ClinicMembership.role for a clinic, or None.

    Roles: owner | admin | doctor | receptionist.
    """
    res = await db.execute(
        select(ClinicMembership.role).where(
            ClinicMembership.clinic_id == clinic_id,
            ClinicMembership.user_id == user_id,
            ClinicMembership.is_active.is_(True),
            ClinicMembership.deleted_at.is_(None),
        )
    )
    return res.scalar_one_or_none()


async def require_membership_role(
    db: AsyncSession,
    user: User,
    clinic_id: UUID,
    allowed_roles: set[str] | list[str] | None = None,
) -> str:
    """Return the caller's active membership role for a clinic.

    Raises 403 NOT_CLINIC_MEMBER when the user holds no active membership,
    and 403 INSUFFICIENT_CLINIC_ROLE when ``allowed_roles`` is given and the
    role is not in it. Pass ``allowed_roles=None`` to accept any active
    membership (membership check only, role returned for further gating
    such as receptionist restrictions).
    """
    role = await get_membership_role(db, user.id, clinic_id)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "NOT_CLINIC_MEMBER", "message": "Not a member of this clinic"}},
        )
    if allowed_roles is not None and role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "INSUFFICIENT_CLINIC_ROLE",
                    "message": f"This action requires one of: {', '.join(sorted(allowed_roles))}",
                }
            },
        )
    return role
