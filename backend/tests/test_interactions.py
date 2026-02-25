"""Tests for drug interaction detection (MD-18)."""

import pytest
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.medicine.salts import Salt
from app.models.medicine.clinical_safety import DrugInteraction
from app.services.interaction_service import InteractionService


@pytest.mark.asyncio
async def test_check_interactions_single_pair(medicine_db: AsyncSession):
    """Test checking interactions between two salts."""
    # Create two salts
    salt1 = Salt(salt_name="Aspirin", prescription_required=False)
    salt2 = Salt(salt_name="Warfarin", prescription_required=True)
    medicine_db.add_all([salt1, salt2])
    await medicine_db.flush()

    # Create interaction (ensure salt_id_1 < salt_id_2)
    if str(salt1.salt_id) > str(salt2.salt_id):
        salt1, salt2 = salt2, salt1

    interaction = DrugInteraction(
        salt_id_1=salt1.salt_id,
        salt_id_2=salt2.salt_id,
        severity="major",
        effect="Increased bleeding risk",
        mechanism="Antiplatelet + anticoagulation",
        management="Monitor INR closely",
        evidence_level="study-based",
    )
    medicine_db.add(interaction)
    await medicine_db.flush()

    # Check interactions
    results = await InteractionService.check_interactions(
        medicine_db,
        [salt1.salt_id, salt2.salt_id],
    )

    assert len(results) == 1
    assert results[0]["severity"] == "major"
    assert "bleeding" in results[0]["effect"].lower()


@pytest.mark.asyncio
async def test_check_interactions_multiple_pairs(medicine_db: AsyncSession):
    """Test checking interactions between three salts with two interactions."""
    # Create salts
    aspirin = Salt(salt_name="Aspirin", prescription_required=False)
    warfarin = Salt(salt_name="Warfarin", prescription_required=True)
    ibuprofen = Salt(salt_name="Ibuprofen", prescription_required=False)
    medicine_db.add_all([aspirin, warfarin, ibuprofen])
    await medicine_db.flush()

    # Create two interactions
    # Sort salt IDs to ensure constraint compliance
    salts_sorted = sorted([aspirin, warfarin, ibuprofen], key=lambda s: str(s.salt_id))

    interaction1 = DrugInteraction(
        salt_id_1=salts_sorted[0].salt_id,
        salt_id_2=salts_sorted[1].salt_id,
        severity="major",
        effect="Test interaction 1",
    )
    interaction2 = DrugInteraction(
        salt_id_1=salts_sorted[0].salt_id,
        salt_id_2=salts_sorted[2].salt_id,
        severity="moderate",
        effect="Test interaction 2",
    )
    medicine_db.add_all([interaction1, interaction2])
    await medicine_db.flush()

    # Check all three together
    results = await InteractionService.check_interactions(
        medicine_db,
        [aspirin.salt_id, warfarin.salt_id, ibuprofen.salt_id],
    )

    assert len(results) == 2
    # Should be ordered by severity (major first)
    assert results[0]["severity"] == "major"


@pytest.mark.asyncio
async def test_check_interactions_severity_ordering(medicine_db: AsyncSession):
    """Test that interactions are returned in severity order."""
    # Create salts
    salt1 = Salt(salt_name="Drug A", prescription_required=False)
    salt2 = Salt(salt_name="Drug B", prescription_required=False)
    salt3 = Salt(salt_name="Drug C", prescription_required=False)
    medicine_db.add_all([salt1, salt2, salt3])
    await medicine_db.flush()

    # Sort for constraint
    salts = sorted([salt1, salt2, salt3], key=lambda s: str(s.salt_id))

    # Create interactions with different severities
    interactions = [
        DrugInteraction(
            salt_id_1=salts[0].salt_id,
            salt_id_2=salts[1].salt_id,
            severity="minor",
            effect="Minor interaction",
        ),
        DrugInteraction(
            salt_id_1=salts[1].salt_id,
            salt_id_2=salts[2].salt_id,
            severity="contraindicated",
            effect="Contraindicated interaction",
        ),
        DrugInteraction(
            salt_id_1=salts[0].salt_id,
            salt_id_2=salts[2].salt_id,
            severity="moderate",
            effect="Moderate interaction",
        ),
    ]
    medicine_db.add_all(interactions)
    await medicine_db.flush()

    # Check all three
    results = await InteractionService.check_interactions(
        medicine_db,
        [s.salt_id for s in salts],
    )

    assert len(results) == 3
    # Verify severity ordering: contraindicated, moderate, minor
    assert results[0]["severity"] == "contraindicated"
    assert results[1]["severity"] == "moderate"
    assert results[2]["severity"] == "minor"


