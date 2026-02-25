# Drug Interactions & Alternatives - Frontend Integration

Frontend implementation for MD-18 (Drug Interactions) and MD-19 (Alternative Medicines).

## Overview

This integration provides:
- **Automatic drug interaction checking** when medicines are added to prescriptions
- **Visual warnings** with severity levels (contraindicated, major, moderate, minor)
- **Alternative medicine suggestions** with same composition
- **Reusable React components** and hooks

---

## New Files

### API Client
- `src/lib/api/medicines-emr.ts` - Extended with interaction endpoints

### Components
- `src/components/medicine/DrugInteractionWarning.tsx` - Display interactions
- `src/components/medicine/AlternativeMedicines.tsx` - Display alternatives
- `src/components/medicine/PrescriptionFormExample.tsx` - Reference implementation

### Hooks
- `src/hooks/useDrugInteractions.ts` - Auto-check interactions

---

## Quick Start

### 1. Import Components

```tsx
import { useDrugInteractions } from '@/hooks/useDrugInteractions';
import DrugInteractionWarning from '@/components/medicine/DrugInteractionWarning';
import AlternativeMedicines from '@/components/medicine/AlternativeMedicines';
```

### 2. Basic Usage - Drug Interactions

```tsx
function PrescriptionForm() {
  const [medicines, setMedicines] = useState<Medicine[]>([]);

  // Extract salt IDs from selected medicines
  const saltIds = medicines.map(m => m.saltId);

  // Auto-check for interactions
  const { interactions, loading, hasContraindicated } = useDrugInteractions(saltIds);

  return (
    <div>
      {/* Show warning if interactions detected */}
      {interactions.length > 0 && (
        <DrugInteractionWarning interactions={interactions} />
      )}

      {/* Disable submit if contraindicated */}
      <button disabled={hasContraindicated}>
        Create Prescription
      </button>
    </div>
  );
}
```

### 3. Basic Usage - Alternatives

```tsx
function MedicineCard({ medicine }) {
  return (
    <div>
      <h3>{medicine.brandName}</h3>

      {/* Show alternative brands */}
      <AlternativeMedicines
        brandId={medicine.brandId}
        brandName={medicine.brandName}
        currentComposition={medicine.composition}
        onSelect={(alternative) => {
          // Replace current medicine with alternative
          replaceMedicine(medicine.id, alternative);
        }}
      />
    </div>
  );
}
```

---

## API Reference

### useDrugInteractions Hook

```tsx
const {
  interactions,      // DrugInteraction[] - All detected interactions
  loading,           // boolean - Loading state
  error,             // string | null - Error message
  hasContraindicated,// boolean - Has contraindicated interactions
  hasMajor,          // boolean - Has major interactions
  hasModerate,       // boolean - Has moderate interactions
  hasAny,            // boolean - Has any interactions
  countBySeverity,   // Record<string, number> - Count by severity
  refresh,           // () => Promise<void> - Manual refresh
} = useDrugInteractions(
  saltIds,           // string[] - Array of salt IDs
  {
    autoCheck: true, // Auto-check on saltIds change
    debounceMs: 300, // Debounce delay
  }
);
```

### DrugInteractionWarning Component

```tsx
<DrugInteractionWarning
  interactions={interactions}  // DrugInteraction[]
  className="mb-4"            // Optional CSS classes
/>
```

**Severity Levels:**
- 🔴 **Contraindicated** - Red border, ban icon
- 🟠 **Major** - Orange border, alert triangle
- 🟡 **Moderate** - Yellow border, alert circle
- 🔵 **Minor** - Blue border, info icon

### AlternativeMedicines Component

```tsx
<AlternativeMedicines
  brandId="uuid"
  brandName="Current Medicine"
  currentComposition="Paracetamol (500mg)"
  onSelect={(alternative) => {
    console.log('Selected:', alternative);
  }}
  className="mt-4"
/>
```

