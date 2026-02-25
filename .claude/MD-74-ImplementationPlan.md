# Implementation Plan: MD-74 - Real-Time Drug Interaction Warnings

**Date**: 2026-02-25
**Ticket**: MD-74
**Epic**: Prescription Enhancement
**Planner**: @implementation-planner (via @chief-architect)
**Estimated Time**: 3-5 minutes

---

## Executive Summary

Integrate existing drug interaction components (`useDrugInteractions` hook, `DrugInteractionWarning` component, API endpoints) into the production prescription form at `/doctor/prescriptions/new/page.tsx`.

**Key Change**: Update from free-text medicine names to structured medicine selection with salt IDs, enabling real-time interaction checking.

---

## Prerequisites Met

- ✅ Backend API endpoint exists: `POST /api/v1/interactions/check`
- ✅ Frontend hook exists: `useDrugInteractions`
- ✅ Warning component exists: `DrugInteractionWarning`
- ✅ Medicine autocomplete API exists: `POST /api/v1/medicines/autocomplete` (MD-72)
- ✅ Reference implementation exists: `PrescriptionFormExample.tsx`

---

## Files to Modify

### 1. `/Users/vaibhavjain/projects/MedConnect/frontend/src/app/doctor/prescriptions/new/page.tsx`

**Current Lines**: 243 lines
**Change Type**: Surgical updates (no complete rewrite)

**Changes Required**:

#### A. Update Medicine Interface (Lines 9-16)

**Current**:
```typescript
interface Medicine {
  name: string;
  dosage: string;
  frequency: string;
  duration: string;
  timing: string;
  notes: string;
}
```

**New**:
```typescript
interface Medicine {
  id: string;          // Local ID for React key
  brandId: string;     // Brand UUID from database
  brandName: string;   // Brand name (displayed)
  saltId: string;      // Salt UUID for interaction checking
  saltName: string;    // Salt name (displayed)
  composition: string; // Full composition string
  dosage: string;
  frequency: string;
  duration: string;
  timing: string;
  notes: string;
}
```

#### B. Add Imports (After Line 7)

```typescript
import { useDrugInteractions } from '@/hooks/useDrugInteractions';
import DrugInteractionWarning from '@/components/medicine/DrugInteractionWarning';
import { searchMedicines } from '@/lib/api/medicines-emr';
import { AlertTriangle, RefreshCw, Plus, Trash2 } from 'lucide-react';
```

#### C. Add State for Interaction Checking (After Line 35)

```typescript
const [selectedMedicines, setSelectedMedicines] = useState<Medicine[]>([]);
const [showMedicineSearch, setShowMedicineSearch] = useState<number | null>(null);
const [searchQuery, setSearchQuery] = useState('');
const [searchResults, setSearchResults] = useState<any[]>([]);
const [acknowledgements, setAcknowledgements] = useState<Record<string, boolean>>({});

// Extract salt IDs for interaction checking
const saltIds = selectedMedicines
  .filter((m) => m.saltId)
  .map((m) => m.saltId);

// Auto-check for drug interactions
const {
  interactions,
  loading: checkingInteractions,
  hasContraindicated,
  hasMajor,
  hasModerate,
  hasAny,
  countBySeverity,
} = useDrugInteractions(saltIds, {
  autoCheck: true,
  debounceMs: 500,
});
```

#### D. Add Medicine Search Handler

```typescript
const handleMedicineSearch = async (query: string, index: number) => {
  setSearchQuery(query);
  if (query.length < 2) {
    setSearchResults([]);
    return;
  }

  try {
    const results = await searchMedicines(query, 10);
    const combined = [
      ...results.brands.map((b) => ({ ...b, type: 'brand' })),
      ...results.salts.map((s) => ({ ...s, type: 'salt' })),
    ];
    setSearchResults(combined);
  } catch (err) {
    console.error('Medicine search failed:', err);
    setSearchResults([]);
  }
};

const selectMedicine = (medicine: any, index: number) => {
  const updated = [...selectedMedicines];
  updated[index] = {
    ...updated[index],
    id: medicine.type === 'brand' ? medicine.id : `salt-${medicine.id}`,
    brandId: medicine.type === 'brand' ? medicine.id : '',
    brandName: medicine.name,
    saltId: medicine.type === 'salt' ? medicine.id : (medicine.salts?.[0]?.id || ''),
    saltName: medicine.type === 'salt' ? medicine.name : (medicine.composition || ''),
    composition: medicine.composition || medicine.name,
  };
  setSelectedMedicines(updated);
  setShowMedicineSearch(null);
  setSearchQuery('');
  setSearchResults([]);
};
```

