"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import api from "@/lib/api";

interface Template {
  id: string;
  name: string;
  medicines: Array<{
    name: string;
    dosage: string;
    frequency: string;
    duration: string;
    timing?: string;
    notes?: string;
  }>;
  diagnosis?: string;
  notes?: string;
  created_at: string;
}

export default function TemplatesPage() {
  const router = useRouter();
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [deleteId, setDeleteId] = useState<string | null>(null);

  useEffect(() => {
    fetchTemplates();
  }, []);

  const fetchTemplates = async () => {
    try {
      const response = await api.get("/api/v1/doctors/prescription-templates");
      setTemplates(response.data.data);
    } catch (err: any) {
      setError("Failed to load templates");
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.delete(`/api/v1/doctors/prescription-templates/${id}`);
      setTemplates(templates.filter((t) => t.id !== id));
      setDeleteId(null);
    } catch (err: any) {
      setError("Failed to delete template");
    }
  };

  // Close delete-confirm dialog on Escape
  useEffect(() => {
    if (!deleteId) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setDeleteId(null);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [deleteId]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-dreams-textPrimary">
            Prescription Templates
          </h1>
          <p className="text-dreams-textSecondary mt-1">
            Reusable medicine sets for faster prescribing
          </p>
        </div>
        <button
          onClick={() => router.push("/doctor/prescriptions/new")}
          className="rounded-lg bg-dreams-blue px-4 py-2 text-sm font-medium text-white hover:opacity-90 transition-opacity"
        >
          Create Prescription
        </button>
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
        </div>
      ) : templates.length === 0 ? (
        <div className="rounded-xl border border-dreams-border bg-white p-8 text-center shadow-card">
          <p className="mb-2 text-lg font-medium text-dreams-textPrimary">No templates yet</p>
          <p className="mb-4 text-sm text-dreams-textSecondary">
            Create a prescription and save it as a template for quick reuse
          </p>
          <button
            onClick={() => router.push("/doctor/prescriptions/new")}
            className="rounded-lg bg-dreams-blue px-4 py-2 text-sm font-medium text-white hover:opacity-90 transition-opacity"
          >
            Create First Prescription
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {templates.map((template) => (
            <div
              key={template.id}
              className="rounded-xl border border-dreams-border bg-white p-4 shadow-card"
            >
              <div className="mb-3 flex items-start justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-dreams-textPrimary">{template.name}</h3>
                  {template.diagnosis && (
                    <p className="text-sm text-dreams-textSecondary">
                      Diagnosis: {template.diagnosis}
                    </p>
                  )}
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => setDeleteId(template.id)}
                    className="text-sm text-red-500 hover:underline"
                  >
                    Delete
                  </button>
                </div>
              </div>

              <div className="mb-2">
                <p className="mb-1 text-sm font-medium text-dreams-textPrimary">
                  Medicines ({template.medicines.length}):
                </p>
                <ul className="space-y-1 text-sm text-dreams-textSecondary">
                  {template.medicines.map((med, idx) => (
                    <li key={idx}>
                      {med.name} - {med.dosage} - {med.frequency} for {med.duration}
                    </li>
                  ))}
                </ul>
              </div>

              {template.notes && (
                <p className="text-sm text-dreams-textSecondary">Notes: {template.notes}</p>
              )}
            </div>
          ))}
        </div>
      )}

      {deleteId && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          onClick={() => setDeleteId(null)}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Delete template"
            className="w-full max-w-md rounded-xl bg-white p-6 mx-4"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="mb-4 text-lg font-semibold text-dreams-textPrimary">Delete Template?</h3>
            <p className="mb-6 text-sm text-dreams-textSecondary">
              This action cannot be undone. The template will be permanently deleted.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setDeleteId(null)}
                className="rounded-lg border border-dreams-border px-4 py-2 text-sm font-medium text-dreams-textPrimary hover:bg-dreams-lightBg"
              >
                Cancel
              </button>
              <button
                onClick={() => handleDelete(deleteId)}
                className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
