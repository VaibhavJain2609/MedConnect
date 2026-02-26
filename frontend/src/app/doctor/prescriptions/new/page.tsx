"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import api from "@/lib/api";
import { Navbar } from "@/components/layout/navbar";
import { AuthGuard } from "@/components/layout/auth-guard";
import MedicineAutocomplete from "@/components/medicine/MedicineAutocomplete";

interface Medicine {
  name: string;
  dosage: string;
  meals: string[];  // Changed from frequency to meals
  duration: string;
  foodRelation: string;  // New field
  notes: string;
}

const EMPTY_MEDICINE: Medicine = {
  name: "",
  dosage: "",
  meals: [],
  duration: "5",  // Default 5 days
  foodRelation: "after_food",  // Default
  notes: "",
};

const MEAL_OPTIONS = [
  { id: "breakfast", label: "Breakfast", icon: "🌅" },
  { id: "lunch", label: "Lunch", icon: "☀️" },
  { id: "afternoon_tea", label: "Tea", icon: "☕" },
  { id: "dinner", label: "Dinner", icon: "🌙" },
  { id: "bedtime", label: "Bedtime", icon: "😴" },
];

const DURATION_OPTIONS = [
  { value: "3", label: "3 days" },
  { value: "5", label: "5 days" },
  { value: "7", label: "7 days" },
  { value: "10", label: "10 days" },
  { value: "14", label: "14 days" },
  { value: "21", label: "21 days" },
  { value: "30", label: "1 month" },
  { value: "60", label: "2 months" },
  { value: "90", label: "3 months" },
];

const FOOD_RELATION_OPTIONS = [
  { value: "empty_stomach", label: "Empty stomach", icon: "🚫" },
  { value: "with_food", label: "With food", icon: "🍽️" },
  { value: "after_food", label: "After food", icon: "✅" },
  { value: "anytime", label: "Anytime", icon: "⏰" },
];

