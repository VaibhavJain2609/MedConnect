"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Copy, Building2, CheckCircle, XCircle, Clock, RefreshCw, ShieldCheck } from "lucide-react";
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
import { toast } from "@/hooks/use-toast";
import {
  getPatientLinkCode,
  getMyClinicLinks,
  updateClinicLinkConsent,
  type ClinicLink,
  type PatientLinkCode,
} from "@/lib/api/patient-links";
import {
  getPatientRecordAccessRequests,
  actOnRecordAccessRequest,
  type RecordAccessConsent,
} from "@/lib/api/record-access";

const consentBadgeVariant = {
  pending: "pending" as const,
  approved: "completed" as const,
  revoked: "cancelled" as const,
};

const accessBadgeVariant = {
  pending: "pending" as const,
  approved: "completed" as const,
  rejected: "overdue" as const,
  revoked: "overdue" as const,
};

export default function PatientClinicsPage() {
  const queryClient = useQueryClient();
  const [copied, setCopied] = useState(false);

  const { data: codeData, isLoading: codeLoading } = useQuery<PatientLinkCode>({
    queryKey: ["patient-link-code"],
    queryFn: () => getPatientLinkCode(),
  });

  const { data: linksData, isLoading: linksLoading } = useQuery<{ data: ClinicLink[] }>({
    queryKey: ["patient-clinic-links"],
    queryFn: () => getMyClinicLinks(),
  });

  const consentMutation = useMutation({
    mutationFn: ({ id, action }: { id: string; action: "approved" | "revoked" }) =>
      updateClinicLinkConsent(id, action),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["patient-clinic-links"] });
    },
    onError: () => {
      toast({
        title: "Could not update clinic access",
        description: "Your change was not saved. Please try again.",
        variant: "destructive",
      });
    },
  });

  const { data: accessRequestsData, isLoading: accessLoading } = useQuery<{ data: RecordAccessConsent[] }>({
    queryKey: ["record-access-requests"],
    queryFn: () => getPatientRecordAccessRequests(),
  });

  const accessActionMutation = useMutation({
    mutationFn: ({ id, action }: { id: string; action: "approved" | "rejected" | "revoked" }) =>
      actOnRecordAccessRequest(id, action),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["record-access-requests"] });
    },
    onError: () => {
      toast({
        title: "Could not update access request",
        description: "Your change was not saved. Please try again.",
        variant: "destructive",
      });
    },
  });

  const accessRequests: RecordAccessConsent[] = accessRequestsData?.data ?? [];

  const copyCode = () => {
    if (!codeData?.code) return;
    navigator.clipboard.writeText(codeData.code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const links: ClinicLink[] = linksData?.data ?? [];

  return (
    <div className="space-y-6">
      <Breadcrumb
        items={[
          { label: "Health Timeline", href: "/patient/timeline" },
          { label: "My Clinics" },
        ]}
      />

      <div>
        <h1 className="text-2xl font-bold text-dreams-textPrimary">My Clinics</h1>
        <p className="mt-1 text-sm text-dreams-textSecondary">
          Share your link code with a doctor to connect your records to their clinic.
        </p>
      </div>

      {/* Link Code Card */}
      <div className="rounded-xl border border-dreams-border bg-white p-6 shadow-card">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="font-semibold text-dreams-textPrimary">Your Link Code</h2>
            <p className="mt-0.5 text-sm text-dreams-textSecondary">
              Give this code to your doctor. It rotates every Sunday.
            </p>
          </div>
          <RefreshCw className="h-4 w-4 text-dreams-textSecondary" />
        </div>

        {codeLoading ? (
          <div className="mt-4 h-14 animate-pulse rounded-lg bg-gray-100" />
        ) : codeData ? (
          <div className="mt-4 flex items-center gap-4">
            <div className="flex-1 rounded-lg bg-blue-50 px-6 py-3 text-center font-mono text-2xl font-bold tracking-[0.3em] text-dreams-blue">
              {codeData.code}
            </div>
            <button
              onClick={copyCode}
              className="flex items-center gap-2 rounded-lg border border-dreams-border px-4 py-3 text-sm font-medium text-dreams-textSecondary hover:bg-gray-50"
            >
              <Copy className="h-4 w-4" />
              {copied ? "Copied!" : "Copy"}
            </button>
          </div>
        ) : null}

        {codeData && (
          <p className="mt-3 flex items-center gap-1 text-xs text-dreams-textSecondary">
            <Clock className="h-3 w-3" />
            Expires {new Date(codeData.expires_at).toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" })}
          </p>
        )}
      </div>

      {/* Linked Clinics */}
      <div>
        <h2 className="mb-3 text-lg font-semibold text-dreams-textPrimary">
          Linked Clinics ({links.length})
        </h2>

        {linksLoading ? (
          <div className="space-y-3">
            {[1, 2].map((i) => (
              <div key={i} className="h-20 animate-pulse rounded-xl bg-gray-100" />
            ))}
          </div>
        ) : links.length === 0 ? (
          <div className="rounded-xl border border-dreams-border bg-white p-8 text-center shadow-card">
            <Building2 className="mx-auto h-8 w-8 text-dreams-textSecondary" />
            <p className="mt-2 text-sm text-dreams-textSecondary">No clinics linked yet</p>
            <p className="mt-1 text-xs text-dreams-textSecondary">
              Share your link code with a doctor to get started.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {links.map((link) => (
              <div
                key={link.id}
                className="flex items-center justify-between rounded-xl border border-dreams-border bg-white p-4 shadow-card"
              >
                <div className="flex items-center gap-4">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50">
                    <Building2 className="h-5 w-5 text-dreams-blue" />
                  </div>
                  <div>
                    <p className="font-medium text-dreams-textPrimary">{link.clinic_name}</p>
                    <p className="text-sm text-dreams-textSecondary">{link.clinic_city}</p>
                    <p className="mt-0.5 text-xs text-dreams-textSecondary">
                      Linked {new Date(link.created_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <Badge variant={consentBadgeVariant[link.consent_status]}>
                    {link.consent_status}
                  </Badge>

                  {link.consent_status === "pending" && (
                    <div className="flex gap-2">
                      <button
                        onClick={() => consentMutation.mutate({ id: link.id, action: "approved" })}
                        disabled={consentMutation.isPending}
                        className="flex items-center gap-1 rounded-lg bg-green-50 px-3 py-1.5 text-sm text-green-700 hover:bg-green-100 disabled:opacity-50"
                      >
                        <CheckCircle className="h-3.5 w-3.5" />
                        Approve
                      </button>
                      <button
                        onClick={() => consentMutation.mutate({ id: link.id, action: "revoked" })}
                        disabled={consentMutation.isPending}
                        className="flex items-center gap-1 rounded-lg bg-red-50 px-3 py-1.5 text-sm text-red-700 hover:bg-red-100 disabled:opacity-50"
                      >
                        <XCircle className="h-3.5 w-3.5" />
                        Decline
                      </button>
                    </div>
                  )}

                  {link.consent_status === "approved" && (
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <button
                          disabled={consentMutation.isPending}
                          className="rounded-lg px-3 py-1.5 text-sm text-red-600 hover:bg-red-50 disabled:opacity-50"
                        >
                          Revoke access
                        </button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>
                            Revoke access for {link.clinic_name}?
                          </AlertDialogTitle>
                          <AlertDialogDescription>
                            The clinic will no longer be able to add new records
                            or appointments on your behalf. Records created
                            before you revoke will still be visible to the
                            clinic. You can restore access at any time.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Keep access</AlertDialogCancel>
                          <AlertDialogAction
                            onClick={() =>
                              consentMutation.mutate({ id: link.id, action: "revoked" })
                            }
                            className="bg-red-600 text-white hover:bg-red-700"
                          >
                            Revoke access
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  )}

                  {link.consent_status === "revoked" && (
                    <button
                      onClick={() => consentMutation.mutate({ id: link.id, action: "approved" })}
                      disabled={consentMutation.isPending}
                      className="flex items-center gap-1 rounded-lg bg-green-50 px-3 py-1.5 text-sm text-green-700 hover:bg-green-100 disabled:opacity-50"
                    >
                      <CheckCircle className="h-3.5 w-3.5" />
                      Restore access
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Record Access Requests */}
      <div>
        <div className="mb-3 flex items-center gap-2">
          <ShieldCheck className="h-5 w-5 text-dreams-textSecondary" />
          <h2 className="text-lg font-semibold text-dreams-textPrimary">
            Record Access Requests ({accessRequests.length})
          </h2>
        </div>
        <p className="mb-3 text-sm text-dreams-textSecondary">
          Doctors can request temporary access to your complete medical history. You control who gets access and for how long.
        </p>

        {accessLoading ? (
          <div className="space-y-3">
            {[1, 2].map((i) => (
              <div key={i} className="h-24 animate-pulse rounded-xl bg-gray-100" />
            ))}
          </div>
        ) : accessRequests.length === 0 ? (
          <div className="rounded-xl border border-dreams-border bg-white p-8 text-center shadow-card">
            <ShieldCheck className="mx-auto h-8 w-8 text-dreams-textSecondary" />
            <p className="mt-2 text-sm text-dreams-textSecondary">No record access requests</p>
            <p className="mt-1 text-xs text-dreams-textSecondary">
              Doctors from your linked clinics can request access to your full medical history.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {accessRequests.map((req) => {
              const now = new Date();
              const isExpired =
                req.status === "approved" &&
                req.expires_at &&
                new Date(req.expires_at) < now;

              return (
                <div
                  key={req.id}
                  className="rounded-xl border border-dreams-border bg-white p-4 shadow-card"
                >
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <p className="font-medium text-dreams-textPrimary">
                          Dr. {req.doctor_name}
                        </p>
                        {req.doctor_specialization && (
                          <span className="text-xs text-dreams-textSecondary">
                            · {req.doctor_specialization}
                          </span>
                        )}
                      </div>
                      {req.clinic_name && (
                        <p className="text-sm text-dreams-textSecondary">{req.clinic_name}</p>
                      )}
                      {req.purpose && (
                        <p className="text-sm text-dreams-textSecondary">
                          <span className="font-medium">Purpose:</span> {req.purpose}
                        </p>
                      )}
                      <p className="text-xs text-dreams-textSecondary">
                        Duration: {req.access_duration_days} days ·{" "}
                        Requested {new Date(req.created_at).toLocaleDateString()}
                      </p>
                      {req.status === "approved" && req.expires_at && (
                        <p className="text-xs text-dreams-textSecondary">
                          {isExpired
                            ? "Expired"
                            : `Access until ${new Date(req.expires_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}`}
                        </p>
                      )}
                    </div>

                    <div className="flex flex-shrink-0 items-center gap-3">
                      <Badge variant={isExpired ? "overdue" : accessBadgeVariant[req.status]}>
                        {isExpired ? "Expired" : req.status}
                      </Badge>

                      {req.status === "pending" && (
                        <div className="flex gap-2">
                          <button
                            onClick={() => accessActionMutation.mutate({ id: req.id, action: "approved" })}
                            disabled={accessActionMutation.isPending}
                            className="flex items-center gap-1 rounded-lg bg-green-50 px-3 py-1.5 text-sm text-green-700 hover:bg-green-100 disabled:opacity-50"
                          >
                            <CheckCircle className="h-3.5 w-3.5" />
                            Approve
                          </button>
                          <button
                            onClick={() => accessActionMutation.mutate({ id: req.id, action: "rejected" })}
                            disabled={accessActionMutation.isPending}
                            className="flex items-center gap-1 rounded-lg bg-red-50 px-3 py-1.5 text-sm text-red-700 hover:bg-red-100 disabled:opacity-50"
                          >
                            <XCircle className="h-3.5 w-3.5" />
                            Reject
                          </button>
                        </div>
                      )}

                      {req.status === "approved" && !isExpired && (
                        <button
                          onClick={() => accessActionMutation.mutate({ id: req.id, action: "revoked" })}
                          disabled={accessActionMutation.isPending}
                          className="rounded-lg px-3 py-1.5 text-sm text-red-600 hover:bg-red-50 disabled:opacity-50"
                        >
                          Revoke
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