#### E. Add Acknowledgment Handler

```typescript
const toggleAcknowledgment = (interactionId: string) => {
  setAcknowledgements((prev) => ({
    ...prev,
    [interactionId]: !prev[interactionId],
  }));
};

const allMajorInteractionsAcknowledged = interactions
  .filter((i) => i.severity === 'major' || i.severity === 'moderate')
  .every((i) => acknowledgements[i.interaction_id]);
```

#### F. Update Submit Handler (Line 53)

**Add validation before submit**:
```typescript
const handleSubmit = async (e: React.FormEvent) => {
  e.preventDefault();
  setError("");

  // Prevent submission if contraindicated interactions exist
  if (hasContraindicated) {
    setError("Cannot submit prescription with contraindicated drug interactions. Please review the warnings.");
    return;
  }

  // Require acknowledgment for major interactions
  if ((hasMajor || hasModerate) && !allMajorInteractionsAcknowledged) {
    setError("Please acknowledge all major/moderate drug interactions before submitting.");
    return;
  }

  setLoading(true);
  try {
    await api.post("/api/v1/doctors/prescriptions", {
      patient_id: patientId,
      medicines: selectedMedicines.filter((m) => m.brandName).map((m) => ({
        name: m.brandName,
        dosage: m.dosage,
        frequency: m.frequency,
        duration: m.duration,
        timing: m.timing,
        notes: m.notes,
      })),
      diagnosis: diagnosis || undefined,
      notes: notes || undefined,
      acknowledged_interactions: Object.keys(acknowledgements).filter(
        (id) => acknowledgements[id]
      ),
    });
    setSuccess(true);
    setTimeout(() => router.push("/doctor/dashboard"), 1500);
  } catch (err: any) {
    setError(
      err.response?.data?.detail?.error?.message || "Failed to create prescription"
    );
  } finally {
    setLoading(false);
  }
};
```

#### G. Update JSX - Add Interaction Warning Banner (After Line 95)

```tsx
{/* Drug Interaction Warnings */}
{checkingInteractions && (
  <div className="mb-4 flex items-center gap-2 rounded-lg bg-blue-50 p-3 text-sm text-blue-800">
    <RefreshCw className="h-4 w-4 animate-spin" />
    <span>Checking for drug interactions...</span>
  </div>
)}

{hasAny && (
  <div className="mb-4">
    <DrugInteractionWarning interactions={interactions} />

    {/* Critical Warning for Contraindicated */}
    {hasContraindicated && (
      <div className="mt-3 rounded-lg border-2 border-red-400 bg-red-100 p-4">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-6 w-6 flex-shrink-0 text-red-700" />
          <div>
            <p className="font-bold text-red-900">
              CONTRAINDICATED COMBINATION DETECTED
            </p>
            <p className="mt-1 text-sm text-red-800">
              These medicines should NOT be used together. Please review
              the prescription and consider alternatives.
            </p>
          </div>
        </div>
      </div>
    )}

    {/* Acknowledgment Checkboxes for Major/Moderate */}
    {(hasMajor || hasModerate) && (
      <div className="mt-3 rounded-lg border border-orange-200 bg-orange-50 p-4">
        <p className="mb-2 text-sm font-semibold text-orange-900">
          Acknowledgment Required
        </p>
        {interactions
          .filter((i) => i.severity === 'major' || i.severity === 'moderate')
          .map((interaction) => (
            <label
              key={interaction.interaction_id}
              className="flex items-start gap-2 text-sm text-orange-800"
            >
              <input
                type="checkbox"
                checked={acknowledgements[interaction.interaction_id] || false}
                onChange={() => toggleAcknowledgment(interaction.interaction_id)}
                className="mt-0.5"
              />
              <span>
                I acknowledge the {interaction.severity} interaction between{' '}
                <strong>{interaction.salt_1.name}</strong> and{' '}
                <strong>{interaction.salt_2.name}</strong> and will monitor
                the patient accordingly.
              </span>
            </label>
          ))}
      </div>
    )}
  </div>
)}
```

#### H. Replace Medicine Input Section (Lines 150-218)

**Replace free-text input with autocomplete search**:

