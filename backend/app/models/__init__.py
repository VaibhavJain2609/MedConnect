from app.models.user import User
from app.models.doctor import Doctor
from app.models.medical_record import MedicalRecord
from app.models.prescription import Prescription
from app.models.notification import Notification, NotificationPreferences, NotificationType

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
