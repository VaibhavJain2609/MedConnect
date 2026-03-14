"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import api from "@/lib/api";
import { Breadcrumb } from "@/components/ui/breadcrumb";

const RECORD_TYPES = [
  { value: "lab_report", label: "Lab Report" },
  { value: "diagnostic_report", label: "Diagnostic Report" },
  { value: "discharge_summary", label: "Discharge Summary" },
  { value: "imaging", label: "Imaging" },
  { value: "immunization", label: "Immunization" },
];

const ACCEPTED_TYPES = ["image/jpeg", "image/png", "application/pdf"];
const ACCEPTED_EXT = ".jpg,.jpeg,.png,.pdf";

export default function PatientNewRecordPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [recordType, setRecordType] = useState("lab_report");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

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
      await api.post("/api/v1/patients/records", {
        record_type: recordType,
        title,
        description: description || undefined,
        document_url: documentUrl,
      });

      setSuccess(true);
      setTimeout(() => router.push("/patient/timeline"), 1200);
    } catch (err: any) {
      setError(
        err.response?.data?.detail?.error?.message ||
          err.response?.data?.detail ||
          "Failed to upload record. Please try again."
      );
    } finally {
      setLoading(false);
      setUploadProgress(null);
    }
  };

  if (success) {
    return (
      <div className="space-y-6">
        <Breadcrumb
          items={[
            { label: "Health Timeline", href: "/patient/timeline" },
            { label: "Upload Record" },
          ]}
        />
        <div className="rounded-lg border border-green-200 bg-green-50 p-8 text-center">
          <p className="text-lg font-medium text-green-800">
            Record uploaded successfully!
          </p>
          <p className="mt-1 text-sm text-green-600">
            Redirecting to your timeline...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Breadcrumb
        items={[
          { label: "Health Timeline", href: "/patient/timeline" },
          { label: "Upload Record" },
        ]}
      />

      <div>
        <h1 className="text-3xl font-bold text-dreams-textPrimary">
          Upload Health Record
        </h1>
        <p className="mt-1 text-dreams-textSecondary">
          Add a health document to your personal health timeline
        </p>
      </div>

      <form
        onSubmit={handleSubmit}
        className="max-w-2xl rounded-lg bg-white p-6 shadow-card"
      >
        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Record Type */}
        <div className="mb-4">
          <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">
            Record Type
          </label>
          <select
            value={recordType}
            onChange={(e) => setRecordType(e.target.value)}
            className="h-10 w-full rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
          >
            {RECORD_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </div>

        {/* Title */}
        <div className="mb-4">
          <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">
            Title <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g., Blood Test — March 2026"
            className="h-10 w-full rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
            required
          />
        </div>

        {/* Description */}
        <div className="mb-4">
          <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">
            Description
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            placeholder="Optional notes about this record..."
            className="w-full rounded-lg border border-dreams-border px-3 py-2 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
          />
        </div>

        {/* File Attachment */}
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
                <span className="font-medium text-dreams-textPrimary">
                  {file.name}
                </span>
              ) : (
                "Click to select a file"
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
                <span className="text-xs text-dreams-textSecondary">
                  Uploading...
                </span>
                <span className="text-xs text-dreams-textSecondary">
                  {uploadProgress}%
                </span>
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

        {/* Actions */}
        <div className="flex gap-3">
          <button
            type="submit"
            disabled={loading}
            className="flex items-center gap-2 rounded-lg bg-dreams-blue px-6 py-2.5 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {loading ? (
              <>
                <svg
                  className="h-4 w-4 animate-spin"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                  />
                </svg>
                Uploading...
              </>
            ) : (
              "Upload Record"
            )}
          </button>
          <Link
            href="/patient/timeline"
            className="rounded-lg border border-dreams-border px-6 py-2.5 text-sm font-medium text-dreams-textPrimary transition-colors hover:bg-dreams-lightBg"
          >
            Cancel
          </Link>
        </div>
      </form>
    </div>
  );
}
