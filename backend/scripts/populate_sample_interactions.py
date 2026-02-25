#!/usr/bin/env python3
"""
Populate sample drug interaction data for MD-18.

This script creates intelligent sample interactions based on common
drug interaction patterns found in clinical practice.

Usage:
    python scripts/populate_sample_interactions.py [--dry-run]
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import medicine_async_session
from app.models.medicine.salts import Salt
from app.services.interaction_service import InteractionService


# Common drug interaction patterns
INTERACTION_PATTERNS = [
    # NSAIDs + Anticoagulants = Major (bleeding risk)
    {
        "salt_1_names": ["Aspirin", "Ibuprofen", "Diclofenac", "Naproxen"],
        "salt_2_names": ["Warfarin", "Heparin"],
        "severity": "major",
        "effect": "Increased risk of bleeding due to antiplatelet effects of NSAIDs combined with anticoagulation.",
        "mechanism": "NSAIDs inhibit platelet aggregation and may displace warfarin from protein binding sites.",
        "management": "Monitor INR closely. Consider alternative analgesic (paracetamol). Use lowest effective NSAID dose for shortest duration.",
        "evidence_level": "study-based",
    },

    # Paracetamol + Warfarin = Moderate
    {
        "salt_1_names": ["Paracetamol"],
        "salt_2_names": ["Warfarin"],
        "severity": "moderate",
        "effect": "Chronic high-dose paracetamol may potentiate warfarin effect, increasing bleeding risk.",
        "mechanism": "Possible inhibition of vitamin K-dependent clotting factor synthesis.",
        "management": "Monitor INR when starting/stopping paracetamol or changing dose. Generally safe at doses <2g/day.",
        "evidence_level": "study-based",
    },

    # Antibiotics + Oral Contraceptives = Moderate
    {
        "salt_1_names": ["Rifampicin", "Griseofulvin"],
        "salt_2_names": ["Ethinylestradiol", "Levonorgestrel"],
        "severity": "moderate",
        "effect": "Reduced contraceptive efficacy, risk of unintended pregnancy.",
        "mechanism": "Enzyme induction increases metabolism of contraceptive hormones.",
        "management": "Use additional non-hormonal contraception during treatment and for 4 weeks after. Consider alternative antibiotic if possible.",
        "evidence_level": "study-based",
    },

    # ACE Inhibitors + Potassium-sparing diuretics = Major
    {
        "salt_1_names": ["Enalapril", "Lisinopril", "Ramipril"],
        "salt_2_names": ["Spironolactone", "Amiloride"],
        "severity": "major",
        "effect": "Severe hyperkalemia, potentially life-threatening cardiac arrhythmias.",
        "mechanism": "Both classes reduce potassium excretion, leading to additive hyperkalemic effect.",
        "management": "Monitor serum potassium frequently. Avoid combination if possible. If necessary, use lowest doses and monitor closely.",
        "evidence_level": "study-based",
    },

    # Metronidazole + Alcohol = Moderate
    {
        "salt_1_names": ["Metronidazole"],
        "salt_2_names": ["Ethanol"],  # If alcohol as a drug exists
        "severity": "moderate",
        "effect": "Disulfiram-like reaction: flushing, headache, nausea, vomiting, tachycardia.",
        "mechanism": "Inhibition of aldehyde dehydrogenase leads to acetaldehyde accumulation.",
        "management": "Avoid alcohol during treatment and for 48 hours after last dose.",
        "evidence_level": "case-report",
    },

    # Statins + Macrolides = Major
    {
        "salt_1_names": ["Atorvastatin", "Simvastatin"],
        "salt_2_names": ["Erythromycin", "Clarithromycin"],
        "severity": "major",
        "effect": "Increased risk of rhabdomyolysis and myopathy.",
        "mechanism": "Macrolides inhibit CYP3A4, increasing statin levels.",
        "management": "Suspend statin therapy during short-term macrolide use. Consider azithromycin as alternative.",
        "evidence_level": "study-based",
    },

    # SSRIs + NSAIDs = Moderate
    {
        "salt_1_names": ["Fluoxetine", "Sertraline", "Escitalopram"],
        "salt_2_names": ["Aspirin", "Ibuprofen", "Diclofenac"],
        "severity": "moderate",
        "effect": "Increased risk of gastrointestinal bleeding.",
        "mechanism": "SSRIs impair platelet aggregation; NSAIDs cause gastric mucosal damage.",
        "management": "Use gastroprotection (PPI) if combination necessary. Monitor for bleeding signs.",
        "evidence_level": "study-based",
    },

    # Digoxin + Loop Diuretics = Moderate
    {
        "salt_1_names": ["Digoxin"],
        "salt_2_names": ["Furosemide"],
        "severity": "moderate",
        "effect": "Increased risk of digoxin toxicity due to hypokalemia.",
        "mechanism": "Diuretic-induced hypokalemia increases myocardial sensitivity to digoxin.",
        "management": "Monitor serum potassium and digoxin levels. Correct electrolyte imbalances promptly.",
        "evidence_level": "study-based",
    },

    # MAO Inhibitors + Tyramine-rich foods (simulated with another salt) = Contraindicated
    {
        "salt_1_names": ["Phenelzine", "Tranylcypromine"],
        "salt_2_names": ["Pseudoephedrine", "Ephedrine"],
        "severity": "contraindicated",
        "effect": "Hypertensive crisis, potentially fatal.",
        "mechanism": "MAO inhibition prevents breakdown of sympathomimetic amines, leading to severe hypertension.",
        "management": "Contraindicated. Do not use together. Allow 2-week washout period.",
        "evidence_level": "study-based",
    },
]


async def get_salt_by_name(db: AsyncSession, name: str) -> Salt | None:
    """Get salt by name (case-insensitive)."""
    result = await db.execute(
        select(Salt).where(func.lower(Salt.salt_name) == name.lower())
    )
    return result.scalar_one_or_none()


async def populate_interactions(db: AsyncSession, dry_run: bool = False):
    """Populate sample drug interactions."""
    print("=" * 70)
    print("POPULATING SAMPLE DRUG INTERACTION DATA")
    print("=" * 70)

    if dry_run:
        print("🔍 DRY RUN MODE - No data will be committed\n")

    stats = {
        "patterns_processed": 0,
        "interactions_created": 0,
        "salts_not_found": 0,
        "duplicates_skipped": 0,
    }

    for pattern in INTERACTION_PATTERNS:
        stats["patterns_processed"] += 1

        for salt1_name in pattern["salt_1_names"]:
            for salt2_name in pattern["salt_2_names"]:
                # Get salts from database
                salt1 = await get_salt_by_name(db, salt1_name)
                salt2 = await get_salt_by_name(db, salt2_name)

                if not salt1:
                    print(f"⚠️  Salt not found: {salt1_name}")
                    stats["salts_not_found"] += 1
                    continue

                if not salt2:
                    print(f"⚠️  Salt not found: {salt2_name}")
                    stats["salts_not_found"] += 1
                    continue

                # Create interaction
                try:
                    interaction = await InteractionService.create_interaction(
                        db=db,
                        salt_id_1=salt1.salt_id,
                        salt_id_2=salt2.salt_id,
                        severity=pattern["severity"],
                        effect=pattern["effect"],
                        mechanism=pattern.get("mechanism"),
                        management=pattern.get("management"),
                        evidence_level=pattern.get("evidence_level"),
                    )

                    stats["interactions_created"] += 1
                    print(f"✓ Created: {salt1_name} + {salt2_name} [{pattern['severity']}]")

                except Exception as e:
                    if "uq_drug_interaction" in str(e):
                        stats["duplicates_skipped"] += 1
                        print(f"⊘ Skipped duplicate: {salt1_name} + {salt2_name}")
                    else:
                        print(f"✗ Error: {salt1_name} + {salt2_name}: {e}")

    if not dry_run:
        await db.commit()
        print("\n✅ Data committed to database")
    else:
        await db.rollback()
        print("\n🔄 Dry run complete - data rolled back")

    # Print statistics
    print("\n" + "=" * 70)
    print("STATISTICS")
    print("=" * 70)
    print(f"Patterns processed:      {stats['patterns_processed']}")
    print(f"Interactions created:    {stats['interactions_created']}")
    print(f"Duplicates skipped:      {stats['duplicates_skipped']}")
    print(f"Salts not found:         {stats['salts_not_found']}")
    print("=" * 70)


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Populate sample drug interaction data"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without committing to database",
    )

    args = parser.parse_args()

    async with medicine_async_session() as db:
        await populate_interactions(db, dry_run=args.dry_run)


if __name__ == "__main__":
    asyncio.run(main())
