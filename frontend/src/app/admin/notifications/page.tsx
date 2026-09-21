"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, Megaphone, Send, Users } from "lucide-react";
import { toast } from "@/hooks/use-toast";
import {
  BroadcastAudience,
  BroadcastType,
  BroadcastsResponse,
  broadcastNotification,
  getBroadcastAudienceCount,
  listBroadcasts,
} from "@/lib/api/notifications";
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
} from "@/components/ui/alert-dialog";

const AUDIENCE_OPTIONS: { value: BroadcastAudience; label: string }[] = [
  { value: "all", label: "All users" },
  { value: "patients", label: "Patients" },
  { value: "doctors", label: "Doctors" },
  { value: "admins", label: "Admins" },
];

const AUDIENCE_LABEL: Record<string, string> = {
  all: "All users",
  patients: "Patients",
  doctors: "Doctors",
  admins: "Admins",
  // legacy singular values from older broadcast rows
  patient: "Patients",
  doctor: "Doctors",
  admin: "Admins",
};

const AUDIENCE_BADGE: Record<string, string> = {
  all: "inProgress",
  patients: "completed",
  doctors: "upcoming",
  admins: "overdue",
  patient: "completed",
  doctor: "upcoming",
  admin: "overdue",
};

const TYPE_OPTIONS: { value: BroadcastType; label: string }[] = [
  { value: "system", label: "System" },
  { value: "info", label: "Info" },
  { value: "warning", label: "Warning" },
];

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
  const [audience, setAudience] = useState<BroadcastAudience>("all");
  const [notifType, setNotifType] = useState<BroadcastType>("system");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [sending, setSending] = useState(false);

  // Live recipient preview for the selected audience
  const { data: audienceCount } = useQuery({
    queryKey: ["admin-broadcast-count", audience],
    queryFn: () => getBroadcastAudienceCount(audience),
  });

  const { data, isLoading, error } = useQuery<BroadcastsResponse>({
    queryKey: ["admin-broadcasts"],
    queryFn: () => listBroadcasts(1, 10),
  });

  const broadcasts = data?.data ?? [];
  const recipientCount = audienceCount?.count;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !body.trim()) {
      toast({
        title: "Missing fields",
        description: "Title and message are required.",
        variant: "destructive",
      });
      return;
    }
    setConfirmOpen(true);
  };

  const handleConfirmSend = async () => {
    setSending(true);
    try {
      const result = await broadcastNotification({
        title: title.trim(),
        body: body.trim(),
        audience,
        type: notifType,
      });
      toast({
        title: "Broadcast sent",
        description: `Delivered to ${result.sent} user${
          result.sent === 1 ? "" : "s"
        }.`,
      });
      setTitle("");
      setBody("");
      setAudience("all");
      setNotifType("system");
      queryClient.invalidateQueries({ queryKey: ["admin-broadcasts"] });
    } catch (err) {
      toast({
        title: "Broadcast failed",
        description:
          (err as { userMessage?: string })?.userMessage ||
          (err instanceof Error
            ? err.message
            : "Could not send the announcement."),
        variant: "destructive",
      });
    } finally {
      setSending(false);
      setConfirmOpen(false);
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
          <h1 className="text-3xl font-bold text-dreams-textPrimary">
            Notifications
          </h1>
          <p className="text-dreams-textSecondary mt-0.5">
            Send platform-wide announcements and review past broadcasts
          </p>
        </div>
      </div>

      {/* Compose form */}
      <form
        onSubmit={handleSubmit}
        className="bg-white rounded-xl border border-dreams-border shadow-card p-6 space-y-4"
      >
        <div className="flex items-center gap-2">
          <Megaphone className="h-5 w-5 text-dreams-blue" />
          <h2 className="text-lg font-semibold text-dreams-textPrimary">
            New announcement
          </h2>
        </div>

        <div>
          <label className="block text-sm font-medium text-dreams-textPrimary mb-2">
            Audience
          </label>
          <div className="flex flex-wrap gap-3">
            {AUDIENCE_OPTIONS.map((opt) => (
              <label
                key={opt.value}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg border text-sm cursor-pointer transition-colors ${
                  audience === opt.value
                    ? "border-dreams-blue bg-dreams-blue/5 text-dreams-textPrimary font-medium"
                    : "border-dreams-border bg-white text-dreams-textSecondary hover:bg-dreams-lightBg"
                }`}
              >
                <input
                  type="radio"
                  name="audience"
                  value={opt.value}
                  checked={audience === opt.value}
                  onChange={() => setAudience(opt.value)}
                  className="accent-dreams-blue"
                />
                {opt.label}
              </label>
            ))}
          </div>
          <p className="flex items-center gap-1.5 text-xs text-dreams-textSecondary mt-2">
            <Users className="h-3.5 w-3.5" />
            {recipientCount === undefined
              ? "Counting recipients…"
              : `Will be sent to ${recipientCount} active user${
                  recipientCount === 1 ? "" : "s"
                }`}
          </p>
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
              Type
            </label>
            <select
              value={notifType}
              onChange={(e) => setNotifType(e.target.value as BroadcastType)}
              className="h-10 w-full px-3 rounded-lg border border-dreams-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
            >
              {TYPE_OPTIONS.map((opt) => (
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

      {/* Confirm dialog */}
      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Send this announcement?</AlertDialogTitle>
            <AlertDialogDescription>
              &ldquo;{title.trim()}&rdquo; will be delivered to{" "}
              <strong>
                {recipientCount ?? "…"} {AUDIENCE_LABEL[audience] ?? audience}
              </strong>{" "}
              as a {notifType} notification. This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={sending}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmSend}
              disabled={sending}
              className="bg-dreams-blue text-white hover:opacity-90"
            >
              {sending ? "Sending..." : "Send"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

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
                broadcasts.map((b) => {
                  const audienceKey = b.audience ?? b.target_role ?? "all";
                  return (
                    <tr
                      key={b.id}
                      className="hover:bg-dreams-lightBg transition-colors"
                    >
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
                            (AUDIENCE_BADGE[audienceKey] as any) ?? "default"
                          }
                        >
                          {AUDIENCE_LABEL[audienceKey] ?? audienceKey}
                        </Badge>
                      </td>
                      <td className="px-5 py-3 text-dreams-textPrimary">
                        {b.recipient_count ?? 0}
                      </td>
                      <td className="px-5 py-3 text-dreams-textSecondary">
                        {b.sent_by_name ?? <span className="italic">System</span>}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
