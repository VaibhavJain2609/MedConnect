from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ComponentBase(BaseModel):
    """Base schema for component data"""
    name: str = Field(..., min_length=2, max_length=255, description="Component name (e.g., Paracetamol)")
    common_names: Optional[str] = Field(None, max_length=500, description="Alternative names, comma-separated")
    category: Optional[str] = Field(None, max_length=100, description="Category (e.g., Analgesic, Antibiotic)")
    description: Optional[str] = None


class ComponentCreate(ComponentBase):
    """Schema for creating a new component"""
    pass


class ComponentUpdate(BaseModel):
    """Schema for updating a component (all fields optional)"""
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    common_names: Optional[str] = Field(None, max_length=500)
    category: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None


class ComponentResponse(ComponentBase):
    """Schema for component response"""
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ComponentWithUsage(ComponentResponse):
    """Component with usage statistics"""
    medicine_count: int = Field(..., description="Number of medicines using this component")


class ComponentSearchResponse(BaseModel):
    """Response for component search/autocomplete"""
    components: list[ComponentWithUsage]
    total: int
