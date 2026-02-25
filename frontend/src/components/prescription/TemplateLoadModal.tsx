"use client";

import { useState, useEffect } from "react";
import api from "@/lib/api";

interface Medicine {
  name: string;
  dosage: string;
  frequency: string;
  duration: string;
  timing: string;
  notes: string;
}

interface Template {
  id: string;
  name: string;
  medicines: Medicine[];
  diagnosis?: string;
  notes?: string;
}

interface Props {
  onClose: () => void;
  onLoad: (template: Template) => void;
}

export function TemplateLoadModal({ onClose, onLoad }: Props) {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [searchTerm, setSearchTerm] = useState("");

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

  const filteredTemplates = templates.filter((t) =>
    t.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-2xl rounded-xl bg-white p-6">
        <h3 className="mb-4 text-lg font-semibold">Load Template</h3>

        {error && (
          <div className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="mb-4">
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search templates..."
            className="w-full rounded-lg border px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
          />
        </div>

        <div className="mb-4 max-h-96 overflow-y-auto">
          {loading ? (
            <p className="py-8 text-center text-gray-500">Loading templates...</p>
          ) : filteredTemplates.length === 0 ? (
            <p className="py-8 text-center text-gray-500">
              {searchTerm ? "No templates match your search" : "No templates available"}
            </p>
          ) : (
            <div className="space-y-2">
              {filteredTemplates.map((template) => (
                <button
                  key={template.id}
                  onClick={() => {
                    onLoad(template);
                    onClose();
                  }}
                  className="w-full rounded-lg border p-4 text-left transition-colors hover:bg-gray-50"
                >
                  <div className="mb-2 flex items-start justify-between">
                    <h4 className="font-semibold">{template.name}</h4>
                    <span className="text-sm text-gray-500">
                      {template.medicines.length} meds
                    </span>
                  </div>
                  {template.diagnosis && (
                    <p className="mb-1 text-sm text-gray-600">
                      Diagnosis: {template.diagnosis}
                    </p>
                  )}
                  <div className="text-xs text-gray-500">
                    {template.medicines.slice(0, 2).map((m, i) => m.name).join(", ")}
                    {template.medicines.length > 2 && ` +${template.medicines.length - 2} more`}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="flex justify-end">
          <button
            onClick={onClose}
            className="rounded-lg border px-4 py-2 text-sm font-medium hover:bg-gray-50"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
