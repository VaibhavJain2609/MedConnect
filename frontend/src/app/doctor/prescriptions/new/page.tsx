"use client";

/**
 * MD-74: Enhanced Prescription Form with Drug Interaction Warnings
 *
 * Features:
 * - Medicine autocomplete (MD-72 integration)
 * - Real-time drug interaction checking
 * - Severity-based warnings (contraindicated/major/moderate/minor)
 * - Acknowledgment for major/moderate interactions
 * - Submission blocking for contraindicated interactions
 */

import { useState, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import api from "@/lib/api";
import { Navbar } from "@/components/layout/navbar";
import { AuthGuard } from "@/components/layout/auth-guard";
import { useDrugInteractions } from '@/hooks/useDrugInteractions';
import DrugInteractionWarning from '@/components/medicine/DrugInteractionWarning';
import { searchMedicines } from '@/lib/api/medicines-emr';
import { AlertTriangle, RefreshCw, Trash2 } from 'lucide-react';

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

const EMPTY_MEDICINE: Medicine = {
  id: "",
  brandId: "",
  brandName: "",
  saltId: "",
  saltName: "",
  composition: "",
  dosage: "",
  frequency: "",
  duration: "",
  timing: "",
  notes: "",
};

export default function NewPrescriptionPage() {
  const router = useRouter();
  const [patientId, setPatientId] = useState("");
  const [diagnosis, setDiagnosis] = useState("");
  const [notes, setNotes] = useState("");
  const [selectedMedicines, setSelectedMedicines] = useState<Medicine[]>([
    { ...EMPTY_MEDICINE, id: `med-${Date.now()}` }
  ]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  // Medicine search state
  const [showMedicineSearch, setShowMedicineSearch] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);

  // Interaction acknowledgment state
  const [acknowledgements, setAcknowledgements] = useState<Record<string, boolean>>({});

  // Extract salt IDs for interaction checking
  const saltIds = selectedMedicines
    .filter((m) => m.saltId && m.saltId !== '')
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

  // Medicine search handler with debounce
  const handleMedicineSearch = useCallback(async (query: string, index: number) => {
    setSearchQuery(query);
    setShowMedicineSearch(index);

    if (query.length < 2) {
      setSearchResults([]);
      return;
    }

    setSearchLoading(true);
    try {
      const results = await searchMedicines(query, 10);
      const combined = [
        ...results.brands.map((b: any) => ({ ...b, type: 'brand' })),
        ...results.salts.map((s: any) => ({ ...s, type: 'salt' })),
      ];
      setSearchResults(combined);
    } catch (err) {
      console.error('Medicine search failed:', err);
      setSearchResults([]);
    } finally {
      setSearchLoading(false);
    }
  }, []);

  // Medicine selection handler
  const selectMedicine = useCallback((medicine: any, index: number) => {
    const updated = [...selectedMedicines];

    // Extract salt ID based on medicine type
    let saltId = '';
    let saltName = '';

    if (medicine.type === 'salt') {
      saltId = medicine.id;
      saltName = medicine.name;
    } else if (medicine.type === 'brand') {
      // For brands, extract first salt from composition
      if (medicine.compositions && medicine.compositions.length > 0) {
        saltId = medicine.compositions[0].salt_id || '';
        saltName = medicine.compositions[0].salt_name || '';
      }
    }

    updated[index] = {
      ...updated[index],
      brandId: medicine.type === 'brand' ? medicine.id : '',
      brandName: medicine.name,
      saltId: saltId,
      saltName: saltName,
      composition: medicine.composition || medicine.name,
    };

    setSelectedMedicines(updated);
    setShowMedicineSearch(null);
    setSearchQuery('');
    setSearchResults([]);
  }, [selectedMedicines]);

  // Update medicine field
  const updateMedicine = (index: number, field: keyof Medicine, value: string) => {
    const updated = [...selectedMedicines];
    updated[index] = { ...updated[index], [field]: value };
    setSelectedMedicines(updated);
  };

  // Add new medicine
  const addMedicine = () => {
    setSelectedMedicines([...selectedMedicines, {
      ...EMPTY_MEDICINE,
      id: `med-${Date.now()}`
    }]);
  };

  // Remove medicine
  const removeMedicine = (index: number) => {
    if (selectedMedicines.length > 1) {
      setSelectedMedicines(selectedMedicines.filter((_, i) => i !== index));
    }
  };

  // Clear medicine selection
  const clearMedicine = (index: number) => {
    const updated = [...selectedMedicines];
    updated[index] = {
      ...updated[index],
      brandId: '',
      brandName: '',
      saltId: '',
      saltName: '',
      composition: '',
    };
    setSelectedMedicines(updated);
  };

  // Toggle interaction acknowledgment
  const toggleAcknowledgment = (interactionId: string) => {
    setAcknowledgements((prev) => ({
      ...prev,
      [interactionId]: !prev[interactionId],
    }));
  };

  // Check if all major/moderate interactions are acknowledged
  const allMajorInteractionsAcknowledged = interactions
    .filter((i) => i.severity === 'major' || i.severity === 'moderate')
    .every((i) => acknowledgements[i.interaction_id]);

  // Handle form submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    // Validate medicine selection
    const validMedicines = selectedMedicines.filter((m) => m.brandName && m.dosage && m.frequency && m.duration);
    if (validMedicines.length === 0) {
      setError("Please add at least one medicine with all required fields.");
      return;
    }

    // Prevent submission if contraindicated interactions exist
    if (hasContraindicated) {
      setError("Cannot submit prescription with contraindicated drug interactions. Please review the warnings and remove conflicting medicines.");
      return;
    }

    // Require acknowledgment for major/moderate interactions
    if ((hasMajor || hasModerate) && !allMajorInteractionsAcknowledged) {
      setError("Please acknowledge all major/moderate drug interactions before submitting.");
      return;
    }

    setLoading(true);
    try {
      await api.post("/api/v1/doctors/prescriptions", {
        patient_id: patientId,
        medicines: validMedicines.map((m) => ({
          name: m.brandName,
          dosage: m.dosage,
          frequency: m.frequency,
          duration: m.duration,
          timing: m.timing || undefined,
          notes: m.notes || undefined,
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

  // Close search dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = () => {
      setShowMedicineSearch(null);
      setSearchResults([]);
    };

    if (showMedicineSearch !== null) {
      document.addEventListener('click', handleClickOutside);
      return () => document.removeEventListener('click', handleClickOutside);
    }
  }, [showMedicineSearch]);

  return (
    <AuthGuard requiredRole="doctor">
      <Navbar />
      <main className="mx-auto max-w-4xl px-4 py-6">
        <h1 className="mb-6 text-2xl font-bold">
          Create Prescription
          {checkingInteractions && (
            <span className="ml-3 text-sm text-gray-500 font-normal">
              <RefreshCw className="inline w-4 h-4 animate-spin mr-1" />
              Checking interactions...
            </span>
          )}
        </h1>

        {success ? (
          <div className="rounded-xl border bg-green-50 p-6 text-center">
            <p className="text-lg font-medium text-green-800">Prescription created!</p>
            <p className="mt-1 text-sm text-green-600">
              The patient can now see this in their timeline.
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="rounded-xl border bg-white p-6 shadow-sm">
              {error && (
                <div className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">
                  {error}
                </div>
              )}

              {/* Drug Interaction Warnings */}
              {hasAny && (
                <div className="mb-6">
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
                            the prescription and consider alternatives or remove conflicting medicines.
                          </p>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Acknowledgment Checkboxes for Major/Moderate */}
                  {(hasMajor || hasModerate) && !hasContraindicated && (
                    <div className="mt-3 rounded-lg border border-orange-200 bg-orange-50 p-4">
                      <p className="mb-3 text-sm font-semibold text-orange-900">
                        Acknowledgment Required
                      </p>
                      <div className="space-y-2">
                        {interactions
                          .filter((i) => i.severity === 'major' || i.severity === 'moderate')
                          .map((interaction) => (
                            <label
                              key={interaction.interaction_id}
                              className="flex items-start gap-2 cursor-pointer"
                            >
                              <input
                                type="checkbox"
                                checked={acknowledgements[interaction.interaction_id] || false}
                                onChange={() => toggleAcknowledgment(interaction.interaction_id)}
                                className="mt-1 h-4 w-4 rounded border-gray-300 text-orange-600 focus:ring-orange-500"
                              />
                              <span className="text-sm text-orange-800">
                                I acknowledge the <strong>{interaction.severity}</strong> interaction between{' '}
                                <strong>{interaction.salt_1.name}</strong> and{' '}
                                <strong>{interaction.salt_2.name}</strong> and will monitor
                                the patient accordingly.
                              </span>
                            </label>
                          ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              <div className="mb-4">
                <label className="mb-1 block text-sm font-medium text-gray-700">
                  Patient ID
                </label>
                <input
                  type="text"
                  value={patientId}
                  onChange={(e) => setPatientId(e.target.value)}
                  placeholder="Patient UUID"
                  className="w-full rounded-lg border px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                  required
                />
              </div>

              <div className="mb-4">
                <label className="mb-1 block text-sm font-medium text-gray-700">
                  Diagnosis
                </label>
                <input
                  type="text"
                  value={diagnosis}
                  onChange={(e) => setDiagnosis(e.target.value)}
                  placeholder="e.g., Upper respiratory infection"
                  className="w-full rounded-lg border px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                />
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">
                  Notes
                </label>
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  rows={2}
                  placeholder="Additional instructions..."
                  className="w-full rounded-lg border px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                />
              </div>
            </div>

            <div>
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-lg font-semibold">
                  Medicines ({selectedMedicines.filter(m => m.brandName).length})
                  {hasAny && (
                    <span className="ml-2 text-xs">
                      {Object.entries(countBySeverity).map(([severity, count]) => (
                        <span
                          key={severity}
                          className={`ml-1 px-2 py-0.5 rounded font-medium ${
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
                    </span>
                  )}
                </h2>
                <button
                  type="button"
                  onClick={addMedicine}
                  className="text-sm text-primary-600 hover:underline"
                >
                  + Add Medicine
                </button>
              </div>

              {selectedMedicines.map((med, idx) => (
                <div
                  key={med.id}
                  className={`mb-3 rounded-xl border p-4 shadow-sm ${
                    hasMajor || hasContraindicated
                      ? 'border-red-200 bg-red-50'
                      : 'border-gray-200 bg-white'
                  }`}
                >
                  <div className="mb-3 flex items-center justify-between">
                    <span className="text-sm font-medium text-gray-500">
                      Medicine {idx + 1}
                    </span>
                    {selectedMedicines.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeMedicine(idx)}
                        className="flex items-center gap-1 text-xs text-red-500 hover:underline"
                      >
                        <Trash2 className="h-3 w-3" />
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
                      <div className="flex items-center gap-2 rounded-lg border bg-gray-50 p-3">
                        <div className="flex-1">
                          <p className="text-sm font-medium">{med.brandName}</p>
                          <p className="text-xs text-gray-600">{med.composition}</p>
                        </div>
                        <button
                          type="button"
                          onClick={() => clearMedicine(idx)}
                          className="text-xs text-blue-600 hover:underline"
                        >
                          Change
                        </button>
                      </div>
                    ) : (
                      <div className="relative" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="text"
                          value={showMedicineSearch === idx ? searchQuery : ''}
                          onChange={(e) => handleMedicineSearch(e.target.value, idx)}
                          onFocus={() => setShowMedicineSearch(idx)}
                          placeholder="Search medicines by name..."
                          className="w-full rounded-lg border px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                        />
                        {searchLoading && showMedicineSearch === idx && (
                          <div className="absolute right-3 top-2.5">
                            <RefreshCw className="h-4 w-4 animate-spin text-gray-400" />
                          </div>
                        )}
                        {showMedicineSearch === idx && searchResults.length > 0 && (
                          <div className="absolute z-10 mt-1 max-h-60 w-full overflow-y-auto rounded-lg border bg-white shadow-lg">
                            {searchResults.map((result, resultIdx) => (
                              <button
                                key={resultIdx}
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  selectMedicine(result, idx);
                                }}
                                className="w-full border-b p-3 text-left text-sm hover:bg-gray-50 last:border-b-0"
                              >
                                <p className="font-medium">{result.name}</p>
                                {result.composition && (
                                  <p className="text-xs text-gray-600 mt-0.5">{result.composition}</p>
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
                        {showMedicineSearch === idx && searchQuery.length >= 2 && searchResults.length === 0 && !searchLoading && (
                          <div className="absolute z-10 mt-1 w-full rounded-lg border bg-white p-3 text-sm text-gray-500 shadow-lg">
                            No medicines found
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Dosage, Frequency, Duration inputs */}
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div>
                      <label className="mb-1 block text-sm font-medium text-gray-700">
                        Dosage *
                      </label>
                      <input
                        type="text"
                        value={med.dosage}
                        onChange={(e) => updateMedicine(idx, "dosage", e.target.value)}
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
                        onChange={(e) => updateMedicine(idx, "frequency", e.target.value)}
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
                        onChange={(e) => updateMedicine(idx, "duration", e.target.value)}
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
                        onChange={(e) => updateMedicine(idx, "timing", e.target.value)}
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
                        onChange={(e) => updateMedicine(idx, "notes", e.target.value)}
                        placeholder="Additional instructions"
                        className="w-full rounded-lg border px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <div className="flex gap-3">
              <button
                type="submit"
                disabled={
                  loading ||
                  hasContraindicated ||
                  ((hasMajor || hasModerate) && !allMajorInteractionsAcknowledged)
                }
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
              <button
                type="button"
                onClick={() => router.back()}
                className="rounded-lg border px-6 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
            </div>

            {/* Info Box */}
            <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm">
              <p className="font-semibold text-blue-900 mb-2">Drug Interaction Checking:</p>
              <ul className="space-y-1 text-blue-800 list-disc list-inside">
                <li>Interactions are checked automatically as you select medicines</li>
                <li>Search for medicines by brand name or generic (salt) name</li>
                <li>Major/moderate interactions require acknowledgment before submission</li>
                <li>Contraindicated combinations cannot be submitted</li>
              </ul>
            </div>
          </form>
        )}
      </main>
    </AuthGuard>
  );
}
