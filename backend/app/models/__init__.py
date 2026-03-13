from app.models.user import User
from app.models.doctor import Doctor
from app.models.medical_record import MedicalRecord
from app.models.prescription import Prescription
from app.models.notification import Notification, NotificationPreferences, NotificationType
from app.models.clinic import Clinic, ClinicBranch, ClinicMembership
from app.models.clinic_invite import ClinicInvite, ClinicJoinRequest
from app.models.patient_link import PatientClinicLink, PatientLinkCode
from app.models.appointment import Appointment
from app.models.vital import PatientVital, VITAL_TYPES
from app.models.audit import AuditLog

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
    "Notification",
    "NotificationPreferences",
    "NotificationType",
    "Clinic",
    "ClinicBranch",
    "ClinicMembership",
    "ClinicInvite",
    "ClinicJoinRequest",
    "PatientClinicLink",
    "PatientLinkCode",
    "Appointment",
    "PatientVital",
    "VITAL_TYPES",
    "AuditLog",
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
