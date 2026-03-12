"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Mail,
  Phone,
  Building2,
  FileText,
  Stethoscope,
  CheckCircle,
  XCircle,
  ShieldCheck,
  ShieldX,
  FileImage,
  ClipboardList,
  CalendarDays,
  Pill,
} from "lucide-react";
import { getAdminDoctor, verifyDoctor } from "@/lib/api/doctors";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";

// Verification checklist items — local UI state only (no backend persistence for now)
const CHECKLIST_ITEMS = [
  { id: "license", label: "License verified" },
  { id: "identity", label: "Identity verified" },
  { id: "credentials", label: "Credentials confirmed" },
  { id: "background", label: "Background check passed" },
];

function RejectModal({
  doctorName,
  onClose,
  onConfirm,
  isPending,
}: {
  doctorName: string;
  onClose: () => void;
  onConfirm: (reason: string) => void;
  isPending: boolean;
}) {
  const [reason, setReason] = useState("");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
        <div className="flex items-center gap-3 mb-4">
          <XCircle className="h-6 w-6 text-red-500" />
          <h2 className="text-lg font-semibold text-dreams-textPrimary">
            Reject Doctor
          </h2>
        </div>

        <p className="text-dreams-textSecondary text-sm mb-4">
          Reject {doctorName}&apos;s verification? Please provide a reason so
          they can address the issue.
        </p>

        <div className="mb-5">
          <label className="block text-sm font-medium text-dreams-textPrimary mb-1.5">
            Reason for rejection{" "}
            <span className="text-red-500">*</span>
          </label>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
            placeholder="Explain what needs to be corrected..."
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
            disabled={isPending || !reason.trim()}
            className="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-lg transition-colors disabled:opacity-50"
          >
            {isPending ? "Rejecting..." : "Reject"}
          </button>
        </div>
      </div>
    </div>
  );
}

