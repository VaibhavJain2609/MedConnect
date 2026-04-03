"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import api from "@/lib/api";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import MedicineAutocomplete from "@/components/medicine/MedicineAutocomplete";
import { AlertTriangle, X, ChevronDown, BookOpen, Save } from "lucide-react";
import { getMyClinics, getClinicBranches, type ClinicBranch } from "@/lib/api/clinics";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Medicine {
  _uid: string;
  brand_name: string;
  brand_id: string | null;
  salt_id: string | null;
  dose: string;
  frequency: string;
  duration: string;
  route: string;
  instructions: string;
}

interface ClinicOption {
  id: string;
  name: string;
}

interface PatientSuggestion {
  id: string;
  full_name: string;
  phone: string | null;
  last_visit_at: string | null;
}

interface DrugInteraction {
  interaction_id: string;
  salt_1: { id: string; name: string };
  salt_2: { id: string; name: string };
  severity: string;
  effect: string;
  mechanism: string | null;
  management: string | null;
}

interface PrescriptionTemplate {
  id: string;
  name: string;
  medicines: Medicine[];
  diagnosis: string | null;
  notes: string | null;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

function newEmptyMedicine(): Medicine {
  return {
    _uid: Math.random().toString(36).slice(2),
    brand_name: "",
    brand_id: null,
    salt_id: null,
    dose: "",
    frequency: "OD",
    duration: "7 days",
    route: "oral",
    instructions: "",
  };
}

const FREQUENCY_OPTIONS = ["OD", "BD", "TDS", "QID", "1-0-1", "SOS", "HS"];
const DURATION_OPTIONS = [
  "3 days",
  "5 days",
  "7 days",
  "10 days",
  "14 days",
  "1 month",
  "2 months",
  "3 months",
  "Ongoing",
];
const ROUTE_OPTIONS = [
  { value: "oral", label: "Oral" },
  { value: "topical", label: "Topical" },
  { value: "IV", label: "IV" },
  { value: "IM", label: "IM" },
  { value: "SC", label: "SC" },
  { value: "inhaled", label: "Inhaled" },
  { value: "sublingual", label: "Sublingual" },
];

// ---------------------------------------------------------------------------
// Patient Search Typeahead
// ---------------------------------------------------------------------------

function PatientSearch({
  onSelect,
}: {
  onSelect: (patient: PatientSuggestion) => void;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<PatientSuggestion[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const search = useCallback((q: string) => {
    if (q.length < 2) {
      setResults([]);
      setOpen(false);
      return;
    }
    setLoading(true);
    api
      .get(`/api/v1/doctors/patients/search?q=${encodeURIComponent(q)}`)
      .then((res) => {
        setResults(res.data.data || []);
        setOpen(true);
      })
      .catch(() => {
        setResults([]);
      })
      .finally(() => setLoading(false));
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setQuery(val);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => search(val), 400);
  };

  const handleSelect = (patient: PatientSuggestion) => {
    setOpen(false);
    setQuery("");
    onSelect(patient);
  };

  return (
    <div className="relative">
      <input
        type="text"
        value={query}
        onChange={handleChange}
        placeholder="Search patient by name or phone..."
        className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
        onFocus={() => results.length > 0 && setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
      />
      {loading && (
        <div className="absolute right-3 top-1/2 -translate-y-1/2">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-dreams-blue border-t-transparent" />
        </div>
      )}
      {open && results.length > 0 && (
        <div className="absolute z-50 mt-1 w-full rounded-lg border border-dreams-border bg-white shadow-lg">
          {results.map((p) => (
            <button
              key={p.id}
              type="button"
              className="flex w-full items-start gap-3 px-4 py-3 text-left hover:bg-dreams-lightBg transition-colors"
              onMouseDown={() => handleSelect(p)}
            >
              <div className="flex-1">
                <p className="text-sm font-medium text-dreams-textPrimary">
                  {p.full_name}
                </p>
                {p.phone && (
                  <p className="text-xs text-dreams-textSecondary">{p.phone}</p>
                )}
              </div>
              {p.last_visit_at && (
                <p className="text-xs text-dreams-textSecondary whitespace-nowrap">
                  Last visit:{" "}
                  {new Date(p.last_visit_at).toLocaleDateString("en-IN")}
                </p>
              )}
            </button>
          ))}
        </div>
      )}
      {open && results.length === 0 && !loading && query.length >= 2 && (
        <div className="absolute z-50 mt-1 w-full rounded-lg border border-dreams-border bg-white px-4 py-3 text-sm text-dreams-textSecondary shadow-lg">
          No patients found.
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Drug Interaction Banner
// ---------------------------------------------------------------------------

function InteractionBanner({
  interactions,
}: {
  interactions: DrugInteraction[];
}) {
  if (interactions.length === 0) return null;

  const severityOrder: Record<string, number> = {
    contraindicated: 4,
    major: 3,
    moderate: 2,
    minor: 1,
  };

  const sorted = [...interactions].sort(
    (a, b) =>
      (severityOrder[b.severity] ?? 0) - (severityOrder[a.severity] ?? 0)
  );

  const highest = sorted[0].severity;

  let classes =
    "rounded-lg border p-4 mb-4 flex items-start gap-3";
  if (highest === "contraindicated" || highest === "major") {
    classes += " bg-red-50 border-red-200";
  } else if (highest === "moderate") {
    classes += " bg-yellow-50 border-yellow-200";
  } else {
    classes += " bg-gray-50 border-gray-200";
  }

  const iconColor =
    highest === "contraindicated" || highest === "major"
      ? "text-red-500"
      : highest === "moderate"
      ? "text-yellow-500"
      : "text-gray-400";

  return (
    <div className={classes}>
      <AlertTriangle className={`h-5 w-5 mt-0.5 flex-shrink-0 ${iconColor}`} />
      <div className="flex-1">
        <p className="text-sm font-semibold text-dreams-textPrimary mb-1">
          Drug Interaction Warning ({sorted.length} interaction
          {sorted.length !== 1 ? "s" : ""} detected)
        </p>
        <ul className="space-y-1">
          {sorted.map((ix) => (
            <li key={ix.interaction_id} className="text-xs text-dreams-textPrimary">
              <span className="font-medium capitalize">[{ix.severity}]</span>{" "}
              <span className="font-semibold">
                {ix.salt_1.name} + {ix.salt_2.name}:
              </span>{" "}
              {ix.effect}
              {ix.management && (
                <span className="text-dreams-textSecondary">
                  {" "}
                  — {ix.management}
                </span>
              )}
            </li>
          ))}
        </ul>
        <p className="mt-2 text-xs text-dreams-textSecondary">
          You can still submit this prescription. Use clinical judgment.
        </p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Template Modal
// ---------------------------------------------------------------------------

function LoadTemplateModal({
  templates,
  onLoad,
  onClose,
}: {
  templates: PrescriptionTemplate[];
  onLoad: (t: PrescriptionTemplate) => void;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-xl bg-white shadow-xl p-6">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-dreams-textPrimary">
            Load Template
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="text-dreams-textSecondary hover:text-dreams-textPrimary"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        {templates.length === 0 ? (
          <p className="text-sm text-dreams-textSecondary text-center py-4">
            No templates saved yet.
          </p>
        ) : (
          <ul className="space-y-2 max-h-72 overflow-y-auto">
            {templates.map((t) => (
              <li key={t.id}>
                <button
                  type="button"
                  className="w-full text-left rounded-lg border border-dreams-border px-4 py-3 hover:border-dreams-blue hover:bg-dreams-lightBg transition-colors"
                  onClick={() => onLoad(t)}
                >
                  <p className="text-sm font-medium text-dreams-textPrimary">
                    {t.name}
                  </p>
                  {t.diagnosis && (
                    <p className="text-xs text-dreams-textSecondary mt-0.5">
                      {t.diagnosis}
                    </p>
                  )}
                  <p className="text-xs text-dreams-textSecondary mt-0.5">
                    {t.medicines.length} medicine
                    {t.medicines.length !== 1 ? "s" : ""}
                  </p>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function SaveTemplateModal({
  onSave,
  onClose,
}: {
  onSave: (name: string) => void;
  onClose: () => void;
}) {
  const [name, setName] = useState("");
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-sm rounded-xl bg-white shadow-xl p-6">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-dreams-textPrimary">
            Save as Template
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="text-dreams-textSecondary hover:text-dreams-textPrimary"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Template name (e.g., Fever protocol)"
          className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20 mb-4"
          autoFocus
        />
        <div className="flex gap-3">
          <button
            type="button"
            disabled={!name.trim()}
            onClick={() => name.trim() && onSave(name.trim())}
            className="flex-1 px-4 py-2 bg-dreams-blue text-white text-sm font-medium rounded-lg hover:opacity-90 disabled:opacity-50 transition-opacity"
          >
            Save Template
          </button>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 border border-dreams-border text-sm font-medium text-dreams-textPrimary rounded-lg hover:bg-dreams-lightBg transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function NewPrescriptionPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // Read appointment context from query params (set when navigating from appointments page)
  const appointmentId = searchParams.get("appointment_id");
  const prefillPatientId = searchParams.get("patient_id");

  // Patient state
  const [selectedPatient, setSelectedPatient] =
    useState<PatientSuggestion | null>(null);

  // Clinic + branch state
  const [clinics, setClinics] = useState<ClinicOption[]>([]);
  const [selectedClinicId, setSelectedClinicId] = useState("");
  const [branches, setBranches] = useState<ClinicBranch[]>([]);
  const [selectedBranchId, setSelectedBranchId] = useState("");
  const [branchesLoading, setBranchesLoading] = useState(false);

  // Form fields
  const [diagnosis, setDiagnosis] = useState("");
  const [notes, setNotes] = useState("");
  const [medicines, setMedicines] = useState<Medicine[]>([newEmptyMedicine()]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  // Drug interactions
  const [interactions, setInteractions] = useState<DrugInteraction[]>([]);

  // Templates
  const [templates, setTemplates] = useState<PrescriptionTemplate[]>([]);
  const [showLoadModal, setShowLoadModal] = useState(false);
  const [showSaveModal, setShowSaveModal] = useState(false);

  // Load templates and clinics on mount; pre-fill patient if appointment_id provided
  useEffect(() => {
    api
      .get("/api/v1/doctors/prescription-templates")
      .then((res) => setTemplates(res.data.data || []))
      .catch(() => {});
    getMyClinics()
      .then((res) => setClinics(res.data || []))
      .catch(() => {});

    // Pre-fill patient when navigating from appointments page
    if (prefillPatientId) {
      api
        .get(`/api/v1/doctors/patients/${prefillPatientId}/profile`)
        .then((res) => {
          const p = res.data;
          if (p?.id) {
            setSelectedPatient({
              id: p.id,
              full_name: p.full_name || "Unknown",
              phone: p.phone || null,
              last_visit_at: p.last_visit_at || null,
            });
          }
        })
        .catch(() => {});
    }
  }, [prefillPatientId]);

  // Fetch branches when a clinic is selected
  useEffect(() => {
    setSelectedBranchId("");
    setBranches([]);
    if (!selectedClinicId) return;
    setBranchesLoading(true);
    getClinicBranches(selectedClinicId)
      .then((data) => setBranches(data))
      .catch(() => setBranches([]))
      .finally(() => setBranchesLoading(false));
  }, [selectedClinicId]);

  // Drug interaction check whenever medicines change (2+ with salt_id)
  useEffect(() => {
    const saltIds = medicines
      .map((m) => m.salt_id)
      .filter((id): id is string => !!id);

    if (saltIds.length < 2) {
      setInteractions([]);
      return;
    }

    const timer = setTimeout(() => {
      api
        .post("/api/v1/interactions/check", { salt_ids: saltIds })
        .then((res) => setInteractions(res.data || []))
        .catch(() => setInteractions([]));
    }, 600);

    return () => clearTimeout(timer);
  }, [medicines]);

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  const updateMedicine = (index: number, field: keyof Medicine, value: string | null) => {
    const updated = [...medicines];
    updated[index] = { ...updated[index], [field]: value };
    setMedicines(updated);
  };

  const addMedicine = () => {
    setMedicines([...medicines, newEmptyMedicine()]);
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
      saltId?: string;
    }
  ) => {
    const updated = [...medicines];
    updated[index] = {
      ...updated[index],
      brand_name: medicine.brandName,
      brand_id: medicine.brandId || null,
      salt_id: medicine.saltId || null,
      dose: `${medicine.dosageForm} ${medicine.strength}`.trim(),
    };
    setMedicines(updated);
  };

  const handleLoadTemplate = (t: PrescriptionTemplate) => {
    setMedicines(
      t.medicines.map((m) => ({
        _uid: Math.random().toString(36).slice(2),
        brand_name: m.brand_name || "",
        brand_id: m.brand_id || null,
        salt_id: m.salt_id || null,
        dose: m.dose || "",
        frequency: m.frequency || "OD",
        duration: m.duration || "7 days",
        route: m.route || "oral",
        instructions: m.instructions || "",
      }))
    );
    if (t.diagnosis) setDiagnosis(t.diagnosis);
    if (t.notes) setNotes(t.notes);
    setShowLoadModal(false);
  };

  const handleSaveTemplate = async (name: string) => {
    const validMeds = medicines.filter((m) => m.brand_name);
    if (validMeds.length === 0) return;
    try {
      const res = await api.post("/api/v1/doctors/prescription-templates", {
        name,
        medicines: validMeds,
        diagnosis: diagnosis || undefined,
        notes: notes || undefined,
      });
      setTemplates((prev) => [res.data, ...prev]);
      setShowSaveModal(false);
    } catch (err) {
      console.error("Template save failed:", err);
      // non-critical — prescription can still be created without saving template
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    if (!selectedPatient) {
      setError("Please select a patient");
      setLoading(false);
      return;
    }

    const medicinesFormatted = medicines
      .filter((m) => m.brand_name)
      .map((m) => ({
        brand_name: m.brand_name,
        brand_id: m.brand_id || undefined,
        salt_id: m.salt_id || undefined,
        dose: m.dose,
        frequency: m.frequency,
        duration: m.duration,
        route: m.route,
        instructions: m.instructions || undefined,
      }));

    if (medicinesFormatted.length === 0) {
      setError("Please add at least one medicine");
      setLoading(false);
      return;
    }

    try {
      await api.post(
        "/api/v1/doctors/prescriptions",
        {
          patient_id: selectedPatient.id,
          medicines: medicinesFormatted,
          diagnosis: diagnosis || undefined,
          notes: notes || undefined,
          clinic_id: selectedClinicId || undefined,
          branch_id: selectedBranchId || undefined,
          appointment_id: appointmentId || undefined,
        },
        selectedClinicId ? { headers: { "X-Clinic-Id": selectedClinicId } } : undefined
      );
      setSuccess(true);
      setTimeout(() => router.push("/doctor/prescriptions"), 1500);
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

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  if (success) {
    return (
      <div className="space-y-6">
        <Breadcrumb
          items={[
            { label: "Prescriptions", href: "/doctor/prescriptions" },
            { label: "New Prescription" },
          ]}
        />
        <div className="bg-green-50 rounded-lg border border-green-200 p-6 text-center">
          <p className="text-lg font-medium text-green-800">
            Prescription created!
          </p>
          <p className="mt-1 text-sm text-green-600">
            The patient can now see this in their timeline.
          </p>
        </div>
      </div>
    );
  }

  const hasMedicines = medicines.some((m) => m.brand_name);

  return (
    <div className="space-y-6">
      {showLoadModal && (
        <LoadTemplateModal
          templates={templates}
          onLoad={handleLoadTemplate}
          onClose={() => setShowLoadModal(false)}
        />
      )}
      {showSaveModal && (
        <SaveTemplateModal
          onSave={handleSaveTemplate}
          onClose={() => setShowSaveModal(false)}
        />
      )}

      <Breadcrumb
        items={[
          { label: "Prescriptions", href: "/doctor/prescriptions" },
          { label: "New Prescription" },
        ]}
      />

      {appointmentId && (
        <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800">
          Linked to appointment — prescription will be associated with this appointment on save.
        </div>
      )}

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-dreams-textPrimary">
            Create Prescription
          </h1>
          <p className="text-dreams-textSecondary mt-1">
            Write a new prescription for a patient
          </p>
        </div>
        <div className="flex gap-2">
          {templates.length > 0 && (
            <button
              type="button"
              onClick={() => setShowLoadModal(true)}
              className="flex items-center gap-2 px-4 py-2 border border-dreams-border text-sm font-medium text-dreams-textPrimary rounded-lg hover:bg-dreams-lightBg transition-colors"
            >
              <BookOpen className="h-4 w-4" />
              Load Template
            </button>
          )}
          {hasMedicines && (
            <button
              type="button"
              onClick={() => setShowSaveModal(true)}
              className="flex items-center gap-2 px-4 py-2 border border-dreams-border text-sm font-medium text-dreams-textPrimary rounded-lg hover:bg-dreams-lightBg transition-colors"
            >
              <Save className="h-4 w-4" />
              Save as Template
            </button>
          )}
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6 max-w-4xl">
        {/* Patient & Diagnosis */}
        <div className="bg-white rounded-lg shadow-card p-6">
          <h2 className="text-lg font-semibold text-dreams-textPrimary mb-4">
            Patient Details
          </h2>

          {error && (
            <div className="mb-4 rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <div className="mb-4">
            <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">
              Patient *
            </label>
            {selectedPatient ? (
              <div className="flex items-center gap-3 rounded-lg border border-dreams-blue bg-dreams-blue/5 px-4 py-2.5">
                <div className="flex-1">
                  <p className="text-sm font-semibold text-dreams-textPrimary">
                    {selectedPatient.full_name}
                  </p>
                  {selectedPatient.phone && (
                    <p className="text-xs text-dreams-textSecondary">
                      {selectedPatient.phone}
                    </p>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedPatient(null)}
                  className="text-dreams-textSecondary hover:text-red-500 transition-colors"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ) : (
              <PatientSearch onSelect={setSelectedPatient} />
            )}
          </div>

          {/* Clinic selector */}
          {clinics.length > 0 && (
            <div className="mb-4">
              <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">
                Clinic
              </label>
              <select
                value={selectedClinicId}
                onChange={(e) => setSelectedClinicId(e.target.value)}
                className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
              >
                <option value="">No clinic (private)</option>
                {clinics.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Branch selector (shown when clinic has branches) */}
          {selectedClinicId && (branchesLoading || branches.length > 0) && (
            <div className="mb-4">
              <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">
                Branch
              </label>
              {branchesLoading ? (
                <div className="h-10 rounded-lg border border-dreams-border bg-gray-50 flex items-center px-3">
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-dreams-blue border-t-transparent" />
                  <span className="ml-2 text-sm text-dreams-textSecondary">Loading branches...</span>
                </div>
              ) : (
                <select
                  value={selectedBranchId}
                  onChange={(e) => setSelectedBranchId(e.target.value)}
                  className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
                >
                  <option value="">Any branch</option>
                  {branches.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name}{b.city ? ` — ${b.city}` : ""}
                    </option>
                  ))}
                </select>
              )}
            </div>
          )}

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
            <h2 className="text-lg font-semibold text-dreams-textPrimary">
              Medicines
            </h2>
            <button
              type="button"
              onClick={addMedicine}
              className="text-sm text-dreams-blue hover:underline font-medium"
            >
              + Add Medicine
            </button>
          </div>

          {/* Drug interaction banner */}
          <InteractionBanner interactions={interactions} />

          {medicines.map((med, idx) => (
            <div key={med._uid} className="mb-4 bg-white rounded-lg shadow-card p-6">
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
                {med.brand_name ? (
                  <div className="mt-2 rounded-md bg-green-50 border-2 border-green-200 px-3 py-2">
                    <div className="flex items-center gap-2">
                      <div>
                        <p className="text-sm font-medium text-green-900">
                          {med.brand_name}
                        </p>
                        {med.dose && (
                          <p className="text-xs text-green-700 mt-1">
                            {med.dose}
                          </p>
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

              <div className="grid gap-4 sm:grid-cols-2">
                {/* Dose */}
                <div>
                  <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">
                    Dose
                  </label>
                  <input
                    type="text"
                    value={med.dose}
                    onChange={(e) => updateMedicine(idx, "dose", e.target.value)}
                    placeholder="e.g., 500mg tablet"
                    className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
                  />
                </div>

                {/* Frequency */}
                <div>
                  <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">
                    Frequency *
                  </label>
                  <div className="flex flex-wrap gap-1.5">
                    {FREQUENCY_OPTIONS.map((f) => (
                      <button
                        key={f}
                        type="button"
                        onClick={() => updateMedicine(idx, "frequency", f)}
                        className={`rounded-md border px-3 py-1.5 text-xs font-medium transition-colors
                          ${
                            med.frequency === f
                              ? "border-dreams-blue bg-dreams-blue text-white"
                              : "border-dreams-border bg-white text-dreams-textPrimary hover:border-dreams-blue/50"
                          }`}
                      >
                        {f}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Duration */}
                <div>
                  <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">
                    Duration *
                  </label>
                  <select
                    value={med.duration}
                    onChange={(e) =>
                      updateMedicine(idx, "duration", e.target.value)
                    }
                    className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
                  >
                    {DURATION_OPTIONS.map((d) => (
                      <option key={d} value={d}>
                        {d}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Route */}
                <div>
                  <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">
                    Route
                  </label>
                  <select
                    value={med.route}
                    onChange={(e) =>
                      updateMedicine(idx, "route", e.target.value)
                    }
                    className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
                  >
                    {ROUTE_OPTIONS.map((r) => (
                      <option key={r.value} value={r.value}>
                        {r.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Instructions */}
              <div className="mt-4">
                <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">
                  Instructions
                </label>
                <input
                  type="text"
                  value={med.instructions}
                  onChange={(e) =>
                    updateMedicine(idx, "instructions", e.target.value)
                  }
                  placeholder="e.g., Take with plenty of water, after meals"
                  className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
                />
              </div>
            </div>
          ))}
        </div>

        {/* Submit */}
        <div>
          {!hasMedicines && (
            <div className="mb-3 rounded-lg bg-amber-50 border border-amber-200 px-4 py-2 text-sm text-amber-800">
              Please select at least one medicine
            </div>
          )}

          <div className="flex gap-3">
            <button
              type="submit"
              disabled={loading || !selectedPatient || !hasMedicines}
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
