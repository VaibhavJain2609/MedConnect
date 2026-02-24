# Medicine Database Schema v2.0 - EMR Edition

## Overview
Comprehensive pharmaceutical database designed for Electronic Medical Records (EMR) system with support for:
- Prescription writing with clinical decision support
- Drug interaction checking
- Allergy management
- ABDM (Ayushman Bharat Digital Mission) integration
- Inventory management
- Clinical guidelines

---

## 🧬 CORE PHARMACEUTICAL LAYER

### 1. salts (Active Pharmaceutical Ingredients)
Primary table for active ingredients/generic drugs.

```sql
CREATE TABLE salts (
    salt_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    salt_name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    chemical_formula VARCHAR(100),

    -- Classifications (Foreign Keys)
    chemical_class_id UUID REFERENCES chemical_classes(chemical_class_id),
    therapeutic_class_id UUID REFERENCES therapeutic_classes(therapeutic_class_id),
    action_class_id UUID REFERENCES action_classes(action_class_id),

    -- Clinical Safety
    habit_forming BOOLEAN DEFAULT false,
    prescription_required BOOLEAN DEFAULT true,
    schedule VARCHAR(10),  -- H, H1, X, etc. (Indian drug schedule)

    -- Pregnancy & Lactation
    pregnancy_category VARCHAR(10),  -- A, B, C, D, X (FDA categories)
    lactation_safe BOOLEAN,
    lactation_notes TEXT,

    -- ABDM Integration
    snomed_code VARCHAR(50),  -- SNOMED CT code for interoperability
    rxcui VARCHAR(20),        -- RxNorm CUI

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by UUID,

    -- Indexes
    INDEX idx_salt_name (salt_name),
    INDEX idx_chemical_class (chemical_class_id),
    INDEX idx_therapeutic_class (therapeutic_class_id),
    INDEX idx_prescription_required (prescription_required),
    FULLTEXT INDEX idx_salt_search (salt_name, description)
);
```

### 2. salt_strengths
Available strengths for each salt.

```sql
CREATE TABLE salt_strengths (
    salt_strength_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    salt_id UUID NOT NULL REFERENCES salts(salt_id) ON DELETE CASCADE,

    strength_value DECIMAL(10, 3) NOT NULL,
    strength_unit VARCHAR(20) NOT NULL,  -- mg, mcg, g, ml, %, IU, mEq

    -- Dosing information
    is_standard_strength BOOLEAN DEFAULT true,
    pediatric_approved BOOLEAN DEFAULT false,

    created_at TIMESTAMP DEFAULT NOW(),

    UNIQUE (salt_id, strength_value, strength_unit),
    INDEX idx_salt_strength (salt_id)
);
```

---

## 🏷️ CLASSIFICATION LAYER

### 3. chemical_classes
Chemical classification of drugs.

```sql
CREATE TABLE chemical_classes (
    chemical_class_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    class_name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    parent_class_id UUID REFERENCES chemical_classes(chemical_class_id),

    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_chemical_class_name (class_name)
);
```

### 4. therapeutic_classes
Therapeutic/pharmacological classification.

```sql
CREATE TABLE therapeutic_classes (
    therapeutic_class_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    class_name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    icd10_codes TEXT,  -- Associated ICD-10 codes (comma-separated)

    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_therapeutic_class_name (class_name)
);
```

### 5. action_classes
Mechanism of action classification.

```sql
CREATE TABLE action_classes (
    action_class_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    class_name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    mechanism TEXT,

    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_action_class_name (class_name)
);
```

---

## ⚠️ CLINICAL SAFETY LAYER

### 6. side_effects
Known adverse effects.

```sql
CREATE TABLE side_effects (
    side_effect_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    side_effect_name VARCHAR(255) NOT NULL UNIQUE,
    severity VARCHAR(20),  -- mild, moderate, severe, life-threatening
    frequency VARCHAR(20),  -- rare, uncommon, common, very common
    description TEXT,

    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_side_effect_name (side_effect_name),
    INDEX idx_severity (severity)
);
```

### 7. salt_side_effects (Many-to-Many)
```sql
CREATE TABLE salt_side_effects (
    salt_id UUID NOT NULL REFERENCES salts(salt_id) ON DELETE CASCADE,
    side_effect_id UUID NOT NULL REFERENCES side_effects(side_effect_id) ON DELETE CASCADE,

    frequency VARCHAR(20),  -- Override frequency for this specific salt
    notes TEXT,

    PRIMARY KEY (salt_id, side_effect_id),
    INDEX idx_salt_effects (salt_id),
    INDEX idx_effect_salts (side_effect_id)
);
```

### 8. contraindications
Conditions where drug should not be used.

```sql
CREATE TABLE contraindications (
    contraindication_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contraindication_name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    icd10_code VARCHAR(20),
    severity VARCHAR(20),  -- absolute, relative

    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_contraindication_name (contraindication_name)
);
```

