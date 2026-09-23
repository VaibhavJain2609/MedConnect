"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Building2, MapPin, Phone, Mail, Users, FileText, Pill, ArrowLeft, Settings, Stethoscope, UserCheck, Hourglass, Calendar, Clock } from "lucide-react";
import { getAdminClinic, updateAdminClinic, deleteAdminClinic, getClinicMetrics } from "@/lib/api/clinics";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { Badge } from "@/components/ui/badge";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";

export default function AdminClinicDetailPage() {
  const t = useTranslations("adminClinics");
  const td = useTranslations("adminClinics.detail");
  const tStatus = useTranslations("statusBadge");
  const tCommon = useTranslations("common");
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [editMode, setEditMode] = useState(false);
  const [editData, setEditData] = useState<Record<string, string>>({});

  const { data: clinic, isLoading } = useQuery({
    queryKey: ["admin-clinic", id],
    queryFn: () => getAdminClinic(id),
  });

  const { data: metrics } = useQuery({
    queryKey: ["admin-clinic-metrics", id],
    queryFn: () => getClinicMetrics(id),
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
          { label: t("breadcrumbDashboard"), href: "/admin/dashboard" },
          { label: t("breadcrumb"), href: "/admin/clinics" },
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
            {editMode ? tCommon("cancel") : td("edit")}
          </button>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <button className="rounded-lg bg-red-50 px-4 py-2 text-sm text-red-600 hover:bg-red-100">
                {td("delete")}
              </button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>{td("deleteTitle")}</AlertDialogTitle>
                <AlertDialogDescription>
                  {td("deleteDesc", { name: clinic.name })}
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>{tCommon("cancel")}</AlertDialogCancel>
                <AlertDialogAction
                  onClick={() => deleteMutation.mutate()}
                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                  disabled={deleteMutation.isPending}
                >
                  {deleteMutation.isPending ? td("deleting") : td("delete")}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {[
          { label: td("stats.members"), value: clinic.member_count, icon: Users, color: "blue" },
          { label: td("stats.records"), value: clinic.record_count, icon: FileText, color: "green" },
          { label: td("stats.prescriptions"), value: clinic.prescription_count, icon: Pill, color: "purple" },
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

      {/* Usage metrics */}
      {metrics && (
        <div>
          <h2 className="mb-4 text-base font-semibold text-dreams-textPrimary">{td("metricsTitle")}</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            {[
              { label: td("metrics.doctors"), value: metrics.members.doctors, icon: Stethoscope, color: "blue" },
              { label: td("metrics.patientsLinked"), value: metrics.patients.approved, icon: UserCheck, color: "green" },
              { label: td("metrics.pendingLinks"), value: metrics.patients.pending, icon: Hourglass, color: "amber" },
              { label: td("metrics.appointments30d"), value: metrics.appointments.last_30d, icon: Calendar, color: "purple" },
              { label: td("metrics.inQueueToday"), value: metrics.queue_today.waiting + metrics.queue_today.in_consultation, icon: Clock, color: "orange" },
              { label: td("metrics.branches"), value: metrics.branches, icon: Building2, color: "teal" },
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
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Clinic Info */}
        <div className="rounded-xl border border-dreams-border bg-white p-6 shadow-card">
          <h2 className="mb-4 text-base font-semibold text-dreams-textPrimary">{td("infoTitle")}</h2>
          {editMode ? (
            <div className="space-y-3">
              {[
                { key: "name", label: td("fields.name"), defaultValue: clinic.name },
                { key: "address", label: td("fields.address"), defaultValue: clinic.address ?? "" },
                { key: "city", label: td("fields.city"), defaultValue: clinic.city ?? "" },
                { key: "state", label: td("fields.state"), defaultValue: clinic.state ?? "" },
                { key: "phone", label: td("fields.phone"), defaultValue: clinic.phone ?? "" },
                { key: "email", label: td("fields.email"), defaultValue: clinic.email ?? "" },
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
                {updateMutation.isPending ? td("saving") : td("saveChanges")}
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {[
                { icon: Building2, label: td("fields.name"), value: clinic.name },
                { icon: MapPin, label: td("fields.address"), value: [clinic.address, clinic.city, clinic.state].filter(Boolean).join(", ") || "—" },
                { icon: Phone, label: td("fields.phone"), value: clinic.phone ?? "—" },
                { icon: Mail, label: td("fields.email"), value: clinic.email ?? "—" },
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
                <p className="text-xs text-dreams-textSecondary mb-1">{td("recordSharing")}</p>
                <span className="rounded-full bg-blue-50 px-3 py-1 text-xs text-dreams-blue font-medium">
                  {clinic.record_sharing_mode === "per_clinic" ? t("sharing.perClinic") : t("sharing.perDoctor")}
                </span>
              </div>
              <div>
                <p className="text-xs text-dreams-textSecondary mb-1">{t("table.status")}</p>
                <Badge variant={clinic.is_active ? "completed" : "overdue"}>
                  {clinic.is_active ? tStatus("active") : tStatus("inactive")}
                </Badge>
              </div>
            </div>
          )}
        </div>

        {/* Branches */}
        <div className="rounded-xl border border-dreams-border bg-white p-6 shadow-card">
          <h2 className="mb-4 text-base font-semibold text-dreams-textPrimary">
            {td("branchesTitle", { count: clinic.branches.length })}
          </h2>
          {clinic.branches.length === 0 ? (
            <p className="text-sm text-dreams-textSecondary">{td("noBranches")}</p>
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
