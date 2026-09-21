"use client";

import { Suspense, useState, useRef, useCallback, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import api from "@/lib/api";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { Loader2, ScanLine, X } from "lucide-react";
import { requestUpload, uploadBytes } from "@/lib/api/uploads";
import {
  ingestLabResultImage,
  type LabIngestCandidate,
} from "@/lib/api/lab-results";

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
  selected,
  onSelect,
}: {
  selected: PatientSuggestion | null;
  onSelect: (patient: PatientSuggestion | null) => void;
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
    setOpen(false);
    setQuery("");
    onSelect(patient);
  };

  const handleClear = () => {
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
          aria-label="Clear selected patient"
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
        id="record-patient"
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

/**
 * "Extract from image" — lab-report OCR assist (scaffold).
 *
 * NOTE: no structured lab-result entry form exists yet (the admin "New
 * Test" action is disabled and lab values land on LabResult rows only via
 * the admin CRUD API), so this lives on the doctor's record form — the
 * closest lab-entry context — and is shown when Record Type = Lab Report.
 *
 * Flow: presign → PUT the image → POST /api/v1/lab-results/ingest → render
 * returned candidates in an editable table for review. Candidates are
 * human-in-the-loop only: nothing is saved until the doctor clicks
 * "Insert into notes" (which formats them into the Description field) and
 * then submits the record. When OCR is disabled server-side the endpoint
 * answers 503 OCR_NOT_CONFIGURED and we show a quiet notice.
 */
function LabReportExtract({
  patientId,
  onApply,
}: {
  patientId: string | null;
  onApply: (notes: string) => void;
}) {
  const fileRef = useRef<HTMLInputElement | null>(null);
  const [busy, setBusy] = useState(false);
  const [extractError, setExtractError] = useState("");
  const [candidates, setCandidates] = useState<LabIngestCandidate[] | null>(
    null
  );

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setExtractError("");
    setCandidates(null);
    setBusy(true);
    try {
      const { presigned_url, object_key } = await requestUpload(
        file.name,
        file.type
      );
      await uploadBytes(object_key, file, undefined, presigned_url);
      const res = await ingestLabResultImage(
        object_key,
        patientId ?? undefined
      );
      setCandidates(res.candidates);
      if (res.candidates.length === 0) {
        setExtractError("No lab values were detected in the image.");
      }
    } catch (err: any) {
      const status = err.response?.status;
      const code = err.response?.data?.error?.code;
      if (status === 503 && code === "OCR_NOT_CONFIGURED") {
        setExtractError("Image extraction is not enabled on this server.");
      } else if (status === 503) {
        setExtractError(
          "Extraction service is unavailable right now — please enter values manually."
        );
      } else {
        setExtractError(
          err.response?.data?.error?.message ||
            "Failed to extract values from the image."
        );
      }
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const updateCandidate = (
    idx: number,
    field: keyof LabIngestCandidate,
    value: string
  ) => {
    setCandidates(
      (prev) =>
        prev?.map((c, i) => (i === idx ? { ...c, [field]: value } : c)) ?? null
    );
  };

  const applyToNotes = () => {
    if (!candidates?.length) return;
    const lines = candidates.map((c) => {
      const range =
        c.ref_low || c.ref_high
          ? ` (ref ${c.ref_low ?? "—"}–${c.ref_high ?? "—"}${
              c.unit ? ` ${c.unit}` : ""
            })`
          : "";
      const flag =
        c.flag && c.flag !== "normal" ? ` [${c.flag.toUpperCase()}]` : "";
      return `• ${c.name}: ${c.value ?? "—"}${
        c.unit ? ` ${c.unit}` : ""
      }${range}${flag}`;
    });
    onApply(
      ["Extracted lab values (review before saving):", ...lines].join("\n")
    );
  };

  const cellInput =
    "w-full rounded border border-transparent px-1 py-0.5 text-sm hover:border-dreams-border focus:border-dreams-blue focus:outline-none";

  return (
    <div className="rounded-lg border border-dashed border-dreams-border p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-dreams-textPrimary">
            Extract from image
          </p>
          <p className="text-xs text-dreams-textSecondary mt-0.5">
            Upload a photo/scan of the report to prefill values for review.
          </p>
        </div>
        <input
          ref={fileRef}
          type="file"
          accept="image/jpeg,image/png"
          className="hidden"
          onChange={handleFile}
        />
        <button
          type="button"
          disabled={busy}
          onClick={() => fileRef.current?.click()}
          className="flex items-center gap-2 px-3 py-2 text-sm border border-dreams-border rounded-lg text-dreams-textPrimary hover:bg-dreams-lightBg disabled:opacity-50 transition-colors"
        >
          {busy ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <ScanLine className="h-4 w-4" />
          )}
          {busy ? "Extracting…" : "Choose image"}
        </button>
      </div>

      {extractError && (
        <p className="mt-3 text-sm text-red-600">{extractError}</p>
      )}

      {candidates && candidates.length > 0 && (
        <div className="mt-4 space-y-3">
          <p className="text-xs font-medium text-dreams-textSecondary uppercase tracking-wide">
            Extracted values — review and edit before inserting
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-dreams-textSecondary border-b border-dreams-border">
                  <th className="py-1 pr-2 font-medium">Test</th>
                  <th className="py-1 pr-2 font-medium">Value</th>
                  <th className="py-1 pr-2 font-medium">Unit</th>
                  <th className="py-1 pr-2 font-medium">Ref Low</th>
                  <th className="py-1 pr-2 font-medium">Ref High</th>
                  <th className="py-1 font-medium">Flag</th>
                </tr>
              </thead>
              <tbody>
                {candidates.map((c, i) => (
                  <tr key={i} className="border-b border-dreams-border/50">
                    {(
                      [
                        "name",
                        "value",
                        "unit",
                        "ref_low",
                        "ref_high",
                        "flag",
                      ] as const
                    ).map((f) => (
                      <td key={f} className="py-1 pr-2">
                        <input
                          value={c[f] ?? ""}
                          onChange={(e) =>
                            updateCandidate(i, f, e.target.value)
                          }
                          className={cellInput}
                        />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <button
            type="button"
            onClick={applyToNotes}
            className="px-3 py-1.5 text-sm bg-dreams-blue text-white rounded-lg hover:opacity-90 transition-opacity"
          >
            Insert into notes
          </button>
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
            full_name: "Loading patient…",
            phone: null,
            last_visit_at: null,
          }
        : null
    );

  // Hydrate the patient's real name when arriving via ?patient_id=
  useEffect(() => {
    if (!initialPatientId) return;
    api
      .get(`/api/v1/doctors/patients/${initialPatientId}/profile`)
      .then((res) => {
        const p = res.data;
        if (p?.id) {
          setSelectedPatient({
            id: p.id,
            full_name: p.full_name || initialPatientId,
            phone: p.phone ?? null,
            last_visit_at: p.last_visit_at ?? null,
          });
        }
      })
      .catch(() => {
        // Fall back to showing the raw id rather than a stuck "Loading…"
        setSelectedPatient((prev) =>
          prev?.id === initialPatientId
            ? { ...prev, full_name: initialPatientId }
            : prev
        );
      });
  }, [initialPatientId]);

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
      setTimeout(() => router.push(`/doctor/patients/${selectedPatient.id}`), 1500);
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
          Redirecting to patient profile...
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
        <label htmlFor="record-patient" className="mb-1 block text-sm font-medium text-dreams-textPrimary">
          Patient *
        </label>
        <PatientSearch
          selected={selectedPatient}
          onSelect={setSelectedPatient}
        />
      </div>

      <div className="mb-4">
        <label htmlFor="record-type" className="mb-1 block text-sm font-medium text-dreams-textPrimary">
          Record Type
        </label>
        <select
          id="record-type"
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

      {recordType === "lab_report" && (
        <div className="mb-4">
          <LabReportExtract
            patientId={selectedPatient?.id ?? null}
            onApply={(text) =>
              setDescription((prev) => (prev ? `${prev}\n\n${text}` : text))
            }
          />
        </div>
      )}

      <div className="mb-4">
        <label htmlFor="record-title" className="mb-1 block text-sm font-medium text-dreams-textPrimary">
          Title
        </label>
        <input
          id="record-title"
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="e.g., General Checkup — Fever"
          className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
          required
        />
      </div>

      <div className="mb-6">
        <label htmlFor="record-description" className="mb-1 block text-sm font-medium text-dreams-textPrimary">
          Description / Notes
        </label>
        <textarea
          id="record-description"
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
