"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { UserPlus, Users, CheckCircle, AlertCircle, Search } from "lucide-react";
import api from "@/lib/api";
import { useClinicStore } from "@/stores/clinic-store";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { Badge } from "@/components/ui/badge";

interface LinkedPatient {
  link_id: string;
  patient_id: string;
  full_name: string;
  email: string;
  phone: string | null;
  consent_status: "pending" | "approved" | "revoked";
  linked_at: string;
}

export default function LinkPatientPage() {
  const { activeClinicId } = useClinicStore();
  const queryClient = useQueryClient();

  const [code, setCode] = useState("");
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const { data: patientsData, isLoading: patientsLoading } = useQuery<{ data: LinkedPatient[]; total: number }>({
    queryKey: ["clinic-patients", activeClinicId],
    queryFn: () =>
      api
        .get(`/api/v1/clinics/${activeClinicId}/patients`, { params: { consent_only: false } })
        .then((r) => r.data),
    enabled: !!activeClinicId,
  });

  const linkMutation = useMutation({
    mutationFn: (linkCode: string) =>
      api
        .post(`/api/v1/clinics/${activeClinicId}/link-patient`, { code: linkCode })
        .then((r) => r.data),
    onSuccess: (data) => {
      setSuccessMsg(`${data.patient_name ?? "Patient"} linked successfully. Awaiting their consent.`);
      setErrorMsg(null);
      setCode("");
      queryClient.invalidateQueries({ queryKey: ["clinic-patients", activeClinicId] });
    },
    onError: (err: any) => {
      const code = err?.response?.data?.error?.code;
      const messages: Record<string, string> = {
        INVALID_CODE: "Invalid link code. Please check with the patient.",
        EXPIRED_CODE: "This link code has expired. Ask the patient to share their current code.",
        ALREADY_LINKED: "This patient is already linked to this clinic.",
        NOT_CLINIC_MEMBER: "You are not a member of this clinic.",
        FORBIDDEN: "Only doctors can link patients.",
      };
      setErrorMsg(messages[code] ?? "Something went wrong. Please try again.");
      setSuccessMsg(null);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!code.trim() || !activeClinicId) return;
    linkMutation.mutate(code.trim().toUpperCase());
  };

  const patients: LinkedPatient[] = patientsData?.data ?? [];
  const pendingCount = patients.filter((p) => p.consent_status === "pending").length;
  const approvedCount = patients.filter((p) => p.consent_status === "approved").length;

  return (
    <div className="space-y-6">
      <Breadcrumb
        items={[
          { label: "Dashboard", href: "/doctor/dashboard" },
          { label: "Link Patient" },
        ]}
      />

      <div>
        <h1 className="text-2xl font-bold text-dreams-textPrimary">Link Patient</h1>
        <p className="mt-1 text-sm text-dreams-textSecondary">
          Enter a patient's link code to connect them to your clinic.
        </p>
      </div>

      {!activeClinicId ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-6 text-center">
          <AlertCircle className="mx-auto h-6 w-6 text-amber-500" />
          <p className="mt-2 text-sm font-medium text-amber-800">No clinic selected</p>
          <p className="mt-1 text-xs text-amber-700">
            Select a clinic from the header dropdown before linking patients.
          </p>
        </div>
      ) : (
        <>
          {/* Link Code Form */}
          <div className="rounded-xl border border-dreams-border bg-white p-6 shadow-card">
            <h2 className="mb-4 font-semibold text-dreams-textPrimary">Enter Patient Link Code</h2>
            <form onSubmit={handleSubmit} className="flex gap-3">
              <input
                type="text"
                value={code}
                onChange={(e) => setCode(e.target.value.toUpperCase())}
                placeholder="e.g. AB3X7YZ2K9"
                maxLength={10}
                className="flex-1 rounded-lg border border-dreams-border px-4 py-2.5 font-mono text-sm tracking-widest uppercase placeholder:normal-case placeholder:tracking-normal focus:outline-none focus:ring-2 focus:ring-dreams-blue"
              />
              <button
                type="submit"
                disabled={linkMutation.isPending || code.length < 10}
                className="flex items-center gap-2 rounded-lg bg-dreams-blue px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              >
                <UserPlus className="h-4 w-4" />
                {linkMutation.isPending ? "Linking..." : "Link Patient"}
              </button>
            </form>

            {successMsg && (
              <div className="mt-4 flex items-start gap-2 rounded-lg bg-green-50 p-3 text-sm text-green-800">
                <CheckCircle className="h-4 w-4 mt-0.5 flex-shrink-0 text-green-600" />
                {successMsg}
              </div>
            )}
            {errorMsg && (
              <div className="mt-4 flex items-start gap-2 rounded-lg bg-red-50 p-3 text-sm text-red-800">
                <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0 text-red-500" />
                {errorMsg}
              </div>
            )}
          </div>

          {/* Stats */}
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            {[
              { label: "Total Linked", value: patients.length },
              { label: "Consent Approved", value: approvedCount },
              { label: "Awaiting Consent", value: pendingCount },
            ].map(({ label, value }) => (
              <div key={label} className="rounded-xl border border-dreams-border bg-white p-4 shadow-card">
                <p className="text-2xl font-bold text-dreams-textPrimary">{value}</p>
                <p className="text-sm text-dreams-textSecondary">{label}</p>
              </div>
            ))}
          </div>

          {/* Patients List */}
          <div>
            <h2 className="mb-3 text-lg font-semibold text-dreams-textPrimary">
              Linked Patients
            </h2>

            {patientsLoading ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-16 animate-pulse rounded-xl bg-gray-100" />
                ))}
              </div>
            ) : patients.length === 0 ? (
              <div className="rounded-xl border border-dreams-border bg-white p-8 text-center shadow-card">
                <Users className="mx-auto h-8 w-8 text-dreams-textSecondary" />
                <p className="mt-2 text-sm text-dreams-textSecondary">No patients linked yet</p>
              </div>
            ) : (
              <div className="space-y-2">
                {patients.map((patient) => (
                  <div
                    key={patient.link_id}
                    className="flex items-center justify-between rounded-xl border border-dreams-border bg-white px-4 py-3 shadow-card"
                  >
                    <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 items-center justify-center rounded-full bg-blue-100 text-sm font-semibold text-dreams-blue">
                        {patient.full_name.charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <p className="font-medium text-dreams-textPrimary">{patient.full_name}</p>
                        <p className="text-xs text-dreams-textSecondary">{patient.email}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <p className="text-xs text-dreams-textSecondary">
                        {new Date(patient.linked_at).toLocaleDateString()}
                      </p>
                      <Badge
                        variant={
                          patient.consent_status === "approved"
                            ? "completed"
                            : patient.consent_status === "revoked"
                            ? "overdue"
                            : "pending"
                        }
                      >
                        {patient.consent_status}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
