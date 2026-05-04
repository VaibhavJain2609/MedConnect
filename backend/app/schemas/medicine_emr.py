"""Pydantic schemas for EMR medicine API."""

from uuid import UUID
from datetime import datetime, date
from decimal import Decimal
from pydantic import BaseModel, Field


# ============================================================================
# CLASSIFICATIONS
# ============================================================================

class ChemicalClassBase(BaseModel):
    class_name: str
    description: str | None = None


class ChemicalClassResponse(ChemicalClassBase):
    chemical_class_id: UUID

    class Config:
        from_attributes = True


class TherapeuticClassBase(BaseModel):
    class_name: str
    description: str | None = None
    icd10_codes: str | None = None


class TherapeuticClassResponse(TherapeuticClassBase):
    therapeutic_class_id: UUID

    class Config:
        from_attributes = True


class ActionClassBase(BaseModel):
    class_name: str
    description: str | None = None
    mechanism: str | None = None


class ActionClassResponse(ActionClassBase):
    action_class_id: UUID

    class Config:
        from_attributes = True


# ============================================================================
# SALTS & STRENGTHS
# ============================================================================

class SaltStrengthBase(BaseModel):
    strength_value: Decimal
    strength_unit: str
    is_standard_strength: bool | None = True
    pediatric_approved: bool | None = False


class SaltStrengthResponse(SaltStrengthBase):
    salt_strength_id: UUID
    salt_id: UUID
    display_strength: str

    class Config:
        from_attributes = True


class SaltBase(BaseModel):
    salt_name: str
    description: str | None = None
    chemical_formula: str | None = None
    habit_forming: bool = False
    prescription_required: bool = True
    schedule: str | None = None
    pregnancy_category: str | None = None
    lactation_safe: bool | None = None
    lactation_notes: str | None = None


class SaltSideEffectItem(BaseModel):
    """A side effect as exposed on the salt detail view (flattened from join)."""
    side_effect_id: UUID
    side_effect_name: str
    severity: str | None = None
    frequency: str | None = None
    description: str | None = None
    notes: str | None = None


class SaltContraindicationItem(BaseModel):
    """A contraindication as exposed on the salt detail view (flattened from join)."""
    contraindication_id: UUID
    contraindication_name: str
    description: str | None = None
    icd10_code: str | None = None
    severity: str | None = None
    notes: str | None = None


class SaltResponse(SaltBase):
    salt_id: UUID
    chemical_class: ChemicalClassResponse | None = None
    therapeutic_class: TherapeuticClassResponse | None = None
    action_class: ActionClassResponse | None = None
    strengths: list[SaltStrengthResponse] = []
    side_effects: list[SaltSideEffectItem] = []
    contraindications: list[SaltContraindicationItem] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SaltListResponse(BaseModel):
    """Response for salt search/list."""
    salts: list[SaltResponse]
    total: int
    page: int
    pages: int


# ============================================================================
# MANUFACTURERS & BRANDS
# ============================================================================

class ManufacturerBase(BaseModel):
    manufacturer_name: str
    country: str | None = None
    license_number: str | None = None
    is_active: bool = True


class ManufacturerResponse(ManufacturerBase):
    manufacturer_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BrandCompositionResponse(BaseModel):
    """Composition detail for a brand."""
    composition_id: UUID
    salt_name: str
    strength_value: Decimal
    strength_unit: str
    display_strength: str
    sequence: int

    class Config:
        from_attributes = True


class BrandBase(BaseModel):
    brand_name: str
    is_discontinued: bool = False
    drug_type: str = "allopathy"


class BrandResponse(BrandBase):
    brand_id: UUID
    manufacturer: ManufacturerResponse | None = None
    compositions: list[BrandCompositionResponse] = []
    salt_composition: str  # Computed property
    side_effects: list[SaltSideEffectItem] = []
    launch_date: date | None = None
    discontinuation_date: date | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BrandListResponse(BaseModel):
    """Response for brand search/list."""
    brands: list[BrandResponse]
    total: int
    page: int
    pages: int


# ============================================================================
# UNIFIED SEARCH
# ============================================================================

class SaltSearchResult(BaseModel):
    """Salt search result (simplified)."""
    id: UUID = Field(alias="salt_id")
    name: str = Field(alias="salt_name")
    type: str = "salt"
    chemical_class: str | None = None
    therapeutic_class: str | None = None
    strengths: list[dict]

    class Config:
        populate_by_name = True


class BrandSearchResult(BaseModel):
    """Brand search result (simplified)."""
    id: UUID = Field(alias="brand_id")
    name: str = Field(alias="brand_name")
    type: str = "brand"
    manufacturer: str | None = None
    composition: str
    is_discontinued: bool

    class Config:
        populate_by_name = True


class UnifiedSearchResponse(BaseModel):
    """Unified search across salts and brands."""
    salts: list[dict]
    brands: list[dict]
    total_salts: int
    total_brands: int


# ============================================================================
# CLINICAL SAFETY
# ============================================================================

class SideEffectResponse(BaseModel):
    side_effect_id: UUID
    side_effect_name: str
    severity: str | None = None
    frequency: str | None = None
    description: str | None = None

    class Config:
        from_attributes = True


class ContraindicationResponse(BaseModel):
    contraindication_id: UUID
    contraindication_name: str
    description: str | None = None
    icd10_code: str | None = None
    severity: str | None = None

    class Config:
        from_attributes = True


class DrugInteractionResponse(BaseModel):
    interaction_id: UUID
    salt_1_name: str
    salt_2_name: str
    severity: str
    effect: str
    mechanism: str | None = None
    management: str | None = None
    evidence_level: str | None = None

    class Config:
        from_attributes = True


# ============================================================================
# USES
# ============================================================================

class UseResponse(BaseModel):
    use_id: UUID
    use_name: str
    description: str | None = None
    icd10_code: str | None = None
    is_primary_indication: bool = False

    class Config:
        from_attributes = True
