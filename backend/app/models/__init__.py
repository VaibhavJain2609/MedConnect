from app.models.user import User
from app.models.doctor import Doctor
from app.models.medical_record import MedicalRecord
from app.models.prescription import Prescription
from app.models.prescription_refill import PrescriptionRefillRequest
from app.models.prescription_template import PrescriptionTemplate
from app.models.notification import Notification, NotificationPreferences, NotificationType
from app.models.push_subscription import PushSubscription
from app.models.clinic import Clinic, ClinicBranch, ClinicMembership
from app.models.clinic_invite import ClinicInvite, ClinicJoinRequest
from app.models.patient_link import PatientClinicLink, PatientLinkCode
from app.models.record_access import RecordAccessConsent
from app.models.appointment import Appointment
from app.models.doctor_availability import DoctorAvailability, DoctorLeave
from app.models.encounter import Encounter
from app.models.platform_setting import PlatformSetting
from app.models.reminder_log import ReminderLog
from app.models.billing import Billing, BillingItem
from app.models.vital import PatientVital, VITAL_TYPES
from app.models.audit import AuditLog
from app.models.lab_result import LabResult

# EMR Medicine Models
from app.models.medicine import (
    # Classifications
    ChemicalClass,
    TherapeuticClass,
    ActionClass,
    # Salts
    Salt,
    SaltStrength,
    # Clinical Safety
    SideEffect,
    Contraindication,
    DrugInteraction,
    SaltSideEffect,
    SaltContraindication,
    BrandSideEffect,
    # Indications
    Use,
    SaltUse,
    # Alternatives
    SaltAlternative,
    # Commercial
    Manufacturer,
    Brand,
    BrandComposition,
    # Packaging
    PackForm,
    BrandPackaging,
    # Dosing
    DosingGuideline,
    # Audit
    MedicineSearchLog,
    PrescriptionAudit,
)

__all__ = [
    # Main app models
    "User",
    "Doctor",
    "MedicalRecord",
    "Prescription",
    "PrescriptionRefillRequest",
    "PrescriptionTemplate",
    "Notification",
    "NotificationPreferences",
    "NotificationType",
    "PushSubscription",
    "Clinic",
    "ClinicBranch",
    "ClinicMembership",
    "ClinicInvite",
    "ClinicJoinRequest",
    "PatientClinicLink",
    "PatientLinkCode",
    "RecordAccessConsent",
    "Appointment",
    "DoctorAvailability",
    "DoctorLeave",
    "Encounter",
    "PlatformSetting",
    "ReminderLog",
    "Billing",
    "BillingItem",
    "PatientVital",
    "VITAL_TYPES",
    "AuditLog",
    "LabResult",
    # Medicine models
    "ChemicalClass",
    "TherapeuticClass",
    "ActionClass",
    "Salt",
    "SaltStrength",
    "SideEffect",
    "Contraindication",
    "DrugInteraction",
    "SaltSideEffect",
    "SaltContraindication",
    "BrandSideEffect",
    "Use",
    "SaltUse",
    "SaltAlternative",
    "Manufacturer",
    "Brand",
    "BrandComposition",
    "PackForm",
    "BrandPackaging",
    "DosingGuideline",
    "MedicineSearchLog",
    "PrescriptionAudit",
]