**Features:**
- Shows all brands with exact same composition
- Highlights discontinued medicines
- Optional `onSelect` callback for replacement
- Loading and error states built-in

---

## API Functions

### Check Drug Interactions

```ts
import { checkDrugInteractions } from '@/lib/api/medicines-emr';

const interactions = await checkDrugInteractions([
  'salt-paracetamol-id',
  'salt-warfarin-id',
]);

// Returns: DrugInteraction[]
```

### Get Salt Interactions

```ts
import { getSaltInteractions } from '@/lib/api/medicines-emr';

const interactions = await getSaltInteractions(
  'salt-aspirin-id',
  'major' // Optional: filter by severity
);
```

### Get Brand Alternatives

```ts
import { getBrandAlternatives } from '@/lib/api/medicines-emr';

const alternatives = await getBrandAlternatives('brand-uuid');

// Returns: Brand[] with same composition
```

---

## Integration Patterns

### Pattern 1: Real-time Checking (Recommended)

Auto-check as medicines are added:

```tsx
function PrescriptionForm() {
  const [medicines, setMedicines] = useState([]);
  const saltIds = medicines.map(m => m.saltId);

  const { interactions, hasContraindicated } = useDrugInteractions(saltIds, {
    autoCheck: true,
    debounceMs: 500, // Wait 500ms after last change
  });

  // Warn user immediately
  useEffect(() => {
    if (hasContraindicated) {
      alert('CONTRAINDICATED: Please review prescription!');
    }
  }, [hasContraindicated]);
}
```

### Pattern 2: Manual Checking

Check only when user requests:

```tsx
function PrescriptionForm() {
  const saltIds = medicines.map(m => m.saltId);

  const { interactions, refresh } = useDrugInteractions(saltIds, {
    autoCheck: false, // Disable auto-check
  });

  return (
    <button onClick={refresh}>
      Check for Interactions
    </button>
  );
}
```

### Pattern 3: Alternative Suggestion

Show alternatives when interaction detected:

```tsx
function MedicineList() {
  const { interactions } = useDrugInteractions(saltIds);

  return medicines.map(medicine => {
    // Check if THIS medicine has interactions
    const hasInteraction = interactions.some(int =>
      int.salt_1.id === medicine.saltId || int.salt_2.id === medicine.saltId
    );

    return (
      <div>
        <MedicineCard medicine={medicine} />

        {/* Show alternatives if involved in interaction */}
        {hasInteraction && (
          <AlternativeMedicines
            brandId={medicine.brandId}
            // ... other props
          />
        )}
      </div>
    );
  });
}
```

---

## TypeScript Types

```ts
interface DrugInteraction {
  interaction_id: string;
  salt_1: {
    id: string;
    name: string;
  };
  salt_2: {
    id: string;
    name: string;
  };
  severity: 'minor' | 'moderate' | 'major' | 'contraindicated';
  effect: string;
  mechanism?: string;
  management?: string;
  evidence_level?: 'theoretical' | 'case-report' | 'study-based';
}

interface Brand {
  brand_id: string;
  brand_name: string;
  manufacturer?: Manufacturer;
  compositions: BrandComposition[];
  salt_composition: string;
  is_discontinued: boolean;
  // ... other fields
}
```

---

## Styling

Components use Tailwind CSS with these color schemes:

### Interaction Severities

| Severity | Background | Border | Text |
|----------|------------|--------|------|
| Contraindicated | `bg-red-50` | `border-red-200` | `text-red-900` |
| Major | `bg-orange-50` | `border-orange-200` | `text-orange-900` |
| Moderate | `bg-yellow-50` | `border-yellow-200` | `text-yellow-900` |
| Minor | `bg-blue-50` | `border-blue-200` | `text-blue-900` |

### Alternatives

- Active: `bg-green-50` with `border-green-200`
- Discontinued: `bg-gray-50` with `border-gray-300`

