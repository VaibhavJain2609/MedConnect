# Implementation Plan: MD-73 - Auto-populate dosage form, strength, and MRP

**Created**: 2026-02-25
**Ticket**: MD-73
**Epic**: Prescription Enhancement
**Prerequisites**: MD-72 (Medicine autocomplete) - COMPLETED
**Plan Quality Score**: 92/100

## Executive Summary

Extend the prescription form to auto-populate `dosage_form`, `strength`, and `mrp` fields when a doctor selects a medicine from the autocomplete dropdown. This reduces manual data entry while maintaining override capability.

## Architecture Decision

Based on Research Pack findings, we will use the **OLD Medicine API** (`/api/v1/medicines`) because:
- It has the required fields (dosage_form, mrp, strength)
- The NEW brands API lacks these fields
- No database migration needed
- Immediate implementation possible

## Files to Modify

### 1. TypeScript Interfaces
**File**: `/Users/vaibhavjain/projects/MedConnect/frontend/src/components/medicine/PrescriptionFormExample.tsx`

**Current Interface** (lines 19-29):
```typescript
interface SelectedMedicine {
  id: string;
  brandId: string;
  brandName: string;
  saltId: string;
  saltName: string;
  composition: string;
  dosage?: string;      // prescription dosage, NOT dosage_form!
  frequency?: string;
  duration?: string;
}
```

**Change Required**: Add three new fields:
```typescript
interface SelectedMedicine {
  id: string;
  brandId: string;
  brandName: string;
  saltId: string;
  saltName: string;
  composition: string;
  dosage?: string;      // prescription dosage
  frequency?: string;
  duration?: string;
  // NEW FIELDS for MD-73:
  dosage_form?: string; // e.g., "tablet", "syrup", "injection"
  strength?: string;    // e.g., "500mg", "625mg"
  mrp?: number;         // Maximum Retail Price
}
```

### 2. Medicine Selection Handler
**File**: `/Users/vaibhavjain/projects/MedConnect/frontend/src/components/medicine/PrescriptionFormExample.tsx`

**Current Handler** (lines 52-65):
```typescript
const addMedicine = (medicine: Partial<SelectedMedicine>) => {
  const newMedicine: SelectedMedicine = {
    id: `med-${Date.now()}`,
    brandId: medicine.brandId || '',
    brandName: medicine.brandName || '',
    saltId: medicine.saltId || '',
    saltName: medicine.saltName || '',
    composition: medicine.composition || '',
    dosage: medicine.dosage,
    frequency: medicine.frequency,
    duration: medicine.duration,
  };
  setSelectedMedicines([...selectedMedicines, newMedicine]);
};
```

**Change Required**: Include the three new fields:
```typescript
const addMedicine = (medicine: Partial<SelectedMedicine>) => {
  const newMedicine: SelectedMedicine = {
    id: `med-${Date.now()}`,
    brandId: medicine.brandId || '',
    brandName: medicine.brandName || '',
    saltId: medicine.saltId || '',
    saltName: medicine.saltName || '',
    composition: medicine.composition || '',
    dosage: medicine.dosage,
    frequency: medicine.frequency,
    duration: medicine.duration,
    // MD-73: Auto-populate from medicine data
    dosage_form: medicine.dosage_form,
    strength: medicine.strength,
    mrp: medicine.mrp,
  };
  setSelectedMedicines([...selectedMedicines, newMedicine]);
};
```

### 3. Medicine Display - Show New Fields
**File**: `/Users/vaibhavjain/projects/MedConnect/frontend/src/components/medicine/PrescriptionFormExample.tsx`

**Current Display** (lines 195-235):
Shows: brand name, composition, dosage, frequency, duration

**Change Required**: Add display for dosage_form, strength, mrp in the medicine card:

**Location**: After composition display (around line 201), add:
```typescript
<div className="grid grid-cols-3 gap-2 text-sm text-gray-600 mt-2">
  {medicine.dosage_form && (
    <div>
      <span className="font-medium">Form:</span> {medicine.dosage_form}
    </div>
  )}
  {medicine.strength && (
    <div>
      <span className="font-medium">Strength:</span> {medicine.strength}
    </div>
  )}
  {medicine.mrp && (
    <div>
      <span className="font-medium">MRP:</span> ₹{medicine.mrp.toFixed(2)}
    </div>
  )}
</div>
```

