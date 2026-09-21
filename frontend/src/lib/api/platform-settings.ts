/**
 * Admin Platform Settings / Feature Flags API Functions
 *
 * Backed by GET/PUT /api/v1/admin/settings (routers/admin/broadcast.py).
 */

import api from "../api";

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
