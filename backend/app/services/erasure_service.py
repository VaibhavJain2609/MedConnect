"""DPDP (Digital Personal Data Protection Act, 2023) data-erasure primitives.

Semantics:

* Soft-delete semantics only — the user row is anonymized in place, never
  hard-deleted, so FK integrity is preserved.
* Clinical rows (medical records, prescriptions, appointments, vitals, lab
  results) are RETAINED — they form part of the clinical record kept by the
  doctor/clinic under healthcare record-keeping obligations. Only free-text
  fields the patient entered themselves (self-uploaded record description /
  raw text) are anonymized.
* All PatientClinicLinks are revoked (consent_status="revoked") — the patient
  withdraws consent for clinics to process their data going forward.
* NotificationPreferences are deleted outright (pure account metadata).
* Audit: log_change(action="ERASE"). The audit payload records WHICH fields
  were erased, never the erased PII itself — audit_logs are immutable and
  copying the PII there would defeat the erasure.
* Keycloak is intentionally NOT touched — the app holds no IdP admin
  credential. Identity-store cleanup is a separate operational step:
  `backend/scripts/keycloak_erasure.sh` (runbook: `docs/dpdp-erasure.md`).
  Every response therefore carries ``keycloak_identity_retained: true`` so
  ops automation can detect accounts awaiting that step.

The operation is idempotent: a second request returns
``{"status": "already_processed", ...}`` without changing anything.
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.medical_record import MedicalRecord
from app.models.notification import NotificationPreferences
from app.models.patient_link import PatientClinicLink
from app.models.user import User
from app.services.audit_service import log_change

ERASED_FULL_NAME = "Erased User"
ERASED_EMAIL_DOMAIN = "erased.invalid"

# User columns anonymized in place on erasure.
_PII_FIELDS = (
    "full_name",
    "email",
    "phone",
    "emergency_contact_name",
    "emergency_contact_phone",
)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


async def request_patient_erasure(db: AsyncSession, user: User) -> dict:
    """Erase the patient's personal data. Caller owns the transaction/commit."""
    if user.erasure_requested_at is not None or user.erased_at is not None:
        return {
            "status": "already_processed",
            "erasure_requested_at": _iso(user.erasure_requested_at),
            "erased_at": _iso(user.erased_at),
            "keycloak_identity_retained": True,
        }

    now = datetime.now(timezone.utc)

    # ── Anonymize account PII ──────────────────────────────────────────────
    user.full_name = ERASED_FULL_NAME
    user.email = f"erased-{user.id}@{ERASED_EMAIL_DOMAIN}"
    user.phone = None
    user.emergency_contact_name = None
    user.emergency_contact_phone = None
    user.erasure_requested_at = now
    user.erased_at = now

    # ── Revoke all clinic consent links ────────────────────────────────────
    links_result = await db.execute(
        select(PatientClinicLink).where(
            PatientClinicLink.patient_id == user.id,
            PatientClinicLink.deleted_at.is_(None),
        )
    )
    links = list(links_result.scalars().all())
    for link in links:
        link.consent_status = "revoked"
        link.revoked_at = now

    # ── Delete notification preferences ────────────────────────────────────
    prefs_result = await db.execute(
        select(NotificationPreferences).where(
            NotificationPreferences.user_id == user.id
        )
    )
    prefs = prefs_result.scalar_one_or_none()
    prefs_deleted = prefs is not None
    if prefs is not None:
        await db.delete(prefs)

    # ── Anonymize patient-entered free text ────────────────────────────────
    # Clinical rows stay; only the free-text fields the patient typed into
    # their own self-uploaded records are blanked.
    records_result = await db.execute(
        select(MedicalRecord).where(
            MedicalRecord.patient_id == user.id,
            MedicalRecord.source == "patient_uploaded",
            MedicalRecord.deleted_at.is_(None),
        )
    )
    records = list(records_result.scalars().all())
    for record in records:
        record.description = None
        record.raw_text = None

    # ── Audit (metadata only — no erased PII values) ───────────────────────
    await log_change(
        db,
        table_name="users",
        record_id=user.id,
        action="ERASE",
        old_values={"erasure_requested_at": None, "erased_at": None},
        new_values={
            "erasure_requested_at": now.isoformat(),
            "erased_at": now.isoformat(),
            "pii_fields_erased": list(_PII_FIELDS),
            "clinic_links_revoked": len(links),
            "patient_records_anonymized": len(records),
            "notification_preferences_deleted": prefs_deleted,
        },
    )

    await db.flush()
    return {
        "status": "erased",
        "erasure_requested_at": now.isoformat(),
        "erased_at": now.isoformat(),
        # The Keycloak identity still holds the original name/email — see
        # module docstring and docs/dpdp-erasure.md for the ops follow-up.
        "keycloak_identity_retained": True,
    }
