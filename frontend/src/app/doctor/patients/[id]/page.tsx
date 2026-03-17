"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { Badge } from "@/components/ui/badge";
import { FileText, Pill, Activity, User, AlertCircle, Edit2, X, ShieldCheck, ShieldAlert, ShieldOff } from "lucide-react";
import { getMyRecordAccessConsent, requestRecordAccess } from "@/lib/api/record-access";

const VITAL_LABELS: Record<string, { label: string; unit: string }> = {
  bp_systolic: { label: "BP Systolic", unit: "mmHg" },
  bp_diastolic: { label: "BP Diastolic", unit: "mmHg" },
  pulse: { label: "Pulse", unit: "bpm" },
  spo2: { label: "SpO2", unit: "%" },
  temperature_c: { label: "Temperature", unit: "°C" },
  weight_kg: { label: "Weight", unit: "kg" },
  glucose_fasting: { label: "Glucose (Fasting)", unit: "mg/dL" },
  glucose_pp: { label: "Glucose (PP)", unit: "mg/dL" },
};

const RECORD_TYPE_LABELS: Record<string, string> = {
  prescription: "Prescription",
  opd_note: "OPD Note",
  lab_report: "Lab Report",
  diagnostic_report: "Diagnostic Report",
  discharge_summary: "Discharge Summary",
  imaging: "Imaging",
  immunization: "Immunization",
  other: "Other",
};

