"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  X,
  Mail,
  Phone,
  Globe,
  Droplets,
  PhoneCall,
  FileText,
  Pill,
  Activity,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import {
  getAdminUser,
  getAdminUserPrescriptions,
  getAdminUserRecords,
} from "@/lib/api/admin-users";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";

type Tab = "overview" | "prescriptions" | "records";

const recordTypeBadge: Record<string, string> = {
  lab_result: "inProgress",
  prescription: "completed",
  imaging: "upcoming",
  clinical_note: "pending",
  discharge_summary: "overdue",
};

interface PatientDetailDrawerProps {
  patientId: string | null;
  onClose: () => void;
}

export function PatientDetailDrawer({
  patientId,
  onClose,
}: PatientDetailDrawerProps) {
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [rxPage, setRxPage] = useState(1);
  const [recPage, setRecPage] = useState(1);

  const { data: user, isLoading } = useQuery({
    queryKey: ["admin-user", patientId],
    queryFn: () => getAdminUser(patientId!),
    enabled: !!patientId,
  });

  const { data: prescriptions } = useQuery({
    queryKey: ["admin-user-prescriptions", patientId, rxPage],
    queryFn: () => getAdminUserPrescriptions(patientId!, { page: rxPage }),
    enabled: !!patientId && activeTab === "prescriptions",
  });

  const { data: records } = useQuery({
    queryKey: ["admin-user-records", patientId, recPage],
    queryFn: () => getAdminUserRecords(patientId!, { page: recPage }),
    enabled: !!patientId && activeTab === "records",
  });

  const isOpen = !!patientId;

  // Reset tabs when opening a new patient
  const handleTabChange = (tab: Tab) => {
    setActiveTab(tab);
    if (tab === "prescriptions") setRxPage(1);
    if (tab === "records") setRecPage(1);
  };

  return (
    <>
      {/* Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/40 z-40"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      {/* Panel */}
      <div
        className={`fixed right-0 top-0 h-full w-full max-w-2xl bg-white z-50 flex flex-col shadow-2xl transition-transform duration-300 ${
          isOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-dreams-border shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            {isLoading || !user ? (
              <div className="h-5 w-48 bg-gray-200 rounded animate-pulse" />
            ) : (
              <>
                <Avatar fallback={user.full_name} size="sm" />
                <div className="min-w-0">
                  <h2 className="text-base font-semibold text-dreams-textPrimary truncate">
                    {user.full_name}
                  </h2>
                  <div className="flex items-center gap-2 mt-0.5">
                    <Badge variant={user.is_active ? "completed" : "pending"}>
                      {user.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </div>
                </div>
              </>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-dreams-textSecondary hover:bg-dreams-lightBg transition-colors shrink-0"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Tabs */}
        {user && (
          <div className="border-b border-dreams-border px-6 shrink-0">
            <nav className="flex gap-1">
              {(
                [
                  { id: "overview" as Tab, label: "Overview" },
                  {
                    id: "prescriptions" as Tab,
                    label: `Prescriptions (${user.prescriptions_count})`,
                  },
                  {
                    id: "records" as Tab,
                    label: `Records (${user.records_count})`,
                  },
                ] as const
              ).map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => handleTabChange(tab.id)}
                  className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
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

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6">
          {isLoading ? (
            <div className="flex justify-center py-12">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
            </div>
          ) : !user ? null : (
            <>
              {/* Overview Tab */}
              {activeTab === "overview" && (
                <div className="space-y-5">
                  {/* Profile Card */}
                  <div className="bg-white rounded-xl border border-dreams-border p-5 shadow-card space-y-5">
                    <div className="flex items-start gap-4">
                      <Avatar fallback={user.full_name} size="xl" />
                      <div className="space-y-2 flex-1 min-w-0">
                        <h3 className="text-base font-semibold text-dreams-textPrimary">
                          {user.full_name}
                        </h3>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm">
                          <div className="flex items-center gap-2 text-dreams-textSecondary">
                            <Mail className="h-4 w-4 shrink-0" />
                            <span className="truncate">{user.email ?? "—"}</span>
                          </div>
                          <div className="flex items-center gap-2 text-dreams-textSecondary">
                            <Phone className="h-4 w-4 shrink-0" />
                            <span>{user.phone ?? "—"}</span>
                          </div>
                          <div className="flex items-center gap-2 text-dreams-textSecondary">
                            <Globe className="h-4 w-4 shrink-0" />
                            <span>
                              Language: {user.language_pref.toUpperCase()}
                            </span>
                          </div>
                          <div className="flex items-center gap-2 text-dreams-textSecondary">
                            <Droplets className="h-4 w-4 shrink-0" />
                            <span>Blood Group: {user.blood_group ?? "—"}</span>
                          </div>
                        </div>
                      </div>
                    </div>

                    {(user.emergency_contact_name ||
                      user.emergency_contact_phone) && (
                      <div className="border-t border-dreams-border pt-4">
                        <p className="text-xs font-semibold text-dreams-textSecondary uppercase tracking-wider mb-2">
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

                  {/* Stats row */}
                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-white rounded-xl border border-dreams-border p-4 shadow-card">
                      <div className="flex items-center gap-2 mb-1">
                        <FileText className="h-4 w-4 text-dreams-blue" />
                        <p className="text-xs text-dreams-textSecondary">
                          Medical Records
                        </p>
                      </div>
                      <p className="text-2xl font-bold text-dreams-textPrimary">
                        {user.records_count}
                      </p>
                    </div>
                    <div className="bg-white rounded-xl border border-dreams-border p-4 shadow-card">
                      <div className="flex items-center gap-2 mb-1">
                        <Pill className="h-4 w-4 text-dreams-blue" />
                        <p className="text-xs text-dreams-textSecondary">
                          Prescriptions
                        </p>
                      </div>
                      <p className="text-2xl font-bold text-dreams-textPrimary">
                        {user.prescriptions_count}
                      </p>
                    </div>
                  </div>

                  {/* Vitals */}
                  {(user.height_cm || user.weight_kg) && (
                    <div className="bg-white rounded-xl border border-dreams-border p-5 shadow-card">
                      <div className="flex items-center gap-2 mb-4">
                        <Activity className="h-5 w-5 text-dreams-blue" />
                        <h3 className="text-sm font-semibold text-dreams-textPrimary">
                          Vitals
                        </h3>
                      </div>
                      <div className="grid grid-cols-3 gap-3">
                        {user.height_cm && (
                          <div className="bg-dreams-lightBg rounded-lg p-3 text-center">
                            <p className="text-xs text-dreams-textSecondary mb-1">
                              Height
                            </p>
                            <p className="text-lg font-bold text-dreams-textPrimary">
                              {user.height_cm}
                            </p>
                            <p className="text-xs text-dreams-textSecondary">
                              cm
                            </p>
                          </div>
                        )}
                        {user.weight_kg && (
                          <div className="bg-dreams-lightBg rounded-lg p-3 text-center">
                            <p className="text-xs text-dreams-textSecondary mb-1">
                              Weight
                            </p>
                            <p className="text-lg font-bold text-dreams-textPrimary">
                              {user.weight_kg}
                            </p>
                            <p className="text-xs text-dreams-textSecondary">
                              kg
                            </p>
                          </div>
                        )}
                        {user.height_cm && user.weight_kg && (
                          <div className="bg-dreams-lightBg rounded-lg p-3 text-center">
                            <p className="text-xs text-dreams-textSecondary mb-1">
                              BMI
                            </p>
                            <p className="text-lg font-bold text-dreams-textPrimary">
                              {(
                                user.weight_kg /
                                Math.pow(user.height_cm / 100, 2)
                              ).toFixed(1)}
                            </p>
                            <p className="text-xs text-dreams-textSecondary">
                              kg/m²
                            </p>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Health Info */}
                  {((user.allergies && user.allergies.length > 0) ||
                    (user.chronic_conditions &&
                      user.chronic_conditions.length > 0)) && (
                    <div className="bg-white rounded-xl border border-dreams-border p-5 shadow-card space-y-4">
                      <h3 className="text-sm font-semibold text-dreams-textPrimary">
                        Health Information
                      </h3>
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
                      {user.chronic_conditions &&
                        user.chronic_conditions.length > 0 && (
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
                            <th className="text-left px-4 py-3 text-xs font-semibold text-dreams-textSecondary uppercase tracking-wider">
                              Date
                            </th>
                            <th className="text-left px-4 py-3 text-xs font-semibold text-dreams-textSecondary uppercase tracking-wider">
                              Doctor
                            </th>
                            <th className="text-left px-4 py-3 text-xs font-semibold text-dreams-textSecondary uppercase tracking-wider">
                              Diagnosis
                            </th>
                            <th className="text-left px-4 py-3 text-xs font-semibold text-dreams-textSecondary uppercase tracking-wider">
                              Meds
                            </th>
                            <th className="text-left px-4 py-3 text-xs font-semibold text-dreams-textSecondary uppercase tracking-wider">
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
                              <tr
                                key={rx.id}
                                className="hover:bg-dreams-lightBg transition-colors"
                              >
                                <td className="px-4 py-3 text-dreams-textSecondary whitespace-nowrap">
                                  {new Date(rx.created_at).toLocaleDateString()}
                                </td>
                                <td className="px-4 py-3 text-dreams-textPrimary font-medium">
                                  {rx.doctor_name}
                                </td>
                                <td className="px-4 py-3 text-dreams-textSecondary max-w-[120px] truncate">
                                  {rx.diagnosis ?? "—"}
                                </td>
                                <td className="px-4 py-3">
                                  <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700">
                                    {medCount}
                                  </span>
                                </td>
                                <td className="px-4 py-3 text-dreams-textSecondary whitespace-nowrap">
                                  {rx.valid_until
                                    ? new Date(
                                        rx.valid_until
                                      ).toLocaleDateString()
                                    : "—"}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                      <DrawerPagination
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
                            <th className="text-left px-4 py-3 text-xs font-semibold text-dreams-textSecondary uppercase tracking-wider">
                              Date
                            </th>
                            <th className="text-left px-4 py-3 text-xs font-semibold text-dreams-textSecondary uppercase tracking-wider">
                              Type
                            </th>
                            <th className="text-left px-4 py-3 text-xs font-semibold text-dreams-textSecondary uppercase tracking-wider">
                              Title
                            </th>
                            <th className="text-left px-4 py-3 text-xs font-semibold text-dreams-textSecondary uppercase tracking-wider">
                              Doctor
                            </th>
                            <th className="text-left px-4 py-3 text-xs font-semibold text-dreams-textSecondary uppercase tracking-wider">
                              Source
                            </th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-dreams-border">
                          {records.data.map((rec) => (
                            <tr
                              key={rec.id}
                              className="hover:bg-dreams-lightBg transition-colors"
                            >
                              <td className="px-4 py-3 text-dreams-textSecondary whitespace-nowrap">
                                {new Date(rec.created_at).toLocaleDateString()}
                              </td>
                              <td className="px-4 py-3">
                                <Badge
                                  variant={
                                    (recordTypeBadge[rec.record_type] as any) ??
                                    "pending"
                                  }
                                >
                                  {rec.record_type.replace(/_/g, " ")}
                                </Badge>
                              </td>
                              <td className="px-4 py-3 text-dreams-textPrimary font-medium max-w-[120px] truncate">
                                {rec.title}
                              </td>
                              <td className="px-4 py-3 text-dreams-textSecondary">
                                {rec.doctor_name ?? "—"}
                              </td>
                              <td className="px-4 py-3">
                                <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
                                  {rec.source}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      <DrawerPagination
                        page={recPage}
                        totalPages={records.totalPages}
                        total={records.total}
                        onPageChange={setRecPage}
                      />
                    </>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </>
  );
}

function DrawerPagination({
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
    <div className="flex items-center justify-between px-4 py-3 border-t border-dreams-border">
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
