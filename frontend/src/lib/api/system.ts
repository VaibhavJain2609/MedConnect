/**
 * System Health API Functions
 * Wraps the public /health probe and the admin-only /api/v1/admin/system/status
 * diagnostics endpoint for the admin System Health page.
 */

import api from "../api";

export interface PublicHealth {
  status: "ok" | "degraded";
  db: "ok" | "error";
  medicine_db: "ok" | "error";
  redis: "ok" | "error";
  version: string;
}

export interface DependencyStatus {
  status: "ok" | "error";
  latency_ms: number | null;
}

export interface QueueStatus {
  pending: number | null;
  deferred: number | null;
  in_progress: number | null;
  worker_last_heartbeat: string | null;
}

export interface SystemCounts {
  users: number;
  patients: number;
  doctors: number;
  clinics: number;
  appointments_today: number;
}

export interface SystemStatus {
  status: "ok" | "degraded";
  version: string;
  checked_at: string;
  started_at: string;
  uptime_seconds: number;
  dependencies: {
    db: DependencyStatus;
    medicine_db: DependencyStatus;
    redis: DependencyStatus;
  };
  queue: QueueStatus;
  counts: SystemCounts | null;
  last_audit_at: string | null;
}

/**
 * Public deep-health probe (GET /health). Returns 503 when a dependency is
 * down, so accept every status code — the body still reports which dep failed.
 */
export async function getPublicHealth(): Promise<PublicHealth> {
  const response = await api.get("/health", { validateStatus: () => true });
  return response.data;
}

/**
 * Admin-only diagnostics: dependency latency, ARQ queue depth, entity counts,
 * last audit timestamp, uptime. Requires an admin token.
 */
export async function getSystemStatus(): Promise<SystemStatus> {
  const response = await api.get("/api/v1/admin/system/status");
  return response.data;
}
