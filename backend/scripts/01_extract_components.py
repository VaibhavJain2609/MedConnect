#!/usr/bin/env python3
"""
Extract unique components from CSV and build master components table
Usage: python scripts/01_extract_components.py
"""
import json
import re
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings


def parse_composition(comp_string: str) -> Optional[Tuple[str, float, str]]:
    """
    Parse composition string to extract component name, strength, unit

    Examples:
        "Amoxycillin  (500mg)" -> ("Amoxycillin", 500.0, "mg")
        "Paracetamol (650mg)" -> ("Paracetamol", 650.0, "mg")
        "Vitamin D3 (600000IU)" -> ("Vitamin D3", 600000.0, "IU")
        "Levosalbutamol (1mg/5ml)" -> ("Levosalbutamol", 1.0, "mg")

    Returns:
        Tuple of (component_name, strength, unit) or None if parsing fails
    """
    if not comp_string or pd.isna(comp_string) or comp_string.strip() == "":
        return None

    comp_string = comp_string.strip()

    # Pattern: ComponentName (StrengthUnit) or ComponentName (Strength/5ml)
    # Handle cases like "Amoxycillin  (500mg)" or "Levosalbutamol (1mg/5ml)"
    pattern = r'^(.+?)\s*\((\d+(?:\.\d+)?)\s*(mg|mcg|g|ml|%|IU)(?:/\d+ml)?\)'
    match = re.match(pattern, comp_string, re.IGNORECASE)

    if match:
        name = match.group(1).strip()
        strength = float(match.group(2))
        unit = match.group(3)
        return (name, strength, unit)

    # Try alternative pattern without parentheses
    pattern2 = r'^(.+?)\s+(\d+(?:\.\d+)?)\s*(mg|mcg|g|ml|%|IU)$'
    match2 = re.match(pattern2, comp_string, re.IGNORECASE)

    if match2:
        name = match2.group(1).strip()
        strength = float(match2.group(2))
        unit = match2.group(3)
        return (name, strength, unit)

    print(f"⚠️  Could not parse composition: '{comp_string}'")
    return None


def normalize_component_name(name: str) -> str:
    """Normalize component name for consistency"""
    # Remove extra spaces
    name = re.sub(r'\s+', ' ', name.strip())
    # Capitalize first letter of each word
    name = name.title()
    return name


def extract_components_from_csv(csv_path: str) -> Dict[str, Dict]:
    """
    Extract unique components from CSV file

    Returns:
        Dictionary mapping component_name -> {count, common_names, category}
    """
    print(f"📖 Reading CSV: {csv_path}")
    df = pd.read_csv(csv_path)
    print(f"   Total rows: {len(df):,}")

    components_data = {}
    parse_failures = []

    for idx, row in df.iterrows():
        # Parse short_composition1
        comp1 = parse_composition(row.get('short_composition1'))
        if comp1:
            name = normalize_component_name(comp1[0])
            if name not in components_data:
                components_data[name] = {
                    'count': 0,
                    'common_names': set(),
                    'therapeutic_classes': set()
                }
            components_data[name]['count'] += 1
            if pd.notna(row.get('Therapeutic Class')):
                components_data[name]['therapeutic_classes'].add(row['Therapeutic Class'].strip())
        elif pd.notna(row.get('short_composition1')) and row.get('short_composition1').strip():
            parse_failures.append(row.get('short_composition1'))

        # Parse short_composition2
        comp2 = parse_composition(row.get('short_composition2'))
        if comp2:
            name = normalize_component_name(comp2[0])
            if name not in components_data:
                components_data[name] = {
                    'count': 0,
                    'common_names': set(),
                    'therapeutic_classes': set()
                }
            components_data[name]['count'] += 1
            if pd.notna(row.get('Therapeutic Class')):
                components_data[name]['therapeutic_classes'].add(row['Therapeutic Class'].strip())

    print(f"\n✅ Extracted {len(components_data):,} unique components")
    print(f"⚠️  Failed to parse {len(set(parse_failures))} unique composition strings")

    # Show top 10 components by usage
    print("\n📊 Top 10 most common components:")
    sorted_components = sorted(components_data.items(), key=lambda x: x[1]['count'], reverse=True)
    for name, data in sorted_components[:10]:
        print(f"   {name}: {data['count']:,} medicines")

    return components_data