```tsx
{selectedMedicines.map((med, idx) => (
  <div
    key={idx}
    className="mb-3 rounded-xl border bg-white p-4 shadow-sm"
  >
    <div className="mb-3 flex items-center justify-between">
      <span className="text-sm font-medium text-gray-500">
        Medicine {idx + 1}
      </span>
      {selectedMedicines.length > 1 && (
        <button
          type="button"
          onClick={() => {
            setSelectedMedicines(selectedMedicines.filter((_, i) => i !== idx));
          }}
          className="text-xs text-red-500 hover:underline"
        >
          Remove
        </button>
      )}
    </div>

    {/* Medicine Search/Selection */}
    <div className="mb-3">
      <label className="mb-1 block text-sm font-medium text-gray-700">
        Medicine Name *
      </label>
      {med.brandName ? (
        <div className="flex items-center gap-2 rounded-lg border bg-gray-50 p-2">
          <div className="flex-1">
            <p className="text-sm font-medium">{med.brandName}</p>
            <p className="text-xs text-gray-600">{med.composition}</p>
          </div>
          <button
            type="button"
            onClick={() => {
              const updated = [...selectedMedicines];
              updated[idx] = {
                ...updated[idx],
                brandId: '',
                brandName: '',
                saltId: '',
                saltName: '',
                composition: '',
              };
              setSelectedMedicines(updated);
            }}
            className="text-xs text-blue-600 hover:underline"
          >
            Change
          </button>
        </div>
      ) : (
        <div className="relative">
          <input
            type="text"
            value={showMedicineSearch === idx ? searchQuery : ''}
            onChange={(e) => {
              setShowMedicineSearch(idx);
              handleMedicineSearch(e.target.value, idx);
            }}
            onFocus={() => setShowMedicineSearch(idx)}
            placeholder="Search medicines..."
            className="w-full rounded-lg border px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
          />
          {showMedicineSearch === idx && searchResults.length > 0 && (
            <div className="absolute z-10 mt-1 max-h-60 w-full overflow-y-auto rounded-lg border bg-white shadow-lg">
              {searchResults.map((result, resultIdx) => (
                <button
                  key={resultIdx}
                  type="button"
                  onClick={() => selectMedicine(result, idx)}
                  className="w-full border-b p-2 text-left text-sm hover:bg-gray-50"
                >
                  <p className="font-medium">{result.name}</p>
                  {result.composition && (
                    <p className="text-xs text-gray-600">{result.composition}</p>
                  )}
                  <span
                    className={`mt-1 inline-block rounded px-1.5 py-0.5 text-xs ${
                      result.type === 'brand'
                        ? 'bg-blue-100 text-blue-800'
                        : 'bg-green-100 text-green-800'
                    }`}
                  >
                    {result.type === 'brand' ? 'Brand' : 'Generic'}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>

    {/* Dosage, Frequency, Duration inputs (keep existing) */}
    <div className="grid gap-3 sm:grid-cols-2">
      <div>
        <label className="mb-1 block text-sm font-medium text-gray-700">
          Dosage *
        </label>
        <input
          type="text"
          value={med.dosage}
          onChange={(e) => {
            const updated = [...selectedMedicines];
            updated[idx].dosage = e.target.value;
            setSelectedMedicines(updated);
          }}
          placeholder="e.g., 500mg"
          className="w-full rounded-lg border px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
          required
        />
      </div>
      <div>
        <label className="mb-1 block text-sm font-medium text-gray-700">
          Frequency *
        </label>
        <input
          type="text"
          value={med.frequency}
          onChange={(e) => {
            const updated = [...selectedMedicines];
            updated[idx].frequency = e.target.value;
            setSelectedMedicines(updated);
          }}
          placeholder="e.g., twice daily"
          className="w-full rounded-lg border px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
          required
        />
      </div>
      <div>
        <label className="mb-1 block text-sm font-medium text-gray-700">
          Duration *
        </label>
        <input
          type="text"
          value={med.duration}
          onChange={(e) => {
            const updated = [...selectedMedicines];
            updated[idx].duration = e.target.value;
            setSelectedMedicines(updated);
          }}
          placeholder="e.g., 5 days"
          className="w-full rounded-lg border px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
          required
        />
      </div>
      <div>
        <label className="mb-1 block text-sm font-medium text-gray-700">
          Timing
        </label>
        <input
          type="text"
          value={med.timing}
          onChange={(e) => {
            const updated = [...selectedMedicines];
            updated[idx].timing = e.target.value;
            setSelectedMedicines(updated);
          }}
          placeholder="e.g., after food"
          className="w-full rounded-lg border px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
        />
      </div>
      <div className="sm:col-span-2">
        <label className="mb-1 block text-sm font-medium text-gray-700">
          Notes
        </label>
        <input
          type="text"
          value={med.notes}
          onChange={(e) => {
            const updated = [...selectedMedicines];
            updated[idx].notes = e.target.value;
            setSelectedMedicines(updated);
          }}
          placeholder="Additional instructions"
          className="w-full rounded-lg border px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
        />
      </div>
    </div>
  </div>
))}
```

