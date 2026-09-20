"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Trash2 } from "lucide-react";
import {
  deleteEncounter,
  getEncounter,
  updateEncounter,
} from "@/lib/api/encounters";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { Badge } from "@/components/ui/badge";

const VITAL_LABELS: Record<string, string> = {
  bp_systolic: "BP Systolic",
  bp_diastolic: "BP Diastolic",
  pulse: "Pulse",
  spo2: "SpO2",
  temperature_c: "Temperature",
  weight_kg: "Weight",
};

function formatDateTime(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function EncounterDetailPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const id = params.id as string;

  const [editing, setEditing] = useState(false);
  const [subjective, setSubjective] = useState("");
  const [objective, setObjective] = useState("");
  const [assessment, setAssessment] = useState("");
  const [plan, setPlan] = useState("");
  const [error, setError] = useState("");

  const { data: enc, isLoading, error: loadError } = useQuery({
    queryKey: ["encounter", id],
    queryFn: () => getEncounter(id),
  });

  const updateMutation = useMutation({
    mutationFn: () =>
      updateEncounter(id, {
        subjective: subjective || null,
        objective: objective || null,
        assessment: assessment || null,
        plan: plan || null,
      }),
    onSuccess: () => {
      setEditing(false);
      queryClient.invalidateQueries({ queryKey: ["encounter", id] });
      queryClient.invalidateQueries({ queryKey: ["doctor-encounters"] });
    },
    onError: () => setError("Failed to update encounter."),
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteEncounter(id),
    onSuccess: () => router.push("/doctor/visits"),
    onError: () => setError("Failed to delete encounter."),
  });

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-200 border-t-blue-600" />
      </div>
    );
  }

  if (loadError || !enc) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
        Failed to load encounter.
      </div>
    );
  }

  const startEdit = () => {
    setSubjective(enc.subjective ?? "");
    setObjective(enc.objective ?? "");
    setAssessment(enc.assessment ?? "");
    setPlan(enc.plan ?? "");
    setError("");
    setEditing(true);
  };

  const soapSections = editing
    ? null
    : [
        { label: "Subjective", value: enc.subjective },
        { label: "Objective", value: enc.objective },
        { label: "Assessment", value: enc.assessment },
        { label: "Plan", value: enc.plan },
      ];

  return (
    <div className="space-y-6">
      <Breadcrumb
        items={[
          { label: "Dashboard", href: "/doctor/dashboard" },
          { label: "Encounters", href: "/doctor/visits" },
          { label: "Encounter Detail" },
        ]}
      />

      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold text-dreams-textPrimary">
              {enc.patient_name ?? "Encounter"}
            </h1>
            {enc.clinic_name && (
              <Badge variant="pending" className="text-sm px-3 py-1">
                {enc.clinic_name}
              </Badge>
            )}
          </div>
          <p className="text-dreams-textSecondary mt-1">
            {formatDateTime(enc.created_at)}
            {enc.appointment_id ? " · Linked to appointment" : " · Walk-in"}
          </p>
        </div>

        {!editing && (
          <div className="flex items-center gap-2">
            <button
              onClick={startEdit}
              className="flex items-center gap-2 px-4 py-2 border border-dreams-border text-sm rounded-lg hover:bg-dreams-lightBg transition-colors"
            >
              <Pencil className="h-4 w-4" />
              Edit
            </button>
            <button
              onClick={() => {
                if (window.confirm("Delete this encounter?")) {
                  deleteMutation.mutate();
                }
              }}
              disabled={deleteMutation.isPending}
              className="flex items-center gap-2 px-4 py-2 border border-red-300 text-red-600 text-sm rounded-lg hover:bg-red-50 disabled:opacity-40 transition-colors"
            >
              <Trash2 className="h-4 w-4" />
              Delete
            </button>
          </div>
        )}
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Vitals snapshot */}
      {enc.vitals_snapshot && Object.keys(enc.vitals_snapshot).length > 0 && (
        <div className="bg-white rounded-lg border border-dreams-border p-4">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-dreams-textSecondary mb-3">
            Vitals
          </h2>
          <div className="flex flex-wrap gap-4">
            {Object.entries(enc.vitals_snapshot).map(([key, val]) => (
              <div key={key} className="text-sm">
                <span className="text-dreams-textSecondary">
                  {VITAL_LABELS[key] ?? key}:
                </span>{" "}
                <span className="font-medium text-dreams-textPrimary">
                  {String(val)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {editing ? (
        <div className="bg-white rounded-lg border border-dreams-border p-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            {(
              [
                { label: "Subjective", value: subjective, setter: setSubjective },
                { label: "Objective", value: objective, setter: setObjective },
                { label: "Assessment", value: assessment, setter: setAssessment },
                { label: "Plan", value: plan, setter: setPlan },
              ] as const
            ).map((s) => (
              <div key={s.label} className="flex flex-col">
                <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">
                  {s.label}
                </label>
                <textarea
                  value={s.value}
                  onChange={(e) => s.setter(e.target.value)}
                  rows={6}
                  className="w-full flex-1 rounded-lg border border-dreams-border px-3 py-2 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20 resize-y"
                />
              </div>
            ))}
          </div>
          <div className="flex gap-3">
            <button
              onClick={() => updateMutation.mutate()}
              disabled={updateMutation.isPending}
              className="px-6 py-2.5 bg-dreams-blue text-white text-sm font-medium rounded-lg hover:opacity-90 disabled:opacity-50 transition-opacity"
            >
              {updateMutation.isPending ? "Saving..." : "Save Changes"}
            </button>
            <button
              onClick={() => setEditing(false)}
              className="px-6 py-2.5 border border-dreams-border text-sm font-medium text-dreams-textPrimary rounded-lg hover:bg-dreams-lightBg transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {soapSections?.map((s) => (
            <div
              key={s.label}
              className="bg-white rounded-lg border border-dreams-border p-4"
            >
              <h2 className="text-xs font-semibold uppercase tracking-wider text-dreams-textSecondary mb-2">
                {s.label}
              </h2>
              <p className="text-sm text-dreams-textPrimary whitespace-pre-wrap">
                {s.value || (
                  <span className="text-dreams-textSecondary italic">
                    Not recorded
                  </span>
                )}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
