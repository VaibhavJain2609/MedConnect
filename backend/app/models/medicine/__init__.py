"""Medicine models for EMR schema."""

from .catalog import Component, Medicine, MedicineComponent
from .classifications import ChemicalClass, TherapeuticClass, ActionClass
from .salts import Salt, SaltStrength
from .clinical_safety import SideEffect, Contraindication, DrugInteraction, SaltSideEffect, SaltContraindication, BrandSideEffect
from .indications import Use, SaltUse
from .alternatives import SaltAlternative
from .commercial import Manufacturer, Brand, BrandComposition
from .packaging import PackForm, BrandPackaging
from .dosing import DosingGuideline
from .audit import MedicineSearchLog, PrescriptionAudit

__all__ = [
    # Catalog (admin-managed medicines and components)
    "Medicine",
    "Component",
    "MedicineComponent",
    # Classifications
    "ChemicalClass",
    "TherapeuticClass",
    "ActionClass",
    # Salts
    "Salt",
    "SaltStrength",
    # Clinical Safety
    "SideEffect",
    "Contraindication",
    "DrugInteraction",
    "SaltSideEffect",
    "SaltContraindication",
    "BrandSideEffect",
    # Indications
    "Use",
    "SaltUse",
    # Alternatives
    "SaltAlternative",
    # Commercial
    "Manufacturer",
    "Brand",
    "BrandComposition",
    # Packaging
    "PackForm",
    "BrandPackaging",
    # Dosing
    "DosingGuideline",
    # Audit
    "MedicineSearchLog",
    "PrescriptionAudit",
]