function ApproveModal({
  doctorName,
  onClose,
  onConfirm,
  isPending,
}: {
  doctorName: string;
  onClose: () => void;
  onConfirm: (reason: string) => void;
  isPending: boolean;
}) {
  const [note, setNote] = useState("");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
        <div className="flex items-center gap-3 mb-4">
          <CheckCircle className="h-6 w-6 text-green-500" />
          <h2 className="text-lg font-semibold text-dreams-textPrimary">
            Approve Doctor
          </h2>
        </div>

        <p className="text-dreams-textSecondary text-sm mb-4">
          Approve {doctorName}&apos;s verification? They will be notified and
          can start seeing patients.
        </p>

        <div className="mb-5">
          <label className="block text-sm font-medium text-dreams-textPrimary mb-1.5">
            Note (optional)
          </label>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={3}
            placeholder="Add a welcome note..."
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
            onClick={() => onConfirm(note)}
            disabled={isPending}
            className="px-4 py-2 text-sm font-medium text-white bg-green-600 hover:bg-green-700 rounded-lg transition-colors disabled:opacity-50"
          >
            {isPending ? "Approving..." : "Approve"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function DoctorDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();

  const [checklist, setChecklist] = useState<Record<string, boolean>>({
    license: false,
    identity: false,
    credentials: false,
    background: false,
  });
  const [adminNotes, setAdminNotes] = useState("");
  const [modal, setModal] = useState<"approve" | "reject" | null>(null);

  const {
    data: doctor,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["admin-doctor", id],
    queryFn: () => getAdminDoctor(id),
    enabled: !!id,
  });

  const verifyMutation = useMutation({
    mutationFn: ({
      action,
      reason,
    }: {
      action: "approve" | "reject";
      reason: string;
    }) => verifyDoctor(id, { action, reason }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-doctor", id] });
      queryClient.invalidateQueries({ queryKey: ["admin-doctors"] });
      queryClient.invalidateQueries({ queryKey: ["admin-doctors-pending"] });
      setModal(null);
    },
  });

  const toggleCheck = (itemId: string) => {
    setChecklist((prev) => ({ ...prev, [itemId]: !prev[itemId] }));
  };

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
      </div>
    );
  }

  if (error || !doctor) {
    return (
      <div className="flex flex-col items-center justify-center py-12 space-y-4">
        <p className="text-red-600 font-medium">Failed to load doctor</p>
        <p className="text-dreams-textSecondary text-sm">
          {error instanceof Error ? error.message : "Doctor not found"}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Breadcrumb
        items={[
          { label: "Doctors", href: "/admin/doctors" },
          { label: doctor.name },
        ]}
      />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={() => router.push("/admin/doctors")}
            className="p-2 rounded-lg hover:bg-dreams-lightBg transition-colors text-dreams-textSecondary"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <div>
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="text-2xl font-bold text-dreams-textPrimary">
                {doctor.name}
              </h1>
              {doctor.verified ? (
                <Badge variant="completed">
                  <ShieldCheck className="h-3 w-3 mr-1" />
                  Verified
                </Badge>
              ) : (
                <Badge variant="pending">
                  <ShieldX className="h-3 w-3 mr-1" />
                  Pending Verification
                </Badge>
              )}
              {!doctor.is_active && (
                <Badge variant="cancelled">Inactive</Badge>
              )}
            </div>
            <p className="text-dreams-textSecondary text-sm mt-0.5">
              Registered{" "}
              {new Date(doctor.created_at).toLocaleDateString("en-IN", {
                year: "numeric",
                month: "long",
                day: "numeric",
              })}
            </p>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => setModal("reject")}
            disabled={verifyMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-red-700 bg-red-50 border border-red-200 rounded-lg hover:bg-red-100 transition-colors disabled:opacity-50"
          >
            <XCircle className="h-4 w-4" />
            Reject
          </button>
          <button
            onClick={() => setModal("approve")}
            disabled={verifyMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-green-600 hover:bg-green-700 rounded-lg transition-colors disabled:opacity-50"
          >
            <CheckCircle className="h-4 w-4" />
            Approve
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column: Profile + Documents */}
        <div className="lg:col-span-2 space-y-6">
          {/* Doctor Profile */}
          <div className="bg-white rounded-xl border border-dreams-border p-6 shadow-card">
            <div className="flex items-center gap-2 mb-5">
              <Stethoscope className="h-5 w-5 text-dreams-blue" />
              <h2 className="text-base font-semibold text-dreams-textPrimary">
                Doctor Profile
              </h2>
            </div>

            <div className="flex items-start gap-4 mb-6">
              <Avatar fallback={doctor.name} size="xl" />
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-dreams-textPrimary mb-1">
                  {doctor.name}
                </h3>
                {doctor.specialization && (
                  <Badge variant="upcoming" className="mb-3">
                    {doctor.specialization}
                  </Badge>
                )}
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
              <div className="flex items-center gap-2 text-dreams-textSecondary">
                <Mail className="h-4 w-4 flex-shrink-0" />
                <span>{doctor.email ?? "—"}</span>
              </div>
              <div className="flex items-center gap-2 text-dreams-textSecondary">
                <Phone className="h-4 w-4 flex-shrink-0" />
                <span>{doctor.phone ?? "—"}</span>
              </div>
              <div>
                <p className="text-xs text-dreams-textSecondary uppercase tracking-wider mb-1">
                  License Number
                </p>
                <div className="flex items-center gap-2 text-dreams-textPrimary font-medium">
                  <FileText className="h-4 w-4 text-dreams-textSecondary flex-shrink-0" />
                  <span>{doctor.license_number ?? "—"}</span>
                </div>
              </div>
              <div>
                <p className="text-xs text-dreams-textSecondary uppercase tracking-wider mb-1">
                  Facility
                </p>
                <div className="flex items-center gap-2 text-dreams-textPrimary font-medium">
                  <Building2 className="h-4 w-4 text-dreams-textSecondary flex-shrink-0" />
                  <div>
                    <span>{doctor.facility_name ?? "—"}</span>
                    {doctor.facility_city && (
                      <span className="text-dreams-textSecondary font-normal">
                        {" "}
                        · {doctor.facility_city}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Documents Section */}
          <div className="bg-white rounded-xl border border-dreams-border p-6 shadow-card">
            <div className="flex items-center gap-2 mb-5">
              <FileImage className="h-5 w-5 text-dreams-blue" />
              <h2 className="text-base font-semibold text-dreams-textPrimary">
                Uploaded Documents
              </h2>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {/* License Certificate */}
              <div className="border border-dashed border-dreams-border rounded-lg p-5 flex flex-col items-center justify-center text-center gap-2 bg-dreams-lightBg">
                <FileText className="h-8 w-8 text-gray-300" />
                <p className="text-sm font-medium text-dreams-textSecondary">
                  License Certificate
                </p>
                <p className="text-xs text-gray-400">
                  No document uploaded yet
                </p>
              </div>

              {/* ID Proof */}
              <div className="border border-dashed border-dreams-border rounded-lg p-5 flex flex-col items-center justify-center text-center gap-2 bg-dreams-lightBg">
                <FileImage className="h-8 w-8 text-gray-300" />
                <p className="text-sm font-medium text-dreams-textSecondary">
                  ID Proof
                </p>
                <p className="text-xs text-gray-400">
                  No document uploaded yet
                </p>
              </div>
            </div>

            <p className="text-xs text-dreams-textSecondary mt-4">
              Document upload will be available once the document management
              feature is implemented.
            </p>
          </div>
        </div>

        {/* Right column: Stats + Checklist + Notes */}
        <div className="space-y-5">
          {/* Stats */}
          <div className="bg-white rounded-xl border border-dreams-border p-5 shadow-card">
            <div className="flex items-center gap-3 mb-2">
              <Pill className="h-5 w-5 text-dreams-blue" />
              <p className="text-sm text-dreams-textSecondary">Prescriptions</p>
            </div>
            <p className="text-3xl font-bold text-dreams-textPrimary">
              {doctor.prescriptions_count}
            </p>
          </div>

          <div className="bg-white rounded-xl border border-dreams-border p-5 shadow-card">
            <div className="flex items-center gap-3 mb-2">
              <FileText className="h-5 w-5 text-dreams-blue" />
              <p className="text-sm text-dreams-textSecondary">
                Medical Records
              </p>
            </div>
            <p className="text-3xl font-bold text-dreams-textPrimary">
              {doctor.records_count}
            </p>
          </div>

          <div className="bg-white rounded-xl border border-dreams-border p-5 shadow-card">
            <div className="flex items-center gap-3 mb-2">
              <CalendarDays className="h-5 w-5 text-dreams-blue" />
              <p className="text-sm text-dreams-textSecondary">Registered</p>
            </div>
            <p className="text-sm font-semibold text-dreams-textPrimary">
              {new Date(doctor.created_at).toLocaleDateString("en-IN", {
                year: "numeric",
                month: "long",
                day: "numeric",
              })}
            </p>
          </div>

          {/* Verification Checklist */}
          <div className="bg-white rounded-xl border border-dreams-border p-5 shadow-card">
            <div className="flex items-center gap-2 mb-4">
              <ClipboardList className="h-5 w-5 text-dreams-blue" />
              <h2 className="text-sm font-semibold text-dreams-textPrimary">
                Verification Checklist
              </h2>
            </div>
            <div className="space-y-3">
              {CHECKLIST_ITEMS.map((item) => (
                <label
                  key={item.id}
                  className="flex items-center gap-3 cursor-pointer group"
                >
                  <input
                    type="checkbox"
                    checked={checklist[item.id]}
                    onChange={() => toggleCheck(item.id)}
                    className="h-4 w-4 rounded border-gray-300 text-dreams-blue focus:ring-dreams-blue cursor-pointer"
                  />
                  <span
                    className={`text-sm transition-colors ${
                      checklist[item.id]
                        ? "text-dreams-textSecondary line-through"
                        : "text-dreams-textPrimary"
                    }`}
                  >
                    {item.label}
                  </span>
                </label>
              ))}
            </div>
            <p className="text-xs text-gray-400 mt-3">
              Checklist is local — use as a review aid before approving.
            </p>
          </div>

          {/* Admin Notes */}
          <div className="bg-white rounded-xl border border-dreams-border p-5 shadow-card">
            <h2 className="text-sm font-semibold text-dreams-textPrimary mb-3">
              Admin Notes
            </h2>
            <textarea
              value={adminNotes}
              onChange={(e) => setAdminNotes(e.target.value)}
              rows={4}
              placeholder="Add internal notes about this doctor..."
              className="w-full px-3 py-2 border border-dreams-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue resize-none text-dreams-textPrimary placeholder:text-gray-400"
            />
            <p className="text-xs text-gray-400 mt-2">
              Notes are stored locally in this session.
            </p>
          </div>
        </div>
      </div>

      {/* Approve Modal */}
      {modal === "approve" && (
        <ApproveModal
          doctorName={doctor.name}
          onClose={() => setModal(null)}
          onConfirm={(note) =>
            verifyMutation.mutate({ action: "approve", reason: note })
          }
          isPending={verifyMutation.isPending}
        />
      )}

      {/* Reject Modal */}
      {modal === "reject" && (
        <RejectModal
          doctorName={doctor.name}
          onClose={() => setModal(null)}
          onConfirm={(reason) =>
            verifyMutation.mutate({ action: "reject", reason })
          }
          isPending={verifyMutation.isPending}
        />
      )}
    </div>
  );
}
