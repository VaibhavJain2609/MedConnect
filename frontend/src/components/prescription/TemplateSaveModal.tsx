"use client";

import { useState } from "react";
import api from "@/lib/api";

interface Medicine {
  name: string;
  dosage: string;
  frequency: string;
  duration: string;
  timing: string;
  notes: string;
}

interface Props {
  medicines: Medicine[];
  diagnosis: string;
  notes: string;
  onClose: () => void;
  onSaved: () => void;
}

export function TemplateSaveModal({ medicines, diagnosis, notes, onClose, onSaved }: Props) {
  const [templateName, setTemplateName] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const handleSave = async () => {
    if (!templateName.trim()) {
      setError("Please enter a template name");
      return;
    }

    setSaving(true);
    setError("");

    try {
      await api.post("/api/v1/doctors/templates", {
        name: templateName,
        medicines: medicines.filter((m) => m.name),
        diagnosis: diagnosis || undefined,
        notes: notes || undefined,
      });
      onSaved();
      onClose();
    } catch (err: any) {
      setError(err.response?.data?.detail?.error?.message || "Failed to save template");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-xl bg-white p-6">
        <h3 className="mb-4 text-lg font-semibold">Save as Template</h3>

        {error && (
          <div className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="mb-4">
          <label className="mb-1 block text-sm font-medium text-gray-700">
            Template Name
          </label>
          <input
            type="text"
            value={templateName}
            onChange={(e) => setTemplateName(e.target.value)}
            placeholder="e.g., Common Cold Treatment"
            className="w-full rounded-lg border px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
            autoFocus
          />
        </div>

        <div className="mb-6 rounded-lg bg-gray-50 p-3">
          <p className="mb-2 text-sm font-medium text-gray-700">
            This template will save:
          </p>
          <ul className="space-y-1 text-sm text-gray-600">
            <li>{medicines.filter((m) => m.name).length} medicines</li>
            {diagnosis && <li>Diagnosis: {diagnosis}</li>}
            {notes && <li>Notes included</li>}
          </ul>
        </div>

        <div className="flex justify-end gap-3">
          <button
            onClick={onClose}
            disabled={saving}
            className="rounded-lg border px-4 py-2 text-sm font-medium hover:bg-gray-50 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save Template"}
          </button>
        </div>
      </div>
    </div>
  );
}
