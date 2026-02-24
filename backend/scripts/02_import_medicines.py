#!/usr/bin/env python3
"""
Import medicines from CSV with component relationships
Usage: python scripts/02_import_medicines.py
"""
import json
import re
import sys
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings


def parse_composition(comp_string: str) -> Optional[Tuple[str, float, str]]:
    """
    Parse composition string to extract component name, strength, unit
    Same logic as in 01_extract_components.py
    """
    if not comp_string or pd.isna(comp_string) or comp_string.strip() == "":
        return None

    comp_string = comp_string.strip()
    pattern = r'^(.+?)\s*\((\d+(?:\.\d+)?)\s*(mg|mcg|g|ml|%|IU)(?:/\d+ml)?\)'
    match = re.match(pattern, comp_string, re.IGNORECASE)

    if match:
        name = match.group(1).strip()
        strength = float(match.group(2))
        unit = match.group(3)
        return (name, strength, unit)

    pattern2 = r'^(.+?)\s+(\d+(?:\.\d+)?)\s*(mg|mcg|g|ml|%|IU)$'
    match2 = re.match(pattern2, comp_string, re.IGNORECASE)

    if match2:
        name = match2.group(1).strip()
        strength = float(match2.group(2))
        unit = match2.group(3)
        return (name, strength, unit)

    return None


def normalize_component_name(name: str) -> str:
    """Normalize component name for consistency"""
    return re.sub(r'\s+', ' ', name.strip()).title()


def clean_text(value) -> Optional[str]:
    """Clean and normalize text fields"""
    if pd.isna(value) or value == "":
        return None
    return str(value).strip()


def parse_price(price_value) -> Optional[Decimal]:
    """Parse price to Decimal"""
    if pd.isna(price_value):
        return None
    try:
        return Decimal(str(price_value))
    except:
        return None


def parse_bool(value) -> bool:
    """Parse boolean from string"""
    if pd.isna(value):
        return False
    value_str = str(value).strip().lower()
    return value_str in ('true', 'yes', '1', 't')


def extract_dosage_form(pack_size_label: str) -> Optional[str]:
    """
    Extract dosage form from pack_size_label
    Examples:
        "strip of 10 tablets" -> "tablet"
        "bottle of 100 ml Syrup" -> "syrup"
    """
    if not pack_size_label or pd.isna(pack_size_label):
        return None

    forms = {
        'tablet': 'tablet',
        'capsule': 'capsule',
        'syrup': 'syrup',
        'suspension': 'suspension',
        'injection': 'injection',
        'cream': 'cream',
        'ointment': 'ointment',
        'gel': 'gel',
        'lotion': 'lotion',
        'drops': 'drops',
        'inhaler': 'inhaler',
        'spray': 'spray',
        'powder': 'powder',
    }

    pack_lower = pack_size_label.lower()
    for form_key, form_value in forms.items():
        if form_key in pack_lower:
            return form_value

    return None


def build_alternatives_jsonb(row: pd.Series) -> Optional[Dict]:
    """Build alternatives array from substitute columns"""
    alternatives = []

    for i in range(5):  # substitute0 to substitute4
        col = f'substitute{i}'
        if col in row and pd.notna(row[col]) and row[col].strip():
            alternatives.append({
                "brand_name": row[col].strip()
            })

    return alternatives if alternatives else None


def build_interactions_jsonb(row: pd.Series) -> Optional[Dict]:
    """Build interactions object from various columns"""
    interactions = {}

    # Side effects
    if pd.notna(row.get('Consolidated_Side_Effects')):
        side_effects = [s.strip() for s in row['Consolidated_Side_Effects'].split(',') if s.strip()]
        if side_effects:
            interactions['side_effects'] = side_effects

    # Uses
    uses = []
    for i in range(5):  # use0 to use4
        col = f'use{i}'
        if col in row and pd.notna(row[col]) and row[col].strip():
            uses.append(row[col].strip())
    if uses:
        interactions['uses'] = uses

    # Chemical class
    if pd.notna(row.get('Chemical Class')):
        # Clean up chemical class (remove curly braces if present)
        chemical_class = row['Chemical Class'].strip().replace('{', '').replace('}', '')
        if chemical_class:
            interactions['chemical_class'] = chemical_class

    # Action class
    if pd.notna(row.get('Action Class')):
        interactions['action_class'] = row['Action Class'].strip()

    return interactions if interactions else None


