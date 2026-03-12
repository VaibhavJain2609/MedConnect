"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Mail,
  Phone,
  Globe,
  Droplets,
  PhoneCall,
  Building2,
  Stethoscope,
  FileText,
  Pill,
  CalendarDays,
  ShieldCheck,
  Activity,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import {
  getAdminUser,
  getAdminUserPrescriptions,
  getAdminUserRecords,
  toggleUserActive,
} from "@/lib/api/admin-users";
import { useAuthStore } from "@/stores/auth-store";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";

const roleBadgeVariant: Record<string, string> = {
  admin: "overdue",
  doctor: "inProgress",
  patient: "completed",
};

const roleLabel: Record<string, string> = {
  admin: "Admin",
  doctor: "Doctor",
  patient: "Patient",
};

const recordTypeBadge: Record<string, string> = {
  lab_result: "inProgress",
  prescription: "completed",
  imaging: "upcoming",
  clinical_note: "pending",
  discharge_summary: "overdue",
};

type Tab = "overview" | "prescriptions" | "records";

export default function AdminUserDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user: currentUser } = useAuthStore();
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [rxPage, setRxPage] = useState(1);
  const [recPage, setRecPage] = useState(1);

  const { data: user, isLoading, error } = useQuery({
    queryKey: ["admin-user", id],
    queryFn: () => getAdminUser(id),
    enabled: !!id,
  });

  const { data: prescriptions } = useQuery({
    queryKey: ["admin-user-prescriptions", id, rxPage],
    queryFn: () => getAdminUserPrescriptions(id, { page: rxPage, limit: 20 }),
    enabled: !!id && activeTab === "prescriptions" && user?.role === "patient",
  });

  const { data: records } = useQuery({
    queryKey: ["admin-user-records", id, recPage],
    queryFn: () => getAdminUserRecords(id, { page: recPage, limit: 20 }),
    enabled: !!id && activeTab === "records" && user?.role === "patient",
  });

  const { mutate: toggleActive, isPending: isToggling } = useMutation({
    mutationFn: () => toggleUserActive(id, !user!.is_active),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-user", id] });
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
  });

  const isSelf = currentUser?.id === id;
  const isPatient = user?.role === "patient";

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
      </div>
    );
  }

  if (error || !user) {
    return (
      <div className="flex flex-col items-center justify-center py-12 space-y-4">
        <p className="text-red-600 font-medium">Failed to load user</p>
        <p className="text-dreams-textSecondary text-sm">
          {error instanceof Error ? error.message : "User not found"}
        </p>
      </div>
    );
  }

  const tabs: { id: Tab; label: string }[] = isPatient
    ? [
        { id: "overview", label: "Overview" },
        { id: "prescriptions", label: `Prescriptions (${user.prescriptions_count})` },
        { id: "records", label: `Medical Records (${user.records_count})` },
      ]
    : [{ id: "overview", label: "Overview" }];

  return (
    <div className="space-y-6">
      <Breadcrumb
        items={[
          { label: "Users", href: "/admin/users" },
          { label: user.full_name },
        ]}
      />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={() => router.push("/admin/users")}
            className="p-2 rounded-lg hover:bg-dreams-lightBg transition-colors text-dreams-textSecondary"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-dreams-textPrimary">
                {user.full_name}
              </h1>
              <Badge variant={roleBadgeVariant[user.role] as any}>
                {roleLabel[user.role] ?? user.role}
              </Badge>
              <Badge variant={user.is_active ? "completed" : "pending"}>
                {user.is_active ? "Active" : "Inactive"}
              </Badge>
            </div>
            <div className="flex items-center gap-4 mt-0.5">
              <p className="text-dreams-textSecondary text-sm">
                Member since {new Date(user.created_at).toLocaleDateString()}
              </p>
              {user.last_visit && (
                <p className="text-dreams-textSecondary text-sm">
                  Last visit {new Date(user.last_visit).toLocaleDateString()}
                </p>
              )}
            </div>
          </div>
        </div>

        {!isSelf && (
          <button
            onClick={() => toggleActive()}
            disabled={isToggling}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 ${
              user.is_active
                ? "bg-red-50 text-red-600 hover:bg-red-100 border border-red-200"
                : "bg-green-50 text-green-700 hover:bg-green-100 border border-green-200"
            }`}
          >
            {isToggling
              ? "Updating..."
              : user.is_active
              ? "Deactivate User"
              : "Activate User"}
          </button>
        )}
      </div>

      {/* Tabs (patients only) */}
      {isPatient && (
        <div className="border-b border-dreams-border">
          <nav className="flex gap-1">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? "border-dreams-blue text-dreams-blue"
                    : "border-transparent text-dreams-textSecondary hover:text-dreams-textPrimary"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </nav>
        </div>
      )}

      {/* Overview Tab */}
      {activeTab === "overview" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Profile + Health */}
          <div className="lg:col-span-2 space-y-6">
            {/* Profile Card */}
            <div className="bg-white rounded-xl border border-dreams-border p-6 shadow-card space-y-6">
              <div className="flex items-start gap-4">
                <Avatar fallback={user.full_name} size="xl" />
                <div className="space-y-2 flex-1">
                  <h2 className="text-lg font-semibold text-dreams-textPrimary">
                    {user.full_name}
                  </h2>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
                    <div className="flex items-center gap-2 text-dreams-textSecondary">
                      <Mail className="h-4 w-4 flex-shrink-0" />
                      <span>{user.email ?? "—"}</span>
                    </div>
                    <div className="flex items-center gap-2 text-dreams-textSecondary">
                      <Phone className="h-4 w-4 flex-shrink-0" />
                      <span>{user.phone ?? "—"}</span>
                    </div>
                    <div className="flex items-center gap-2 text-dreams-textSecondary">
                      <Globe className="h-4 w-4 flex-shrink-0" />
                      <span>Language: {user.language_pref.toUpperCase()}</span>
                    </div>
                    <div className="flex items-center gap-2 text-dreams-textSecondary">
                      <Droplets className="h-4 w-4 flex-shrink-0" />
                      <span>Blood Group: {user.blood_group ?? "—"}</span>
                    </div>
                  </div>
                </div>
              </div>

              {(user.emergency_contact_name || user.emergency_contact_phone) && (
                <div className="border-t border-dreams-border pt-4">
                  <p className="text-xs font-semibold text-dreams-textSecondary uppercase tracking-wider mb-3">
                    Emergency Contact
                  </p>
                  <div className="flex items-center gap-4 text-sm text-dreams-textSecondary">
                    <span>{user.emergency_contact_name ?? "—"}</span>
                    <div className="flex items-center gap-1">
                      <PhoneCall className="h-4 w-4" />
                      <span>{user.emergency_contact_phone ?? "—"}</span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Patient Vitals + Health Info */}
            {isPatient && (
              <>
                {(user.height_cm || user.weight_kg) && (
                  <div className="bg-white rounded-xl border border-dreams-border p-6 shadow-card">
                    <div className="flex items-center gap-2 mb-4">
                      <Activity className="h-5 w-5 text-dreams-blue" />
                      <h2 className="text-base font-semibold text-dreams-textPrimary">
                        Vitals
                      </h2>
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                      {user.height_cm && (
                        <div className="bg-dreams-lightBg rounded-lg p-3 text-center">
                          <p className="text-xs text-dreams-textSecondary mb-1">Height</p>
                          <p className="text-lg font-bold text-dreams-textPrimary">
                            {user.height_cm}
                          </p>
                          <p className="text-xs text-dreams-textSecondary">cm</p>
                        </div>
                      )}
                      {user.weight_kg && (
                        <div className="bg-dreams-lightBg rounded-lg p-3 text-center">
                          <p className="text-xs text-dreams-textSecondary mb-1">Weight</p>
                          <p className="text-lg font-bold text-dreams-textPrimary">
                            {user.weight_kg}
                          </p>
                          <p className="text-xs text-dreams-textSecondary">kg</p>
                        </div>
                      )}
                      {user.height_cm && user.weight_kg && (
                        <div className="bg-dreams-lightBg rounded-lg p-3 text-center">
                          <p className="text-xs text-dreams-textSecondary mb-1">BMI</p>
                          <p className="text-lg font-bold text-dreams-textPrimary">
                            {(user.weight_kg / Math.pow(user.height_cm / 100, 2)).toFixed(1)}
                          </p>
                          <p className="text-xs text-dreams-textSecondary">kg/m²</p>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {((user.allergies && user.allergies.length > 0) ||
                  (user.chronic_conditions && user.chronic_conditions.length > 0)) && (
                  <div className="bg-white rounded-xl border border-dreams-border p-6 shadow-card space-y-4">
                    <h2 className="text-base font-semibold text-dreams-textPrimary">
                      Health Information
                    </h2>
                    {user.allergies && user.allergies.length > 0 && (
                      <div>
                        <p className="text-xs font-semibold text-dreams-textSecondary uppercase tracking-wider mb-2">
                          Allergies
                        </p>
                        <div className="flex flex-wrap gap-2">
                          {user.allergies.map((a) => (
                            <span
                              key={a}
                              className="px-2.5 py-1 rounded-full text-xs font-medium bg-red-50 text-red-700 border border-red-200"
                            >
                              {a}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                    {user.chronic_conditions && user.chronic_conditions.length > 0 && (
                      <div>
                        <p className="text-xs font-semibold text-dreams-textSecondary uppercase tracking-wider mb-2">
                          Chronic Conditions
                        </p>
                        <div className="flex flex-wrap gap-2">
                          {user.chronic_conditions.map((c) => (
                            <span
                              key={c}
                              className="px-2.5 py-1 rounded-full text-xs font-medium bg-orange-50 text-orange-700 border border-orange-200"
                            >
                              {c}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </>
            )}

            {/* Doctor Profile */}
            {user.doctor_profile && (
              <div className="bg-white rounded-xl border border-dreams-border p-6 shadow-card">
                <div className="flex items-center gap-2 mb-4">
                  <Stethoscope className="h-5 w-5 text-dreams-blue" />
                  <h2 className="text-base font-semibold text-dreams-textPrimary">
                    Doctor Profile
                  </h2>
                  {user.doctor_profile.verified && (
                    <div className="flex items-center gap-1 ml-2 text-green-600 text-xs font-medium">
                      <ShieldCheck className="h-4 w-4" />
                      Verified
                    </div>
                  )}
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
                  <div>
                    <p className="text-dreams-textSecondary text-xs uppercase tracking-wider mb-1">
                      Specialization
                    </p>
                    <p className="text-dreams-textPrimary font-medium">
                      {user.doctor_profile.specialization ?? "—"}
                    </p>
                  </div>
                  <div>
                    <p className="text-dreams-textSecondary text-xs uppercase tracking-wider mb-1">
                      License Number
                    </p>
                    <p className="text-dreams-textPrimary font-medium">
                      {user.doctor_profile.license_number ?? "—"}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Building2 className="h-4 w-4 text-dreams-textSecondary" />
                    <div>
                      <p className="text-dreams-textPrimary font-medium">
                        {user.doctor_profile.facility_name ?? "—"}
                      </p>
                      {user.doctor_profile.facility_city && (
                        <p className="text-dreams-textSecondary text-xs">
                          {user.doctor_profile.facility_city}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Stats Sidebar */}
          <div className="space-y-4">
            <div className="bg-white rounded-xl border border-dreams-border p-5 shadow-card">
              <div className="flex items-center gap-3 mb-2">
                <FileText className="h-5 w-5 text-dreams-blue" />
                <p className="text-sm text-dreams-textSecondary">Medical Records</p>
              </div>
              <p className="text-3xl font-bold text-dreams-textPrimary">
                {user.records_count}
              </p>
            </div>

            <div className="bg-white rounded-xl border border-dreams-border p-5 shadow-card">
              <div className="flex items-center gap-3 mb-2">
                <Pill className="h-5 w-5 text-dreams-blue" />
                <p className="text-sm text-dreams-textSecondary">Prescriptions</p>
              </div>
              <p className="text-3xl font-bold text-dreams-textPrimary">
                {user.prescriptions_count}
              </p>
            </div>

            <div className="bg-white rounded-xl border border-dreams-border p-5 shadow-card">
              <div className="flex items-center gap-3 mb-2">
                <CalendarDays className="h-5 w-5 text-dreams-blue" />
                <p className="text-sm text-dreams-textSecondary">Member Since</p>
              </div>
              <p className="text-sm font-semibold text-dreams-textPrimary">
                {new Date(user.created_at).toLocaleDateString("en-IN", {
                  year: "numeric",
                  month: "long",
                  day: "numeric",
                })}
              </p>
            </div>

            {user.last_visit && (
              <div className="bg-white rounded-xl border border-dreams-border p-5 shadow-card">
                <div className="flex items-center gap-3 mb-2">
                  <Activity className="h-5 w-5 text-dreams-blue" />
                  <p className="text-sm text-dreams-textSecondary">Last Visit</p>
                </div>
                <p className="text-sm font-semibold text-dreams-textPrimary">
                  {new Date(user.last_visit).toLocaleDateString("en-IN", {
                    year: "numeric",
                    month: "long",
                    day: "numeric",
                  })}
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Prescriptions Tab */}
      {activeTab === "prescriptions" && (
        <div className="bg-white rounded-xl border border-dreams-border shadow-card overflow-hidden">
          {!prescriptions ? (
            <div className="flex justify-center py-12">
              <div className="h-6 w-6 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
            </div>
          ) : prescriptions.data.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-dreams-textSecondary">
              <Pill className="h-10 w-10 mb-3 opacity-30" />
              <p className="text-sm">No prescriptions found</p>
            </div>
          ) : (
            <>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-dreams-border bg-dreams-lightBg">
                    <th className="text-left px-5 py-3 text-xs font-semibold text-dreams-textSecondary uppercase tracking-wider">
                      Date
                    </th>
                    <th className="text-left px-5 py-3 text-xs font-semibold text-dreams-textSecondary uppercase tracking-wider">
                      Doctor
                    </th>
                    <th className="text-left px-5 py-3 text-xs font-semibold text-dreams-textSecondary uppercase tracking-wider">
                      Diagnosis
                    </th>
                    <th className="text-left px-5 py-3 text-xs font-semibold text-dreams-textSecondary uppercase tracking-wider">
                      Medicines
                    </th>
                    <th className="text-left px-5 py-3 text-xs font-semibold text-dreams-textSecondary uppercase tracking-wider">
                      Valid Until
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-dreams-border">
                  {prescriptions.data.map((rx) => {
                    const medCount = Array.isArray(rx.medicines)
                      ? rx.medicines.length
                      : Object.keys(rx.medicines).length;
                    return (
                      <tr key={rx.id} className="hover:bg-dreams-lightBg transition-colors">
                        <td className="px-5 py-3 text-dreams-textSecondary whitespace-nowrap">
                          {new Date(rx.created_at).toLocaleDateString()}
                        </td>
                        <td className="px-5 py-3 text-dreams-textPrimary font-medium">
                          {rx.doctor_name}
                        </td>
                        <td className="px-5 py-3 text-dreams-textSecondary">
                          {rx.diagnosis ?? "—"}
                        </td>
                        <td className="px-5 py-3">
                          <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700">
                            {medCount} {medCount === 1 ? "medicine" : "medicines"}
                          </span>
                        </td>
                        <td className="px-5 py-3 text-dreams-textSecondary whitespace-nowrap">
                          {rx.valid_until
                            ? new Date(rx.valid_until).toLocaleDateString()
                            : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <Pagination
                page={rxPage}
                totalPages={prescriptions.totalPages}
                total={prescriptions.total}
                onPageChange={setRxPage}
              />
            </>
          )}
        </div>
      )}

      {/* Records Tab */}
      {activeTab === "records" && (
        <div className="bg-white rounded-xl border border-dreams-border shadow-card overflow-hidden">
          {!records ? (
            <div className="flex justify-center py-12">
              <div className="h-6 w-6 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
            </div>
          ) : records.data.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-dreams-textSecondary">
              <FileText className="h-10 w-10 mb-3 opacity-30" />
              <p className="text-sm">No medical records found</p>
            </div>
          ) : (
            <>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-dreams-border bg-dreams-lightBg">
                    <th className="text-left px-5 py-3 text-xs font-semibold text-dreams-textSecondary uppercase tracking-wider">
                      Date
                    </th>
                    <th className="text-left px-5 py-3 text-xs font-semibold text-dreams-textSecondary uppercase tracking-wider">
                      Type
                    </th>
                    <th className="text-left px-5 py-3 text-xs font-semibold text-dreams-textSecondary uppercase tracking-wider">
                      Title
                    </th>
                    <th className="text-left px-5 py-3 text-xs font-semibold text-dreams-textSecondary uppercase tracking-wider">
                      Doctor
                    </th>
                    <th className="text-left px-5 py-3 text-xs font-semibold text-dreams-textSecondary uppercase tracking-wider">
                      Source
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-dreams-border">
                  {records.data.map((rec) => (
                    <tr key={rec.id} className="hover:bg-dreams-lightBg transition-colors">
                      <td className="px-5 py-3 text-dreams-textSecondary whitespace-nowrap">
                        {new Date(rec.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-5 py-3">
                        <Badge
                          variant={
                            (recordTypeBadge[rec.record_type] as any) ?? "pending"
                          }
                        >
                          {rec.record_type.replace(/_/g, " ")}
                        </Badge>
                      </td>
                      <td className="px-5 py-3 text-dreams-textPrimary font-medium max-w-xs truncate">
                        {rec.title}
                      </td>
                      <td className="px-5 py-3 text-dreams-textSecondary">
                        {rec.doctor_name ?? "—"}
                      </td>
                      <td className="px-5 py-3">
                        <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
                          {rec.source}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <Pagination
                page={recPage}
                totalPages={records.totalPages}
                total={records.total}
                onPageChange={setRecPage}
              />
            </>
          )}
        </div>
      )}
    </div>
  );
}

function Pagination({
  page,
  totalPages,
  total,
  onPageChange,
}: {
  page: number;
  totalPages: number;
  total: number;
  onPageChange: (p: number) => void;
}) {
  if (totalPages <= 1) return null;
  return (
    <div className="flex items-center justify-between px-5 py-3 border-t border-dreams-border">
      <p className="text-sm text-dreams-textSecondary">
        Page {page} of {totalPages} ({total} total)
      </p>
      <div className="flex items-center gap-2">
        <button
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          className="p-1.5 rounded-lg border border-dreams-border text-dreams-textSecondary hover:bg-dreams-lightBg disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <button
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
          className="p-1.5 rounded-lg border border-dreams-border text-dreams-textSecondary hover:bg-dreams-lightBg disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
