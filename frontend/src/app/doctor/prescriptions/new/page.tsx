"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import api from "@/lib/api";
import { Navbar } from "@/components/layout/navbar";
import { AuthGuard } from "@/components/layout/auth-guard";
import { TemplateSaveModal } from "@/components/prescription/TemplateSaveModal";
import { TemplateLoadModal } from "@/components/prescription/TemplateLoadModal";

interface Medicine {
  name: string;
  dosage: string;
  frequency: string;
  duration: string;
  timing: string;
  notes: string;
}

const EMPTY_MEDICINE: Medicine = {
  name: "",
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
  const [medicines, setMedicines] = useState<Medicine[]>([{ ...EMPTY_MEDICINE }]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [showSaveModal, setShowSaveModal] = useState(false);
  const [showLoadModal, setShowLoadModal] = useState(false);

  const updateMedicine = (index: number, field: keyof Medicine, value: string) => {
    const updated = [...medicines];
    updated[index] = { ...updated[index], [field]: value };
    setMedicines(updated);
  };

  const addMedicine = () => {
    setMedicines([...medicines, { ...EMPTY_MEDICINE }]);
  };

  const removeMedicine = (index: number) => {
    if (medicines.length > 1) {
      setMedicines(medicines.filter((_, i) => i !== index));
    }
  };

  const handleLoadTemplate = (template: any) => {
    setMedicines(template.medicines);
    if (template.diagnosis) setDiagnosis(template.diagnosis);
    if (template.notes) setNotes(template.notes);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await api.post("/api/v1/doctors/prescriptions", {
        patient_id: patientId,
        medicines: medicines.filter((m) => m.name),
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
      <main className="mx-auto max-w-2xl px-4 py-6">
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
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setShowLoadModal(true)}
                    className="text-sm text-primary-600 hover:underline"
                  >
                    Load Template
                  </button>
                  {medicines.some((m) => m.name) && (
                    <button
                      type="button"
                      onClick={() => setShowSaveModal(true)}
                      className="text-sm text-primary-600 hover:underline"
                    >
                      Save as Template
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={addMedicine}
                    className="text-sm text-primary-600 hover:underline"
                  >
                    + Add Medicine
                  </button>
                </div>
              </div>

              {medicines.map((med, idx) => (
                <div
                  key={idx}
                  className="mb-3 rounded-xl border bg-white p-4 shadow-sm"
                >
                  <div className="mb-3 flex items-center justify-between">
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
                  <div className="grid gap-3 sm:grid-cols-2">
                    <input
                      type="text"
                      value={med.name}
                      onChange={(e) => updateMedicine(idx, "name", e.target.value)}
                      placeholder="Medicine name *"
                      className="rounded-lg border px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                      required
                    />
                    <input
                      type="text"
                      value={med.dosage}
                      onChange={(e) => updateMedicine(idx, "dosage", e.target.value)}
                      placeholder="Dosage (e.g., 500mg) *"
                      className="rounded-lg border px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                      required
                    />
                    <input
                      type="text"
                      value={med.frequency}
                      onChange={(e) => updateMedicine(idx, "frequency", e.target.value)}
                      placeholder="Frequency (e.g., twice daily) *"
                      className="rounded-lg border px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                      required
                    />
                    <input
                      type="text"
                      value={med.duration}
                      onChange={(e) => updateMedicine(idx, "duration", e.target.value)}
                      placeholder="Duration (e.g., 5 days) *"
                      className="rounded-lg border px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                      required
                    />
                    <input
                      type="text"
                      value={med.timing}
                      onChange={(e) => updateMedicine(idx, "timing", e.target.value)}
                      placeholder="Timing (e.g., after food)"
                      className="rounded-lg border px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                    />
                    <input
                      type="text"
                      value={med.notes}
                      onChange={(e) => updateMedicine(idx, "notes", e.target.value)}
                      placeholder="Notes"
                      className="rounded-lg border px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                    />
                  </div>
                </div>
              ))}
            </div>

            <div className="flex gap-3">
              <button
                type="submit"
                disabled={loading}
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
          </form>
        )}

        {showSaveModal && (
          <TemplateSaveModal
            medicines={medicines}
            diagnosis={diagnosis}
            notes={notes}
            onClose={() => setShowSaveModal(false)}
            onSaved={() => {
              // Optional: show success message
            }}
          />
        )}

        {showLoadModal && (
          <TemplateLoadModal
            onClose={() => setShowLoadModal(false)}
            onLoad={handleLoadTemplate}
          />
        )}
      </main>
    </AuthGuard>
  );
}
