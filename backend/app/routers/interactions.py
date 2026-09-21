"""Drug interaction API endpoints for MD-18."""

from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db, get_medicine_db
from app.dependencies import get_current_user, require_admin
from app.models.doctor import Doctor
from app.models.user import User
from app.services import access_service, allergy_service
from app.services.interaction_service import InteractionService


router = APIRouter(prefix="/interactions", tags=["interactions"])


class InteractionResponse(BaseModel):
    """Drug interaction response model."""
    interaction_id: str
    salt_1: dict
    salt_2: dict
    severity: str
    effect: str
    mechanism: str | None
    management: str | None
    evidence_level: str | None


class CheckInteractionsRequest(BaseModel):
    """Request model for checking interactions between multiple salts."""
    salt_ids: list[UUID]  # List of salt UUIDs


class CheckAllergiesRequest(BaseModel):
    """Request model for checking a patient's allergies against salts."""
    patient_id: UUID
    salt_ids: list[UUID]  # List of salt UUIDs (e.g. resolved from selected brands)


class AllergyConflict(BaseModel):
    """One allergy↔salt conflict."""
    salt_id: str
    salt_name: str
    allergy: str
    match: Literal["exact", "partial"]


class CheckAllergiesResponse(BaseModel):
    """Structured allergy check result."""
    conflicts: list[AllergyConflict]
    checked_allergies: list[str]  # patient allergy terms that produced NO match


class CreateInteractionRequest(BaseModel):
    """Request model for creating a new interaction."""
    salt_id_1: UUID
    salt_id_2: UUID
    severity: str
    effect: str
    mechanism: str | None = None
    management: str | None = None
    evidence_level: str | None = None


@router.post("/check", response_model=list[InteractionResponse])
async def check_interactions(
    request: CheckInteractionsRequest,
    db: AsyncSession = Depends(get_medicine_db),
    user: User = Depends(get_current_user),
):
    """
    Check for drug interactions between multiple salts.

    Use this endpoint when creating a prescription with multiple medicines
    to detect potential drug-drug interactions.

    Returns interactions ordered by severity (most severe first).
    """
    interactions = await InteractionService.check_interactions(db, request.salt_ids)
    return interactions


@router.post("/check-allergies", response_model=CheckAllergiesResponse)
async def check_allergies(
    request: CheckAllergiesRequest,
    db: AsyncSession = Depends(get_db),
    medicine_db: AsyncSession = Depends(get_medicine_db),
    user: User = Depends(get_current_user),
):
    """
    Check a patient's recorded allergies against a set of catalog salts.

    Replaces client-side fuzzy substring matching on the Rx page: the
    backend matches each free-text allergy term against salt names
    (normalized exact match, or length-guarded containment reported as
    ``match="partial"``).

    Authorization:
    - patients may only check their own record (``patient_id`` == caller)
    - doctors must be verified/onboarded and have a relationship with the
      patient (authored record or approved/revoked clinic link — same rule
      as doctors.py prescription endpoints)
    """
    if user.role == "patient":
        if user.id != request.patient_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "FORBIDDEN", "message": "Patients may only check their own allergies"}},
            )
    elif user.role == "doctor":
        result = await db.execute(
            select(Doctor).where(
                Doctor.user_id == user.id, Doctor.deleted_at.is_(None)
            )
        )
        doctor = result.scalar_one_or_none()
        if (
            doctor is None
            or not doctor.verified
            or doctor.onboarding_step != "completed"
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "ONBOARDING_INCOMPLETE", "message": "Doctor verification not complete"}},
            )
        if not await access_service.doctor_patient_relationship_exists(
            db, doctor.user_id, doctor.id, request.patient_id, allow_revoked=True
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "FORBIDDEN", "message": "No relationship with this patient"}},
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Patient or doctor access required"}},
        )

    patient = await db.get(User, request.patient_id)
    if patient is None or patient.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Patient not found"}},
        )

    return await allergy_service.check_allergies(
        medicine_db, patient.allergies, request.salt_ids
    )


@router.get("/salts/{salt_id}", response_model=list[InteractionResponse])
async def get_salt_interactions(
    salt_id: UUID,
    severity: str | None = Query(
        None,
        description="Filter by severity: minor, moderate, major, contraindicated"
    ),
    db: AsyncSession = Depends(get_medicine_db),
    user: User = Depends(get_current_user),
):
    """
    Get all known interactions for a specific salt.

    Useful for:
    - Displaying warnings on medicine detail pages
    - Pre-checking before adding to prescription
    - Building interaction databases
    """
    if severity and severity not in {"minor", "moderate", "major", "contraindicated"}:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "VALIDATION_ERROR", "message": "Severity must be one of: minor, moderate, major, contraindicated"}},
        )

    interactions = await InteractionService.get_salt_interactions(
        db, salt_id, severity
    )
    return interactions


@router.post("", response_model=InteractionResponse, status_code=status.HTTP_201_CREATED)
async def create_interaction(
    request: CreateInteractionRequest,
    db: AsyncSession = Depends(get_medicine_db),
    admin: User = Depends(require_admin),
):
    """
    Create a new drug interaction record.

    Admin-only endpoint for adding interaction data to the database.

    Severity levels:
    - minor: Minimal clinical significance
    - moderate: May require monitoring
    - major: Serious interaction, intervention needed
    - contraindicated: Combination should not be used

    Evidence levels:
    - theoretical: Based on pharmacology, not observed
    - case-report: Documented in case reports
    - study-based: Proven in clinical studies
    """
    try:
        interaction = await InteractionService.create_interaction(
            db=db,
            salt_id_1=request.salt_id_1,
            salt_id_2=request.salt_id_2,
            severity=request.severity,
            effect=request.effect,
            mechanism=request.mechanism,
            management=request.management,
            evidence_level=request.evidence_level,
        )

        await db.commit()

        # Fetch with relationships for response
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload
        from app.models.medicine.clinical_safety import DrugInteraction

        result = await db.execute(
            select(DrugInteraction)
            .options(
                joinedload(DrugInteraction.salt_1),
                joinedload(DrugInteraction.salt_2),
            )
            .where(DrugInteraction.interaction_id == interaction.interaction_id)
        )
        interaction = result.unique().scalar_one()

        return {
            "interaction_id": str(interaction.interaction_id),
            "salt_1": {
                "id": str(interaction.salt_id_1),
                "name": interaction.salt_1.salt_name,
            },
            "salt_2": {
                "id": str(interaction.salt_id_2),
                "name": interaction.salt_2.salt_name,
            },
            "severity": interaction.severity,
            "effect": interaction.effect,
            "mechanism": interaction.mechanism,
            "management": interaction.management,
            "evidence_level": interaction.evidence_level,
        }

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "VALIDATION_ERROR", "message": "Invalid interaction request"}},
        )


@router.delete("/{interaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_interaction(
    interaction_id: UUID,
    db: AsyncSession = Depends(get_medicine_db),
    admin: User = Depends(require_admin),
):
    """
    Delete a drug interaction record.

    Admin-only endpoint.
    """
    deleted = await InteractionService.delete_interaction(db, interaction_id)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "Interaction not found"}},
        )

    await db.commit()
    return None