### 9. salt_contraindications (Many-to-Many)
```sql
CREATE TABLE salt_contraindications (
    salt_id UUID NOT NULL REFERENCES salts(salt_id) ON DELETE CASCADE,
    contraindication_id UUID NOT NULL REFERENCES contraindications(contraindication_id) ON DELETE CASCADE,

    severity VARCHAR(20),
    notes TEXT,

    PRIMARY KEY (salt_id, contraindication_id),
    INDEX idx_salt_contraindications (salt_id)
);
```

### 10. drug_interactions
Drug-drug interactions.

```sql
CREATE TABLE drug_interactions (
    interaction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    salt_id_1 UUID NOT NULL REFERENCES salts(salt_id) ON DELETE CASCADE,
    salt_id_2 UUID NOT NULL REFERENCES salts(salt_id) ON DELETE CASCADE,

    severity VARCHAR(20) NOT NULL,  -- minor, moderate, major, contraindicated
    effect TEXT NOT NULL,
    mechanism TEXT,
    management TEXT,

    evidence_level VARCHAR(20),  -- theoretical, case-report, study-based

    created_at TIMESTAMP DEFAULT NOW(),

    CHECK (salt_id_1 < salt_id_2),  -- Prevent duplicates (A+B same as B+A)
    UNIQUE (salt_id_1, salt_id_2),
    INDEX idx_interaction_salt1 (salt_id_1),
    INDEX idx_interaction_salt2 (salt_id_2),
    INDEX idx_interaction_severity (severity)
);
```

---

## 🩺 CLINICAL INDICATIONS LAYER

### 11. uses (Indications)
Approved and off-label uses.

```sql
CREATE TABLE uses (
    use_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    use_name VARCHAR(500) NOT NULL UNIQUE,
    description TEXT,
    icd10_code VARCHAR(20),
    is_primary_indication BOOLEAN DEFAULT false,

    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_use_name (use_name),
    FULLTEXT INDEX idx_use_search (use_name, description)
);
```

### 12. salt_uses (Many-to-Many)
```sql
CREATE TABLE salt_uses (
    salt_id UUID NOT NULL REFERENCES salts(salt_id) ON DELETE CASCADE,
    use_id UUID NOT NULL REFERENCES uses(use_id) ON DELETE CASCADE,

    is_approved BOOLEAN DEFAULT true,  -- FDA/CDSCO approved vs off-label
    age_restriction VARCHAR(100),  -- "Adults only", "Children >2 years", etc.
    notes TEXT,

    PRIMARY KEY (salt_id, use_id),
    INDEX idx_salt_uses (salt_id),
    INDEX idx_use_salts (use_id)
);
```

---

## 🔁 THERAPEUTIC ALTERNATIVES

### 13. salt_alternatives (Self-referencing Many-to-Many)
```sql
CREATE TABLE salt_alternatives (
    salt_id UUID NOT NULL REFERENCES salts(salt_id) ON DELETE CASCADE,
    alternative_salt_id UUID NOT NULL REFERENCES salts(salt_id) ON DELETE CASCADE,

    equivalence_type VARCHAR(50),  -- therapeutic, generic, biosimilar
    notes TEXT,

    PRIMARY KEY (salt_id, alternative_salt_id),
    CHECK (salt_id != alternative_salt_id),
    INDEX idx_salt_alternatives (salt_id),
    INDEX idx_alternative_for (alternative_salt_id)
);
```

---

## 💊 COMMERCIAL LAYER

### 14. manufacturers
Pharmaceutical companies.

```sql
CREATE TABLE manufacturers (
    manufacturer_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    manufacturer_name VARCHAR(255) NOT NULL UNIQUE,

    country VARCHAR(100),
    license_number VARCHAR(100),
    contact_info JSONB,

    is_active BOOLEAN DEFAULT true,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    INDEX idx_manufacturer_name (manufacturer_name),
    INDEX idx_manufacturer_active (is_active)
);
```

### 15. brands
Commercial products.

```sql
CREATE TABLE brands (
    brand_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_name VARCHAR(255) NOT NULL,
    manufacturer_id UUID NOT NULL REFERENCES manufacturers(manufacturer_id),

    is_discontinued BOOLEAN DEFAULT false,
    drug_type VARCHAR(50) DEFAULT 'allopathy',  -- allopathy, ayurveda, homeopathy

    -- Market info
    launch_date DATE,
    discontinuation_date DATE,

    -- ABDM Integration
    ndhm_code VARCHAR(50),

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE (brand_name, manufacturer_id),
    INDEX idx_brand_name (brand_name),
    INDEX idx_brand_manufacturer (manufacturer_id),
    INDEX idx_brand_discontinued (is_discontinued),
    FULLTEXT INDEX idx_brand_search (brand_name)
);
```

---

## 🧬 BRAND COMPOSITION

### 16. brand_compositions (Many-to-Many)
Links brands to salt strengths. Supports single-salt and combination drugs.

```sql
CREATE TABLE brand_compositions (
    composition_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id UUID NOT NULL REFERENCES brands(brand_id) ON DELETE CASCADE,
    salt_strength_id UUID NOT NULL REFERENCES salt_strengths(salt_strength_id),

    sequence INT NOT NULL DEFAULT 1,  -- Order of salts in combination

    PRIMARY KEY (brand_id, salt_strength_id),
    INDEX idx_brand_composition (brand_id),
    INDEX idx_salt_brands (salt_strength_id)
);
```