export default function NewPrescriptionPage() {
  const router = useRouter();
  const [patientId, setPatientId] = useState("");
  const [diagnosis, setDiagnosis] = useState("");
  const [notes, setNotes] = useState("");
  const [medicines, setMedicines] = useState<Medicine[]>([{ ...EMPTY_MEDICINE }]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const updateMedicine = (index: number, field: keyof Medicine, value: any) => {
    const updated = [...medicines];
    updated[index] = { ...updated[index], [field]: value };
    setMedicines(updated);
  };

  const toggleMeal = (index: number, mealId: string) => {
    const currentMeals = medicines[index].meals;
    const updated = currentMeals.includes(mealId)
      ? currentMeals.filter((m) => m !== mealId)
      : [...currentMeals, mealId];
    updateMedicine(index, "meals", updated);
  };

  const addMedicine = () => {
    setMedicines([...medicines, { ...EMPTY_MEDICINE }]);
  };

  const removeMedicine = (index: number) => {
    if (medicines.length > 1) {
      setMedicines(medicines.filter((_, i) => i !== index));
    }
  };

  const handleMedicineSelect = (
    index: number,
    medicine: {
      brandId: string;
      brandName: string;
      composition: string;
      manufacturerId: string;
      manufacturerName: string;
      dosageForm: string;
      strength: string;
    }
  ) => {
    // Auto-fill medicine name and dosage
    updateMedicine(index, "name", medicine.brandName);
    updateMedicine(index, "dosage", `${medicine.dosageForm} - ${medicine.strength}`.trim());
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    // Convert meals array to frequency string
    const medicinesFormatted = medicines
      .filter((m) => m.name)
      .map((m) => ({
        name: m.name,
        dosage: m.dosage,
        frequency: m.meals.length > 0
          ? `${m.meals.length}x daily (${m.meals.map(meal => MEAL_OPTIONS.find(mo => mo.id === meal)?.label).join(", ")})`
          : "As needed",
        duration: `${m.duration} days`,
        timing: FOOD_RELATION_OPTIONS.find(fr => fr.value === m.foodRelation)?.label || "After food",
        notes: m.notes,
      }));

    try {
      await api.post("/api/v1/doctors/prescriptions", {
        patient_id: patientId,
        medicines: medicinesFormatted,
        diagnosis: diagnosis || undefined,
        notes: notes || undefined,
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

  return (
    <AuthGuard requiredRole="doctor">
      <Navbar />
      <main className="mx-auto max-w-4xl px-4 py-6">
        <h1 className="mb-6 text-2xl font-bold">Create Prescription</h1>

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
                <h2 className="text-lg font-semibold">Medicines</h2>
                <button
                  type="button"
                  onClick={addMedicine}
                  className="text-sm text-primary-600 hover:underline"
                >
                  + Add Medicine
                </button>
              </div>

              {medicines.map((med, idx) => (
                <div
                  key={idx}
                  className="mb-4 rounded-xl border bg-white p-6 shadow-sm"
                >
                  <div className="mb-4 flex items-center justify-between">
                    <span className="text-sm font-medium text-gray-500">
                      Medicine {idx + 1}
                    </span>
                    {medicines.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeMedicine(idx)}
                        className="text-xs text-red-500 hover:underline"
                      >
                        Remove
                      </button>
                    )}
                  </div>

                  {/* Medicine Search */}
                  <div className="mb-4">
                    <label className="mb-2 block text-sm font-medium text-gray-700">
                      Medicine Name *
                    </label>
                    <MedicineAutocomplete
                      onSelect={(medicine) => handleMedicineSelect(idx, medicine)}
                      placeholder="Search for medicine (e.g., Dolo, Paracetamol)..."
                      className="w-full"
                    />
                    {med.name && (
                      <div className="mt-2 rounded-md bg-blue-50 px-3 py-2">
                        <p className="text-sm font-medium text-blue-900">{med.name}</p>
                        {med.dosage && (
                          <p className="text-xs text-blue-700 mt-1">{med.dosage}</p>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Meal Selector (Replaces Frequency + Timing) */}
                  <div className="mb-4">
                    <label className="mb-2 block text-sm font-medium text-gray-700">
                      When to take *
                    </label>
                    <div className="grid grid-cols-3 gap-2 sm:grid-cols-5">
                      {MEAL_OPTIONS.map((meal) => (
                        <button
                          key={meal.id}
                          type="button"
                          onClick={() => toggleMeal(idx, meal.id)}
                          className={`
                            flex flex-col items-center justify-center rounded-lg border-2 p-3 text-center transition-all
                            ${
                              med.meals.includes(meal.id)
                                ? "border-primary-500 bg-primary-50 text-primary-700"
                                : "border-gray-200 bg-white text-gray-600 hover:border-gray-300"
                            }
                          `}
                        >
                          <span className="text-2xl">{meal.icon}</span>
                          <span className="mt-1 text-xs font-medium">{meal.label}</span>
                        </button>
                      ))}
                    </div>
                    {med.meals.length === 0 && (
                      <p className="mt-1 text-xs text-red-500 font-medium">
                        ⚠️ Required: Select at least one meal time
                      </p>
                    )}
                    {med.meals.length > 0 && (
                      <p className="mt-1 text-xs text-green-600 font-medium">
                        ✅ {med.meals.length}x daily - {med.meals.map(m => MEAL_OPTIONS.find(mo => mo.id === m)?.label).join(", ")}
                      </p>
                    )}
                  </div>

                  <div className="grid gap-4 sm:grid-cols-2">
                    {/* Duration Dropdown */}
                    <div>
                      <label className="mb-2 block text-sm font-medium text-gray-700">
                        Duration *
                      </label>
                      <select
                        value={med.duration}
                        onChange={(e) => updateMedicine(idx, "duration", e.target.value)}
                        className="w-full rounded-lg border px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                        required
                      >
                        {DURATION_OPTIONS.map((opt) => (
                          <option key={opt.value} value={opt.value}>
                            {opt.label}
                          </option>
                        ))}
                      </select>
                    </div>

                    {/* Food Relation */}
                    <div>
                      <label className="mb-2 block text-sm font-medium text-gray-700">
                        Food Relation *
                      </label>
                      <div className="grid grid-cols-2 gap-2">
                        {FOOD_RELATION_OPTIONS.map((fr) => (
                          <button
                            key={fr.value}
                            type="button"
                            onClick={() => updateMedicine(idx, "foodRelation", fr.value)}
                            className={`
                              flex items-center justify-center rounded-lg border-2 px-3 py-2 text-sm transition-all
                              ${
                                med.foodRelation === fr.value
                                  ? "border-primary-500 bg-primary-50 text-primary-700"
                                  : "border-gray-200 bg-white text-gray-600 hover:border-gray-300"
                              }
                            `}
                          >
                            <span className="mr-1">{fr.icon}</span>
                            <span className="text-xs font-medium">{fr.label}</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Additional Notes */}
                  <div className="mt-4">
                    <label className="mb-2 block text-sm font-medium text-gray-700">
                      Additional Instructions
                    </label>
                    <input
                      type="text"
                      value={med.notes}
                      onChange={(e) => updateMedicine(idx, "notes", e.target.value)}
                      placeholder="e.g., Take with plenty of water"
                      className="w-full rounded-lg border px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                    />
                  </div>
                </div>
              ))}
            </div>

            <div>
              {/* Validation hints */}
              {medicines.some(m => !m.name) && (
                <div className="mb-3 rounded-lg bg-amber-50 px-4 py-2 text-sm text-amber-800">
                  ⚠️ Please select a medicine from the autocomplete
                </div>
              )}
              {medicines.some(m => m.name && m.meals.length === 0) && (
                <div className="mb-3 rounded-lg bg-amber-50 px-4 py-2 text-sm text-amber-800">
                  ⚠️ Please select at least one meal time (e.g., breakfast, lunch, dinner)
                </div>
              )}

              <div className="flex gap-3">
                <button
                  type="submit"
                  disabled={loading || medicines.some(m => !m.name || m.meals.length === 0)}
                  className="rounded-lg bg-primary-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
                >
                  {loading ? "Creating..." : "Create Prescription"}
                </button>
                <button
                  type="button"
                  onClick={() => router.back()}
                  className="rounded-lg border px-6 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
              </div>
            </div>
          </form>
        )}
      </main>
    </AuthGuard>
  );
}
