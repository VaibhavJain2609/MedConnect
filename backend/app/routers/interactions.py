"""Drug interaction API endpoints for MD-18."""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_medicine_db
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
    salt_ids: list[str]  # List of salt UUIDs as strings


class CreateInteractionRequest(BaseModel):
    """Request model for creating a new interaction."""
    salt_id_1: str
    salt_id_2: str
    severity: str
    effect: str
    mechanism: str | None = None
    management: str | None = None
    evidence_level: str | None = None


@router.post("/check", response_model=list[InteractionResponse])
async def check_interactions(
    request: CheckInteractionsRequest,
    db: AsyncSession = Depends(get_medicine_db),
):
    """
    Check for drug interactions between multiple salts.

    Use this endpoint when creating a prescription with multiple medicines
    to detect potential drug-drug interactions.

    Returns interactions ordered by severity (most severe first).
    """
    try:
        salt_ids = [UUID(sid) for sid in request.salt_ids]
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid salt ID format: {str(e)}"
        )

    interactions = await InteractionService.check_interactions(db, salt_ids)
    return interactions


@router.get("/salts/{salt_id}", response_model=list[InteractionResponse])
async def get_salt_interactions(
    salt_id: UUID,
    severity: str | None = Query(
        None,
        description="Filter by severity: minor, moderate, major, contraindicated"
    ),
    db: AsyncSession = Depends(get_medicine_db),
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
            detail="Severity must be one of: minor, moderate, major, contraindicated"
        )

    interactions = await InteractionService.get_salt_interactions(
        db, salt_id, severity
    )
    return interactions


@router.post("", response_model=InteractionResponse, status_code=status.HTTP_201_CREATED)
async def create_interaction(
    request: CreateInteractionRequest,
    db: AsyncSession = Depends(get_medicine_db),
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
        salt_id_1 = UUID(request.salt_id_1)
        salt_id_2 = UUID(request.salt_id_2)

        interaction = await InteractionService.create_interaction(
            db=db,
            salt_id_1=salt_id_1,
            salt_id_2=salt_id_2,
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

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{interaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_interaction(
    interaction_id: UUID,
    db: AsyncSession = Depends(get_medicine_db),
):
    """
    Delete a drug interaction record.

    Admin-only endpoint.
    """
    deleted = await InteractionService.delete_interaction(db, interaction_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Interaction not found")

    await db.commit()
    return None