---

## 📦 PACKAGING LAYER

### 17. pack_forms
Dosage forms.

```sql
CREATE TABLE pack_forms (
    pack_form_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    form_name VARCHAR(100) NOT NULL UNIQUE,  -- Tablet, Capsule, Syrup, Injection, etc.

    route_of_administration VARCHAR(50),  -- Oral, IV, IM, Topical, etc.
    is_solid BOOLEAN,
    is_liquid BOOLEAN,
    requires_reconstitution BOOLEAN DEFAULT false,

    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_pack_form_name (form_name)
);
```

### 18. brand_packaging
Packaging details for each brand.

```sql
CREATE TABLE brand_packaging (
    brand_pack_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id UUID NOT NULL REFERENCES brands(brand_id) ON DELETE CASCADE,
    pack_form_id UUID NOT NULL REFERENCES pack_forms(pack_form_id),

    quantity INT NOT NULL,  -- Number of units
    pack_type VARCHAR(100),  -- "strip of 10 tablets", "bottle of 100ml", etc.

    -- Inventory (optional for pharmacy module)
    sku VARCHAR(100),
    barcode VARCHAR(100),

    is_primary_pack BOOLEAN DEFAULT true,

    created_at TIMESTAMP DEFAULT NOW(),

    INDEX idx_brand_packs (brand_id),
    INDEX idx_pack_form (pack_form_id),
    UNIQUE (brand_id, pack_form_id, quantity)
);
```

---

## 📋 DOSING GUIDELINES (EMR Enhancement)

### 19. dosing_guidelines
Standard dosing recommendations.

```sql
CREATE TABLE dosing_guidelines (
    dosing_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    salt_id UUID NOT NULL REFERENCES salts(salt_id) ON DELETE CASCADE,
    use_id UUID REFERENCES uses(use_id),

    -- Patient population
    age_group VARCHAR(50),  -- adult, pediatric, geriatric
    min_age_years DECIMAL(4,1),
    max_age_years DECIMAL(4,1),
    weight_based BOOLEAN DEFAULT false,

    -- Dosing
    standard_dose VARCHAR(255) NOT NULL,
    frequency VARCHAR(100),  -- "Once daily", "BID", "TID", "QID"
    route VARCHAR(50),
    duration VARCHAR(100),

    max_daily_dose VARCHAR(100),

    -- Adjustments
    renal_adjustment TEXT,
    hepatic_adjustment TEXT,

    notes TEXT,

    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_dosing_salt (salt_id),
    INDEX idx_dosing_use (use_id)
);
```

---

## 🔍 SEARCH & AUDIT (EMR Enhancement)

### 20. medicine_search_log
Track searches for analytics and autocomplete improvement.

```sql
CREATE TABLE medicine_search_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID,
    search_query VARCHAR(500),
    search_type VARCHAR(50),  -- brand, salt, indication
    results_count INT,
    selected_id UUID,

    timestamp TIMESTAMP DEFAULT NOW(),

    INDEX idx_search_timestamp (timestamp),
    INDEX idx_search_user (user_id)
);
```

### 21. prescription_audit
Track medicine prescriptions for safety monitoring.

```sql
CREATE TABLE prescription_audit (
    audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prescription_id UUID NOT NULL,
    doctor_id UUID NOT NULL,
    patient_id UUID NOT NULL,
    brand_id UUID REFERENCES brands(brand_id),
    salt_id UUID REFERENCES salts(salt_id),

    dosage VARCHAR(255),
    duration VARCHAR(100),

    -- Alerts triggered
    interaction_alerts JSONB,
    contraindication_alerts JSONB,
    allergy_alerts JSONB,

    prescribed_at TIMESTAMP DEFAULT NOW(),

    INDEX idx_audit_prescription (prescription_id),
    INDEX idx_audit_doctor (doctor_id),
    INDEX idx_audit_patient (patient_id),
    INDEX idx_audit_brand (brand_id)
);
```

---

## 📊 Summary

**Total Tables: 21**

**Categories:**
- Core Pharmaceutical: 2 tables (salts, salt_strengths)
- Classifications: 3 tables
- Clinical Safety: 6 tables (side effects, contraindications, interactions)
- Indications: 2 tables (uses)
- Alternatives: 1 table
- Commercial: 2 tables (manufacturers, brands)
- Composition: 1 table
- Packaging: 2 tables
- Dosing: 1 table
- Audit: 2 tables

**Key Features:**
✅ Normalized pharmaceutical data
✅ Clinical decision support ready
✅ Drug interaction checking
✅ Contraindication alerts
✅ ABDM/SNOMED/RxNorm integration
✅ Pregnancy/lactation safety
✅ Dosing guidelines
✅ Prescription audit trail
✅ Search analytics
✅ Multi-strength support
✅ Combination drugs support
✅ Therapeutic alternatives
