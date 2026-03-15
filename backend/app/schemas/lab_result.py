from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class LabResultCreate(BaseModel):
    patient_id: UUID
    doctor_id: Optional[UUID] = None
    test_name: str
    test_category: Optional[str] = None
    appointment_date: datetime
    notes: Optional[str] = None


class LabResultUpdate(BaseModel):
    status: Optional[str] = None  # pending | in_progress | received | completed
    result_value: Optional[str] = None
    result_unit: Optional[str] = None
    normal_range: Optional[str] = None
    abnormal_flag: Optional[bool] = None
    notes: Optional[str] = None
    test_name: Optional[str] = None
    test_category: Optional[str] = None
    appointment_date: Optional[datetime] = None
    doctor_id: Optional[UUID] = None


class LabResultResponse(BaseModel):
    id: UUID
    test_id: str
    patient_id: UUID
    patient_name: str
    patient_photo: Optional[str] = None
    gender: Optional[str] = None
    doctor_id: Optional[UUID] = None
    doctor_name: Optional[str] = None
    doctor_photo: Optional[str] = None
    test_name: str
    test_category: Optional[str] = None
    appointment_date: datetime
    status: str
    result_value: Optional[str] = None
    result_unit: Optional[str] = None
    normal_range: Optional[str] = None
    abnormal_flag: bool = False
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