@pytest.mark.asyncio
async def test_get_salt_interactions(medicine_db: AsyncSession):
    """Test getting all interactions for a specific salt."""
    # Create salts
    target_salt = Salt(salt_name="Target Drug", prescription_required=False)
    other1 = Salt(salt_name="Other 1", prescription_required=False)
    other2 = Salt(salt_name="Other 2", prescription_required=False)
    unrelated = Salt(salt_name="Unrelated", prescription_required=False)
    medicine_db.add_all([target_salt, other1, other2, unrelated])
    await medicine_db.flush()

    # Create interactions involving target_salt
    salts_sorted = sorted([target_salt, other1, other2, unrelated], key=lambda s: str(s.salt_id))

    # Find target_salt position in sorted list
    target_idx = salts_sorted.index(target_salt)
    other1_idx = salts_sorted.index(other1)
    other2_idx = salts_sorted.index(other2)

    interactions = []
    if target_idx < other1_idx:
        interactions.append(DrugInteraction(
            salt_id_1=target_salt.salt_id,
            salt_id_2=other1.salt_id,
            severity="major",
            effect="Interaction with Other 1",
        ))
    else:
        interactions.append(DrugInteraction(
            salt_id_1=other1.salt_id,
            salt_id_2=target_salt.salt_id,
            severity="major",
            effect="Interaction with Other 1",
        ))

    if target_idx < other2_idx:
        interactions.append(DrugInteraction(
            salt_id_1=target_salt.salt_id,
            salt_id_2=other2.salt_id,
            severity="moderate",
            effect="Interaction with Other 2",
        ))
    else:
        interactions.append(DrugInteraction(
            salt_id_1=other2.salt_id,
            salt_id_2=target_salt.salt_id,
            severity="moderate",
            effect="Interaction with Other 2",
        ))

    medicine_db.add_all(interactions)
    await medicine_db.flush()

    # Get interactions for target_salt
    results = await InteractionService.get_salt_interactions(
        medicine_db,
        target_salt.salt_id,
    )

    assert len(results) == 2
    # All interactions should involve target_salt
    for result in results:
        salt_ids = {result["salt_1"]["id"], result["salt_2"]["id"]}
        assert str(target_salt.salt_id) in salt_ids


@pytest.mark.asyncio
async def test_create_interaction_success(medicine_db: AsyncSession):
    """Test creating a new interaction."""
    # Create salts
    salt1 = Salt(salt_name="Salt A", prescription_required=False)
    salt2 = Salt(salt_name="Salt B", prescription_required=False)
    medicine_db.add_all([salt1, salt2])
    await medicine_db.flush()

    # Create interaction
    interaction = await InteractionService.create_interaction(
        db=medicine_db,
        salt_id_1=salt1.salt_id,
        salt_id_2=salt2.salt_id,
        severity="moderate",
        effect="Test effect",
        mechanism="Test mechanism",
        management="Test management",
        evidence_level="case-report",
    )

    assert interaction.severity == "moderate"
    assert interaction.effect == "Test effect"
    # Verify constraint (salt_id_1 < salt_id_2)
    assert str(interaction.salt_id_1) < str(interaction.salt_id_2)


@pytest.mark.asyncio
async def test_create_interaction_invalid_severity(medicine_db: AsyncSession):
    """Test creating interaction with invalid severity raises error."""
    salt1 = Salt(salt_name="Salt A", prescription_required=False)
    salt2 = Salt(salt_name="Salt B", prescription_required=False)
    medicine_db.add_all([salt1, salt2])
    await medicine_db.flush()

    with pytest.raises(ValueError, match="Severity must be one of"):
        await InteractionService.create_interaction(
            db=medicine_db,
            salt_id_1=salt1.salt_id,
            salt_id_2=salt2.salt_id,
            severity="invalid",
            effect="Test",
        )


@pytest.mark.asyncio
async def test_create_interaction_same_salt_rejected(medicine_db: AsyncSession):
    """Test creating interaction with same salt is rejected."""
    salt = Salt(salt_name="Salt A", prescription_required=False)
    medicine_db.add(salt)
    await medicine_db.flush()

    with pytest.raises(ValueError, match="Cannot create interaction with the same salt"):
        await InteractionService.create_interaction(
            db=medicine_db,
            salt_id_1=salt.salt_id,
            salt_id_2=salt.salt_id,
            severity="moderate",
            effect="Test",
        )


@pytest.mark.asyncio
async def test_delete_interaction(medicine_db: AsyncSession):
    """Test deleting an interaction."""
    salt1 = Salt(salt_name="Salt A", prescription_required=False)
    salt2 = Salt(salt_name="Salt B", prescription_required=False)
    medicine_db.add_all([salt1, salt2])
    await medicine_db.flush()

    # Create interaction
    interaction = await InteractionService.create_interaction(
        db=medicine_db,
        salt_id_1=salt1.salt_id,
        salt_id_2=salt2.salt_id,
        severity="minor",
        effect="Test",
    )

    # Delete it
    deleted = await InteractionService.delete_interaction(
        medicine_db,
        interaction.interaction_id,
    )

    assert deleted is True

    # Verify it's gone
    results = await InteractionService.check_interactions(
        medicine_db,
        [salt1.salt_id, salt2.salt_id],
    )
    assert len(results) == 0
