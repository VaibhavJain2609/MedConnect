"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import api from "@/lib/api";
import { Navbar } from "@/components/layout/navbar";
import { AuthGuard } from "@/components/layout/auth-guard";

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
      const response = await api.get("/api/v1/doctors/templates");
      setTemplates(response.data.data);
    } catch (err: any) {
      setError("Failed to load templates");
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.delete(`/api/v1/doctors/templates/${id}`);
      setTemplates(templates.filter((t) => t.id !== id));
      setDeleteId(null);
    } catch (err: any) {
      setError("Failed to delete template");
    }
  };

  return (
    <AuthGuard requiredRole="doctor">
      <Navbar />
      <main className="mx-auto max-w-4xl px-4 py-6">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-2xl font-bold">Prescription Templates</h1>
          <button
            onClick={() => router.push("/doctor/prescriptions/new")}
            className="rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700"
          >
            Create Prescription
          </button>
        </div>

        {error && (
          <div className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {loading ? (
          <p className="text-center text-gray-500">Loading templates...</p>
        ) : templates.length === 0 ? (
          <div className="rounded-xl border bg-white p-8 text-center">
            <p className="mb-2 text-lg font-medium text-gray-700">No templates yet</p>
            <p className="mb-4 text-sm text-gray-500">
              Create a prescription and save it as a template for quick reuse
            </p>
            <button
              onClick={() => router.push("/doctor/prescriptions/new")}
              className="rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700"
            >
              Create First Prescription
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {templates.map((template) => (
              <div key={template.id} className="rounded-xl border bg-white p-4 shadow-sm">
                <div className="mb-3 flex items-start justify-between">
                  <div>
                    <h3 className="text-lg font-semibold">{template.name}</h3>
                    {template.diagnosis && (
                      <p className="text-sm text-gray-600">Diagnosis: {template.diagnosis}</p>
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
                  <p className="mb-1 text-sm font-medium text-gray-700">
                    Medicines ({template.medicines.length}):
                  </p>
                  <ul className="space-y-1 text-sm text-gray-600">
                    {template.medicines.map((med, idx) => (
                      <li key={idx}>
                        {med.name} - {med.dosage} - {med.frequency} for {med.duration}
                      </li>
                    ))}
                  </ul>
                </div>

                {template.notes && (
                  <p className="text-sm text-gray-600">Notes: {template.notes}</p>
                )}
              </div>
            ))}
          </div>
        )}

        {deleteId && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
            <div className="w-full max-w-md rounded-xl bg-white p-6">
              <h3 className="mb-4 text-lg font-semibold">Delete Template?</h3>
              <p className="mb-6 text-sm text-gray-600">
                This action cannot be undone. The template will be permanently deleted.
              </p>
              <div className="flex justify-end gap-3">
                <button
                  onClick={() => setDeleteId(null)}
                  className="rounded-lg border px-4 py-2 text-sm font-medium hover:bg-gray-50"
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
      </main>
    </AuthGuard>
  );
}
