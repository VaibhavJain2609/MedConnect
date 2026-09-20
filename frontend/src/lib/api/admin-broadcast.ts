/**
 * Admin Announcement Broadcasts + Platform Settings API Functions
 */

import api from "../api";

export type BroadcastTargetRole = "all" | "patient" | "doctor" | "admin";

export interface BroadcastRequest {
  title: string;
  body: string;
  target_role: BroadcastTargetRole;
  action_url?: string;
}

export interface BroadcastResult {
  broadcast_id: string;
  title: string;
  target_role: BroadcastTargetRole;
  recipient_count: number;
}

export interface BroadcastEntry {
  id: string;
  broadcast_id: string;
  title: string | null;
  body: string | null;
  target_role: BroadcastTargetRole | null;
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

export interface PlatformSetting {
  key: string;
  value: unknown;
  description: string | null;
  updated_by: string | null;
  updated_at: string | null;
}

export interface PlatformSettingsResponse {
  data: PlatformSetting[];
}

/**
 * Send an announcement notification to all matching active users
 */
export async function sendBroadcast(
  payload: BroadcastRequest
): Promise<BroadcastResult> {
  const response = await api.post(
    "/api/v1/admin/notifications/broadcast",
    payload
  );
  return response.data;
}

/**
 * List past announcement broadcasts
 */
export async function listBroadcasts(
  page = 1,
  limit = 20
): Promise<BroadcastsResponse> {
  const response = await api.get(
    `/api/v1/admin/notifications/broadcasts?page=${page}&limit=${limit}`
  );
  return response.data;
}

/**
 * Get all platform settings / feature flags
 */
export async function getPlatformSettings(): Promise<PlatformSetting[]> {
  const response = await api.get("/api/v1/admin/settings");
  return response.data.data || [];
}

/**
 * Update a single platform setting (upsert by key)
 */
export async function updatePlatformSetting(
  key: string,
  value: unknown,
  description?: string
): Promise<PlatformSetting[]> {
  const response = await api.put("/api/v1/admin/settings", {
    key,
    value,
    ...(description !== undefined ? { description } : {}),
  });
  return response.data.data || [];
}

/**
 * Bulk update platform settings
 */
export async function updatePlatformSettings(
  settings: Record<string, unknown>
): Promise<PlatformSetting[]> {
  const response = await api.put("/api/v1/admin/settings", { settings });
  return response.data.data || [];
}
