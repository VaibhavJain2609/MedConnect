from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class MedicineComponentInput(BaseModel):
    """Input schema for medicine component when creating/updating medicines"""
    component_id: UUID = Field(..., description="Component UUID")
    strength: Decimal = Field(..., gt=0, description="Strength amount (e.g., 500 for 500mg)")
    unit: str = Field(..., min_length=1, max_length=20, description="Unit (mg, mcg, g, ml, %, IU)")


class MedicineComponentResponse(BaseModel):
    """Response schema for medicine component"""
    component_id: UUID
    component_name: str
    strength: Decimal
    unit: str
    sequence: int

    @property
    def display_strength(self) -> str:
        """Format strength for display"""
        return f"{self.strength}{self.unit}"


class MedicineBase(BaseModel):
    """Base schema for medicine data"""
    brand_name: str = Field(..., min_length=2, max_length=255, description="Brand/product name")
    manufacturer: Optional[str] = Field(None, max_length=255)
    dosage_form: Optional[str] = Field(None, max_length=100, description="tablet, syrup, injection, etc.")
    pack_size: Optional[str] = Field(None, max_length=200, description="strip of 10 tablets, bottle of 100ml, etc.")
    therapeutic_class: Optional[str] = Field(None, max_length=255, description="ANTI INFECTIVES, PAIN ANALGESICS, etc.")
    schedule: Optional[str] = Field(None, max_length=10, description="Drug schedule (H, H1, X, etc.)")
    mrp: Optional[Decimal] = Field(None, ge=0, description="Maximum retail price")
    is_discontinued: bool = Field(False, description="Whether medicine is discontinued")
    habit_forming: bool = Field(False, description="Whether medicine is habit-forming/addictive")
    alternatives: Optional[dict[str, Any]] = Field(None, description="Alternative/substitute medicines")
    interactions: Optional[dict[str, Any]] = Field(None, description="Side effects, uses, chemical class, etc.")


class MedicineCreate(MedicineBase):
    """Schema for creating a new medicine"""
    components: list[MedicineComponentInput] = Field(..., min_length=1, description="At least one component required")


class MedicineUpdate(BaseModel):
    """Schema for updating a medicine (all fields optional)"""
    brand_name: Optional[str] = Field(None, min_length=2, max_length=255)
    manufacturer: Optional[str] = Field(None, max_length=255)
    dosage_form: Optional[str] = Field(None, max_length=100)
    pack_size: Optional[str] = Field(None, max_length=200)
    therapeutic_class: Optional[str] = Field(None, max_length=255)
    schedule: Optional[str] = Field(None, max_length=10)
    mrp: Optional[Decimal] = Field(None, ge=0)
    is_discontinued: Optional[bool] = None
    habit_forming: Optional[bool] = None
    alternatives: Optional[dict[str, Any]] = None
    interactions: Optional[dict[str, Any]] = None
    components: Optional[list[MedicineComponentInput]] = None


class MedicineResponse(MedicineBase):
    """Schema for medicine response"""
    id: UUID
    strength: Optional[str] = Field(None, description="Computed strength display (e.g., '500mg + 125mg')")
    components: list[MedicineComponentResponse]
    salt_composition: str = Field(..., description="Computed from components (e.g., 'Paracetamol (500mg) + Ibuprofen (200mg)')")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MedicineListItem(BaseModel):
    """Simplified medicine schema for list/search results"""
    id: UUID
    brand_name: str
    manufacturer: Optional[str]
    dosage_form: Optional[str]
    strength: Optional[str]
    mrp: Optional[Decimal]
    is_discontinued: bool
    components: list[MedicineComponentResponse]

    class Config:
        from_attributes = True


class MedicineSearchResponse(BaseModel):
    """Response for medicine search"""
    medicines: list[MedicineListItem]
    total: int
    page: int
    pages: int


class AlternativeMedicine(BaseModel):
    """Schema for alternative medicine info"""
    brand_name: str
    manufacturer: Optional[str]
    mrp: Optional[Decimal]


class MedicineAlternativesResponse(BaseModel):
    """Response for medicine alternatives"""
    medicine_id: UUID
    medicine_name: str
    alternatives: list[dict[str, Any]]
