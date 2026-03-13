"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Copy, Link, Trash2, Plus, Users, Clock } from "lucide-react";
import api from "@/lib/api";
import { useClinicStore } from "@/stores/clinic-store";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { Badge } from "@/components/ui/badge";

interface Invite {
  id: string;
  code: string;
  invite_type: string;
  email: string | null;
  role: string;
  expires_at: string | null;
  max_uses: number | null;
  use_count: number;
}

interface JoinRequest {
  id: string;
  user_id: string;
  full_name: string;
  email: string;
  message: string | null;
  status: string;
  created_at: string;
}

export default function ClinicInvitesPage() {
  const { activeClinicId } = useClinicStore();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<"invites" | "requests">("invites");
  const [copied, setCopied] = useState<string | null>(null);

  const { data: invitesData } = useQuery({
    queryKey: ["clinic-invites", activeClinicId],
    queryFn: () =>
      api.get(`/api/v1/clinics/${activeClinicId}/invites`).then((r) => r.data),
    enabled: !!activeClinicId,
  });

  const { data: requestsData } = useQuery({
    queryKey: ["clinic-join-requests", activeClinicId],
    queryFn: () =>
      api.get(`/api/v1/clinics/${activeClinicId}/join-requests`).then((r) => r.data),
    enabled: !!activeClinicId,
  });

  const createInviteMutation = useMutation({
    mutationFn: () =>
      api.post(`/api/v1/clinics/${activeClinicId}/invites`, {
        invite_type: "code",
        role: "doctor",
        expires_days: 7,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["clinic-invites", activeClinicId] });
    },
  });

  const revokeInviteMutation = useMutation({
    mutationFn: (inviteId: string) =>
      api.delete(`/api/v1/clinics/${activeClinicId}/invites/${inviteId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["clinic-invites", activeClinicId] });
    },
  });

  const reviewMutation = useMutation({
    mutationFn: ({ id, action }: { id: string; action: string }) =>
      api.put(`/api/v1/clinics/${activeClinicId}/join-requests/${id}`, { action }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["clinic-join-requests", activeClinicId] });
    },
  });

  const invites: Invite[] = invitesData?.data ?? [];
  const requests: JoinRequest[] = requestsData?.data ?? [];

  const copyCode = (code: string) => {
    navigator.clipboard.writeText(code);
    setCopied(code);
    setTimeout(() => setCopied(null), 2000);
  };

  return (
    <div className="space-y-6">
      <Breadcrumb
        items={[
          { label: "Dashboard", href: "/doctor/dashboard" },
          { label: "My Clinic", href: "/doctor/clinic" },
          { label: "Invites & Requests" },
        ]}
      />

      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-dreams-textPrimary">Invites & Join Requests</h1>
        <button
          onClick={() => createInviteMutation.mutate()}
          disabled={createInviteMutation.isPending}
          className="flex items-center gap-2 rounded-lg bg-dreams-blue px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          <Plus className="h-4 w-4" />
          Generate Invite Code
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-lg border border-dreams-border bg-gray-100 p-1 w-fit">
        {[
          { key: "invites", label: `Invite Codes (${invites.length})` },
          { key: "requests", label: `Join Requests (${requests.filter((r) => r.status === "pending").length})` },
        ].map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setTab(key as any)}
            className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
              tab === key ? "bg-white shadow-sm text-dreams-textPrimary" : "text-dreams-textSecondary hover:text-dreams-textPrimary"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Invite Codes */}
      {tab === "invites" && (
        <div className="space-y-3">
          {invites.length === 0 ? (
            <div className="rounded-xl border border-dreams-border bg-white p-8 text-center shadow-card">
              <Link className="mx-auto h-8 w-8 text-dreams-textSecondary" />
              <p className="mt-2 text-sm text-dreams-textSecondary">No active invite codes</p>
            </div>
          ) : (
            invites.map((invite) => (
              <div
                key={invite.id}
                className="flex items-center justify-between rounded-xl border border-dreams-border bg-white p-4 shadow-card"
              >
                <div className="flex items-center gap-4">
                  <div className="rounded-lg bg-blue-50 px-3 py-2 font-mono text-sm font-bold text-dreams-blue">
                    {invite.code}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <Badge variant="completed">{invite.role}</Badge>
                      <span className="text-xs text-dreams-textSecondary">
                        {invite.use_count}{invite.max_uses ? `/${invite.max_uses}` : ""} uses
                      </span>
                    </div>
                    {invite.expires_at && (
                      <p className="text-xs text-dreams-textSecondary mt-1 flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        Expires {new Date(invite.expires_at).toLocaleDateString()}
                      </p>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => copyCode(invite.code)}
                    className="rounded-lg p-2 hover:bg-gray-100 text-dreams-textSecondary"
                    title="Copy code"
                  >
                    <Copy className="h-4 w-4" />
                    {copied === invite.code && <span className="ml-1 text-xs text-green-600">Copied!</span>}
                  </button>
                  <button
                    onClick={() => revokeInviteMutation.mutate(invite.id)}
                    className="rounded-lg p-2 hover:bg-red-50 text-red-500"
                    title="Revoke"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Join Requests */}
      {tab === "requests" && (
        <div className="space-y-3">
          {requests.length === 0 ? (
            <div className="rounded-xl border border-dreams-border bg-white p-8 text-center shadow-card">
              <Users className="mx-auto h-8 w-8 text-dreams-textSecondary" />
              <p className="mt-2 text-sm text-dreams-textSecondary">No join requests</p>
            </div>
          ) : (
            requests.map((req) => (
              <div
                key={req.id}
                className="flex items-center justify-between rounded-xl border border-dreams-border bg-white p-4 shadow-card"
              >
                <div>
                  <p className="font-medium text-dreams-textPrimary">{req.full_name}</p>
                  <p className="text-sm text-dreams-textSecondary">{req.email}</p>
                  {req.message && (
                    <p className="mt-1 text-xs text-dreams-textSecondary italic">"{req.message}"</p>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {req.status === "pending" ? (
                    <>
                      <button
                        onClick={() => reviewMutation.mutate({ id: req.id, action: "approved" })}
                        className="rounded-lg bg-green-50 px-3 py-1.5 text-sm text-green-700 hover:bg-green-100"
                      >
                        Approve
                      </button>
                      <button
                        onClick={() => reviewMutation.mutate({ id: req.id, action: "rejected" })}
                        className="rounded-lg bg-red-50 px-3 py-1.5 text-sm text-red-700 hover:bg-red-100"
                      >
                        Reject
                      </button>
                    </>
                  ) : (
                    <Badge variant={req.status === "approved" ? "completed" : "overdue"}>
                      {req.status}
                    </Badge>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