def generate_uuid() -> str:
    """Generate UUID as string"""
    return str(uuid.uuid4())


def import_medicines_with_components(csv_path: str, component_id_map: Dict[str, str]):
    """
    Import medicines from CSV and create component relationships
    """
    print(f"📖 Reading CSV: {csv_path}")
    df = pd.read_csv(csv_path)
    print(f"   Total rows: {len(df):,}")

    # Deduplication
    print(f"\n🔍 Deduplicating records...")
    df['dedup_key'] = df.apply(
        lambda row: f"{clean_text(row['name'])}|{clean_text(row.get('short_composition1', ''))}|{clean_text(row.get('short_composition2', ''))}|{clean_text(row.get('manufacturer_name', ''))}",
        axis=1
    )
    df_deduped = df.drop_duplicates(subset=['dedup_key'], keep='first')
    duplicates_removed = len(df) - len(df_deduped)
    print(f"   Removed {duplicates_removed:,} duplicates ({duplicates_removed/len(df)*100:.1f}%)")
    print(f"   Unique medicines: {len(df_deduped):,}")

    # Prepare records
    print(f"\n🔄 Preparing medicine records...")
    medicine_records = []
    medicine_component_records = []
    skipped = 0
    missing_components = set()

    for idx, row in df_deduped.iterrows():
        medicine_id = generate_uuid()

        # Parse components to build strength display
        comp_strengths = []
        comp1 = parse_composition(row.get('short_composition1'))
        if comp1:
            comp_strengths.append(f"{comp1[1]}{comp1[2]}")
        comp2 = parse_composition(row.get('short_composition2'))
        if comp2:
            comp_strengths.append(f"{comp2[1]}{comp2[2]}")

        strength_display = " + ".join(comp_strengths) if comp_strengths else None

        # Build medicine record
        medicine = {
            'id': medicine_id,
            'brand_name': clean_text(row['name']),
            'manufacturer': clean_text(row.get('manufacturer_name')),
            'dosage_form': extract_dosage_form(row.get('pack_size_label')),
            'strength': strength_display,
            'pack_size': clean_text(row.get('pack_size_label')),
            'therapeutic_class': clean_text(row.get('Therapeutic Class')),
            'schedule': None,  # Not in CSV
            'mrp': parse_price(row.get('price(₹)')),
            'is_discontinued': parse_bool(row.get('Is_discontinued')),
            'habit_forming': parse_bool(row.get('Habit Forming')),
            'alternatives': json.dumps(build_alternatives_jsonb(row)) if build_alternatives_jsonb(row) else None,
            'interactions': json.dumps(build_interactions_jsonb(row)) if build_interactions_jsonb(row) else None,
        }

        # Skip if no brand name
        if not medicine['brand_name']:
            skipped += 1
            continue

        medicine_records.append(medicine)

        # Create medicine_component records
        # Use a set to track already added components for this medicine (avoid duplicates)
        medicine_comp_ids = set()
        sequence = 1

        # Component 1
        if comp1:
            comp_name = normalize_component_name(comp1[0])
            component_id = component_id_map.get(comp_name)

            if component_id and component_id not in medicine_comp_ids:
                medicine_component_records.append({
                    'id': generate_uuid(),
                    'medicine_id': medicine_id,
                    'component_id': component_id,
                    'strength': Decimal(str(comp1[1])),
                    'unit': comp1[2],
                    'sequence': sequence
                })
                medicine_comp_ids.add(component_id)
                sequence += 1
            elif not component_id:
                missing_components.add(comp_name)

        # Component 2
        if comp2:
            comp_name = normalize_component_name(comp2[0])
            component_id = component_id_map.get(comp_name)

            if component_id and component_id not in medicine_comp_ids:
                medicine_component_records.append({
                    'id': generate_uuid(),
                    'medicine_id': medicine_id,
                    'component_id': component_id,
                    'strength': Decimal(str(comp2[1])),
                    'unit': comp2[2],
                    'sequence': sequence
                })
                medicine_comp_ids.add(component_id)
            elif not component_id:
                missing_components.add(comp_name)

        # Progress indicator
        if (idx + 1) % 10000 == 0:
            print(f"   Processed {idx + 1:,} / {len(df_deduped):,} rows...")

    print(f"✅ Prepared {len(medicine_records):,} medicine records")
    print(f"✅ Prepared {len(medicine_component_records):,} medicine-component relationships")
    if skipped:
        print(f"⚠️  Skipped {skipped:,} records (missing brand name)")
    if missing_components:
        print(f"⚠️  Missing {len(missing_components)} components in map: {list(missing_components)[:5]}...")

    # Bulk insert
    print(f"\n💾 Inserting into database...")
    engine = create_engine(settings.MEDICINE_DB_URL_SYNC, echo=False)

    with Session(engine) as session:
        # Insert medicines in batches
        batch_size = 1000
        total_medicines = len(medicine_records)

        print(f"   Inserting {total_medicines:,} medicines...")
        for i in range(0, total_medicines, batch_size):
            batch = medicine_records[i:i + batch_size]
            session.execute(
                text("""
                    INSERT INTO medicines (id, brand_name, manufacturer, dosage_form, strength, pack_size,
                                         therapeutic_class, schedule, mrp, is_discontinued, habit_forming,
                                         alternatives, interactions)
                    VALUES (:id, :brand_name, :manufacturer, :dosage_form, :strength, :pack_size,
                           :therapeutic_class, :schedule, :mrp, :is_discontinued, :habit_forming,
                           CAST(:alternatives AS jsonb), CAST(:interactions AS jsonb))
                """),
                batch
            )
            session.commit()
            print(f"   Inserted {min(i + batch_size, total_medicines):,} / {total_medicines:,} medicines...")

        # Insert medicine_components in batches
        total_components = len(medicine_component_records)
        print(f"\n   Inserting {total_components:,} medicine-component relationships...")
        for i in range(0, total_components, batch_size):
            batch = medicine_component_records[i:i + batch_size]
            session.execute(
                text("""
                    INSERT INTO medicine_components (id, medicine_id, component_id, strength, unit, sequence)
                    VALUES (:id, :medicine_id, :component_id, :strength, :unit, :sequence)
                """),
                batch
            )
            session.commit()
            print(f"   Inserted {min(i + batch_size, total_components):,} / {total_components:,} relationships...")

        print(f"\n✅ Import complete!")

        # Statistics
        result = session.execute(text("SELECT COUNT(*) FROM medicines"))
        med_count = result.scalar()

        result = session.execute(text("SELECT COUNT(*) FROM medicine_components"))
        comp_count = result.scalar()

        result = session.execute(text("SELECT COUNT(*) FROM medicines WHERE is_discontinued = true"))
        discontinued_count = result.scalar()

        print(f"\n📊 Database Statistics:")
        print(f"   Total medicines: {med_count:,}")
        print(f"   Total medicine-component relationships: {comp_count:,}")
        print(f"   Discontinued medicines: {discontinued_count:,}")
        print(f"   Average components per medicine: {comp_count/med_count:.2f}")


