"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Building2, MapPin, Phone, Mail, Users, FileText, Pill, ArrowLeft, Settings } from "lucide-react";
import { getAdminClinic, updateAdminClinic, deleteAdminClinic } from "@/lib/api/clinics";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { Badge } from "@/components/ui/badge";

export default function AdminClinicDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [editMode, setEditMode] = useState(false);
  const [editData, setEditData] = useState<Record<string, string>>({});

  const { data: clinic, isLoading } = useQuery({
    queryKey: ["admin-clinic", id],
    queryFn: () => getAdminClinic(id),
  });

  const updateMutation = useMutation({
    mutationFn: (data: Record<string, string>) => updateAdminClinic(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-clinic", id] });
      setEditMode(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteAdminClinic(id),
    onSuccess: () => router.push("/admin/clinics"),
  });

  if (isLoading || !clinic) {
    return (
      <div className="flex justify-center py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-200 border-t-dreams-blue" />
      </div>
    );
  }

  const handleEditSave = () => {
    updateMutation.mutate(editData);
  };

  return (
    <div className="space-y-6">
      <Breadcrumb
        items={[
          { label: "Dashboard", href: "/admin/dashboard" },
          { label: "Clinics", href: "/admin/clinics" },
          { label: clinic.name },
        ]}
      />

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.push("/admin/clinics")}
            className="rounded-lg border border-dreams-border p-2 hover:bg-gray-50"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div>
            <h1 className="text-2xl font-bold text-dreams-textPrimary">{clinic.name}</h1>
            <p className="text-sm text-dreams-textSecondary">
              {[clinic.city, clinic.state].filter(Boolean).join(", ")}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => { setEditMode(!editMode); setEditData({}); }}
            className="flex items-center gap-2 rounded-lg border border-dreams-border px-4 py-2 text-sm hover:bg-gray-50"
          >
            <Settings className="h-4 w-4" />
            {editMode ? "Cancel" : "Edit"}
          </button>
          <button
            onClick={() => {
              if (confirm(`Delete clinic "${clinic.name}"? This cannot be undone.`)) {
                deleteMutation.mutate();
              }
            }}
            className="rounded-lg bg-red-50 px-4 py-2 text-sm text-red-600 hover:bg-red-100"
          >
            Delete
          </button>
        </div>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {[
          { label: "Members", value: clinic.member_count, icon: Users, color: "blue" },
          { label: "Records", value: clinic.record_count, icon: FileText, color: "green" },
          { label: "Prescriptions", value: clinic.prescription_count, icon: Pill, color: "purple" },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="rounded-xl border border-dreams-border bg-white p-5 shadow-card">
            <div className="flex items-center gap-3">
              <div className={`flex h-10 w-10 items-center justify-center rounded-lg bg-${color}-50`}>
                <Icon className={`h-5 w-5 text-${color}-600`} />
              </div>
              <div>
                <p className="text-2xl font-bold text-dreams-textPrimary">{value}</p>
                <p className="text-sm text-dreams-textSecondary">{label}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Clinic Info */}
        <div className="rounded-xl border border-dreams-border bg-white p-6 shadow-card">
          <h2 className="mb-4 text-base font-semibold text-dreams-textPrimary">Clinic Information</h2>
          {editMode ? (
            <div className="space-y-3">
              {[
                { key: "name", label: "Name", defaultValue: clinic.name },
                { key: "address", label: "Address", defaultValue: clinic.address ?? "" },
                { key: "city", label: "City", defaultValue: clinic.city ?? "" },
                { key: "state", label: "State", defaultValue: clinic.state ?? "" },
                { key: "phone", label: "Phone", defaultValue: clinic.phone ?? "" },
                { key: "email", label: "Email", defaultValue: clinic.email ?? "" },
              ].map(({ key, label, defaultValue }) => (
                <div key={key}>
                  <label className="mb-1 block text-xs font-medium text-dreams-textSecondary">{label}</label>
                  <input
                    type="text"
                    defaultValue={defaultValue}
                    onChange={(e) => setEditData((d) => ({ ...d, [key]: e.target.value }))}
                    className="w-full rounded-lg border border-dreams-border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
                  />
                </div>
              ))}
              <button
                onClick={handleEditSave}
                disabled={updateMutation.isPending}
                className="mt-2 w-full rounded-lg bg-dreams-blue px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {updateMutation.isPending ? "Saving..." : "Save Changes"}
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {[
                { icon: Building2, label: "Name", value: clinic.name },
                { icon: MapPin, label: "Address", value: [clinic.address, clinic.city, clinic.state].filter(Boolean).join(", ") || "—" },
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
              <div className="pt-2 border-t border-dreams-border">
                <p className="text-xs text-dreams-textSecondary mb-1">Record Sharing</p>
                <span className="rounded-full bg-blue-50 px-3 py-1 text-xs text-dreams-blue font-medium">
                  {clinic.record_sharing_mode === "per_clinic" ? "Per Clinic" : "Per Doctor"}
                </span>
              </div>
              <div>
                <p className="text-xs text-dreams-textSecondary mb-1">Status</p>
                <Badge variant={clinic.is_active ? "completed" : "overdue"}>
                  {clinic.is_active ? "Active" : "Inactive"}
                </Badge>
              </div>
            </div>
          )}
        </div>

        {/* Branches */}
        <div className="rounded-xl border border-dreams-border bg-white p-6 shadow-card">
          <h2 className="mb-4 text-base font-semibold text-dreams-textPrimary">
            Branches ({clinic.branches.length})
          </h2>
          {clinic.branches.length === 0 ? (
            <p className="text-sm text-dreams-textSecondary">No branches</p>
          ) : (
            <div className="space-y-3">
              {clinic.branches.map((branch) => (
                <div
                  key={branch.id}
                  className="rounded-lg border border-dreams-border p-3"
                >
                  <p className="font-medium text-sm text-dreams-textPrimary">{branch.name}</p>
                  {branch.city && (
                    <p className="text-xs text-dreams-textSecondary mt-1">
                      <MapPin className="inline h-3 w-3 mr-1" />
                      {[branch.city, branch.state].filter(Boolean).join(", ")}
                    </p>
                  )}
                  {branch.phone && (
                    <p className="text-xs text-dreams-textSecondary">
                      <Phone className="inline h-3 w-3 mr-1" />
                      {branch.phone}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