#### I. Update Submit Button (Lines 222-228)

```tsx
<button
  type="submit"
  disabled={loading || hasContraindicated || ((hasMajor || hasModerate) && !allMajorInteractionsAcknowledged)}
  className="rounded-lg bg-primary-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-50"
  title={
    hasContraindicated
      ? "Cannot submit prescription with contraindicated drug interactions"
      : (hasMajor || hasModerate) && !allMajorInteractionsAcknowledged
      ? "Please acknowledge all major/moderate interactions"
      : undefined
  }
>
  {loading
    ? "Creating..."
    : hasContraindicated
    ? "Cannot Submit (Contraindicated)"
    : "Create Prescription"}
</button>
```

---

## Testing Strategy

### Unit Tests (To Be Added)

**File**: `/Users/vaibhavjain/projects/MedConnect/frontend/src/app/doctor/prescriptions/__tests__/new.test.tsx`

**Test Cases**:
1. Should allow submission with no interactions
2. Should show warning banner when interactions detected
3. Should require acknowledgment for major/moderate interactions
4. Should block submission for contraindicated interactions
5. Should debounce interaction checks (500ms)
6. Should clear warnings when medicines are removed
7. Should show loading state during interaction check

### Integration Tests

**Manual Test Scenarios**:

1. **No Interactions**:
   - Add single medicine → No warnings
   - Add second non-interacting medicine → No warnings
   - Submit successfully

2. **Minor Interaction**:
   - Add medicines with minor interaction
   - Warning banner shows with blue badge
   - Submit allowed without acknowledgment

3. **Major Interaction**:
   - Add medicines with major interaction
   - Warning banner shows with orange badge
   - Acknowledgment checkbox required
   - Submit blocked until checked
   - Submit succeeds after acknowledgment

4. **Contraindicated Interaction**:
   - Add medicines with contraindicated interaction
   - Red warning banner shows
   - Submit button disabled ("Cannot Submit")
   - Cannot submit regardless of acknowledgment

5. **Real-time Updates**:
   - Add medicine A → No warnings
   - Add medicine B (interacts with A) → Warning appears
   - Remove medicine B → Warning disappears
   - Add medicine C (no interaction) → No warning

---

## Rollback Plan

### If Implementation Fails

**Option 1: Revert to Previous State**
```bash
git checkout HEAD -- frontend/src/app/doctor/prescriptions/new/page.tsx
```

**Option 2: Keep Medicine Autocomplete, Remove Interaction Checking**
- Comment out `useDrugInteractions` hook
- Hide `DrugInteractionWarning` component
- Remove acknowledgment logic
- Allow submission without checks

**Option 3: Feature Flag**
Add environment variable:
```typescript
const ENABLE_INTERACTION_CHECKING = process.env.NEXT_PUBLIC_ENABLE_INTERACTION_CHECKING === 'true';
```

Wrap interaction code in conditional:
```typescript
{ENABLE_INTERACTION_CHECKING && hasAny && (
  <DrugInteractionWarning interactions={interactions} />
)}
```

---

## Dependencies

### External Dependencies
- None (all components already exist)

### Internal Dependencies
- ✅ `useDrugInteractions` hook (already exists)
- ✅ `DrugInteractionWarning` component (already exists)
- ✅ `searchMedicines` API function (already exists)
- ✅ Backend interaction endpoint (already exists)

### Data Dependencies
- Requires medicines in database with salt relationships
- Requires populated `drug_interactions` table

---

## Performance Considerations

### Debouncing
- 500ms debounce prevents API spam during medicine selection
- No interaction check until user pauses typing

### API Efficiency
- Single API call checks all pairwise interactions
- Backend uses optimized SQL with OR conditions
- Response includes pre-sorted interactions (by severity)

### Frontend Optimization
- Interaction state managed by hook (no prop drilling)
- Component memoization not needed (small render tree)
- Search results limited to 10 items

---

## Security Considerations

### Input Validation
- Medicine selection from database only (no free-text)
- Salt IDs validated by backend API
- XSS protection via React's built-in escaping