def bulk_insert_components(components_data: Dict[str, Dict]) -> Dict[str, str]:
    """
    Bulk insert components into database

    Returns:
        Dictionary mapping component_name -> component_id (UUID string)
    """
    print(f"\n🔌 Connecting to medicine database...")
    engine = create_engine(settings.MEDICINE_DB_URL_SYNC, echo=False)

    component_id_map = {}

    with Session(engine) as session:
        # Check if components table exists
        result = session.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'components'
            );
        """))
        if not result.scalar():
            print("❌ Components table does not exist. Run migration first:")
            print("   alembic -c alembic_medicine.ini upgrade head")
            sys.exit(1)

        # Clear existing components (optional - comment out if you want to preserve)
        # print("🗑️  Clearing existing components...")
        # session.execute(text("TRUNCATE TABLE components CASCADE"))
        # session.commit()

        print(f"💾 Inserting {len(components_data):,} components...")

        batch_size = 500
        inserted = 0

        for name, data in components_data.items():
            # Determine category from therapeutic classes
            category = None
            if data['therapeutic_classes']:
                # Use most common therapeutic class as category
                category = list(data['therapeutic_classes'])[0]

            # Insert component
            result = session.execute(
                text("""
                    INSERT INTO components (name, common_names, category)
                    VALUES (:name, :common_names, :category)
                    ON CONFLICT (name) DO UPDATE SET
                        category = COALESCE(components.category, EXCLUDED.category),
                        updated_at = now()
                    RETURNING id
                """),
                {
                    "name": name,
                    "common_names": None,  # Can be enriched later
                    "category": category
                }
            )

            component_id = result.scalar()
            component_id_map[name] = str(component_id)

            inserted += 1
            if inserted % batch_size == 0:
                session.commit()
                print(f"   Inserted {inserted:,} / {len(components_data):,} components...")

        session.commit()
        print(f"✅ Inserted {inserted:,} components successfully")

    return component_id_map


def save_component_map(component_id_map: Dict[str, str], output_path: str):
    """Save component ID map to JSON for use in medicine import"""
    print(f"\n💾 Saving component ID map to: {output_path}")
    with open(output_path, 'w') as f:
        json.dump(component_id_map, f, indent=2)
    print(f"✅ Saved {len(component_id_map):,} component mappings")


def main():
    """Main execution"""
    # Paths
    project_root = Path(__file__).parent.parent.parent
    csv_path = project_root / "Dataset" / "Extensive_A_Z_medicines_dataset_of_India.csv"
    output_path = project_root / "backend" / "scripts" / "component_id_map.json"

    if not csv_path.exists():
        print(f"❌ CSV file not found: {csv_path}")
        sys.exit(1)

    print("=" * 80)
    print("STEP 1: EXTRACT COMPONENTS FROM CSV")
    print("=" * 80)

    # Extract components from CSV
    components_data = extract_components_from_csv(str(csv_path))

    print("\n" + "=" * 80)
    print("STEP 2: INSERT COMPONENTS INTO DATABASE")
    print("=" * 80)

    # Insert into database and get ID map
    component_id_map = bulk_insert_components(components_data)

    # Save ID map for medicine import
    save_component_map(component_id_map, str(output_path))

    print("\n" + "=" * 80)
    print("✅ COMPONENT EXTRACTION COMPLETE")
    print("=" * 80)
    print(f"📊 Total unique components: {len(component_id_map):,}")
    print(f"📁 Component ID map saved to: {output_path}")
    print(f"\n🎯 Next step: Run medicine import script")
    print(f"   python scripts/02_import_medicines.py")
    print("=" * 80)


if __name__ == "__main__":
    main()
