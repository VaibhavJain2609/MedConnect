"use client";

import { Suspense, useState, useRef, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import api from "@/lib/api";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { X } from "lucide-react";

const RECORD_TYPES = [
  { value: "opd_note", label: "OPD Note" },
  { value: "lab_report", label: "Lab Report" },
  { value: "diagnostic_report", label: "Diagnostic Report" },
  { value: "discharge_summary", label: "Discharge Summary" },
  { value: "immunization", label: "Immunization" },
  { value: "imaging", label: "Imaging" },
  { value: "other", label: "Other" },
];

interface PatientSuggestion {
  id: string;
  full_name: string;
  phone: string | null;
  last_visit_at: string | null;
}

function PatientSearch({
  initialId,
  onSelect,
}: {
  initialId: string;
  onSelect: (patient: PatientSuggestion | null) => void;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<PatientSuggestion[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<PatientSuggestion | null>(
    initialId ? ({ id: initialId, full_name: initialId, phone: null, last_visit_at: null } as PatientSuggestion) : null
  );
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
      .catch(() => setResults([]))
      .finally(() => setLoading(false));
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setQuery(val);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => search(val), 400);
  };

  const handleSelect = (patient: PatientSuggestion) => {
    setSelected(patient);
    setOpen(false);
    setQuery("");
    onSelect(patient);
  };

  const handleClear = () => {
    setSelected(null);
    onSelect(null);
  };

  if (selected) {
    return (
      <div className="flex items-center gap-3 rounded-lg border border-dreams-blue bg-dreams-blue/5 px-4 py-2.5">
        <div className="flex-1">
          <p className="text-sm font-semibold text-dreams-textPrimary">
            {selected.full_name}
          </p>
          {selected.phone && (
            <p className="text-xs text-dreams-textSecondary">{selected.phone}</p>
          )}
        </div>
        <button
          type="button"
          onClick={handleClear}
          className="text-dreams-textSecondary hover:text-red-500 transition-colors"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    );
  }

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
                  Last:{" "}
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

function NewRecordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const initialPatientId = searchParams.get("patient_id") || "";
  const [selectedPatient, setSelectedPatient] =
    useState<PatientSuggestion | null>(
      initialPatientId
        ? {
            id: initialPatientId,
            full_name: initialPatientId,
            phone: null,
            last_visit_at: null,
          }
        : null
    );
  const [recordType, setRecordType] = useState("opd_note");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!selectedPatient) {
      setError("Please select a patient");
      return;
    }

    setLoading(true);
    try {
      await api.post("/api/v1/doctors/records", {
        patient_id: selectedPatient.id,
        record_type: recordType,
        title,
        description: description || undefined,
      });
      setSuccess(true);
      setTimeout(() => router.push("/doctor/dashboard"), 1500);
    } catch (err: any) {
      setError(
        err.response?.data?.detail?.error?.message || "Failed to create record"
      );
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="bg-green-50 rounded-lg border border-green-200 p-6 text-center">
        <p className="text-lg font-medium text-green-800">
          Record created successfully!
        </p>
        <p className="mt-1 text-sm text-green-600">
          Redirecting to dashboard...
        </p>
      </div>
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-white rounded-lg shadow-card p-6 max-w-2xl"
    >
      {error && (
        <div className="mb-4 rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="mb-4">
        <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">
          Patient *
        </label>
        <PatientSearch
          initialId={initialPatientId}
          onSelect={setSelectedPatient}
        />
      </div>

      <div className="mb-4">
        <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">
          Record Type
        </label>
        <select
          value={recordType}
          onChange={(e) => setRecordType(e.target.value)}
          className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
        >
          {RECORD_TYPES.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>
      </div>

      <div className="mb-4">
        <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">
          Title
        </label>
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="e.g., General Checkup — Fever"
          className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
          required
        />
      </div>

      <div className="mb-6">
        <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">
          Description / Notes
        </label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={4}
          placeholder="Clinical notes, observations, findings..."
          className="w-full rounded-lg border border-dreams-border px-3 py-2 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
        />
      </div>

      <div className="flex gap-3">
        <button
          type="submit"
          disabled={loading || !selectedPatient}
          className="px-6 py-2.5 bg-dreams-blue text-white text-sm font-medium rounded-lg hover:opacity-90 disabled:opacity-50 transition-opacity"
        >
          {loading ? "Creating..." : "Create Record"}
        </button>
        <button
          type="button"
          onClick={() => router.back()}
          className="px-6 py-2.5 border border-dreams-border text-sm font-medium text-dreams-textPrimary rounded-lg hover:bg-dreams-lightBg transition-colors"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

export default function NewRecordPage() {
  return (
    <div className="space-y-6">
      <Breadcrumb
        items={[
          { label: "Dashboard", href: "/doctor/dashboard" },
          { label: "Create Record" },
        ]}
      />

      <div>
        <h1 className="text-3xl font-bold text-dreams-textPrimary">
          Create Medical Record
        </h1>
        <p className="text-dreams-textSecondary mt-1">
          Add a new health record for a patient
        </p>
      </div>

      <Suspense
        fallback={<div className="h-96 animate-pulse rounded-lg bg-gray-100" />}
      >
        <NewRecordForm />
      </Suspense>
    </div>
  );
}
