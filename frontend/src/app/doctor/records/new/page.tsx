"use client";

import { Suspense, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { Breadcrumb } from "@/components/ui/breadcrumb";

const RECORD_TYPES = [
  { value: "opd_note", label: "OPD Note" },
  { value: "lab_report", label: "Lab Report" },
  { value: "diagnostic_report", label: "Diagnostic Report" },
  { value: "discharge_summary", label: "Discharge Summary" },
  { value: "immunization", label: "Immunization" },
  { value: "imaging", label: "Imaging" },
  { value: "other", label: "Other" },
];

const ACCEPTED_TYPES = ["image/jpeg", "image/png", "application/pdf"];
const ACCEPTED_EXT = ".jpg,.jpeg,.png,.pdf";

function NewRecordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [patientId, setPatientId] = useState(searchParams.get("patient_id") || "");
  const [selectedPatientName, setSelectedPatientName] = useState<string | null>(null);
  const [recordType, setRecordType] = useState("opd_note");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
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

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0] ?? null;
    if (selected && !ACCEPTED_TYPES.includes(selected.type)) {
      setError("Only PDF, JPG, and PNG files are allowed.");
      setFile(null);
      return;
    }
    setError("");
    setFile(selected);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      let documentUrl: string | undefined;

      if (file) {
        // Step 1: Get presigned upload URL
        const presignRes = await api.post("/api/v1/uploads/presign", {
          file_name: file.name,
          content_type: file.type,
        });
        const { presigned_url, object_key } = presignRes.data;

        // Step 2: Upload file bytes to the presigned URL
        setUploadProgress(0);
        await api.put(presigned_url.replace(/^https?:\/\/[^/]+/, ""), file, {
          headers: { "Content-Type": file.type },
          onUploadProgress: (progressEvent) => {
            if (progressEvent.total) {
              const pct = Math.round(
                (progressEvent.loaded * 100) / progressEvent.total
              );
              setUploadProgress(pct);
            }
          },
        });
        setUploadProgress(100);
        documentUrl = object_key;
      }

      // Step 3: Create the record
      await api.post("/api/v1/doctors/records", {
        patient_id: patientId,
        record_type: recordType,
        title,
        description: description || undefined,
        document_url: documentUrl,
      });

      setSuccess(true);
      setTimeout(() => router.push("/doctor/dashboard"), 1500);
    } catch (err: any) {
      setError(
        err.response?.data?.detail?.error?.message || "Failed to create record"
      );
    } finally {
      setLoading(false);
      setUploadProgress(null);
    }
  };

  if (success) {
    return (
      <div className="bg-green-50 rounded-lg border border-green-200 p-6 text-center">
        <p className="text-lg font-medium text-green-800">Record created successfully!</p>
        <p className="mt-1 text-sm text-green-600">Redirecting to dashboard...</p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow-card p-6 max-w-2xl">
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
          Patient ID
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
            placeholder="Patient UUID"
            className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
            required
          />
        )}
        <p className="mt-1 text-xs text-dreams-textSecondary">
          Enter the patient&apos;s user ID (UUID) or select a recent patient above.
        </p>
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

      <div className="mb-4">
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

      {/* Optional document attachment */}
      <div className="mb-6">
        <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">
          Attach Document
          <span className="ml-1 text-xs font-normal text-dreams-textSecondary">
            (PDF, JPG, PNG — optional)
          </span>
        </label>

        <div
          className="flex cursor-pointer items-center gap-3 rounded-lg border border-dashed border-dreams-border bg-dreams-lightBg px-4 py-3 transition hover:border-dreams-blue"
          onClick={() => fileInputRef.current?.click()}
        >
          <svg
            className="h-5 w-5 flex-shrink-0 text-dreams-textSecondary"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"
            />
          </svg>
          <span className="text-sm text-dreams-textSecondary">
            {file ? (
              <span className="font-medium text-dreams-textPrimary">{file.name}</span>
            ) : (
              "Click to attach a file"
            )}
          </span>
        </div>

        <input
          ref={fileInputRef}
          type="file"
          accept={ACCEPTED_EXT}
          onChange={handleFileChange}
          className="hidden"
        />

        {/* Upload progress bar */}
        {uploadProgress !== null && (
          <div className="mt-2">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-dreams-textSecondary">Uploading...</span>
              <span className="text-xs text-dreams-textSecondary">{uploadProgress}%</span>
            </div>
            <div className="h-1.5 w-full rounded-full bg-gray-200">
              <div
                className="h-1.5 rounded-full bg-dreams-blue transition-all duration-200"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
          </div>
        )}
      </div>

      <div className="flex gap-3">
        <button
          type="submit"
          disabled={loading}
          className="flex items-center gap-2 px-6 py-2.5 bg-dreams-blue text-white text-sm font-medium rounded-lg hover:opacity-90 disabled:opacity-50 transition-opacity"
        >
          {loading ? (
            <>
              <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              {uploadProgress !== null ? "Uploading..." : "Creating..."}
            </>
          ) : (
            "Create Record"
          )}
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
        <h1 className="text-3xl font-bold text-dreams-textPrimary">Create Medical Record</h1>
        <p className="text-dreams-textSecondary mt-1">Add a new health record for a patient</p>
      </div>

      <Suspense fallback={<div className="h-96 animate-pulse rounded-lg bg-gray-100" />}>
        <NewRecordForm />
      </Suspense>
    </div>
  );
}