def main():
    """Main execution"""
    project_root = Path(__file__).parent.parent
    csv_path = project_root / "Extensive_A_Z_medicines_dataset_of_India.csv"
    component_map_path = project_root / "scripts" / "component_id_map.json"

    if not csv_path.exists():
        print(f"❌ CSV file not found: {csv_path}")
        sys.exit(1)

    if not component_map_path.exists():
        print(f"❌ Component ID map not found: {component_map_path}")
        print(f"   Run component extraction first:")
        print(f"   python scripts/01_extract_components.py")
        sys.exit(1)

    # Load component ID map
    print("📖 Loading component ID map...")
    with open(component_map_path, 'r') as f:
        component_id_map = json.load(f)
    print(f"   Loaded {len(component_id_map):,} component mappings")

    print("\n" + "=" * 80)
    print("IMPORT MEDICINES WITH COMPONENT RELATIONSHIPS")
    print("=" * 80)

    import_medicines_with_components(str(csv_path), component_id_map)

    print("\n" + "=" * 80)
    print("✅ MEDICINE IMPORT COMPLETE")
    print("=" * 80)
    print(f"\n🎯 Next steps:")
    print(f"   1. Verify data: SELECT * FROM medicines LIMIT 10;")
    print(f"   2. Test search: SELECT * FROM medicines WHERE brand_name ILIKE '%augmentin%';")
    print(f"   3. Run API server and test endpoints")
    print("=" * 80)


if __name__ == "__main__":
    main()
