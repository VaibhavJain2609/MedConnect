"""Drug interaction detection service for MD-18."""

from uuid import UUID
from sqlalchemy import select, or_, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.medicine.clinical_safety import DrugInteraction
from app.models.medicine.salts import Salt


class InteractionService:
    """Service for drug interaction detection and management."""

    @staticmethod
    async def check_interactions(
        db: AsyncSession,
        salt_ids: list[UUID],
    ) -> list[dict]:
        """
        Check for interactions between multiple salts.

        Args:
            db: Database session
            salt_ids: List of salt IDs to check for interactions

        Returns:
            List of interaction dictionaries with severity, effect, management
        """
        if len(salt_ids) < 2:
            return []

        # Sort salt IDs to match constraint (salt_id_1 < salt_id_2)
        salt_ids_sorted = sorted([str(sid) for sid in salt_ids])

        # Build query for all pairwise interactions
        interaction_conditions = []
        for i, salt_id_1 in enumerate(salt_ids_sorted):
            for salt_id_2 in salt_ids_sorted[i+1:]:
                interaction_conditions.append(
                    and_(
                        DrugInteraction.salt_id_1 == UUID(salt_id_1),
                        DrugInteraction.salt_id_2 == UUID(salt_id_2),
                    )
                )

        if not interaction_conditions:
            return []

        # Query interactions with salt details
        query = (
            select(DrugInteraction)
            .options(
                joinedload(DrugInteraction.salt_1),
                joinedload(DrugInteraction.salt_2),
            )
            .where(or_(*interaction_conditions))
            .order_by(
                # Order by severity (most severe first)
                func.case(
                    (DrugInteraction.severity == "contraindicated", 1),
                    (DrugInteraction.severity == "major", 2),
                    (DrugInteraction.severity == "moderate", 3),
                    (DrugInteraction.severity == "minor", 4),
                    else_=5,
                )
            )
        )

        result = await db.execute(query)
        interactions = result.unique().scalars().all()

        # Format response
        return [
            {
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
            for interaction in interactions
        ]

    @staticmethod
    async def get_salt_interactions(
        db: AsyncSession,
        salt_id: UUID,
        severity: str | None = None,
    ) -> list[dict]:
        """
        Get all known interactions for a specific salt.

        Args:
            db: Database session
            salt_id: Salt ID to check
            severity: Optional filter by severity level

        Returns:
            List of interactions involving this salt
        """
        query = (
            select(DrugInteraction)
            .options(
                joinedload(DrugInteraction.salt_1),
                joinedload(DrugInteraction.salt_2),
            )
            .where(
                or_(
                    DrugInteraction.salt_id_1 == salt_id,
                    DrugInteraction.salt_id_2 == salt_id,
                )
            )
        )

        if severity:
            query = query.where(DrugInteraction.severity == severity)

        query = query.order_by(
            func.case(
                (DrugInteraction.severity == "contraindicated", 1),
                (DrugInteraction.severity == "major", 2),
                (DrugInteraction.severity == "moderate", 3),
                (DrugInteraction.severity == "minor", 4),
                else_=5,
            )
        )

        result = await db.execute(query)
        interactions = result.unique().scalars().all()

        return [
            {
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
            for interaction in interactions
        ]

    @staticmethod
    async def create_interaction(
        db: AsyncSession,
        salt_id_1: UUID,
        salt_id_2: UUID,
        severity: str,
        effect: str,
        mechanism: str | None = None,
        management: str | None = None,
        evidence_level: str | None = None,
    ) -> DrugInteraction:
        """
        Create a new drug interaction record.

        Args:
            db: Database session
            salt_id_1: First salt ID (will be sorted to ensure salt_id_1 < salt_id_2)
            salt_id_2: Second salt ID
            severity: Severity level (minor, moderate, major, contraindicated)
            effect: Description of the interaction effect
            mechanism: Optional mechanism description
            management: Optional management recommendations
            evidence_level: Optional evidence level (theoretical, case-report, study-based)

        Returns:
            Created DrugInteraction instance

        Raises:
            ValueError: If salt IDs are the same or severity is invalid
        """
        if salt_id_1 == salt_id_2:
            raise ValueError("Cannot create interaction with the same salt")

        valid_severities = {"minor", "moderate", "major", "contraindicated"}
        if severity not in valid_severities:
            raise ValueError(f"Severity must be one of {valid_severities}")

        # Ensure salt_id_1 < salt_id_2 (database constraint)
        if str(salt_id_1) > str(salt_id_2):
            salt_id_1, salt_id_2 = salt_id_2, salt_id_1

        # Verify salts exist
        result = await db.execute(
            select(Salt.salt_id).where(
                Salt.salt_id.in_([salt_id_1, salt_id_2])
            )
        )
        found_salts = {row[0] for row in result.all()}

        if len(found_salts) != 2:
            missing = {salt_id_1, salt_id_2} - found_salts
            raise ValueError(f"Salt(s) not found: {missing}")

        interaction = DrugInteraction(
            salt_id_1=salt_id_1,
            salt_id_2=salt_id_2,
            severity=severity,
            effect=effect,
            mechanism=mechanism,
            management=management,
            evidence_level=evidence_level,
        )

        db.add(interaction)
        await db.flush()

        return interaction

    @staticmethod
    async def delete_interaction(
        db: AsyncSession,
        interaction_id: UUID,
    ) -> bool:
        """
        Delete a drug interaction record.

        Args:
            db: Database session
            interaction_id: Interaction ID to delete

        Returns:
            True if deleted, False if not found
        """
        result = await db.execute(
            select(DrugInteraction).where(
                DrugInteraction.interaction_id == interaction_id
            )
        )
        interaction = result.scalar_one_or_none()

        if not interaction:
            return False

        await db.delete(interaction)
        await db.flush()

        return True