---

## Example: Complete Prescription Flow

See `src/components/medicine/PrescriptionFormExample.tsx` for full implementation showing:

1. ✅ Add/remove medicines
2. ✅ Auto-check interactions with debounce
3. ✅ Display interaction warnings
4. ✅ Show alternatives on demand
5. ✅ Replace medicine with alternative
6. ✅ Block submission if contraindicated
7. ✅ Show severity counts

---

## Error Handling

```tsx
const { interactions, error } = useDrugInteractions(saltIds);

if (error) {
  return <ErrorMessage>Failed to check interactions: {error}</ErrorMessage>;
}
```

All API functions throw errors that can be caught:

```tsx
try {
  const interactions = await checkDrugInteractions(saltIds);
} catch (error) {
  console.error('Interaction check failed:', error);
  // Show error to user
}
```

---

## Performance Optimization

### 1. Debouncing

```tsx
useDrugInteractions(saltIds, {
  debounceMs: 500, // Wait 500ms after last change
});
```

Prevents excessive API calls when medicines are added/removed rapidly.

### 2. Conditional Rendering

```tsx
{interactions.length > 0 && <DrugInteractionWarning interactions={interactions} />}
```

Only render warning component when needed.

### 3. Lazy Loading Alternatives

```tsx
const [showAlternatives, setShowAlternatives] = useState(false);

// Only load when user clicks "Show Alternatives"
{showAlternatives && <AlternativeMedicines ... />}
```

---

## Accessibility

Components include:
- ✅ Semantic HTML structure
- ✅ Color + icon for severity (not color alone)
- ✅ Descriptive labels
- ✅ Keyboard navigation support
- ✅ Screen reader friendly

---

## Testing

### Unit Tests

```tsx
import { render, screen } from '@testing-library/react';
import DrugInteractionWarning from '@/components/medicine/DrugInteractionWarning';

test('displays contraindicated interaction prominently', () => {
  const interactions = [{
    severity: 'contraindicated',
    salt_1: { name: 'Aspirin' },
    salt_2: { name: 'Warfarin' },
    // ...
  }];

  render(<DrugInteractionWarning interactions={interactions} />);

  expect(screen.getByText(/CONTRAINDICATED/i)).toBeInTheDocument();
});
```

### Integration Tests

```tsx
import { renderHook, waitFor } from '@testing-library/react';
import { useDrugInteractions } from '@/hooks/useDrugInteractions';

test('checks interactions automatically', async () => {
  const { result } = renderHook(() =>
    useDrugInteractions(['salt1', 'salt2'])
  );

  await waitFor(() => {
    expect(result.current.loading).toBe(false);
  });

  expect(result.current.interactions).toBeDefined();
});
```

---

## Troubleshooting

### Interactions not loading?

1. Check backend is running: `http://localhost:8000/docs`
2. Verify API_BASE_URL in `medicines-emr.ts`
3. Check browser console for errors
4. Ensure sample data is populated: `python scripts/populate_sample_interactions.py`

### Alternatives not showing?

1. Verify brand exists in database
2. Check composition matches exactly (same salts + strengths)
3. Look for network errors in DevTools

### TypeScript errors?

Run `npm run type-check` to see all type errors.

---

## Next Steps

1. ✅ Integrate into actual prescription form
2. ✅ Add to medicine detail pages
3. ✅ Customize styling to match design system
4. 🔲 Add unit tests
5. 🔲 Add E2E tests
6. 🔲 Monitor API performance

---

## Support

- **Backend API Docs**: http://localhost:8000/docs
- **Implementation Guide**: `/IMPLEMENTATION_MD18_MD19_MD29.md`
- **Example Component**: `src/components/medicine/PrescriptionFormExample.tsx`

---

**Built for:** MedConnect Healthcare Platform
**Jira Tickets:** MD-18, MD-19
**Last Updated:** 2026-02-25
