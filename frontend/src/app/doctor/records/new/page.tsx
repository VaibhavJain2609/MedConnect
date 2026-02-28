"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
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

function NewRecordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [patientId, setPatientId] = useState(searchParams.get("patient_id") || "");
  const [recordType, setRecordType] = useState("opd_note");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await api.post("/api/v1/doctors/records", {
        patient_id: patientId,
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

      <div className="mb-4">
        <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">
          Patient ID
        </label>
        <input
          type="text"
          value={patientId}
          onChange={(e) => setPatientId(e.target.value)}
          placeholder="Patient UUID"
          className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
          required
        />
        <p className="mt-1 text-xs text-dreams-textSecondary">
          Enter the patient&apos;s user ID (UUID)
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
          disabled={loading}
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
        <h1 className="text-3xl font-bold text-dreams-textPrimary">Create Medical Record</h1>
        <p className="text-dreams-textSecondary mt-1">Add a new health record for a patient</p>
      </div>

      <Suspense fallback={<div className="h-96 animate-pulse rounded-lg bg-gray-100" />}>
        <NewRecordForm />
      </Suspense>
    </div>
  );
}
