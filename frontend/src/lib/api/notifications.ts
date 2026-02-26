/**
 * Notifications API Functions
 * Handles user notifications
 */

import api from "../api";

export interface Notification {
  id: string;
  user_id: string;
  type: "appointment" | "lab_result" | "prescription" | "system" | "message";
  title: string;
  message: string;
  read: boolean;
  action_url?: string;
  metadata?: Record<string, any>;
  created_at: string;
  read_at?: string;
}

export interface NotificationsListParams {
  unread_only?: boolean;
  type?: string;
  limit?: number;
  offset?: number;
}

export interface NotificationsListResponse {
  notifications: Notification[];
  total: number;
  unread_count: number;
}

/**
 * Get user notifications
 */
export async function getNotifications(
  params: NotificationsListParams = {}
): Promise<NotificationsListResponse> {
  const queryParams = new URLSearchParams();

  if (params.unread_only) {
    queryParams.append("unread_only", "true");
  }
  if (params.type) {
    queryParams.append("type", params.type);
  }
  if (params.limit) {
    queryParams.append("limit", params.limit.toString());
  }
  if (params.offset) {
    queryParams.append("offset", params.offset.toString());
  }

  const response = await api.get(`/api/v1/notifications?${queryParams}`);
  return response.data;
}

/**
 * Get unread notification count
 */
export async function getUnreadCount(): Promise<number> {
  const response = await api.get("/api/v1/notifications/unread-count");
  return response.data.count || 0;
}

/**
 * Mark notification as read
 */
export async function markAsRead(id: string): Promise<Notification> {
  const response = await api.post(`/api/v1/notifications/${id}/read`);
  return response.data;
}

/**
 * Mark notification as unread
 */
export async function markAsUnread(id: string): Promise<Notification> {
  const response = await api.post(`/api/v1/notifications/${id}/unread`);
  return response.data;
}

/**
 * Mark all notifications as read
 */
export async function markAllAsRead(): Promise<void> {
  await api.post("/api/v1/notifications/read-all");
}

/**
 * Delete notification
 */
export async function deleteNotification(id: string): Promise<void> {
  await api.delete(`/api/v1/notifications/${id}`);
}

/**
 * Delete all read notifications
 */
export async function deleteAllRead(): Promise<void> {
  await api.delete("/api/v1/notifications/read");
}

/**
 * Get notification preferences
 */
export async function getNotificationPreferences(): Promise<Record<string, boolean>> {
  const response = await api.get("/api/v1/notifications/preferences");
  return response.data;
}

/**
 * Update notification preferences
 */
export async function updateNotificationPreferences(
  preferences: Record<string, boolean>
): Promise<Record<string, boolean>> {
  const response = await api.put("/api/v1/notifications/preferences", preferences);
  return response.data;
}

/**
 * WebSocket connection for real-time notifications
 * Note: This requires WebSocket implementation on the backend
 */
export function connectNotificationWebSocket(
  onNotification: (notification: Notification) => void,
  onError?: (error: Event) => void
): WebSocket | null {
  if (typeof window === "undefined") return null;

  const token = localStorage.getItem("access_token");
  if (!token) return null;

  const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${wsProtocol}//${window.location.host}/ws/notifications?token=${token}`;

  const ws = new WebSocket(wsUrl);

  ws.onmessage = (event) => {
    try {
      const notification = JSON.parse(event.data);
      onNotification(notification);
    } catch (error) {
      console.error("Failed to parse notification:", error);
    }
  };

  ws.onerror = (error) => {
    console.error("WebSocket error:", error);
    if (onError) onError(error);
  };

  ws.onclose = () => {
    console.log("WebSocket connection closed");
  };

  return ws;
}
