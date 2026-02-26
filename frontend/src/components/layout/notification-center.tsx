"use client";

import * as React from "react";
import { Bell, Check, X, Calendar, TestTube, AlertCircle } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

interface Notification {
  id: string;
  type: "appointment" | "lab_result" | "system";
  title: string;
  message: string;
  timestamp: string;
  read: boolean;
  actionUrl?: string;
}

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
  const dropdownRef = React.useRef<HTMLDivElement>(null);

  // Fetch notifications
  const { data: notifications } = useQuery({
    queryKey: ["notifications"],
    queryFn: async () => {
      // TODO: Replace with actual API call to /api/v1/notifications
      // Mock data for now
      return [
        {
          id: "1",
          type: "appointment",
          title: "Upcoming Appointment",
          message: "Appointment with Dr. Sarah Smith tomorrow at 10:00 AM",
          timestamp: "2 hours ago",
          read: false,
        },
        {
          id: "2",
          type: "lab_result",
          title: "Lab Results Available",
          message: "Complete Blood Count (CBC) results are ready to view",
          timestamp: "5 hours ago",
          read: false,
        },
        {
          id: "3",
          type: "system",
          title: "System Maintenance",
          message: "Scheduled maintenance tonight from 12:00 AM to 2:00 AM",
          timestamp: "1 day ago",
          read: true,
        },
        {
          id: "4",
          type: "appointment",
          title: "Appointment Confirmed",
          message: "Your appointment request has been approved",
          timestamp: "2 days ago",
          read: true,
        },
      ] as Notification[];
    },
    refetchInterval: 30000, // Poll every 30 seconds
  });

  // Mark notification as read
  const markAsReadMutation = useMutation({
    mutationFn: async (notificationId: string) => {
      // TODO: Replace with actual API call
      return Promise.resolve();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  // Mark all as read
  const markAllAsReadMutation = useMutation({
    mutationFn: async () => {
      // TODO: Replace with actual API call
      return Promise.resolve();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
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

  const unreadCount = notifications?.filter((n) => !n.read).length || 0;

  const getNotificationIcon = (type: Notification["type"]) => {
    switch (type) {
      case "appointment":
        return <Calendar className="h-5 w-5 text-dreams-blue" />;
      case "lab_result":
        return <TestTube className="h-5 w-5 text-status-completed" />;
      case "system":
        return <AlertCircle className="h-5 w-5 text-status-pending" />;
      default:
        return <Bell className="h-5 w-5 text-dreams-textSecondary" />;
    }
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
        <div className="absolute right-0 mt-2 w-96 bg-white rounded-lg shadow-lg border border-dreams-border z-50">
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
                    if (notification.actionUrl) {
                      window.location.href = notification.actionUrl;
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
                        {notification.timestamp}
                      </p>
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
                href="/notifications"
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