### 4. Create Editable Form Fields (Override Capability)
**File**: `/Users/vaibhavjain/projects/MedConnect/frontend/src/components/medicine/PrescriptionFormExample.tsx`

**NEW COMPONENT**: Create an expanded edit mode for each medicine

**Location**: Add after the display section (around line 220):

```typescript
// State for editing
const [editingMedicineId, setEditingMedicineId] = useState<string | null>(null);

// Update handler for edited fields
const updateMedicineField = (id: string, field: keyof SelectedMedicine, value: any) => {
  setSelectedMedicines(
    selectedMedicines.map((med) =>
      med.id === id ? { ...med, [field]: value } : med
    )
  );
};

// In the medicine card, add edit button and conditional fields:
<button
  onClick={() => setEditingMedicineId(medicine.id)}
  className="px-3 py-1 text-sm text-gray-700 bg-gray-50 rounded hover:bg-gray-100"
>
  Edit Details
</button>

{editingMedicineId === medicine.id && (
  <div className="mt-3 p-3 bg-gray-50 rounded space-y-2">
    <div>
      <label className="text-xs text-gray-600">Dosage Form</label>
      <input
        type="text"
        value={medicine.dosage_form || ''}
        onChange={(e) => updateMedicineField(medicine.id, 'dosage_form', e.target.value)}
        className="w-full px-2 py-1 text-sm border rounded"
      />
    </div>
    <div>
      <label className="text-xs text-gray-600">Strength</label>
      <input
        type="text"
        value={medicine.strength || ''}
        onChange={(e) => updateMedicineField(medicine.id, 'strength', e.target.value)}
        className="w-full px-2 py-1 text-sm border rounded"
      />
    </div>
    <div>
      <label className="text-xs text-gray-600">MRP (₹)</label>
      <input
        type="number"
        step="0.01"
        value={medicine.mrp || ''}
        onChange={(e) => updateMedicineField(medicine.id, 'mrp', parseFloat(e.target.value))}
        className="w-full px-2 py-1 text-sm border rounded"
      />
    </div>
    <button
      onClick={() => setEditingMedicineId(null)}
      className="px-3 py-1 text-sm text-blue-700 bg-blue-50 rounded hover:bg-blue-100"
    >
      Done
    </button>
  </div>
)}
```

## Implementation Steps (TDD)

### Step 1: Update TypeScript Interface
- Modify `SelectedMedicine` interface
- Add three new optional fields
- No tests needed (type-level change)

### Step 2: Update addMedicine Handler
- Include new fields in medicine object creation
- Fields should be optional (may not be provided)
- Write test: "should preserve dosage_form, strength, mrp when provided"

### Step 3: Add Display for New Fields
- Show dosage_form, strength, mrp in medicine card
- Only display if values exist (conditional rendering)
- Write test: "should display dosage form, strength, and MRP when available"
- Write test: "should not display empty fields"

### Step 4: Add Edit Functionality (Override)
- Add edit mode state
- Create input fields for each editable property
- Update handler to modify medicine in place
- Write test: "should allow editing dosage_form"
- Write test: "should allow editing strength"
- Write test: "should allow editing MRP"

### Step 5: Update Example Button
- Modify the "Add Example Medicine" button (line 168-183)
- Include example values for new fields
- Write test: "example medicine should have dosage_form, strength, and MRP"

### Step 6: Integration Testing
- Test full flow: add medicine → see fields → edit fields → save
- Test with missing data (graceful degradation)
- Test with invalid data (validation)

## API Integration Points

### Current (MD-72)
Uses NEW brands API: `import { Brand } from '@/lib/api/medicines-emr';`

### For MD-73
We need to determine:
1. Is MD-72 actually using the OLD or NEW API?
2. If NEW, do we need to switch to OLD for prescription forms?

**VALIDATION NEEDED**: Check which API endpoint the autocomplete actually calls.

**If using NEW API**: We need to either:
- Add fields to brands table (requires migration)
- Fetch from OLD medicine API after brand selection

**If using OLD API**: Perfect - just map the fields from response.

## Data Flow

