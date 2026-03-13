"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Building2,
  Users,
  MapPin,
  Phone,
  Mail,
  GitBranch,
  Settings,
  Plus,
} from "lucide-react";
import {
  getClinic,
  getClinicMembers,
  createBranch,
  updateClinicSettings,
  type ClinicMember,
} from "@/lib/api/clinics";
import { useClinicStore } from "@/stores/clinic-store";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { Badge } from "@/components/ui/badge";

export default function DoctorClinicPage() {
  const { activeClinicId } = useClinicStore();
  const queryClient = useQueryClient();
  const [showBranchForm, setShowBranchForm] = useState(false);
  const [branchName, setBranchName] = useState("");

  const { data: clinic, isLoading: clinicLoading } = useQuery({
    queryKey: ["clinic", activeClinicId],
    queryFn: () => getClinic(activeClinicId!),
    enabled: !!activeClinicId,
  });

  const { data: membersData } = useQuery({
    queryKey: ["clinic-members", activeClinicId],
    queryFn: () => getClinicMembers(activeClinicId!),
    enabled: !!activeClinicId,
  });

  const createBranchMutation = useMutation({
    mutationFn: () => createBranch(activeClinicId!, { name: branchName }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["clinic", activeClinicId] });
      setBranchName("");
      setShowBranchForm(false);
    },
  });

  const toggleSharingMutation = useMutation({
    mutationFn: (mode: "per_clinic" | "per_doctor") =>
      updateClinicSettings(activeClinicId!, mode),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["clinic", activeClinicId] });
    },
  });

  if (!activeClinicId) {
    return (
      <div className="space-y-6">
        <Breadcrumb items={[{ label: "Dashboard", href: "/doctor/dashboard" }, { label: "My Clinic" }]} />
        <div className="rounded-xl border border-dreams-border bg-white p-12 text-center shadow-card">
          <Building2 className="mx-auto h-12 w-12 text-dreams-textSecondary" />
          <h2 className="mt-4 text-lg font-semibold text-dreams-textPrimary">No Clinic Selected</h2>
          <p className="mt-2 text-sm text-dreams-textSecondary">
            You are not a member of any clinic yet. Complete onboarding to create or join one.
          </p>
        </div>
      </div>
    );
  }

  if (clinicLoading || !clinic) {
    return (
      <div className="flex justify-center py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-200 border-t-dreams-blue" />
      </div>
    );
  }

  const members: ClinicMember[] = membersData?.data ?? [];
  const roleBadge: Record<string, string> = { owner: "overdue", admin: "inProgress", doctor: "completed" };

  return (
    <div className="space-y-6">
      <Breadcrumb
        items={[
          { label: "Dashboard", href: "/doctor/dashboard" },
          { label: "My Clinic" },
        ]}
      />

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-dreams-textPrimary">{clinic.name}</h1>
          <p className="text-sm text-dreams-textSecondary mt-1">
            {[clinic.city, clinic.state].filter(Boolean).join(", ")}
          </p>
        </div>
        <Badge variant={clinic.is_active ? "completed" : "overdue"}>
          {clinic.is_active ? "Active" : "Inactive"}
        </Badge>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Clinic Info */}
        <div className="lg:col-span-2 space-y-6">
          <div className="rounded-xl border border-dreams-border bg-white p-6 shadow-card">
            <h2 className="mb-4 text-base font-semibold text-dreams-textPrimary">Clinic Details</h2>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {[
                { icon: MapPin, label: "Address", value: clinic.address ?? "—" },
                { icon: Phone, label: "Phone", value: clinic.phone ?? "—" },
                { icon: Mail, label: "Email", value: clinic.email ?? "—" },
              ].map(({ icon: Icon, label, value }) => (
                <div key={label} className="flex items-start gap-3">
                  <Icon className="mt-0.5 h-4 w-4 shrink-0 text-dreams-textSecondary" />
                  <div>
                    <p className="text-xs text-dreams-textSecondary">{label}</p>
                    <p className="text-sm text-dreams-textPrimary">{value}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Members */}
          <div className="rounded-xl border border-dreams-border bg-white p-6 shadow-card">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-base font-semibold text-dreams-textPrimary">
                Members ({members.length})
              </h2>
              <Users className="h-4 w-4 text-dreams-textSecondary" />
            </div>
            <div className="space-y-3">
              {members.map((member) => (
                <div
                  key={member.id}
                  className="flex items-center justify-between rounded-lg border border-dreams-border p-3"
                >
                  <div>
                    <p className="text-sm font-medium text-dreams-textPrimary">{member.full_name}</p>
                    {member.email && (
                      <p className="text-xs text-dreams-textSecondary">{member.email}</p>
                    )}
                  </div>
                  <Badge variant={roleBadge[member.role] as any ?? "completed"}>
                    {member.role}
                  </Badge>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Settings sidebar */}
        <div className="space-y-6">
          {/* Record Sharing */}
          <div className="rounded-xl border border-dreams-border bg-white p-5 shadow-card">
            <div className="mb-3 flex items-center gap-2">
              <Settings className="h-4 w-4 text-dreams-textSecondary" />
              <h2 className="text-sm font-semibold text-dreams-textPrimary">Record Sharing</h2>
            </div>
            <p className="mb-3 text-xs text-dreams-textSecondary">
              Controls which records doctors in this clinic can see.
            </p>
            <div className="space-y-2">
              {(["per_clinic", "per_doctor"] as const).map((mode) => (
                <button
                  key={mode}
                  onClick={() => toggleSharingMutation.mutate(mode)}
                  disabled={toggleSharingMutation.isPending}
                  className={`w-full rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
                    clinic.record_sharing_mode === mode
                      ? "border-dreams-blue bg-blue-50 text-dreams-blue"
                      : "border-dreams-border bg-white text-dreams-textPrimary hover:bg-gray-50"
                  }`}
                >
                  <p className="font-medium">
                    {mode === "per_clinic" ? "Per Clinic" : "Per Doctor"}
                  </p>
                  <p className="text-xs opacity-70">
                    {mode === "per_clinic"
                      ? "All doctors see all clinic records"
                      : "Doctors see only their own records"}
                  </p>
                </button>
              ))}
            </div>
          </div>

          {/* Branches */}
          <div className="rounded-xl border border-dreams-border bg-white p-5 shadow-card">
            <div className="mb-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <GitBranch className="h-4 w-4 text-dreams-textSecondary" />
                <h2 className="text-sm font-semibold text-dreams-textPrimary">Branches</h2>
              </div>
              <button
                onClick={() => setShowBranchForm(!showBranchForm)}
                className="rounded-lg p-1 hover:bg-gray-100"
              >
                <Plus className="h-4 w-4 text-dreams-textSecondary" />
              </button>
            </div>

            {showBranchForm && (
              <div className="mb-3 flex gap-2">
                <input
                  type="text"
                  value={branchName}
                  onChange={(e) => setBranchName(e.target.value)}
                  placeholder="Branch name"
                  className="flex-1 rounded-lg border border-dreams-border px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-dreams-blue"
                />
                <button
                  onClick={() => createBranchMutation.mutate()}
                  disabled={!branchName || createBranchMutation.isPending}
                  className="rounded-lg bg-dreams-blue px-3 py-1.5 text-xs text-white disabled:opacity-50"
                >
                  Add
                </button>
              </div>
            )}

            <p className="text-xs text-dreams-textSecondary">
              Branches are managed via clinic settings.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
