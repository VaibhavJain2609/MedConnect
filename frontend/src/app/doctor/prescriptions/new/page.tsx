"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import MedicineAutocomplete from "@/components/medicine/MedicineAutocomplete";

interface Medicine {
  name: string;
  dosage: string;
  meals: string[];
  duration: string;
  foodRelation: string;
  notes: string;
}

const EMPTY_MEDICINE: Medicine = {
  name: "",
  dosage: "",
  meals: [],
  duration: "5",
  foodRelation: "after_food",
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
  const [selectedPatientName, setSelectedPatientName] = useState<string | null>(null);
  const [diagnosis, setDiagnosis] = useState("");
  const [notes, setNotes] = useState("");
  const [medicines, setMedicines] = useState<Medicine[]>([{ ...EMPTY_MEDICINE }]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  // Fetch recent patients from prescription history (MD-263)
  const { data: recentPrescriptionsData } = useQuery({
    queryKey: ["doctor-prescriptions-recent"],
    queryFn: async () => {
      const res = await api.get("/api/v1/doctors/prescriptions", { params: { limit: 10 } });
      return res.data;
    },
  });

  // Deduplicate patients from recent prescriptions, take first 5 unique
  const recentPatients: Array<{ id: string; name: string }> = [];
  const seenPatientIds = new Set<string>();
  for (const rx of recentPrescriptionsData?.data ?? []) {
    if (rx.patient_id && !seenPatientIds.has(rx.patient_id)) {
      seenPatientIds.add(rx.patient_id);
      recentPatients.push({ id: rx.patient_id, name: rx.patient_name || "Patient" });
    }
    if (recentPatients.length >= 5) break;
  }

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
    const updated = [...medicines];
    updated[index] = {
      ...updated[index],
      name: medicine.brandName,
      dosage: `${medicine.dosageForm} - ${medicine.strength}`.trim(),
    };
    setMedicines(updated);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    if (!uuidRegex.test(patientId)) {
      setError("Patient ID must be a valid UUID format (e.g., 123e4567-e89b-12d3-a456-426614174000)");
      setLoading(false);
      return;
    }

    const medicinesFormatted = medicines
      .filter((m) => m.name)
      .map((m) => ({
        name: m.name,
        dosage: m.dosage,
        frequency:
          m.meals.length > 0
            ? `${m.meals.length}x daily (${m.meals
                .map((meal) => MEAL_OPTIONS.find((mo) => mo.id === meal)?.label)
                .join(", ")})`
            : "As needed",
        duration: `${m.duration} days`,
        timing:
          FOOD_RELATION_OPTIONS.find((fr) => fr.value === m.foodRelation)?.label ||
          "After food",
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
      const errorMsg =
        err.response?.data?.detail?.error?.message ||
        err.response?.data?.detail ||
        "Failed to create prescription";
      setError(typeof errorMsg === "string" ? errorMsg : JSON.stringify(errorMsg));
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="space-y-6">
        <Breadcrumb items={[{ label: "Dashboard", href: "/doctor/dashboard" }, { label: "New Prescription" }]} />
        <div className="bg-green-50 rounded-lg border border-green-200 p-6 text-center">
          <p className="text-lg font-medium text-green-800">Prescription created!</p>
          <p className="mt-1 text-sm text-green-600">
            The patient can now see this in their timeline.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Breadcrumb
        items={[
          { label: "Dashboard", href: "/doctor/dashboard" },
          { label: "New Prescription" },
        ]}
      />

      <div>
        <h1 className="text-3xl font-bold text-dreams-textPrimary">Create Prescription</h1>
        <p className="text-dreams-textSecondary mt-1">Write a new prescription for a patient</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6 max-w-4xl">
        {/* Patient & Diagnosis */}
        <div className="bg-white rounded-lg shadow-card p-6">
          <h2 className="text-lg font-semibold text-dreams-textPrimary mb-4">Patient Details</h2>

          {error && (
            <div className="mb-4 rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {/* Recent patients quick-select (MD-263) */}
          {!patientId && recentPatients.length > 0 && (
            <div className="mb-4">
              <p className="mb-2 text-xs font-medium text-dreams-textSecondary">Recent patients</p>
              <div className="flex flex-wrap gap-2">
                {recentPatients.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => {
                      setPatientId(p.id);
                      setSelectedPatientName(p.name);
                    }}
                    className="rounded-full border border-dreams-border bg-white px-3 py-1 text-xs font-medium text-dreams-textPrimary hover:border-dreams-blue hover:text-dreams-blue transition-colors"
                  >
                    {p.name}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="mb-4">
            <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">
              Patient ID *
            </label>
            {selectedPatientName && patientId ? (
              <div className="flex items-center gap-3 rounded-lg border border-green-200 bg-green-50 px-3 py-2">
                <span className="flex-1 text-sm font-medium text-green-900">{selectedPatientName}</span>
                <button
                  type="button"
                  onClick={() => { setPatientId(""); setSelectedPatientName(null); }}
                  className="text-xs text-green-700 hover:text-red-600"
                >
                  Change
                </button>
              </div>
            ) : (
              <input
                type="text"
                value={patientId}
                onChange={(e) => { setPatientId(e.target.value); setSelectedPatientName(null); }}
                placeholder="e.g., 123e4567-e89b-12d3-a456-426614174000"
                className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm font-mono focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
                required
              />
            )}
            <p className="mt-1 text-xs text-dreams-textSecondary">
              Enter the patient's UUID or select a recent patient above.
            </p>
          </div>

          <div className="mb-4">
            <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">
              Diagnosis
            </label>
            <input
              type="text"
              value={diagnosis}
              onChange={(e) => setDiagnosis(e.target.value)}
              placeholder="e.g., Upper respiratory infection"
              className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">
              Notes
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              placeholder="Additional instructions..."
              className="w-full rounded-lg border border-dreams-border px-3 py-2 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
            />
          </div>
        </div>

        {/* Medicines */}
        <div>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-dreams-textPrimary">Medicines</h2>
            <button
              type="button"
              onClick={addMedicine}
              className="text-sm text-dreams-blue hover:underline font-medium"
            >
              + Add Medicine
            </button>
          </div>

          {medicines.map((med, idx) => (
            <div key={idx} className="mb-4 bg-white rounded-lg shadow-card p-6">
              <div className="mb-4 flex items-center justify-between">
                <span className="text-sm font-medium text-dreams-textSecondary">
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
                <label className="mb-2 block text-sm font-medium text-dreams-textPrimary">
                  Medicine Name *
                </label>
                <MedicineAutocomplete
                  onSelect={(medicine) => handleMedicineSelect(idx, medicine)}
                  placeholder="Search for medicine (e.g., Dolo, Paracetamol)..."
                  className="w-full"
                />
                {med.name ? (
                  <div className="mt-2 rounded-md bg-green-50 border-2 border-green-200 px-3 py-2">
                    <div className="flex items-center gap-2">
                      <span className="text-green-600">✅</span>
                      <div>
                        <p className="text-sm font-medium text-green-900">{med.name}</p>
                        {med.dosage && (
                          <p className="text-xs text-green-700 mt-1">{med.dosage}</p>
                        )}
                      </div>
                    </div>
                  </div>
                ) : (
                  <p className="mt-2 text-xs text-dreams-textSecondary">
                    Start typing to search medicines...
                  </p>
                )}
              </div>

              {/* Meal Selector */}
              <div className="mb-4">
                <label className="mb-2 block text-sm font-medium text-dreams-textPrimary">
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
                            ? "border-dreams-blue bg-dreams-blue/5 text-dreams-blue"
                            : "border-dreams-border bg-white text-dreams-textSecondary hover:border-dreams-blue/30"
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
                    Required: Select at least one meal time
                  </p>
                )}
                {med.meals.length > 0 && (
                  <p className="mt-1 text-xs text-green-600 font-medium">
                    {med.meals.length}x daily —{" "}
                    {med.meals
                      .map((m) => MEAL_OPTIONS.find((mo) => mo.id === m)?.label)
                      .join(", ")}
                  </p>
                )}
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                {/* Duration */}
                <div>
                  <label className="mb-2 block text-sm font-medium text-dreams-textPrimary">
                    Duration *
                  </label>
                  <select
                    value={med.duration}
                    onChange={(e) => updateMedicine(idx, "duration", e.target.value)}
                    className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
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
                  <label className="mb-2 block text-sm font-medium text-dreams-textPrimary">
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
                              ? "border-dreams-blue bg-dreams-blue/5 text-dreams-blue"
                              : "border-dreams-border bg-white text-dreams-textSecondary hover:border-dreams-blue/30"
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
                <label className="mb-2 block text-sm font-medium text-dreams-textPrimary">
                  Additional Instructions
                </label>
                <input
                  type="text"
                  value={med.notes}
                  onChange={(e) => updateMedicine(idx, "notes", e.target.value)}
                  placeholder="e.g., Take with plenty of water"
                  className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
                />
              </div>
            </div>
          ))}
        </div>

        {/* Submit */}
        <div>
          {!medicines[0].name && (
            <div className="mb-3 rounded-lg bg-amber-50 border border-amber-200 px-4 py-2 text-sm text-amber-800">
              Please select a medicine from the autocomplete for Medicine 1
            </div>
          )}
          {medicines[0].name && medicines[0].meals.length === 0 && (
            <div className="mb-3 rounded-lg bg-amber-50 border border-amber-200 px-4 py-2 text-sm text-amber-800">
              Please select at least one meal time for Medicine 1
            </div>
          )}
          {medicines.length > 1 &&
            medicines.slice(1).some((m) => m.name && m.meals.length === 0) && (
              <div className="mb-3 rounded-lg bg-amber-50 border border-amber-200 px-4 py-2 text-sm text-amber-800">
                Some medicines need meal times selected
              </div>
            )}

          <div className="flex gap-3">
            <button
              type="submit"
              disabled={
                loading ||
                !medicines[0].name ||
                medicines.filter((m) => m.name).some((m) => m.meals.length === 0)
              }
              className="px-6 py-2.5 bg-dreams-blue text-white text-sm font-medium rounded-lg hover:opacity-90 disabled:opacity-50 transition-opacity"
            >
              {loading ? "Creating..." : "Create Prescription"}
            </button>
            <button
              type="button"
              onClick={() => router.back()}
              className="px-6 py-2.5 border border-dreams-border text-sm font-medium text-dreams-textPrimary rounded-lg hover:bg-dreams-lightBg transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
