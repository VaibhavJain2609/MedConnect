"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Bell, Check, Calendar, TestTube, AlertCircle, Pill, Trash2,
  CheckCircle, XCircle, Filter,
} from "lucide-react";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  getNotifications,
  markAsRead,
  markAllAsRead,
  deleteNotification,
  deleteAllRead,
  type Notification,
} from "@/lib/api/notifications";

const PAGE_SIZE = 20;

const TYPE_OPTIONS = [
  { value: "", label: "All" },
  { value: "appointment", label: "Appointments" },
  { value: "prescription", label: "Prescriptions" },
  { value: "lab_result", label: "Lab Results" },
  { value: "system", label: "System" },
  { value: "message", label: "Messages" },
];

function getIcon(type: Notification["type"]) {
  switch (type) {
    case "appointment": return <Calendar className="h-5 w-5 text-dreams-blue" />;
    case "lab_result":  return <TestTube className="h-5 w-5 text-status-completed" />;
    case "prescription": return <Pill className="h-5 w-5 text-status-inProgress" />;
    case "system":      return <AlertCircle className="h-5 w-5 text-status-pending" />;
    default:            return <Bell className="h-5 w-5 text-dreams-textSecondary" />;
  }
}

function formatTimestamp(ts: string) {
  const date = new Date(ts);
  const diff = Math.floor((Date.now() - date.getTime()) / 1000);
  if (diff < 60) return "Just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
  return date.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

export default function DoctorNotificationsPage() {
  const queryClient = useQueryClient();
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [typeFilter, setTypeFilter] = useState("");
  const [offset, setOffset] = useState(0);

  const { data, isLoading } = useQuery({
    queryKey: ["notifications-all", unreadOnly, typeFilter, offset],
    queryFn: () =>
      getNotifications({
        unread_only: unreadOnly,
        type: typeFilter || undefined,
        limit: PAGE_SIZE,
        offset,
      }),
  });

  const notifications = data?.notifications ?? [];
  const total = data?.total ?? 0;
  const unreadCount = data?.unread_count ?? 0;

  const markReadMutation = useMutation({
    mutationFn: markAsRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
      queryClient.invalidateQueries({ queryKey: ["notifications-all"] });
    },
  });

  const markAllMutation = useMutation({
    mutationFn: markAllAsRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
      queryClient.invalidateQueries({ queryKey: ["notifications-all"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteNotification,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
      queryClient.invalidateQueries({ queryKey: ["notifications-all"] });
    },
  });

  const deleteReadMutation = useMutation({
    mutationFn: deleteAllRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
      queryClient.invalidateQueries({ queryKey: ["notifications-all"] });
    },
  });

  const totalPages = Math.ceil(total / PAGE_SIZE);
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

  function handleFilter(key: "unread" | "type", value: string | boolean) {
    setOffset(0);
    if (key === "unread") setUnreadOnly(value as boolean);
    if (key === "type") setTypeFilter(value as string);
  }

  return (
    <div className="space-y-6">
      <Breadcrumb items={[{ label: "Notifications" }]} />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-dreams-textPrimary">Notifications</h1>
          {unreadCount > 0 && (
            <p className="text-sm text-dreams-textSecondary mt-0.5">
              {unreadCount} unread
            </p>
          )}
        </div>
        <div className="flex gap-2">
          {unreadCount > 0 && (
            <button
              onClick={() => markAllMutation.mutate()}
              disabled={markAllMutation.isPending}
              className="flex items-center gap-1.5 rounded-lg border border-dreams-border bg-white px-3 py-2 text-sm font-medium text-dreams-textPrimary hover:bg-dreams-lightBg disabled:opacity-50"
            >
              <CheckCircle className="h-4 w-4" />
              Mark all read
            </button>
          )}
          <button
            onClick={() => deleteReadMutation.mutate()}
            disabled={deleteReadMutation.isPending}
            className="flex items-center gap-1.5 rounded-lg border border-dreams-border bg-white px-3 py-2 text-sm font-medium text-dreams-textPrimary hover:bg-dreams-lightBg disabled:opacity-50"
          >
            <Trash2 className="h-4 w-4" />
            Clear read
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <div className="flex items-center gap-1.5 text-sm text-dreams-textSecondary">
          <Filter className="h-4 w-4" />
          <span>Filter:</span>
        </div>
        <button
          onClick={() => handleFilter("unread", !unreadOnly)}
          className={cn(
            "rounded-full px-3 py-1 text-sm font-medium border transition-colors",
            unreadOnly
              ? "bg-dreams-blue text-white border-dreams-blue"
              : "bg-white text-dreams-textPrimary border-dreams-border hover:bg-dreams-lightBg"
          )}
        >
          Unread only
        </button>
        {TYPE_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            onClick={() => handleFilter("type", opt.value)}
            className={cn(
              "rounded-full px-3 py-1 text-sm font-medium border transition-colors",
              typeFilter === opt.value
                ? "bg-dreams-blue text-white border-dreams-blue"
                : "bg-white text-dreams-textPrimary border-dreams-border hover:bg-dreams-lightBg"
            )}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {/* List */}
      <div className="bg-white rounded-xl border border-dreams-border shadow-card overflow-hidden">
        {isLoading ? (
          <div className="p-12 text-center text-dreams-textSecondary">Loading...</div>
        ) : notifications.length === 0 ? (
          <div className="p-12 flex flex-col items-center justify-center text-center">
            <Bell className="h-10 w-10 text-dreams-textSecondary opacity-40 mb-3" />
            <p className="text-dreams-textSecondary">No notifications</p>
          </div>
        ) : (
          <ul className="divide-y divide-dreams-border">
            {notifications.map((n) => (
              <li
                key={n.id}
                className={cn(
                  "flex gap-3 p-4 hover:bg-dreams-lightBg/50 transition-colors",
                  !n.read && "bg-dreams-blue/5"
                )}
              >
                <div className="flex-shrink-0 mt-0.5">{getIcon(n.type)}</div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2">
                    <p className="font-medium text-sm text-dreams-textPrimary">{n.title}</p>
                    <div className="flex items-center gap-1.5 flex-shrink-0">
                      {!n.read && (
                        <span className="h-2 w-2 rounded-full bg-dreams-blue" />
                      )}
                      <span className="text-xs text-dreams-textSecondary whitespace-nowrap">
                        {formatTimestamp(n.created_at)}
                      </span>
                    </div>
                  </div>
                  <p className="text-sm text-dreams-textSecondary mt-0.5">{n.message}</p>
                  {n.action_url && (
                    <a
                      href={n.action_url}
                      className="mt-1 text-xs text-dreams-blue hover:underline"
                      onClick={() => !n.read && markReadMutation.mutate(n.id)}
                    >
                      View details
                    </a>
                  )}
                </div>

                {/* Actions */}
                <div className="flex-shrink-0 flex items-start gap-1 pt-0.5">
                  {!n.read && (
                    <button
                      onClick={() => markReadMutation.mutate(n.id)}
                      disabled={markReadMutation.isPending}
                      className="p-1.5 rounded hover:bg-dreams-lightBg text-dreams-textSecondary"
                      title="Mark as read"
                    >
                      <Check className="h-3.5 w-3.5" />
                    </button>
                  )}
                  <button
                    onClick={() => deleteMutation.mutate(n.id)}
                    disabled={deleteMutation.isPending}
                    className="p-1.5 rounded hover:bg-red-50 text-dreams-textSecondary hover:text-red-500"
                    title="Delete"
                  >
                    <XCircle className="h-3.5 w-3.5" />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm text-dreams-textSecondary">
          <span>
            Showing {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total}
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setOffset((p) => Math.max(0, p - PAGE_SIZE))}
              disabled={currentPage === 1}
              className="rounded-lg border border-dreams-border bg-white px-3 py-1.5 hover:bg-dreams-lightBg disabled:opacity-40"
            >
              Previous
            </button>
            <button
              onClick={() => setOffset((p) => p + PAGE_SIZE)}
              disabled={currentPage === totalPages}
              className="rounded-lg border border-dreams-border bg-white px-3 py-1.5 hover:bg-dreams-lightBg disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
