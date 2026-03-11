"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Search,
  CheckCircle,
  XCircle,
  Eye,
  Stethoscope,
  Building2,
  FileText,
  Calendar,
} from "lucide-react";
import { getDoctors, verifyDoctor, Doctor } from "@/lib/api/doctors";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { Badge } from "@/components/ui/badge";

function VerifyModal({
  doctor,
  action,
  onClose,
  onConfirm,
  isPending,
}: {
  doctor: Doctor;
  action: "approve" | "reject";
  onClose: () => void;
  onConfirm: (reason: string) => void;
  isPending: boolean;
}) {
  const [reason, setReason] = useState("");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
        <div className="flex items-center gap-3 mb-4">
          {action === "approve" ? (
            <CheckCircle className="h-6 w-6 text-green-500" />
          ) : (
            <XCircle className="h-6 w-6 text-red-500" />
          )}
          <h2 className="text-lg font-semibold text-dreams-textPrimary">
            {action === "approve" ? "Approve Doctor" : "Reject Doctor"}
          </h2>
        </div>

        <p className="text-dreams-textSecondary text-sm mb-4">
          {action === "approve"
            ? `Approve ${doctor.name}'s verification? They will be notified and can start seeing patients.`
            : `Reject ${doctor.name}'s verification? Please provide a reason so they can address the issue.`}
        </p>

        <div className="mb-5">
          <label className="block text-sm font-medium text-dreams-textPrimary mb-1.5">
            {action === "approve" ? "Note (optional)" : "Reason for rejection"}
          </label>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
            placeholder={
              action === "approve"
                ? "Add a welcome note..."
                : "Explain what needs to be corrected..."
            }
            className="w-full px-3 py-2 border border-dreams-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue resize-none"
          />
        </div>

        <div className="flex gap-3 justify-end">
          <button
            onClick={onClose}
            disabled={isPending}
            className="px-4 py-2 text-sm font-medium text-dreams-textSecondary border border-dreams-border rounded-lg hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={() => onConfirm(reason)}
            disabled={isPending || (action === "reject" && !reason.trim())}
            className={`px-4 py-2 text-sm font-medium text-white rounded-lg transition-colors disabled:opacity-50 ${
              action === "approve"
                ? "bg-green-600 hover:bg-green-700"
                : "bg-red-600 hover:bg-red-700"
            }`}
          >
            {isPending
              ? "Processing..."
              : action === "approve"
              ? "Approve"
              : "Reject"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function DoctorVerificationQueuePage() {
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState("");
  const [page, setPage] = useState(1);
  const [modal, setModal] = useState<{
    doctor: Doctor;
    action: "approve" | "reject";
  } | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["admin-doctors-pending", searchQuery, page],
    queryFn: () =>
      getDoctors({
        search: searchQuery || undefined,
        verified: "false",
        page,
        limit: 20,
      }),
  });

  const verifyMutation = useMutation({
    mutationFn: ({
      id,
      action,
      reason,
    }: {
      id: string;
      action: "approve" | "reject";
      reason: string;
    }) => verifyDoctor(id, { action, reason }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-doctors-pending"] });
      queryClient.invalidateQueries({ queryKey: ["admin-doctors"] });
      setModal(null);
    },
  });

  const doctors = data?.doctors ?? [];
  const total = data?.total ?? 0;
  const totalPages = data?.totalPages ?? 1;

  return (
    <div className="space-y-6">
      <Breadcrumb
        items={[
          { label: "Doctors", href: "/admin/doctors" },
          { label: "Verification Queue" },
        ]}
      />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-dreams-textPrimary">
            Doctor Verification Queue
          </h1>
          <p className="text-dreams-textSecondary mt-1">
            Review and approve pending doctor registrations
            {total > 0 && (
              <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                {total} pending
              </span>
            )}
          </p>
        </div>
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
        <input
          type="text"
          placeholder="Search by name, email, or license..."
          value={searchQuery}
          onChange={(e) => {
            setSearchQuery(e.target.value);
            setPage(1);
          }}
          className="w-full h-10 pl-10 pr-4 rounded-lg border border-dreams-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
        />
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-dreams-border shadow-card overflow-hidden">
        {isLoading ? (
          <div className="flex justify-center py-16">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-dreams-blue" />
          </div>
        ) : error ? (
          <div className="text-center py-16">
            <p className="text-red-600 font-medium">
              Failed to load pending doctors
            </p>
          </div>
        ) : doctors.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <CheckCircle className="h-12 w-12 text-green-400 mb-3" />
            <p className="text-lg font-semibold text-dreams-textPrimary">
              All caught up!
            </p>
            <p className="text-dreams-textSecondary text-sm mt-1">
              No pending doctor verifications.
            </p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-dreams-border bg-gray-50">
                <th className="text-left px-6 py-3 text-xs font-semibold text-dreams-textSecondary uppercase tracking-wider">
                  Doctor
                </th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-dreams-textSecondary uppercase tracking-wider">
                  Specialization
                </th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-dreams-textSecondary uppercase tracking-wider">
                  License
                </th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-dreams-textSecondary uppercase tracking-wider">
                  Facility
                </th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-dreams-textSecondary uppercase tracking-wider">
                  Registered
                </th>
                <th className="text-right px-6 py-3 text-xs font-semibold text-dreams-textSecondary uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-dreams-border">
              {doctors.map((doctor) => (
                <tr
                  key={doctor.id}
                  className="hover:bg-gray-50 transition-colors"
                >
                  {/* Doctor name + email */}
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className="h-9 w-9 rounded-full bg-dreams-blue/10 flex items-center justify-center flex-shrink-0">
                        <Stethoscope className="h-4 w-4 text-dreams-blue" />
                      </div>
                      <div>
                        <p className="font-medium text-dreams-textPrimary">
                          {doctor.name}
                        </p>
                        <p className="text-xs text-dreams-textSecondary">
                          {doctor.email ?? "—"}
                        </p>
                      </div>
                    </div>
                  </td>

                  {/* Specialization */}
                  <td className="px-6 py-4">
                    {doctor.specialization ? (
                      <Badge variant="upcoming">{doctor.specialization}</Badge>
                    ) : (
                      <span className="text-dreams-textSecondary">—</span>
                    )}
                  </td>

                  {/* License */}
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-1.5 text-dreams-textSecondary">
                      <FileText className="h-3.5 w-3.5 flex-shrink-0" />
                      <span>{doctor.license_number ?? "—"}</span>
                    </div>
                  </td>

                  {/* Facility */}
                  <td className="px-6 py-4">
                    {doctor.facility_name ? (
                      <div className="flex items-center gap-1.5 text-dreams-textSecondary">
                        <Building2 className="h-3.5 w-3.5 flex-shrink-0" />
                        <span>
                          {doctor.facility_name}
                          {doctor.facility_city
                            ? `, ${doctor.facility_city}`
                            : ""}
                        </span>
                      </div>
                    ) : (
                      <span className="text-dreams-textSecondary">—</span>
                    )}
                  </td>

                  {/* Registered date */}
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-1.5 text-dreams-textSecondary">
                      <Calendar className="h-3.5 w-3.5 flex-shrink-0" />
                      <span>
                        {new Date(doctor.created_at).toLocaleDateString(
                          "en-IN",
                          { day: "numeric", month: "short", year: "numeric" }
                        )}
                      </span>
                    </div>
                  </td>

                  {/* Actions */}
                  <td className="px-6 py-4">
                    <div className="flex items-center justify-end gap-2">
                      <a
                        href={`/admin/doctors/${doctor.id}`}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-dreams-textSecondary border border-dreams-border rounded-lg hover:bg-gray-50 transition-colors"
                      >
                        <Eye className="h-3.5 w-3.5" />
                        View
                      </a>
                      <button
                        onClick={() =>
                          setModal({ doctor, action: "approve" })
                        }
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-green-700 bg-green-50 border border-green-200 rounded-lg hover:bg-green-100 transition-colors"
                      >
                        <CheckCircle className="h-3.5 w-3.5" />
                        Approve
                      </button>
                      <button
                        onClick={() =>
                          setModal({ doctor, action: "reject" })
                        }
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-red-700 bg-red-50 border border-red-200 rounded-lg hover:bg-red-100 transition-colors"
                      >
                        <XCircle className="h-3.5 w-3.5" />
                        Reject
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-dreams-textSecondary">
            Showing {(page - 1) * 20 + 1}–{Math.min(page * 20, total)} of{" "}
            {total} pending doctors
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-3 py-1.5 text-sm border border-dreams-border rounded-lg disabled:opacity-40 hover:bg-gray-50 transition-colors"
            >
              Previous
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="px-3 py-1.5 text-sm border border-dreams-border rounded-lg disabled:opacity-40 hover:bg-gray-50 transition-colors"
            >
              Next
            </button>
          </div>
        </div>
      )}

      {/* Verify / Reject modal */}
      {modal && (
        <VerifyModal
          doctor={modal.doctor}
          action={modal.action}
          onClose={() => setModal(null)}
          onConfirm={(reason) =>
            verifyMutation.mutate({
              id: modal.doctor.id,
              action: modal.action,
              reason,
            })
          }
          isPending={verifyMutation.isPending}
        />
      )}
    </div>
  );
}