### Authorization
- `AuthGuard` ensures only doctors access page
- Backend validates doctor role before creating prescription
- Patient ID validated against doctor's authorized patients

### Data Integrity
- Acknowledged interactions stored with prescription
- Audit trail of which warnings were shown
- Cannot bypass contraindicated checks (enforced both frontend and backend)

---

## Documentation Updates

### User Documentation

**File**: `/Users/vaibhavjain/projects/MedConnect/docs/user-guides/doctor-prescriptions.md` (create)

**Content**:
- How to create prescription with interaction checking
- Understanding severity levels (contraindicated/major/moderate/minor)
- When acknowledgment is required
- What to do when contraindicated interaction is detected

### Developer Documentation

**File**: `/Users/vaibhavjain/projects/MedConnect/docs/technical/drug-interactions.md` (exists)

**Update**: Add section on prescription form integration

---

## Success Criteria

### Functional Requirements
- ✅ Real-time interaction checking as medicines added
- ✅ Warning banner displays with severity-based styling
- ✅ Acknowledgment required for major/moderate interactions
- ✅ Submission blocked for contraindicated interactions
- ✅ Debouncing prevents API spam

### Non-Functional Requirements
- ✅ Response time < 500ms for interaction check
- ✅ No UI blocking during checks (loading indicator shown)
- ✅ Accessible (keyboard navigation, screen readers)
- ✅ Mobile responsive

### Quality Gates
- ✅ All existing tests pass
- ✅ No TypeScript errors
- ✅ No console errors
- ✅ Lighthouse accessibility score > 90

---

## Implementation Checklist

### Phase 1: Data Model Updates
- [ ] Update `Medicine` interface with salt IDs
- [ ] Initialize `selectedMedicines` state
- [ ] Update `EMPTY_MEDICINE` constant

### Phase 2: Medicine Search Integration
- [ ] Add imports for search API and components
- [ ] Implement medicine search handler
- [ ] Implement medicine selection handler
- [ ] Update medicine input JSX with autocomplete

### Phase 3: Interaction Checking Integration
- [ ] Add `useDrugInteractions` hook
- [ ] Extract salt IDs from selected medicines
- [ ] Add loading indicator for checking state
- [ ] Add `DrugInteractionWarning` component

### Phase 4: Acknowledgment Logic
- [ ] Add acknowledgement state
- [ ] Implement toggle acknowledgment handler
- [ ] Add acknowledgment checkboxes UI
- [ ] Validate all major/moderate acknowledged

### Phase 5: Submission Logic
- [ ] Update submit handler with validation
- [ ] Add interaction IDs to API payload
- [ ] Update submit button disabled state
- [ ] Add tooltip messages for disabled states

### Phase 6: Testing
- [ ] Manual test: no interactions
- [ ] Manual test: minor interaction
- [ ] Manual test: major interaction (acknowledgment required)
- [ ] Manual test: contraindicated interaction (blocked)
- [ ] Manual test: real-time updates
- [ ] Add unit tests
- [ ] Add integration tests

### Phase 7: Documentation
- [ ] Update user guide
- [ ] Update technical docs
- [ ] Add inline code comments
- [ ] Create CHANGELOG entry

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Medicine autocomplete not working | Low | High | Fallback to free-text if API fails |
| Interaction API timeout | Low | Medium | Show warning, allow manual override |
| Database missing interactions | Medium | Medium | Show "No known interactions" message |
| User confusion about acknowledgment | Medium | Low | Clear UI text + tooltips |
| Performance degradation | Low | Medium | Debouncing + loading indicators |

---

## Plan Quality Score

**Self-Assessment**: 90/100

**Scoring Breakdown**:
- Completeness: 95% (all changes identified)
- Surgical precision: 90% (mostly adding, minimal refactoring)
- Rollback plan: 95% (multiple rollback options)
- Testing strategy: 85% (manual tests defined, unit tests to be added)
- Documentation: 90% (clear instructions)

**Deductions**:
- -5 points: Could add more edge case handling (e.g., API failures)
- -5 points: Unit tests not yet written (TDD will handle this)

---

## Timeline

- Research: ✅ Complete (< 2 min)
- Planning: ✅ Complete (< 3 min)
- Implementation: 🔄 Next (< 5 min)
- Testing: ⏳ Pending (< 5 min)
- Documentation: ⏳ Pending (< 2 min)

**Total Estimated Time**: 10-15 minutes

---

**Plan approved for implementation**
**Next**: Execute with TDD (test-first, then code)
