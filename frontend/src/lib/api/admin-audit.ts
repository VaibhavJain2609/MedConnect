/**
 * Admin Audit Log API Functions
 * Wraps GET /api/v1/admin/audit (requires admin role).
 */

import api from "@/lib/api";

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