function getInitials(name: string): string {
  return name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

interface AmendFormState {
  recordId: string;
  title: string;
  description: string;
}

function AmendModal({
  initial,
  onClose,
  onSubmit,
  isPending,
}: {
  initial: AmendFormState;
  onClose: () => void;
  onSubmit: (data: AmendFormState) => void;
  isPending: boolean;
}) {
  const [title, setTitle] = useState(initial.title);
  const [description, setDescription] = useState(initial.description || "");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-bold text-dreams-textPrimary">Amend Record</h2>
          <button onClick={onClose} className="text-dreams-textSecondary hover:text-dreams-textPrimary">
            <X className="h-5 w-5" />
          </button>
        </div>
        <p className="mb-4 text-sm text-dreams-textSecondary">
          Creating an amendment preserves the original record and creates a new linked version.
        </p>
        <div className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">
              Title
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full rounded-lg border border-dreams-border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
              required
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">
              Description / Notes
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={4}
              className="w-full resize-none rounded-lg border border-dreams-border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
            />
          </div>
        </div>
        <div className="mt-6 flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-dreams-border px-4 py-2 text-sm font-medium text-dreams-textPrimary hover:bg-dreams-lightBg transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={isPending || !title.trim()}
            onClick={() => onSubmit({ recordId: initial.recordId, title, description })}
            className="rounded-lg bg-dreams-blue px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors disabled:opacity-50"
          >
            {isPending ? "Saving..." : "Save Amendment"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function DoctorPatientProfilePage() {
  const params = useParams();
  const patientId = params.id as string;
  const queryClient = useQueryClient();

  const { data: profile, isLoading: profileLoading } = useQuery({
    queryKey: ["doctor-patient-profile", patientId],
    queryFn: async () => {
      const res = await api.get(`/api/v1/doctors/patients/${patientId}/profile`);
      return res.data;
    },
    enabled: !!patientId,
  });

  const { data: recordsData, isLoading: recordsLoading } = useQuery({
    queryKey: ["doctor-patient-records", patientId],
    queryFn: async () => {
      const res = await api.get(`/api/v1/doctors/patients/${patientId}/records`, {
        params: { limit: 3 },
      });
      return res.data;
    },
    enabled: !!patientId,
  });

  const { data: prescriptionsData, isLoading: prescriptionsLoading } = useQuery({
    queryKey: ["doctor-patient-prescriptions-latest", patientId],
    queryFn: async () => {
      const res = await api.get(`/api/v1/doctors/patients/${patientId}/prescriptions`, {
        params: { limit: 1 },
      });
      return res.data;
    },
    enabled: !!patientId,
  });

  const { data: vitalsData, isLoading: vitalsLoading } = useQuery({
    queryKey: ["doctor-patient-vitals", patientId],
    queryFn: async () => {
      const res = await api.get(`/api/v1/doctors/patients/${patientId}/vitals`, {
        params: { days: 7 },
      });
      return res.data;
    },
    enabled: !!patientId,
  });

  const { data: consentData, isLoading: consentLoading } = useQuery({
    queryKey: ["record-access", patientId],
    queryFn: () => getMyRecordAccessConsent(patientId),
    enabled: !!patientId,
  });

  // Record access request modal state
  const [showAccessModal, setShowAccessModal] = useState(false);
  const [accessPurpose, setAccessPurpose] = useState("");
  const [accessDuration, setAccessDuration] = useState(30);

  const requestAccessMutation = useMutation({
    mutationFn: () =>
      requestRecordAccess(patientId, {
        purpose: accessPurpose || undefined,
        access_duration_days: accessDuration,
      }),
    onSuccess: () => {
      setShowAccessModal(false);
      setAccessPurpose("");
      setAccessDuration(30);
      queryClient.invalidateQueries({ queryKey: ["record-access", patientId] });
    },
  });

  // Amend record state
  const [amendTarget, setAmendTarget] = useState<AmendFormState | null>(null);
  const [amendError, setAmendError] = useState("");

  const amendMutation = useMutation({
    mutationFn: async (data: AmendFormState) => {
      const res = await api.post(
        `/api/v1/doctors/records/${data.recordId}/amend`,
        {
          record_type: "opd_note",
          title: data.title,
          description: data.description,
        }
      );
      return res.data;
    },
    onSuccess: () => {
      setAmendTarget(null);
      queryClient.invalidateQueries({ queryKey: ["doctor-patient-records", patientId] });
    },
    onError: () => {
      setAmendError("Failed to save amendment. Please try again.");
    },
  });

  const patientName = profile?.full_name || "Patient";

  // Deduplicate vitals — keep only latest reading per type
  const latestVitals: Record<string, { value: number; unit: string; recorded_at: string }> = {};
  if (vitalsData?.data) {
    for (const vital of vitalsData.data) {
      if (!latestVitals[vital.vital_type]) {
        latestVitals[vital.vital_type] = {
          value: vital.value,
          unit: vital.unit,
          recorded_at: vital.recorded_at,
        };
      }
    }
  }

  // Latest prescription medicines
  const latestPrescription = prescriptionsData?.data?.[0];
  const activeMedicines: string[] = latestPrescription?.medicines?.map((m: any) => m.name) || [];

  return (
    <div className="space-y-6">
      <Breadcrumb
        items={[
          { label: "Dashboard", href: "/doctor/dashboard" },
          { label: "Patients", href: "/doctor/patients" },
          { label: profileLoading ? "Loading..." : patientName },
        ]}
      />

      {/* Header */}
      {profileLoading ? (
        <div className="animate-pulse rounded-xl border border-dreams-border bg-white p-6 shadow-card">
          <div className="flex items-center gap-4">
            <div className="h-16 w-16 rounded-full bg-gray-200" />
            <div className="space-y-2">
              <div className="h-5 w-48 rounded bg-gray-200" />
              <div className="h-4 w-32 rounded bg-gray-200" />
            </div>
          </div>
        </div>
      ) : profile ? (
        <div className="rounded-xl border border-dreams-border bg-white p-6 shadow-card">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="flex items-center gap-4">
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-dreams-blue text-xl font-bold text-white">
                {getInitials(profile.full_name)}
              </div>
              <div>
                <h1 className="text-2xl font-bold text-dreams-textPrimary">{profile.full_name}</h1>
                <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-sm text-dreams-textSecondary">
                  {profile.phone && <span>{profile.phone}</span>}
                  {profile.email && <span>{profile.email}</span>}
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center">
          <AlertCircle className="mx-auto h-6 w-6 text-red-500" />
          <p className="mt-2 text-sm font-medium text-red-800">Patient not found</p>
        </div>
      )}

      {/* Record Access Consent Banner */}
      {!consentLoading && (() => {
        const consent = consentData;
        const now = new Date();
        const isActive =
          consent?.status === "approved" &&
          consent.expires_at &&
          new Date(consent.expires_at) > now;
        const isPending = consent?.status === "pending";

        if (isActive) {
          return (
            <div className="flex items-center gap-3 rounded-xl border border-green-200 bg-green-50 px-4 py-3">
              <ShieldCheck className="h-5 w-5 shrink-0 text-green-600" />
              <p className="text-sm text-green-800">
                Full record access granted until{" "}
                <span className="font-medium">
                  {new Date(consent!.expires_at!).toLocaleDateString("en-IN", {
                    day: "numeric",
                    month: "short",
                    year: "numeric",
                  })}
                </span>.
              </p>
            </div>
          );
        }

        if (isPending) {
          return (
            <div className="flex items-center gap-3 rounded-xl border border-yellow-200 bg-yellow-50 px-4 py-3">
              <ShieldOff className="h-5 w-5 shrink-0 text-yellow-600" />
              <p className="text-sm text-yellow-800">
                Access request pending patient approval.
              </p>
            </div>
          );
        }

        return (
          <div className="flex flex-col gap-3 rounded-xl border border-dreams-border bg-dreams-lightBg px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <ShieldAlert className="h-5 w-5 shrink-0 text-dreams-textSecondary" />
              <p className="text-sm text-dreams-textSecondary">
                You are viewing your own records for this patient.
              </p>
            </div>
            <button
              onClick={() => setShowAccessModal(true)}
              className="shrink-0 rounded-lg bg-dreams-blue px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
            >
              Request Full Record Access
            </button>
          </div>
        );
      })()}

      {/* Medical Info */}
      {profile && (
        <div className="rounded-xl border border-dreams-border bg-white p-6 shadow-card">
          <div className="mb-4 flex items-center gap-2">
            <User className="h-4 w-4 text-dreams-textSecondary" />
            <h2 className="text-base font-semibold text-dreams-textPrimary">Medical Information</h2>
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div>
              <p className="text-xs text-dreams-textSecondary">Blood Group</p>
              {profile.blood_group ? (
                <Badge variant="inProgress" className="mt-1">
                  {profile.blood_group}
                </Badge>
              ) : (
                <p className="mt-1 text-sm text-dreams-textSecondary">Not recorded</p>
              )}
            </div>
            <div>
              <p className="text-xs text-dreams-textSecondary">Allergies</p>
              {profile.allergies && profile.allergies.length > 0 ? (
                <p className="mt-1 text-sm text-dreams-textPrimary">
                  {profile.allergies.join(", ")}
                </p>
              ) : (
                <p className="mt-1 text-sm text-dreams-textSecondary">None recorded</p>
              )}
            </div>
            <div>
              <p className="text-xs text-dreams-textSecondary">Chronic Conditions</p>
              {profile.chronic_conditions && profile.chronic_conditions.length > 0 ? (
                <p className="mt-1 text-sm text-dreams-textPrimary">
                  {profile.chronic_conditions.join(", ")}
                </p>
              ) : (
                <p className="mt-1 text-sm text-dreams-textSecondary">None recorded</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Vitals Panel (MD-255) */}
      <div className="rounded-xl border border-dreams-border bg-white p-6 shadow-card">
        <div className="mb-4 flex items-center gap-2">
          <Activity className="h-4 w-4 text-dreams-textSecondary" />
          <h2 className="text-base font-semibold text-dreams-textPrimary">Recent Vitals</h2>
          <span className="text-xs text-dreams-textSecondary">(last 7 days)</span>
        </div>
        {vitalsLoading ? (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-16 animate-pulse rounded-lg bg-gray-100" />
            ))}
          </div>
        ) : Object.keys(latestVitals).length === 0 ? (
          <div className="rounded-lg border border-dashed border-dreams-border p-4 text-center">
            <p className="text-sm text-dreams-textSecondary">No vitals recorded in the last 7 days</p>
            <p className="mt-1 text-xs text-dreams-textSecondary">
              Patient can add vitals from their portal
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {Object.entries(latestVitals).map(([type, reading]) => {
              const meta = VITAL_LABELS[type];
              return (
                <div
                  key={type}
                  className="rounded-lg border border-dreams-border bg-dreams-lightBg p-3"
                >
                  <p className="text-xs text-dreams-textSecondary">
                    {meta?.label || type}
                  </p>
                  <p className="mt-1 text-lg font-bold text-dreams-textPrimary">
                    {reading.value}
                    <span className="ml-1 text-xs font-normal text-dreams-textSecondary">
                      {meta?.unit || reading.unit}
                    </span>
                  </p>
                  <p className="mt-0.5 text-xs text-dreams-textSecondary">
                    {formatDate(reading.recorded_at)}
                  </p>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Recent Records */}
        <div className="rounded-xl border border-dreams-border bg-white p-6 shadow-card">
          <div className="mb-4 flex items-center gap-2">
            <FileText className="h-4 w-4 text-dreams-textSecondary" />
            <h2 className="text-base font-semibold text-dreams-textPrimary">Recent Records</h2>
          </div>
          {recordsLoading ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-14 animate-pulse rounded-lg bg-gray-100" />
              ))}
            </div>
          ) : recordsData?.data?.length === 0 ? (
            <p className="text-sm text-dreams-textSecondary">No records found.</p>
          ) : (
            <div className="space-y-2">
              {recordsData?.data?.map((record: any) => (
                <div
                  key={record.id}
                  className="rounded-lg border border-dreams-border p-3"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <p className="truncate text-sm font-medium text-dreams-textPrimary">
                          {record.title}
                        </p>
                        {record.amended_from_id && (
                          <span className="inline-flex items-center rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700 border border-amber-200">
                            Amendment
                          </span>
                        )}
                        {record.source === "amended" && !record.amended_from_id && (
                          <span className="inline-flex items-center rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700 border border-blue-200">
                            Amended
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-dreams-textSecondary">
                        {RECORD_TYPE_LABELS[record.record_type] || record.record_type} &middot;{" "}
                        {formatDate(record.created_at)}
                      </p>
                    </div>
                    {record.is_amendable && (
                      <button
                        onClick={() =>
                          setAmendTarget({
                            recordId: record.id,
                            title: record.title,
                            description: record.description || "",
                          })
                        }
                        className="shrink-0 flex items-center gap-1 rounded-lg border border-dreams-border px-2.5 py-1 text-xs font-medium text-dreams-textSecondary hover:bg-dreams-lightBg hover:text-dreams-textPrimary transition-colors"
                      >
                        <Edit2 className="h-3 w-3" />
                        Amend
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Active Medications */}
        <div className="rounded-xl border border-dreams-border bg-white p-6 shadow-card">
          <div className="mb-4 flex items-center gap-2">
            <Pill className="h-4 w-4 text-dreams-textSecondary" />
            <h2 className="text-base font-semibold text-dreams-textPrimary">Active Medications</h2>
            {latestPrescription && (
              <span className="text-xs text-dreams-textSecondary">
                (from {formatDate(latestPrescription.created_at)})
              </span>
            )}
          </div>
          {prescriptionsLoading ? (
            <div className="space-y-2">
              {[1, 2].map((i) => (
                <div key={i} className="h-8 animate-pulse rounded-lg bg-gray-100" />
              ))}
            </div>
          ) : activeMedicines.length === 0 ? (
            <p className="text-sm text-dreams-textSecondary">No active medications found.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {activeMedicines.map((name: string, idx: number) => (
                <span
                  key={idx}
                  className="rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-medium text-dreams-blue"
                >
                  {name}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Quick Actions */}
      <div className="rounded-xl border border-dreams-border bg-white p-6 shadow-card">
        <h2 className="mb-4 text-base font-semibold text-dreams-textPrimary">Quick Actions</h2>
        <div className="flex flex-wrap gap-3">
          <Link
            href={`/doctor/prescriptions/new?patientId=${patientId}`}
            className="flex items-center gap-2 rounded-lg bg-dreams-blue px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
          >
            <Pill className="h-4 w-4" />
            New Prescription
          </Link>
          <Link
            href={`/doctor/records/new?patient_id=${patientId}`}
            className="flex items-center gap-2 rounded-lg border border-dreams-border px-4 py-2 text-sm font-medium text-dreams-textPrimary hover:bg-dreams-lightBg transition-colors"
          >
            <FileText className="h-4 w-4" />
            New Record
          </Link>
          <Link
            href={`/doctor/patients/${patientId}/prescriptions`}
            className="flex items-center gap-2 rounded-lg border border-dreams-border px-4 py-2 text-sm font-medium text-dreams-textPrimary hover:bg-dreams-lightBg transition-colors"
          >
            <Activity className="h-4 w-4" />
            View All Records
          </Link>
        </div>
      </div>

      {/* Record Access Request Modal */}
      {showAccessModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-bold text-dreams-textPrimary">Request Full Record Access</h2>
              <button onClick={() => setShowAccessModal(false)} className="text-dreams-textSecondary hover:text-dreams-textPrimary">
                <X className="h-5 w-5" />
              </button>
            </div>
            <p className="mb-4 text-sm text-dreams-textSecondary">
              The patient will receive a notification and can approve or reject your request.
            </p>
            <div className="space-y-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">
                  Purpose (optional)
                </label>
                <input
                  type="text"
                  value={accessPurpose}
                  onChange={(e) => setAccessPurpose(e.target.value)}
                  placeholder="e.g. Continuity of care for ongoing treatment"
                  className="w-full rounded-lg border border-dreams-border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">
                  Access Duration
                </label>
                <select
                  value={accessDuration}
                  onChange={(e) => setAccessDuration(Number(e.target.value))}
                  className="w-full rounded-lg border border-dreams-border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
                >
                  <option value={7}>7 days</option>
                  <option value={14}>14 days</option>
                  <option value={30}>30 days</option>
                  <option value={90}>90 days</option>
                </select>
              </div>
            </div>
            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setShowAccessModal(false)}
                className="rounded-lg border border-dreams-border px-4 py-2 text-sm font-medium text-dreams-textPrimary hover:bg-dreams-lightBg transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={requestAccessMutation.isPending}
                onClick={() => requestAccessMutation.mutate()}
                className="rounded-lg bg-dreams-blue px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors disabled:opacity-50"
              >
                {requestAccessMutation.isPending ? "Sending..." : "Send Request"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Amend Record Modal */}
      {amendTarget && (
        <AmendModal
          initial={amendTarget}
          onClose={() => {
            setAmendTarget(null);
            setAmendError("");
          }}
          onSubmit={(data) => {
            setAmendError("");
            amendMutation.mutate(data);
          }}
          isPending={amendMutation.isPending}
        />
      )}
      {amendError && (
        <div className="fixed bottom-4 right-4 z-50 rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700 shadow-lg">
          {amendError}
        </div>
      )}
    </div>
  );
}
