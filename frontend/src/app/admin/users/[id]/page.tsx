"use client";

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
} from "lucide-react";
import { getAdminUser, toggleUserActive } from "@/lib/api/admin-users";
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

export default function AdminUserDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user: currentUser } = useAuthStore();

  const { data: user, isLoading, error } = useQuery({
    queryKey: ["admin-user", id],
    queryFn: () => getAdminUser(id),
    enabled: !!id,
  });

  const { mutate: toggleActive, isPending: isToggling } = useMutation({
    mutationFn: () => toggleUserActive(id, !user!.is_active),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-user", id] });
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
  });

  const isSelf = currentUser?.id === id;

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
            <p className="text-dreams-textSecondary text-sm mt-0.5">
              Member since {new Date(user.created_at).toLocaleDateString()}
            </p>
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

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Profile Card */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-dreams-border p-6 shadow-card space-y-6">
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

        {/* Stats */}
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
        </div>
      </div>

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
  );
}
