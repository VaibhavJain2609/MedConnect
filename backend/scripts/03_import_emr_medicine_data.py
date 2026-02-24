"""
EMR Medicine Data Import Pipeline
Transforms CSV data into normalized pharmaceutical database structure.
"""

import re
import sys
from pathlib import Path
from decimal import Decimal
from datetime import datetime
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings

# Database connection
engine = create_engine(settings.MEDICINE_DB_URL_SYNC)
Session = sessionmaker(bind=engine)


class MedicineDataImporter:
    """Imports and transforms medicine CSV data into EMR schema."""

    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.session = Session()

        # ID mappings for relationships
        self.chemical_class_map = {}
        self.therapeutic_class_map = {}
        self.action_class_map = {}
        self.salt_map = {}  # salt_name -> salt_id
        self.salt_strength_map = {}  # (salt_id, value, unit) -> salt_strength_id
        self.manufacturer_map = {}  # manufacturer_name -> manufacturer_id
        self.side_effect_map = {}
        self.use_map = {}

        # Regex for parsing composition
        self.composition_regex = re.compile(
            r'^(.+?)\s*\((\d+(?:\.\d+)?)\s*(mg|mcg|g|ml|%|IU|mEq)(?:/\d+ml)?\)'
        )

    def parse_composition(self, comp_string: str):
        """
        Parse composition string like "Amoxycillin (500mg)"
        Returns: (salt_name, strength_value, unit) or None
        """
        if not comp_string or pd.isna(comp_string):
            return None

        comp_string = comp_string.strip()
        match = self.composition_regex.match(comp_string)

        if match:
            salt_name = match.group(1).strip()
            strength = match.group(2).strip()
            unit = match.group(3).strip()
            return (salt_name, strength, unit)

        return None

    def import_classifications(self, df):
        """Import chemical, therapeutic, and action classes."""
        print("\n=== Importing Classifications ===")

        # Chemical Classes
        chemical_classes = df['Chemical Class'].dropna().unique()
        for class_name in chemical_classes:
            if class_name and class_name.strip():
                class_name = class_name.strip()
                result = self.session.execute(
                    text("""
                        INSERT INTO chemical_classes (class_name)
                        VALUES (:name)
                        ON CONFLICT (class_name) DO UPDATE SET class_name = EXCLUDED.class_name
                        RETURNING chemical_class_id
                    """),
                    {"name": class_name}
                )
                self.chemical_class_map[class_name] = result.scalar()

        print(f"  ✓ {len(self.chemical_class_map)} chemical classes")

        # Therapeutic Classes
        therapeutic_classes = df['Therapeutic Class'].dropna().unique()
        for class_name in therapeutic_classes:
            if class_name and class_name.strip():
                class_name = class_name.strip()
                result = self.session.execute(
                    text("""
                        INSERT INTO therapeutic_classes (class_name)
                        VALUES (:name)
                        ON CONFLICT (class_name) DO UPDATE SET class_name = EXCLUDED.class_name
                        RETURNING therapeutic_class_id
                    """),
                    {"name": class_name}
                )
                self.therapeutic_class_map[class_name] = result.scalar()

        print(f"  ✓ {len(self.therapeutic_class_map)} therapeutic classes")

        # Action Classes
        action_classes = df['Action Class'].dropna().unique()
        for class_name in action_classes:
            if class_name and class_name.strip():
                class_name = class_name.strip()
                result = self.session.execute(
                    text("""
                        INSERT INTO action_classes (class_name)
                        VALUES (:name)
                        ON CONFLICT (class_name) DO UPDATE SET class_name = EXCLUDED.class_name
                        RETURNING action_class_id
                    """),
                    {"name": class_name}
                )
                self.action_class_map[class_name] = result.scalar()

        print(f"  ✓ {len(self.action_class_map)} action classes")

        self.session.commit()

    def import_manufacturers(self, df):
        """Import unique manufacturers."""
        print("\n=== Importing Manufacturers ===")

        manufacturers = df['manufacturer_name'].dropna().unique()

        for mfr_name in manufacturers:
            if mfr_name and mfr_name.strip():
                mfr_name = mfr_name.strip()
                result = self.session.execute(
                    text("""
                        INSERT INTO manufacturers (manufacturer_name, is_active)
                        VALUES (:name, TRUE)
                        ON CONFLICT (manufacturer_name) DO UPDATE SET manufacturer_name = EXCLUDED.manufacturer_name
                        RETURNING manufacturer_id
                    """),
                    {"name": mfr_name}
                )
                self.manufacturer_map[mfr_name] = result.scalar()

        print(f"  ✓ {len(self.manufacturer_map)} manufacturers")
        self.session.commit()

    def import_salts_and_strengths(self, df):
        """Extract and import unique salts and their strengths."""
        print("\n=== Extracting Salts and Strengths ===")

        salt_data = {}  # salt_name -> {chemical_class, therapeutic_class, action_class, strengths: set()}

        # Parse all compositions
        for idx, row in df.iterrows():
            # Get classifications for this medicine
            chem_class = row.get('Chemical Class')
            ther_class = row.get('Therapeutic Class')
            act_class = row.get('Action Class')
            habit = row.get('Habit Forming', 'No')

            # Parse compositions
            for comp_col in ['short_composition1', 'short_composition2']:
                comp_str = row.get(comp_col)
                parsed = self.parse_composition(comp_str)

                if parsed:
                    salt_name, strength_val, unit = parsed

                    if salt_name not in salt_data:
                        salt_data[salt_name] = {
                            'chemical_class': chem_class,
                            'therapeutic_class': ther_class,
                            'action_class': act_class,
                            'habit_forming': habit == 'Yes',
                            'strengths': set()
                        }

                    # Add strength
                    salt_data[salt_name]['strengths'].add((strength_val, unit))

        print(f"  ✓ Extracted {len(salt_data)} unique salts")

        # Insert salts
        for salt_name, data in salt_data.items():
            # Get classification IDs
            chem_id = self.chemical_class_map.get(data['chemical_class']) if data['chemical_class'] else None
            ther_id = self.therapeutic_class_map.get(data['therapeutic_class']) if data['therapeutic_class'] else None
            act_id = self.action_class_map.get(data['action_class']) if data['action_class'] else None

            # Insert salt
            result = self.session.execute(
                text("""
                    INSERT INTO salts (
                        salt_name,
                        chemical_class_id,
                        therapeutic_class_id,
                        action_class_id,
                        habit_forming,
                        prescription_required
                    )
                    VALUES (:name, :chem, :ther, :act, :habit, TRUE)
                    ON CONFLICT (salt_name) DO UPDATE
                    SET chemical_class_id = EXCLUDED.chemical_class_id
                    RETURNING salt_id
                """),
                {
                    "name": salt_name,
                    "chem": chem_id,
                    "ther": ther_id,
                    "act": act_id,
                    "habit": data['habit_forming']
                }
            )
            salt_id = result.scalar()
            self.salt_map[salt_name] = salt_id

            # Insert strengths
            for strength_val, unit in data['strengths']:
                result = self.session.execute(
                    text("""
                        INSERT INTO salt_strengths (salt_id, strength_value, strength_unit)
                        VALUES (:salt_id, :value, :unit)
                        ON CONFLICT (salt_id, strength_value, strength_unit) DO NOTHING
                        RETURNING salt_strength_id
                    """),
                    {
                        "salt_id": salt_id,
                        "value": Decimal(strength_val),
                        "unit": unit
                    }
                )
                strength_id_result = result.scalar()
                if strength_id_result:
                    self.salt_strength_map[(salt_id, strength_val, unit)] = strength_id_result

        self.session.commit()

        # Fetch all salt_strength IDs for mapping (use UUID and numeric value for key)
        result = self.session.execute(
            text("SELECT salt_id, strength_value, strength_unit, salt_strength_id FROM salt_strengths")
        )
        for row in result:
            # Key: (salt_id as UUID, strength as normalized float, unit)
            key = (row[0], float(row[1]), row[2])
            self.salt_strength_map[key] = row[3]

        print(f"  ✓ {len(self.salt_map)} salts imported")
        print(f"  ✓ {len(self.salt_strength_map)} strengths imported")

    def import_side_effects(self, df):
        """Import side effects from Consolidated_Side_Effects column."""
        print("\n=== Importing Side Effects ===")

        side_effects_set = set()

        for effects_str in df['Consolidated_Side_Effects'].dropna():
            if effects_str and effects_str.strip():
                # Split by comma
                effects = [e.strip() for e in effects_str.split(',')]
                side_effects_set.update(effects)

        for effect_name in side_effects_set:
            if effect_name:
                result = self.session.execute(
                    text("""
                        INSERT INTO side_effects (side_effect_name)
                        VALUES (:name)
                        ON CONFLICT (side_effect_name) DO NOTHING
                        RETURNING side_effect_id
                    """),
                    {"name": effect_name}
                )
                effect_id = result.scalar()
                if effect_id:
                    self.side_effect_map[effect_name] = effect_id

        # Fetch all for mapping
        result = self.session.execute(text("SELECT side_effect_name, side_effect_id FROM side_effects"))
        for row in result:
            self.side_effect_map[row[0]] = row[1]

        print(f"  ✓ {len(self.side_effect_map)} side effects")
        self.session.commit()

    def import_uses(self, df):
        """Import uses from use0-use4 columns."""
        print("\n=== Importing Uses ===")

        uses_set = set()

        for col in ['use0', 'use1', 'use2', 'use3', 'use4']:
            uses = df[col].dropna().unique()
            uses_set.update([u.strip() for u in uses if u and u.strip()])

        for use_name in uses_set:
            # Truncate very long use names (data quality issue in CSV)
            use_name_truncated = use_name[:500] if len(use_name) > 500 else use_name

            result = self.session.execute(
                text("""
                    INSERT INTO uses (use_name)
                    VALUES (:name)
                    ON CONFLICT (use_name) DO NOTHING
                    RETURNING use_id
                """),
                {"name": use_name_truncated}
            )
            use_id = result.scalar()
            if use_id:
                self.use_map[use_name] = use_id

        # Fetch all for mapping
        result = self.session.execute(text("SELECT use_name, use_id FROM uses"))
        for row in result:
            self.use_map[row[0]] = row[1]

        print(f"  ✓ {len(self.use_map)} uses")
        self.session.commit()

    def import_brands_and_compositions(self, df):
        """Import brands and their compositions."""
        print("\n=== Importing Brands and Compositions ===")

        brands_imported = 0
        compositions_imported = 0
        errors = []

        for idx, row in df.iterrows():
            try:
                brand_name = row['name']
                mfr_name = row['manufacturer_name']
                is_discontinued = row['Is_discontinued']
                drug_type = row.get('type', 'allopathy')

                # Get manufacturer ID
                mfr_id = self.manufacturer_map.get(mfr_name)
                if not mfr_id:
                    errors.append(f"Row {idx}: Manufacturer '{mfr_name}' not found")
                    continue

                # Insert brand
                result = self.session.execute(
                    text("""
                        INSERT INTO brands (brand_name, manufacturer_id, is_discontinued, drug_type)
                        VALUES (:name, :mfr_id, :disc, :type)
                        ON CONFLICT (brand_name, manufacturer_id) DO UPDATE
                        SET is_discontinued = EXCLUDED.is_discontinued
                        RETURNING brand_id
                    """),
                    {
                        "name": brand_name,
                        "mfr_id": mfr_id,
                        "disc": is_discontinued,
                        "type": drug_type
                    }
                )
                brand_id = result.scalar()
                brands_imported += 1

                # Parse and link compositions
                sequence = 1
                for comp_col in ['short_composition1', 'short_composition2']:
                    comp_str = row.get(comp_col)
                    parsed = self.parse_composition(comp_str)

                    if parsed:
                        salt_name, strength_val, unit = parsed
                        salt_id = self.salt_map.get(salt_name)

                        if not salt_id:
                            errors.append(f"Row {idx}: Salt '{salt_name}' not found")
                            continue

                        # Find salt_strength_id (use same key format as map building)
                        strength_key = (salt_id, float(strength_val), unit)
                        salt_strength_id = self.salt_strength_map.get(strength_key)

                        if not salt_strength_id:
                            errors.append(f"Row {idx}: Strength not found for {salt_name} {strength_val}{unit}")
                            continue

                        # Insert brand composition
                        self.session.execute(
                            text("""
                                INSERT INTO brand_compositions (brand_id, salt_strength_id, sequence)
                                VALUES (:brand_id, :strength_id, :seq)
                                ON CONFLICT (brand_id, salt_strength_id) DO NOTHING
                            """),
                            {
                                "brand_id": brand_id,
                                "strength_id": salt_strength_id,
                                "seq": sequence
                            }
                        )
                        compositions_imported += 1
                        sequence += 1

                # Commit every 1000 brands
                if brands_imported % 1000 == 0:
                    self.session.commit()
                    print(f"  ... {brands_imported} brands processed")

            except Exception as e:
                errors.append(f"Row {idx}: {str(e)}")
                if len(errors) > 100:  # Limit error reporting
                    break

        self.session.commit()

        print(f"  ✓ {brands_imported} brands imported")
        print(f"  ✓ {compositions_imported} compositions linked")

        if errors:
            print(f"\n  ⚠ {len(errors)} errors encountered (showing first 20):")
            for error in errors[:20]:
                print(f"    - {error}")

    def run(self):
        """Execute the complete import pipeline."""
        print("=" * 80)
        print("EMR Medicine Data Import Pipeline")
        print("=" * 80)

        # Load CSV
        print(f"\nLoading CSV from: {self.csv_path}")
        df = pd.read_csv(self.csv_path)
        print(f"  ✓ Loaded {len(df):,} records")

        # Remove duplicates
        df_original_count = len(df)
        df['dedup_key'] = (
            df['name'].astype(str) + '|' +
            df['manufacturer_name'].astype(str) + '|' +
            df['short_composition1'].astype(str)
        )
        df = df.drop_duplicates(subset=['dedup_key'], keep='first')
        df = df.drop(columns=['dedup_key'])
        print(f"  ✓ Removed {df_original_count - len(df):,} duplicates, {len(df):,} remaining")

        # Execute import stages
        try:
            self.import_classifications(df)
            self.import_manufacturers(df)
            self.import_side_effects(df)
            self.import_uses(df)
            self.import_salts_and_strengths(df)
            self.import_brands_and_compositions(df)

            print("\n" + "=" * 80)
            print("✅ Import Complete!")
            print("=" * 80)

            # Print statistics
            result = self.session.execute(text("""
                SELECT
                    (SELECT COUNT(*) FROM salts) as salts,
                    (SELECT COUNT(*) FROM salt_strengths) as strengths,
                    (SELECT COUNT(*) FROM brands) as brands,
                    (SELECT COUNT(*) FROM brand_compositions) as compositions,
                    (SELECT COUNT(*) FROM manufacturers) as manufacturers,
                    (SELECT COUNT(*) FROM chemical_classes) as chemical_classes,
                    (SELECT COUNT(*) FROM therapeutic_classes) as therapeutic_classes,
                    (SELECT COUNT(*) FROM action_classes) as action_classes,
                    (SELECT COUNT(*) FROM side_effects) as side_effects,
                    (SELECT COUNT(*) FROM uses) as uses
            """))
            stats = result.first()

            print("\nDatabase Statistics:")
            print(f"  • Salts: {stats[0]:,}")
            print(f"  • Salt Strengths: {stats[1]:,}")
            print(f"  • Brands: {stats[2]:,}")
            print(f"  • Brand Compositions: {stats[3]:,}")
            print(f"  • Manufacturers: {stats[4]:,}")
            print(f"  • Chemical Classes: {stats[5]:,}")
            print(f"  • Therapeutic Classes: {stats[6]:,}")
            print(f"  • Action Classes: {stats[7]:,}")
            print(f"  • Side Effects: {stats[8]:,}")
            print(f"  • Uses: {stats[9]:,}")

        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            self.session.rollback()
            raise

        finally:
            self.session.close()


if __name__ == "__main__":
    csv_path = "/app/Dataset/Extensive_A_Z_medicines_dataset_of_India.csv"

    importer = MedicineDataImporter(csv_path)
    importer.run()
