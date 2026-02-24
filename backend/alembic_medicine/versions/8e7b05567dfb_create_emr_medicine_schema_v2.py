"""create_emr_medicine_schema_v2

Revision ID: 8e7b05567dfb
Revises: 001
Create Date: 2026-02-24 10:19:28.495997

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '8e7b05567dfb'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Complete database redesign for EMR-focused medicine system.
    This is a destructive migration (Option A - fresh start).
    """

    # Drop old tables (in reverse dependency order)
    op.execute("DROP TABLE IF EXISTS medicine_components CASCADE")
    op.execute("DROP TABLE IF EXISTS medicines CASCADE")
    op.execute("DROP TABLE IF EXISTS components CASCADE")

    # =============================================================================
    # CLASSIFICATION LAYER (must be created first - referenced by salts)
    # =============================================================================

    # 3. chemical_classes
    op.create_table(
        'chemical_classes',
        sa.Column('chemical_class_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('class_name', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('parent_class_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('chemical_classes.chemical_class_id'), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # 4. therapeutic_classes
    op.create_table(
        'therapeutic_classes',
        sa.Column('therapeutic_class_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('class_name', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('icd10_codes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # 5. action_classes
    op.create_table(
        'action_classes',
        sa.Column('action_class_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('class_name', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('mechanism', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # =============================================================================
    # CORE PHARMACEUTICAL LAYER
    # =============================================================================

    # 1. salts (Active Pharmaceutical Ingredients)
    op.create_table(
        'salts',
        sa.Column('salt_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('salt_name', sa.String(255), nullable=False, unique=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('chemical_formula', sa.String(100), nullable=True),

        # Foreign Keys to Classifications
        sa.Column('chemical_class_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('chemical_classes.chemical_class_id'), nullable=True),
        sa.Column('therapeutic_class_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('therapeutic_classes.therapeutic_class_id'), nullable=True),
        sa.Column('action_class_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('action_classes.action_class_id'), nullable=True),

        # Clinical Safety
        sa.Column('habit_forming', sa.Boolean, default=False),
        sa.Column('prescription_required', sa.Boolean, default=True),
        sa.Column('schedule', sa.String(10), nullable=True),  # H, H1, X, etc.

        # Pregnancy & Lactation
        sa.Column('pregnancy_category', sa.String(10), nullable=True),  # A, B, C, D, X
        sa.Column('lactation_safe', sa.Boolean, nullable=True),
        sa.Column('lactation_notes', sa.Text, nullable=True),

        # ABDM Integration
        sa.Column('snomed_code', sa.String(50), nullable=True),
        sa.Column('rxcui', sa.String(20), nullable=True),

        # Metadata
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
    )

    # Create indexes for salts
    op.create_index('idx_salt_name', 'salts', ['salt_name'])
    op.create_index('idx_salt_chemical_class', 'salts', ['chemical_class_id'])
    op.create_index('idx_salt_therapeutic_class', 'salts', ['therapeutic_class_id'])
    op.create_index('idx_salt_prescription_required', 'salts', ['prescription_required'])

    # Full-text search index for salts
    op.execute("""
        CREATE INDEX idx_salt_search ON salts
        USING gin(to_tsvector('english', salt_name || ' ' || COALESCE(description, '')))
    """)

    # 2. salt_strengths
    op.create_table(
        'salt_strengths',
        sa.Column('salt_strength_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('salt_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('salts.salt_id', ondelete='CASCADE'), nullable=False),
        sa.Column('strength_value', sa.Numeric(10, 3), nullable=False),
        sa.Column('strength_unit', sa.String(20), nullable=False),
        sa.Column('is_standard_strength', sa.Boolean, default=True),
        sa.Column('pediatric_approved', sa.Boolean, default=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint('salt_id', 'strength_value', 'strength_unit', name='uq_salt_strength'),
    )
    op.create_index('idx_salt_strength_salt', 'salt_strengths', ['salt_id'])

    # =============================================================================
    # CLINICAL SAFETY LAYER
    # =============================================================================

    # 6. side_effects
    op.create_table(
        'side_effects',
        sa.Column('side_effect_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('side_effect_name', sa.String(255), nullable=False, unique=True),
        sa.Column('severity', sa.String(20), nullable=True),  # mild, moderate, severe, life-threatening
        sa.Column('frequency', sa.String(20), nullable=True),  # rare, uncommon, common, very common
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('idx_side_effect_name', 'side_effects', ['side_effect_name'])
    op.create_index('idx_side_effect_severity', 'side_effects', ['severity'])

    # 7. salt_side_effects (Many-to-Many)
    op.create_table(
        'salt_side_effects',
        sa.Column('salt_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('salts.salt_id', ondelete='CASCADE'), nullable=False),
        sa.Column('side_effect_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('side_effects.side_effect_id', ondelete='CASCADE'), nullable=False),
        sa.Column('frequency', sa.String(20), nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.PrimaryKeyConstraint('salt_id', 'side_effect_id'),
    )
    op.create_index('idx_salt_side_effects_salt', 'salt_side_effects', ['salt_id'])
    op.create_index('idx_salt_side_effects_effect', 'salt_side_effects', ['side_effect_id'])

    # 8. contraindications
    op.create_table(
        'contraindications',
        sa.Column('contraindication_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('contraindication_name', sa.String(255), nullable=False, unique=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('icd10_code', sa.String(20), nullable=True),
        sa.Column('severity', sa.String(20), nullable=True),  # absolute, relative
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('idx_contraindication_name', 'contraindications', ['contraindication_name'])

    # 9. salt_contraindications (Many-to-Many)
    op.create_table(
        'salt_contraindications',
        sa.Column('salt_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('salts.salt_id', ondelete='CASCADE'), nullable=False),
        sa.Column('contraindication_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('contraindications.contraindication_id', ondelete='CASCADE'), nullable=False),
        sa.Column('severity', sa.String(20), nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.PrimaryKeyConstraint('salt_id', 'contraindication_id'),
    )
    op.create_index('idx_salt_contraindications_salt', 'salt_contraindications', ['salt_id'])

    # 10. drug_interactions
    op.create_table(
        'drug_interactions',
        sa.Column('interaction_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('salt_id_1', postgresql.UUID(as_uuid=True), sa.ForeignKey('salts.salt_id', ondelete='CASCADE'), nullable=False),
        sa.Column('salt_id_2', postgresql.UUID(as_uuid=True), sa.ForeignKey('salts.salt_id', ondelete='CASCADE'), nullable=False),
        sa.Column('severity', sa.String(20), nullable=False),  # minor, moderate, major, contraindicated
        sa.Column('effect', sa.Text, nullable=False),
        sa.Column('mechanism', sa.Text, nullable=True),
        sa.Column('management', sa.Text, nullable=True),
        sa.Column('evidence_level', sa.String(20), nullable=True),  # theoretical, case-report, study-based
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint('salt_id_1', 'salt_id_2', name='uq_drug_interaction'),
        sa.CheckConstraint('salt_id_1 < salt_id_2', name='chk_interaction_order'),
    )
    op.create_index('idx_interaction_salt1', 'drug_interactions', ['salt_id_1'])
    op.create_index('idx_interaction_salt2', 'drug_interactions', ['salt_id_2'])
    op.create_index('idx_interaction_severity', 'drug_interactions', ['severity'])

    # =============================================================================
    # CLINICAL INDICATIONS LAYER
    # =============================================================================

    # 11. uses (Indications)
    op.create_table(
        'uses',
        sa.Column('use_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('use_name', sa.String(500), nullable=False, unique=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('icd10_code', sa.String(20), nullable=True),
        sa.Column('is_primary_indication', sa.Boolean, default=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('idx_use_name', 'uses', ['use_name'])

    # Full-text search for uses
    op.execute("""
        CREATE INDEX idx_use_search ON uses
        USING gin(to_tsvector('english', use_name || ' ' || COALESCE(description, '')))
    """)

    # 12. salt_uses (Many-to-Many)
    op.create_table(
        'salt_uses',
        sa.Column('salt_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('salts.salt_id', ondelete='CASCADE'), nullable=False),
        sa.Column('use_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('uses.use_id', ondelete='CASCADE'), nullable=False),
        sa.Column('is_approved', sa.Boolean, default=True),
        sa.Column('age_restriction', sa.String(100), nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.PrimaryKeyConstraint('salt_id', 'use_id'),
    )
    op.create_index('idx_salt_uses_salt', 'salt_uses', ['salt_id'])
    op.create_index('idx_salt_uses_use', 'salt_uses', ['use_id'])

    # =============================================================================
    # THERAPEUTIC ALTERNATIVES
    # =============================================================================

    # 13. salt_alternatives (Self-referencing)
    op.create_table(
        'salt_alternatives',
        sa.Column('salt_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('salts.salt_id', ondelete='CASCADE'), nullable=False),
        sa.Column('alternative_salt_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('salts.salt_id', ondelete='CASCADE'), nullable=False),
        sa.Column('equivalence_type', sa.String(50), nullable=True),  # therapeutic, generic, biosimilar
        sa.Column('notes', sa.Text, nullable=True),
        sa.PrimaryKeyConstraint('salt_id', 'alternative_salt_id'),
        sa.CheckConstraint('salt_id != alternative_salt_id', name='chk_no_self_alternative'),
    )
    op.create_index('idx_salt_alternatives_salt', 'salt_alternatives', ['salt_id'])
    op.create_index('idx_salt_alternatives_alt', 'salt_alternatives', ['alternative_salt_id'])

    # =============================================================================
    # COMMERCIAL LAYER
    # =============================================================================

    # 14. manufacturers
    op.create_table(
        'manufacturers',
        sa.Column('manufacturer_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('manufacturer_name', sa.String(255), nullable=False, unique=True),
        sa.Column('country', sa.String(100), nullable=True),
        sa.Column('license_number', sa.String(100), nullable=True),
        sa.Column('contact_info', postgresql.JSONB, nullable=True),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('idx_manufacturer_name', 'manufacturers', ['manufacturer_name'])
    op.create_index('idx_manufacturer_active', 'manufacturers', ['is_active'])

    # 15. brands
    op.create_table(
        'brands',
        sa.Column('brand_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('brand_name', sa.String(255), nullable=False),
        sa.Column('manufacturer_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('manufacturers.manufacturer_id'), nullable=False),
        sa.Column('is_discontinued', sa.Boolean, default=False),
        sa.Column('drug_type', sa.String(50), default='allopathy'),
        sa.Column('launch_date', sa.Date, nullable=True),
        sa.Column('discontinuation_date', sa.Date, nullable=True),
        sa.Column('ndhm_code', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint('brand_name', 'manufacturer_id', name='uq_brand_manufacturer'),
    )
    op.create_index('idx_brand_name', 'brands', ['brand_name'])
    op.create_index('idx_brand_manufacturer', 'brands', ['manufacturer_id'])
    op.create_index('idx_brand_discontinued', 'brands', ['is_discontinued'])

    # Full-text search for brands
    op.execute("""
        CREATE INDEX idx_brand_search ON brands
        USING gin(to_tsvector('english', brand_name))
    """)

    # =============================================================================
    # BRAND COMPOSITION
    # =============================================================================

    # 16. brand_compositions (Links brands to salt_strengths)
    op.create_table(
        'brand_compositions',
        sa.Column('composition_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('brand_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('brands.brand_id', ondelete='CASCADE'), nullable=False),
        sa.Column('salt_strength_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('salt_strengths.salt_strength_id'), nullable=False),
        sa.Column('sequence', sa.Integer, nullable=False, default=1),
        sa.UniqueConstraint('brand_id', 'salt_strength_id', name='uq_brand_salt_strength'),
    )
    op.create_index('idx_brand_composition_brand', 'brand_compositions', ['brand_id'])
    op.create_index('idx_brand_composition_salt', 'brand_compositions', ['salt_strength_id'])

    # =============================================================================
    # PACKAGING LAYER
    # =============================================================================

    # 17. pack_forms
    op.create_table(
        'pack_forms',
        sa.Column('pack_form_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('form_name', sa.String(100), nullable=False, unique=True),
        sa.Column('route_of_administration', sa.String(50), nullable=True),
        sa.Column('is_solid', sa.Boolean, nullable=True),
        sa.Column('is_liquid', sa.Boolean, nullable=True),
        sa.Column('requires_reconstitution', sa.Boolean, default=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('idx_pack_form_name', 'pack_forms', ['form_name'])

    # 18. brand_packaging
    op.create_table(
        'brand_packaging',
        sa.Column('brand_pack_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('brand_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('brands.brand_id', ondelete='CASCADE'), nullable=False),
        sa.Column('pack_form_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('pack_forms.pack_form_id'), nullable=False),
        sa.Column('quantity', sa.Integer, nullable=False),
        sa.Column('pack_type', sa.String(100), nullable=True),
        sa.Column('sku', sa.String(100), nullable=True),
        sa.Column('barcode', sa.String(100), nullable=True),
        sa.Column('is_primary_pack', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint('brand_id', 'pack_form_id', 'quantity', name='uq_brand_pack'),
    )
    op.create_index('idx_brand_pack_brand', 'brand_packaging', ['brand_id'])
    op.create_index('idx_brand_pack_form', 'brand_packaging', ['pack_form_id'])

    # =============================================================================
    # DOSING GUIDELINES (EMR Enhancement)
    # =============================================================================

    # 19. dosing_guidelines
    op.create_table(
        'dosing_guidelines',
        sa.Column('dosing_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('salt_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('salts.salt_id', ondelete='CASCADE'), nullable=False),
        sa.Column('use_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('uses.use_id'), nullable=True),
        sa.Column('age_group', sa.String(50), nullable=True),
        sa.Column('min_age_years', sa.Numeric(4, 1), nullable=True),
        sa.Column('max_age_years', sa.Numeric(4, 1), nullable=True),
        sa.Column('weight_based', sa.Boolean, default=False),
        sa.Column('standard_dose', sa.String(255), nullable=False),
        sa.Column('frequency', sa.String(100), nullable=True),
        sa.Column('route', sa.String(50), nullable=True),
        sa.Column('duration', sa.String(100), nullable=True),
        sa.Column('max_daily_dose', sa.String(100), nullable=True),
        sa.Column('renal_adjustment', sa.Text, nullable=True),
        sa.Column('hepatic_adjustment', sa.Text, nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('idx_dosing_salt', 'dosing_guidelines', ['salt_id'])
    op.create_index('idx_dosing_use', 'dosing_guidelines', ['use_id'])

    # =============================================================================
    # SEARCH & AUDIT (EMR Enhancement)
    # =============================================================================

    # 20. medicine_search_log
    op.create_table(
        'medicine_search_log',
        sa.Column('log_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('search_query', sa.String(500), nullable=True),
        sa.Column('search_type', sa.String(50), nullable=True),
        sa.Column('results_count', sa.Integer, nullable=True),
        sa.Column('selected_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('timestamp', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('idx_search_log_timestamp', 'medicine_search_log', ['timestamp'])
    op.create_index('idx_search_log_user', 'medicine_search_log', ['user_id'])

    # 21. prescription_audit
    op.create_table(
        'prescription_audit',
        sa.Column('audit_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('prescription_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('doctor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('brand_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('brands.brand_id'), nullable=True),
        sa.Column('salt_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('salts.salt_id'), nullable=True),
        sa.Column('dosage', sa.String(255), nullable=True),
        sa.Column('duration', sa.String(100), nullable=True),
        sa.Column('interaction_alerts', postgresql.JSONB, nullable=True),
        sa.Column('contraindication_alerts', postgresql.JSONB, nullable=True),
        sa.Column('allergy_alerts', postgresql.JSONB, nullable=True),
        sa.Column('prescribed_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('idx_audit_prescription', 'prescription_audit', ['prescription_id'])
    op.create_index('idx_audit_doctor', 'prescription_audit', ['doctor_id'])
    op.create_index('idx_audit_patient', 'prescription_audit', ['patient_id'])
    op.create_index('idx_audit_brand', 'prescription_audit', ['brand_id'])


def downgrade() -> None:
    """
    Rollback to old schema (components/medicines/medicine_components).
    WARNING: This will lose all data in the new schema.
    """

    # Drop all new tables (in reverse dependency order)
    op.drop_table('prescription_audit')
    op.drop_table('medicine_search_log')
    op.drop_table('dosing_guidelines')
    op.drop_table('brand_packaging')
    op.drop_table('pack_forms')
    op.drop_table('brand_compositions')
    op.drop_table('brands')
    op.drop_table('manufacturers')
    op.drop_table('salt_alternatives')
    op.drop_table('salt_uses')
    op.drop_table('uses')
    op.drop_table('drug_interactions')
    op.drop_table('salt_contraindications')
    op.drop_table('contraindications')
    op.drop_table('salt_side_effects')
    op.drop_table('side_effects')
    op.drop_table('salt_strengths')
    op.drop_table('salts')
    op.drop_table('action_classes')
    op.drop_table('therapeutic_classes')
    op.drop_table('chemical_classes')

    # Recreate old schema
    op.create_table(
        'components',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(255), nullable=False, unique=True),
        sa.Column('common_names', sa.String(500), nullable=True),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('idx_component_name', 'components', ['name'])
    op.create_index('idx_component_category', 'components', ['category'])

    op.create_table(
        'medicines',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('brand_name', sa.String(255), nullable=False),
        sa.Column('manufacturer', sa.String(255), nullable=True),
        sa.Column('dosage_form', sa.String(100), nullable=True),
        sa.Column('pack_size', sa.String(100), nullable=True),
        sa.Column('therapeutic_class', sa.String(255), nullable=True),
        sa.Column('schedule', sa.String(50), nullable=True),
        sa.Column('mrp', sa.Numeric(10, 2), nullable=True),
        sa.Column('is_discontinued', sa.Boolean, default=False),
        sa.Column('habit_forming', sa.Boolean, default=False),
        sa.Column('alternatives', postgresql.JSONB, nullable=True),
        sa.Column('interactions', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('idx_medicine_brand_name', 'medicines', ['brand_name'])
    op.create_index('idx_medicine_manufacturer', 'medicines', ['manufacturer'])
    op.create_index('idx_medicine_discontinued', 'medicines', ['is_discontinued'])

    op.create_table(
        'medicine_components',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('medicine_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('medicines.id', ondelete='CASCADE'), nullable=False),
        sa.Column('component_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('components.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('strength', sa.Numeric(10, 3), nullable=False),
        sa.Column('unit', sa.String(20), nullable=False),
        sa.Column('sequence', sa.Integer, nullable=False, default=1),
        sa.UniqueConstraint('medicine_id', 'component_id', name='uq_medicine_component'),
    )
    op.create_index('idx_medicine_component_medicine', 'medicine_components', ['medicine_id'])
    op.create_index('idx_medicine_component_component', 'medicine_components', ['component_id'])
