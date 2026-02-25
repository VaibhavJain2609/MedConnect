'use client';

/**
 * Example component demonstrating integration of:
 * - Drug interaction checking (MD-18)
 * - Alternative medicine suggestions (MD-19)
 *
 * This is a reference implementation for prescription forms.
 * Adapt to your actual prescription workflow.
 */

import { useState } from 'react';
import { useDrugInteractions } from '@/hooks/useDrugInteractions';
import DrugInteractionWarning from './DrugInteractionWarning';
import AlternativeMedicines from './AlternativeMedicines';
import { Brand } from '@/lib/api/medicines-emr';
import { AlertTriangle, Plus, Trash2, RefreshCw } from 'lucide-react';

interface SelectedMedicine {
  id: string;
  brandId: string;
  brandName: string;
  saltId: string;
  saltName: string;
  composition: string;
  dosage?: string;
  frequency?: string;
  duration?: string;
}

export default function PrescriptionFormExample() {
  const [selectedMedicines, setSelectedMedicines] = useState<SelectedMedicine[]>([]);
  const [showAlternativesFor, setShowAlternativesFor] = useState<string | null>(null);

  // Extract salt IDs from selected medicines
  const saltIds = selectedMedicines.map((med) => med.saltId);

  // Auto-check for drug interactions
  const {
    interactions,
    loading: checkingInteractions,
    hasContraindicated,
    hasMajor,
    hasAny,
    countBySeverity,
  } = useDrugInteractions(saltIds, {
    autoCheck: true,
    debounceMs: 500,
  });

  // Handler: Add medicine to prescription
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

  // Handler: Remove medicine from prescription
  const removeMedicine = (id: string) => {
    setSelectedMedicines(selectedMedicines.filter((med) => med.id !== id));
    if (showAlternativesFor === id) {
      setShowAlternativesFor(null);
    }
  };

  // Handler: Replace medicine with alternative
  const replaceWithAlternative = (oldMedicineId: string, alternative: Brand) => {
    setSelectedMedicines(
      selectedMedicines.map((med) =>
        med.id === oldMedicineId
          ? {
              ...med,
              brandId: alternative.brand_id,
              brandName: alternative.brand_name,
              composition: alternative.salt_composition,
            }
          : med
      )
    );
    setShowAlternativesFor(null);
  };

  // Handler: Toggle alternatives view
  const toggleAlternatives = (medicineId: string) => {
    setShowAlternativesFor(showAlternativesFor === medicineId ? null : medicineId);
  };

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-6">
          Create Prescription
          {checkingInteractions && (
            <span className="ml-3 text-sm text-gray-500 font-normal">
              <RefreshCw className="inline w-4 h-4 animate-spin mr-1" />
              Checking interactions...
            </span>
          )}
        </h2>

        {/* Interaction Warning - Shown at top if any detected */}
        {hasAny && (
          <div className="mb-6">
            <DrugInteractionWarning interactions={interactions} />

            {/* Critical warning for contraindicated */}
            {hasContraindicated && (
              <div className="mt-3 p-4 bg-red-100 border-2 border-red-400 rounded-lg">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-6 h-6 text-red-700 flex-shrink-0" />
                  <div>
                    <p className="font-bold text-red-900">
                      CONTRAINDICATED COMBINATION DETECTED
                    </p>
                    <p className="text-sm text-red-800 mt-1">
                      These medicines should NOT be used together. Please review
                      the prescription and consider alternatives.
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Selected Medicines List */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-gray-900">
              Medicines ({selectedMedicines.length})
            </h3>
            {hasAny && (
              <div className="flex gap-2 text-xs">
                {Object.entries(countBySeverity).map(([severity, count]) => (
                  <span
                    key={severity}
                    className={`px-2 py-1 rounded font-medium ${
                      severity === 'contraindicated'
                        ? 'bg-red-100 text-red-800'
                        : severity === 'major'
                        ? 'bg-orange-100 text-orange-800'
                        : severity === 'moderate'
                        ? 'bg-yellow-100 text-yellow-800'
                        : 'bg-blue-100 text-blue-800'
                    }`}
                  >
                    {count} {severity}
                  </span>
                ))}
              </div>
            )}
          </div>

          {selectedMedicines.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <p>No medicines added yet</p>
              <button
                onClick={() =>
                  addMedicine({
                    brandName: 'Paracetamol 500mg (Example)',
                    saltId: 'salt-paracetamol',
                    saltName: 'Paracetamol',
                    composition: 'Paracetamol (500mg)',
                    brandId: 'brand-123',
                    dosage: '1 tablet',
                    frequency: 'Three times daily',
                    duration: '5 days',
                  })
                }
                className="mt-3 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2 mx-auto"
              >
                <Plus className="w-4 h-4" />
                Add Example Medicine
              </button>
            </div>
          ) : (
            selectedMedicines.map((medicine) => (
              <div
                key={medicine.id}
                className={`border rounded-lg p-4 ${
                  hasMajor || hasContraindicated
                    ? 'border-red-200 bg-red-50'
                    : 'border-gray-200 bg-white'
                }`}
              >
                {/* Medicine Header */}
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div className="flex-1">
                    <h4 className="font-semibold text-gray-900">
                      {medicine.brandName}
                    </h4>
                    <p className="text-sm text-gray-600">{medicine.composition}</p>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => toggleAlternatives(medicine.id)}
                      className="px-3 py-1 text-sm text-blue-700 bg-blue-50 rounded hover:bg-blue-100"
                    >
                      {showAlternativesFor === medicine.id
                        ? 'Hide'
                        : 'Alternatives'}
                    </button>
                    <button
                      onClick={() => removeMedicine(medicine.id)}
                      className="p-1 text-red-600 hover:bg-red-50 rounded"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* Dosage Info */}
                <div className="grid grid-cols-3 gap-3 text-sm mb-3">
                  <div>
                    <span className="text-gray-600">Dosage:</span>
                    <span className="ml-1 font-medium">{medicine.dosage}</span>
                  </div>
                  <div>
                    <span className="text-gray-600">Frequency:</span>
                    <span className="ml-1 font-medium">{medicine.frequency}</span>
                  </div>
                  <div>
                    <span className="text-gray-600">Duration:</span>
                    <span className="ml-1 font-medium">{medicine.duration}</span>
                  </div>
                </div>

                {/* Alternatives Section */}
                {showAlternativesFor === medicine.id && (
                  <div className="pt-3 border-t border-gray-200">
                    <AlternativeMedicines
                      brandId={medicine.brandId}
                      brandName={medicine.brandName}
                      currentComposition={medicine.composition}
                      onSelect={(alt) => replaceWithAlternative(medicine.id, alt)}
                    />
                  </div>
                )}
              </div>
            ))
          )}
        </div>

        {/* Action Buttons */}
        {selectedMedicines.length > 0 && (
          <div className="mt-6 pt-6 border-t border-gray-200 flex justify-between items-center">
            <button
              onClick={() => setSelectedMedicines([])}
              className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
            >
              Clear All
            </button>

            <div className="flex gap-3">
              <button
                className="px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Save Draft
              </button>
              <button
                disabled={hasContraindicated}
                className={`px-6 py-2 rounded-lg font-medium ${
                  hasContraindicated
                    ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                    : 'bg-blue-600 text-white hover:bg-blue-700'
                }`}
                title={
                  hasContraindicated
                    ? 'Cannot submit prescription with contraindicated medicines'
                    : undefined
                }
              >
                {hasContraindicated ? 'Cannot Submit' : 'Create Prescription'}
              </button>
            </div>
          </div>
        )}

        {/* Info Box */}
        <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-lg text-sm">
          <p className="font-semibold text-blue-900 mb-2">How it works:</p>
          <ul className="text-blue-800 space-y-1 list-disc list-inside">
            <li>Drug interactions are checked automatically as you add medicines</li>
            <li>Click "Alternatives" to see brands with the same composition</li>
            <li>Contraindicated combinations cannot be submitted</li>
            <li>Major interactions require acknowledgment and close monitoring</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
