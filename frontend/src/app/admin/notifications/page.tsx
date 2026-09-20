"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, Megaphone, Send } from "lucide-react";
import { toast } from "@/hooks/use-toast";
import {
  BroadcastTargetRole,
  BroadcastsResponse,
  listBroadcasts,
  sendBroadcast,
} from "@/lib/api/admin-broadcast";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { Badge } from "@/components/ui/badge";

const AUDIENCE_OPTIONS: { value: BroadcastTargetRole; label: string }[] = [
  { value: "all", label: "All users" },
  { value: "patient", label: "Patients" },
  { value: "doctor", label: "Doctors" },
  { value: "admin", label: "Admins" },
];

const AUDIENCE_BADGE: Record<string, string> = {
  all: "inProgress",
  patient: "completed",
  doctor: "upcoming",
  admin: "overdue",
};

function formatDateTime(isoString: string): string {
  const date = new Date(isoString);
  return date.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export default function AdminNotificationsPage() {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [targetRole, setTargetRole] = useState<BroadcastTargetRole>("all");
  const [actionUrl, setActionUrl] = useState("");
  const [sending, setSending] = useState(false);
  const [page, setPage] = useState(1);
  const limit = 10;

  const { data, isLoading, error } = useQuery<BroadcastsResponse>({
    queryKey: ["admin-broadcasts", page],
    queryFn: () => listBroadcasts(page, limit),
  });

  const broadcasts = data?.data ?? [];
  const totalPages = data?.totalPages ?? 0;

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !body.trim()) {
      toast({
        title: "Missing fields",
        description: "Title and message are required.",
        variant: "destructive",
      });
      return;
    }
    setSending(true);
    try {
      const result = await sendBroadcast({
        title: title.trim(),
        body: body.trim(),
        target_role: targetRole,
        action_url: actionUrl.trim() || undefined,
      });
      toast({
        title: "Broadcast sent",
        description: `Delivered to ${result.recipient_count} user${
          result.recipient_count === 1 ? "" : "s"
        }.`,
      });
      setTitle("");
      setBody("");
      setActionUrl("");
      setTargetRole("all");
      setPage(1);
      queryClient.invalidateQueries({ queryKey: ["admin-broadcasts"] });
    } catch (err) {
      toast({
        title: "Broadcast failed",
        description:
          err instanceof Error ? err.message : "Could not send the announcement.",
        variant: "destructive",
      });
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="space-y-6">
      <Breadcrumb
        items={[
          { label: "Dashboard", href: "/admin/dashboard" },
          { label: "Notifications" },
        ]}
      />

      <div className="flex items-center gap-3">
        <Bell className="h-7 w-7 text-dreams-blue" />
        <div>
          <h1 className="text-3xl font-bold text-dreams-textPrimary">Notifications</h1>
          <p className="text-dreams-textSecondary mt-0.5">
            Send platform-wide announcements and review past broadcasts
          </p>
        </div>
      </div>

      {/* Compose form */}
      <form
        onSubmit={handleSend}
        className="bg-white rounded-xl border border-dreams-border shadow-card p-6 space-y-4"
      >
        <div className="flex items-center gap-2">
          <Megaphone className="h-5 w-5 text-dreams-blue" />
          <h2 className="text-lg font-semibold text-dreams-textPrimary">
            New announcement
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-dreams-textPrimary mb-1">
              Title <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              maxLength={255}
              placeholder="e.g. Scheduled maintenance this Sunday"
              className="h-10 w-full px-3 rounded-lg border border-dreams-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-dreams-textPrimary mb-1">
              Audience
            </label>
            <select
              value={targetRole}
              onChange={(e) => setTargetRole(e.target.value as BroadcastTargetRole)}
              className="h-10 w-full px-3 rounded-lg border border-dreams-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
            >
              {AUDIENCE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-dreams-textPrimary mb-1">
            Message <span className="text-red-500">*</span>
          </label>
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={4}
            maxLength={5000}
            placeholder="Write the announcement shown to recipients in their notifications feed."
            className="w-full px-3 py-2 rounded-lg border border-dreams-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue resize-y"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-dreams-textPrimary mb-1">
            Action URL <span className="text-dreams-textSecondary font-normal">(optional)</span>
          </label>
          <input
            type="text"
            value={actionUrl}
            onChange={(e) => setActionUrl(e.target.value)}
            maxLength={512}
            placeholder="/patient/appointments or https://…"
            className="h-10 w-full px-3 rounded-lg border border-dreams-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
          />
          <p className="text-xs text-dreams-textSecondary mt-1">
            Recipients are taken to this link when they tap the notification.
          </p>
        </div>

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={sending}
            className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-dreams-blue text-white text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            <Send className="h-4 w-4" />
            {sending ? "Sending..." : "Send announcement"}
          </button>
        </div>
      </form>

      {/* Recent broadcasts */}
      <div className="bg-white rounded-xl border border-dreams-border overflow-hidden shadow-card">
        <div className="px-5 py-4 border-b border-dreams-border">
          <h2 className="text-lg font-semibold text-dreams-textPrimary">
            Recent broadcasts
          </h2>
        </div>
        {isLoading ? (
          <div className="flex justify-center py-12">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
          </div>
        ) : error ? (
          <p className="px-5 py-12 text-center text-red-600 text-sm">
            Failed to load broadcasts
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-dreams-lightBg border-b border-dreams-border">
              <tr>
                <th className="px-5 py-3 text-left font-semibold text-dreams-textSecondary">
                  Sent
                </th>
                <th className="px-5 py-3 text-left font-semibold text-dreams-textSecondary">
                  Title
                </th>
                <th className="px-5 py-3 text-left font-semibold text-dreams-textSecondary">
                  Audience
                </th>
                <th className="px-5 py-3 text-left font-semibold text-dreams-textSecondary">
                  Recipients
                </th>
                <th className="px-5 py-3 text-left font-semibold text-dreams-textSecondary">
                  Sent by
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-dreams-border">
              {broadcasts.length === 0 ? (
                <tr>
                  <td
                    colSpan={5}
                    className="px-5 py-12 text-center text-dreams-textSecondary"
                  >
                    No broadcasts sent yet
                  </td>
                </tr>
              ) : (
                broadcasts.map((b) => (
                  <tr key={b.id} className="hover:bg-dreams-lightBg transition-colors">
                    <td className="px-5 py-3 text-dreams-textSecondary whitespace-nowrap">
                      {formatDateTime(b.sent_at)}
                    </td>
                    <td className="px-5 py-3 text-dreams-textPrimary max-w-xs">
                      <p className="font-medium truncate" title={b.title ?? ""}>
                        {b.title}
                      </p>
                      {b.body && (
                        <p
                          className="text-xs text-dreams-textSecondary truncate"
                          title={b.body}
                        >
                          {b.body}
                        </p>
                      )}
                    </td>
                    <td className="px-5 py-3">
                      <Badge
                        variant={
                          (AUDIENCE_BADGE[b.target_role ?? "all"] as any) ??
                          "default"
                        }
                      >
                        {b.target_role ?? "all"}
                      </Badge>
                    </td>
                    <td className="px-5 py-3 text-dreams-textPrimary">
                      {b.recipient_count ?? 0}
                    </td>
                    <td className="px-5 py-3 text-dreams-textSecondary">
                      {b.sent_by_name ?? (
                        <span className="italic">System</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-dreams-textSecondary">
            Page {page} of {totalPages} · {data?.total} total
          </p>
          <div className="flex gap-2">
            <button
              disabled={page === 1}
              onClick={() => setPage((p) => p - 1)}
              className="px-4 py-2 text-sm rounded-lg border border-dreams-border bg-white disabled:opacity-40 hover:bg-dreams-lightBg transition-colors"
            >
              Previous
            </button>
            <button
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="px-4 py-2 text-sm rounded-lg border border-dreams-border bg-white disabled:opacity-40 hover:bg-dreams-lightBg transition-colors"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