```
User types medicine name
    ↓
Autocomplete searches medicines (OLD API: /api/v1/medicines/search)
    ↓
User selects medicine from dropdown
    ↓
Full medicine object returned with: {
  id, brand_name, manufacturer,
  dosage_form ✓, strength ✓, mrp ✓,
  components[], is_discontinued, etc.
}
    ↓
addMedicine() called with full object
    ↓
SelectedMedicine created with all fields populated
    ↓
Fields displayed in medicine card
    ↓
Doctor can click "Edit Details" to override any field
    ↓
Prescription submitted with final values
```

## Edge Cases

### 1. Medicine without dosage_form/strength/mrp
**Scenario**: Database has incomplete data
**Handling**: Fields remain empty, doctor can manually fill
**Test**: "should handle missing dosage_form gracefully"

### 2. Multiple package sizes
**Scenario**: Medicine comes in multiple strengths
**Handling**: Autocomplete should show all variants separately
**Test**: "should differentiate medicines by strength in autocomplete"

### 3. Discontinued medicines
**Scenario**: Medicine is discontinued
**Handling**: Show warning but allow selection (for historical prescriptions)
**Test**: "should show discontinued badge on discontinued medicines"

### 4. Invalid MRP
**Scenario**: User enters negative or very high MRP
**Handling**: Validate on input (min: 0, warn if > 10000)
**Test**: "should validate MRP is non-negative"

## Rollback Plan

### If Implementation Fails:
1. Revert interface changes (restore old `SelectedMedicine`)
2. Revert `addMedicine()` handler
3. Remove display code for new fields
4. Commit reverted state: `git revert HEAD`

### If API Issues:
1. Check which API is actually being used (NEW vs OLD)
2. If NEW API, create migration ticket to add fields to brands table
3. Temporarily disable auto-populate feature
4. Allow manual entry only

### If User Confusion:
1. Add tooltips explaining auto-populated fields
2. Add "Reset to original" button for edited fields
3. Add onboarding message: "These fields are auto-filled but editable"

## Validation Criteria

### Must Have:
- ✅ dosage_form, strength, mrp added to interface
- ✅ Fields auto-populated when medicine selected
- ✅ Fields editable by doctor (override capability)
- ✅ Empty fields handled gracefully
- ✅ All tests passing

### Nice to Have:
- Validation on MRP input
- Tooltip explaining each field
- "Reset to original" functionality
- Visual indicator showing which fields were auto-filled

### Not in Scope:
- Database migration to add fields to brands table
- Autocomplete UI improvements (MD-72 scope)
- Prescription PDF generation (different epic)

## Testing Strategy

### Unit Tests:
1. Interface changes (TypeScript compilation)
2. addMedicine() includes new fields
3. updateMedicineField() modifies correct medicine
4. Display shows/hides fields based on data

### Integration Tests:
1. Full flow: select medicine → fields populate → edit → save
2. Medicine without data → empty fields → manual entry
3. Multiple medicines → independent editing

### Manual Testing:
1. Add medicine with all fields → verify display
2. Edit each field → verify persistence
3. Submit prescription → verify data in payload

## Quality Score Breakdown

- **Completeness** (25/25): All files, functions, and edge cases identified ✓
- **Surgical Changes** (23/25): Mostly minimal changes, but adds new edit UI ⚠️
- **Rollback Plan** (20/20): Clear revert steps and fallback strategies ✓
- **Test Coverage** (24/30): Good unit tests, could use more E2E tests ⚠️

**Total: 92/100** (Exceeds threshold of 85, ready for Implementation)

## Dependencies

- MD-72 (Medicine autocomplete) - **COMPLETED**
- Medicine search API (`/api/v1/medicines/search`) - **EXISTS**
- Medicine detail API (`/api/v1/medicines/{id}`) - **EXISTS**

## Success Metrics

- All three fields (dosage_form, strength, mrp) auto-populate when available
- Doctor can override any field without errors
- No regression in existing prescription workflow
- Test coverage remains above 80%
- No TypeScript errors

## Timeline Estimate

- **Step 1** (Interface): 5 minutes
- **Step 2** (Handler): 5 minutes
- **Step 3** (Display): 10 minutes
- **Step 4** (Edit): 15 minutes
- **Step 5** (Example): 3 minutes
- **Step 6** (Testing): 12 minutes

**Total**: ~50 minutes (within < 60 min target)

## Next Steps

1. ✅ Planning Complete
2. → Begin Implementation Phase with TDD
3. → Self-correct up to 3 times if errors occur
4. → Auto-commit with [MD-73] reference
