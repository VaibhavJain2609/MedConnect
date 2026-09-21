/**
 * Admin Audit Log API Functions
 * Wraps GET /api/v1/admin/audit (requires admin role).
 */

import api from "@/lib/api";
import { downloadFile } from "@/lib/download";

export interface AdminAuditLogEntry {
  id: string;
  table_name: string;
  record_id: string;
  record_id_short: string;
  action: string; // INSERT | UPDATE | DELETE | READ
  changed_by: string | null;
  changed_by_name: string | null;
  changed_at: string;
  old_values: Record<string, any> | null;
  new_values: Record<string, any> | null;
  changes_summary: string | null;
}

export interface AdminAuditLogsResponse {
  data: AdminAuditLogEntry[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}

export interface AdminAuditLogsParams {
  table_name?: string;
  record_id?: string;
  changed_by_name?: string;
  /** Filter to changes made by this user (actor — audit_logs.changed_by). */
  user_id?: string;
  from_date?: string;
  to_date?: string;
  page?: number;
  limit?: number;
}

export async function getAdminAuditLogs(
  params: AdminAuditLogsParams = {}
): Promise<AdminAuditLogsResponse> {
  const response = await api.get("/api/v1/admin/audit", { params });
  return response.data;
}

export type AdminAuditLogsExportParams = Omit<
  AdminAuditLogsParams,
  "page" | "limit"
>;

/**
 * Download the audit-log CSV export.
 *
 * Hits GET /api/v1/admin/audit-logs/export with the same filters as the
 * list endpoint. The filename (audit-logs-<date>.csv) is resolved from
 * the response's Content-Disposition header by downloadFile().
 */
export async function exportAuditLogsCsv(
  params: AdminAuditLogsExportParams = {}
): Promise<void> {
  const qs = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) qs.set(key, value);
  }
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  await downloadFile(`/api/v1/admin/audit-logs/export${suffix}`);
}
