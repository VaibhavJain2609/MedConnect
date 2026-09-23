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
 * Notification preference keys.
 * Both GET and PUT /notifications/preferences return the bare preferences map.
 * sms_notifications / whatsapp_notifications default to false; all others default to true.
 */
export interface NotificationPreferences {
  email_notifications: boolean;
  push_notifications: boolean;
  sms_notifications: boolean;
  whatsapp_notifications: boolean;
  appointment_reminders: boolean;
  queue_updates: boolean;
  lab_results: boolean;
  prescription_alerts: boolean;
  system_alerts: boolean;
}

export type NotificationPreferencesUpdate = Partial<NotificationPreferences>;

/**
 * Get notification preferences
 */
export async function getNotificationPreferences(): Promise<NotificationPreferences> {
  const response = await api.get("/api/v1/notifications/preferences");
  return response.data;
}

/**
 * Update notification preferences
 * Only the keys sent are updated; unset keys keep their current value.
 */
export async function updateNotificationPreferences(
  preferences: NotificationPreferencesUpdate
): Promise<NotificationPreferences> {
  const response = await api.put("/api/v1/notifications/preferences", preferences);
  return response.data;
}

/* ------------------------------------------------------------------------ */
/* Admin announcement broadcasts                                             */
/* ------------------------------------------------------------------------ */

export type BroadcastAudience = "all" | "patients" | "doctors" | "admins";
export type BroadcastType = "system" | "info" | "warning";

export interface BroadcastRequest {
  title: string;
  body: string;
  audience: BroadcastAudience;
  type?: BroadcastType;
  action_url?: string;
}

export interface BroadcastResult {
  sent: number;
  audience: BroadcastAudience;
  broadcast_id: string;
  title: string;
  target_role: "all" | "patient" | "doctor" | "admin";
  recipient_count: number;
  type: BroadcastType;
}

export interface BroadcastAudienceCount {
  audience: BroadcastAudience;
  count: number;
}

export interface BroadcastEntry {
  id: string;
  broadcast_id: string;
  title: string | null;
  body: string | null;
  audience: BroadcastAudience | null;
  target_role: "all" | "patient" | "doctor" | "admin" | null;
  type: BroadcastType | null;
  action_url: string | null;
  recipient_count: number | null;
  sent_by: string | null;
  sent_by_name: string | null;
  sent_at: string;
}

export interface BroadcastsResponse {
  data: BroadcastEntry[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}

/**
 * Broadcast an announcement notification to every active user in the audience (admin only)
 */
export async function broadcastNotification(
  payload: BroadcastRequest
): Promise<BroadcastResult> {
  const response = await api.post(
    "/api/v1/admin/notifications/broadcast",
    payload
  );
  return response.data;
}

/**
 * Preview how many active users a broadcast audience targets (admin only)
 */
export async function getBroadcastAudienceCount(
  audience: BroadcastAudience
): Promise<BroadcastAudienceCount> {
  const response = await api.get(
    `/api/v1/admin/notifications/broadcast/count?audience=${audience}`
  );
  return response.data;
}

/**
 * List past announcement broadcasts, newest first (admin only)
 */
export async function listBroadcasts(
  page = 1,
  limit = 10
): Promise<BroadcastsResponse> {
  const response = await api.get(
    `/api/v1/admin/notifications/broadcasts?page=${page}&limit=${limit}`
  );
  return response.data;
}
