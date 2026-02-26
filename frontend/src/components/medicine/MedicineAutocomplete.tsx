'use client';

/**
 * Medicine Autocomplete Component (MD-72)
 *
 * Provides real-time autocomplete for medicine search using the
 * /api/v1/medicines/autocomplete endpoint.
 *
 * Features:
 * - Debounced search (300ms)
 * - Multi-line display: brand name, salt composition, manufacturer
 * - Loading and error states
 * - Minimum 2 characters before search
 */

import { useState, useEffect, useCallback } from 'react';
import { Autocomplete, AutocompleteOption } from '@/components/ui/autocomplete';
import { autocompleteMedicines, MedicineAutocompleteResult } from '@/lib/api/medicines-emr';

interface MedicineAutocompleteProps {
  onSelect: (medicine: {
    brandId: string;
    brandName: string;
    composition: string;
    manufacturerId: string;
    manufacturerName: string;
    dosageForm: string;
    strength: string;
  }) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
}

export default function MedicineAutocomplete({
  onSelect,
  placeholder = 'Search for medicines...',
  disabled = false,
  className,
}: MedicineAutocompleteProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [options, setOptions] = useState<AutocompleteOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedValue, setSelectedValue] = useState<string>('');

  // Store full medicine data for selected value
  const [medicineData, setMedicineData] = useState<Map<string, MedicineAutocompleteResult>>(
    new Map()
  );

  // Debounce search query (300ms)
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(searchQuery);
    }, 300);

    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Fetch autocomplete results when debounced query changes
  useEffect(() => {
    if (debouncedQuery.length < 2) {
      setOptions([]);
      setError(null);
      return;
    }

    const fetchResults = async () => {
      setLoading(true);
      setError(null);

      try {
        const response = await autocompleteMedicines(debouncedQuery);

        // Transform API results to autocomplete options
        const newMedicineData = new Map<string, MedicineAutocompleteResult>();
        const newOptions: AutocompleteOption[] = response.results.map((result) => {
          newMedicineData.set(result.brand_id, result);

          return {
            value: result.brand_id,
            label: formatMedicineLabel(result),
          };
        });

        setMedicineData(newMedicineData);
        setOptions(newOptions);
      } catch (err) {
        console.error('Autocomplete error:', err);
        setError('Failed to load medicines. Please try again.');
        setOptions([]);
      } finally {
        setLoading(false);
      }
    };

    fetchResults();
  }, [debouncedQuery]);

  // Format medicine label for display in dropdown
  const formatMedicineLabel = (medicine: MedicineAutocompleteResult): string => {
    return `${medicine.brand_name} • ${medicine.salt_composition} • by ${medicine.manufacturer_name}`;
  };

  // Handle search input change
  const handleSearchChange = useCallback((search: string) => {
    setSearchQuery(search);
  }, []);

  // Handle medicine selection
  const handleValueChange = useCallback(
    (value: string) => {
      setSelectedValue(value);

      if (value) {
        const medicine = medicineData.get(value);
        if (medicine) {
          onSelect({
            brandId: medicine.brand_id,
            brandName: medicine.brand_name,
            composition: medicine.salt_composition,
            manufacturerId: medicine.manufacturer_id,
            manufacturerName: medicine.manufacturer_name,
            dosageForm: medicine.dosage_form,
            strength: medicine.strength,
          });

          // Clear selection after emitting
          setSelectedValue('');
          setSearchQuery('');
          setOptions([]);
        }
      }
    },
    [medicineData, onSelect]
  );

  return (
    <div className={className}>
      <Autocomplete
        options={options}
        value={selectedValue}
        onValueChange={handleValueChange}
        onSearchChange={handleSearchChange}
        placeholder={placeholder}
        emptyText={
          loading
            ? 'Loading...'
            : error
            ? error
            : searchQuery.length < 2
            ? 'Type at least 2 characters to search'
            : 'No medicines found'
        }
        disabled={disabled || loading}
        className="w-full"
      />
    </div>
  );
}
