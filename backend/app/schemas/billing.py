from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.billing import BILLING_STATUSES, PAYMENT_METHODS


class BillingItemCreate(BaseModel):
    """One line item supplied at bill creation.

    The server computes the line ``amount`` (quantity * unit_amount) and the
    bill total — clients never send either.
    """

    description: str = Field(min_length=1, max_length=500)
    quantity: Decimal = Field(default=Decimal(1), gt=0, decimal_places=2)
    unit_amount: Decimal = Field(ge=0, decimal_places=2)


class BillingCreate(BaseModel):
    patient_id: UUID
    clinic_id: Optional[UUID] = None
    appointment_id: Optional[UUID] = None
    # Optional when `items` is supplied — the server then computes the total
    # as sum(items). Required otherwise (Billing.amount is NOT NULL and has
    # no tax column).
    amount: Optional[Decimal] = Field(None, gt=0, decimal_places=2)
    notes: Optional[str] = Field(None, max_length=1000)
    items: Optional[list[BillingItemCreate]] = None

    @model_validator(mode="after")
    def amount_or_items_required(self):
        if not self.items and self.amount is None:
            raise ValueError("amount is required when items are not provided")
        return self


class BillingUpdate(BaseModel):
    status: Optional[str] = None
    payment_method: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=1000)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in BILLING_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(BILLING_STATUSES)}")
        return v

    @field_validator("payment_method")
    @classmethod
    def validate_payment_method(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in PAYMENT_METHODS:
            raise ValueError(f"payment_method must be one of: {', '.join(PAYMENT_METHODS)}")
        return v


class BillingItemResponse(BaseModel):
    id: str
    description: str
    quantity: str
    unit_amount: str
    amount: str

    model_config = {"from_attributes": True}

    @field_validator("id", mode="before")
    @classmethod
    def stringify_item_id(cls, v):
        return str(v) if v is not None else v

    @field_validator("quantity", "unit_amount", "amount", mode="before")
    @classmethod
    def stringify_item_decimal(cls, v):
        return str(v) if v is not None else v


class BillingResponse(BaseModel):
    id: str
    patient_id: str
    patient_name: Optional[str] = None
    clinic_id: Optional[str] = None
    clinic_name: Optional[str] = None
    appointment_id: Optional[str] = None
    amount: str
    status: str
    payment_method: Optional[str] = None
    notes: Optional[str] = None
    items: list[BillingItemResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("id", "patient_id", "clinic_id", "appointment_id", mode="before")
    @classmethod
    def stringify_uuid(cls, v):
        return str(v) if v is not None else v

    @field_validator("amount", mode="before")
    @classmethod
    def stringify_amount(cls, v):
        return str(v) if v is not None else v


class BillingListResponse(BaseModel):
    data: list[BillingResponse]
    total: int


class DailyRevenueResponse(BaseModel):
    date: str
    total_paid: str
    bill_count: int


class MonthlyRevenueResponse(BaseModel):
    year: int
    month: int
    total_paid: str
    bill_count: int
    daily_breakdown: list[DailyRevenueResponse]


class UnpaidSummaryResponse(BaseModel):
    data: list[BillingResponse]
    total: int
    total_unpaid_amount: str
