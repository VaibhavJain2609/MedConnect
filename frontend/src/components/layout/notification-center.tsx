"use client";

import * as React from "react";
import { Bell, Check, X, Calendar, TestTube, AlertCircle, Pill, CheckCircle, XCircle } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getNotifications,
  markAsRead,
  markAllAsRead,
  type Notification,
} from "@/lib/api/notifications";
import { actOnRecordAccessRequest } from "@/lib/api/record-access";
import { useAuthStore } from "@/stores/auth-store";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

/**
 * NotificationCenter Component
 *
 * Displays notifications with badge count and dropdown panel
 *
 * Features:
 * - Bell icon with unread count badge
 * - Dropdown panel with notification list
 * - Mark as read/unread
 * - Category icons (Appointments, Lab Results, System)
 * - Real-time updates (polling or WebSocket)
 *
 * @example
 * <NotificationCenter />
 */
export const NotificationCenter: React.FC = () => {
  const [isOpen, setIsOpen] = React.useState(false);
  const queryClient = useQueryClient();
  const { user } = useAuthStore();
  const dropdownRef = React.useRef<HTMLDivElement>(null);

  // Fetch notifications
  const { data } = useQuery({
    queryKey: ["notifications"],
    queryFn: () => getNotifications({ limit: 20 }),
    refetchInterval: 30000, // Poll every 30 seconds
  });

  const notifications = data?.notifications || [];
  const unreadCountFromAPI = data?.unread_count || 0;

  // Mark notification as read
  const markAsReadMutation = useMutation({
    mutationFn: (notificationId: string) => markAsRead(notificationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  // Mark all as read
  const markAllAsReadMutation = useMutation({
    mutationFn: () => markAllAsRead(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  // Inline consent action (patient only)
  const consentActionMutation = useMutation({
    mutationFn: ({ consentId, action }: { consentId: string; action: "approved" | "rejected" }) =>
      actOnRecordAccessRequest(consentId, action),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
      queryClient.invalidateQueries({ queryKey: ["record-access-requests"] });
    },
  });

  // Close dropdown when clicking outside
  React.useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const unreadCount = unreadCountFromAPI;

  const getNotificationIcon = (type: Notification["type"]) => {
    switch (type) {
      case "appointment":
        return <Calendar className="h-5 w-5 text-dreams-blue" />;
      case "lab_result":
        return <TestTube className="h-5 w-5 text-status-completed" />;
      case "prescription":
        return <Pill className="h-5 w-5 text-status-inProgress" />;
      case "message":
        return <Bell className="h-5 w-5 text-dreams-blue" />;
      case "system":
        return <AlertCircle className="h-5 w-5 text-status-pending" />;
      default:
        return <Bell className="h-5 w-5 text-dreams-textSecondary" />;
    }
  };

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = Math.floor((now.getTime() - date.getTime()) / 1000);

    if (diff < 60) return "Just now";
    if (diff < 3600) return `${Math.floor(diff / 60)} minutes ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} hours ago`;
    if (diff < 604800) return `${Math.floor(diff / 86400)} days ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Bell Icon Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 rounded-lg hover:bg-dreams-lightBg transition-colors"
        aria-label="Notifications"
      >
        <Bell className="h-5 w-5 text-dreams-textSecondary" />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 h-5 w-5 bg-status-overdue text-white text-xs font-bold rounded-full flex items-center justify-center">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown Panel */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-[calc(100vw-1rem)] sm:w-96 bg-white rounded-lg shadow-lg border border-dreams-border z-50">
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-dreams-border">
            <div className="flex items-center gap-2">
              <h3 className="font-bold text-dreams-textPrimary">
                Notifications
              </h3>
              {unreadCount > 0 && (
                <Badge variant="pending" className="text-xs">
                  {unreadCount} New
                </Badge>
              )}
            </div>
            {unreadCount > 0 && (
              <button
                onClick={() => markAllAsReadMutation.mutate()}
                className="text-xs text-dreams-blue hover:underline"
              >
                Mark all read
              </button>
            )}
          </div>

          {/* Notification List */}
          <div className="max-h-96 overflow-y-auto">
            {notifications && notifications.length > 0 ? (
              notifications.map((notification) => (
                <div
                  key={notification.id}
                  className={cn(
                    "p-4 border-b border-dreams-border hover:bg-dreams-lightBg/50 transition-colors cursor-pointer",
                    !notification.read && "bg-dreams-blue/5"
                  )}
                  onClick={() => {
                    if (!notification.read) {
                      markAsReadMutation.mutate(notification.id);
                    }
                    if (notification.action_url) {
                      window.location.href = notification.action_url;
                    }
                  }}
                >
                  <div className="flex gap-3">
                    {/* Icon */}
                    <div className="flex-shrink-0 mt-1">
                      {getNotificationIcon(notification.type)}
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2 mb-1">
                        <p className="font-medium text-sm text-dreams-textPrimary">
                          {notification.title}
                        </p>
                        {!notification.read && (
                          <div className="h-2 w-2 bg-dreams-blue rounded-full flex-shrink-0 mt-1" />
                        )}
                      </div>
                      <p className="text-sm text-dreams-textSecondary mb-2">
                        {notification.message}
                      </p>
                      <p className="text-xs text-dreams-textSecondary">
                        {formatTimestamp(notification.created_at)}
                      </p>

                      {/* Inline consent actions for patients */}
                      {user?.role === "patient" && notification.metadata?.consent_id && !notification.read && (
                        <div className="mt-2 flex gap-2" onClick={(e) => e.stopPropagation()}>
                          <button
                            disabled={consentActionMutation.isPending}
                            onClick={() =>
                              consentActionMutation.mutate({
                                consentId: notification.metadata!.consent_id,
                                action: "approved",
                              })
                            }
                            className="flex items-center gap-1 rounded-lg bg-green-50 px-2.5 py-1 text-xs font-medium text-green-700 hover:bg-green-100 disabled:opacity-50"
                          >
                            <CheckCircle className="h-3 w-3" />
                            Approve
                          </button>
                          <button
                            disabled={consentActionMutation.isPending}
                            onClick={() =>
                              consentActionMutation.mutate({
                                consentId: notification.metadata!.consent_id,
                                action: "rejected",
                              })
                            }
                            className="flex items-center gap-1 rounded-lg bg-red-50 px-2.5 py-1 text-xs font-medium text-red-700 hover:bg-red-100 disabled:opacity-50"
                          >
                            <XCircle className="h-3 w-3" />
                            Reject
                          </button>
                        </div>
                      )}
                    </div>

                    {/* Mark as read button */}
                    {!notification.read && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          markAsReadMutation.mutate(notification.id);
                        }}
                        className="flex-shrink-0 p-1 rounded hover:bg-dreams-lightBg"
                        aria-label="Mark as read"
                      >
                        <Check className="h-4 w-4 text-dreams-textSecondary" />
                      </button>
                    )}
                  </div>
                </div>
              ))
            ) : (
              <div className="p-8 text-center">
                <Bell className="h-12 w-12 text-dreams-textSecondary mx-auto mb-3 opacity-50" />
                <p className="text-dreams-textSecondary">
                  No notifications yet
                </p>
              </div>
            )}
          </div>

          {/* Footer */}
          {notifications && notifications.length > 0 && (
            <div className="p-3 text-center border-t border-dreams-border">
              <a
                href={
                  user?.role === "admin"
                    ? "/admin/notifications"
                    : user?.role === "doctor"
                    ? "/doctor/notifications"
                    : "/patient/notifications"
                }
                className="text-sm text-dreams-blue hover:underline"
              >
                View all notifications
              </a>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

NotificationCenter.displayName = "NotificationCenter";
