"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Building2,
  Calendar,
  CheckCircle2,
  Database,
  HardDrive,
  RefreshCw,
  Server,
  Stethoscope,
  Tablets,
  Users,
  XCircle,
} from "lucide-react";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import {
  getPublicHealth,
  getSystemStatus,
  PublicHealth,
} from "@/lib/api/system";
import { cn } from "@/lib/utils";

const REFRESH_INTERVAL_MS = 30_000;
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface HealthWithRtt {
  health: PublicHealth | null;
  /** Client-measured round-trip to GET /health in ms; null when unreachable. */
  rttMs: number | null;
}

async function fetchHealthWithRtt(): Promise<HealthWithRtt> {
  const start = performance.now();
  try {
    const health = await getPublicHealth();
    return { health, rttMs: Math.round(performance.now() - start) };
  } catch {
    return { health: null, rttMs: null };
  }
}

function formatLatency(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "—";
  return `${ms} ms`;
}

function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "medium",
  });
}

function formatUptime(seconds: number | undefined): string {
  if (seconds === undefined) return "—";
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d > 0) return `${d}d ${h}h ${m}m`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m ${seconds % 60}s`;
}

function StatusDot({ ok }: { ok: boolean | null }) {
  return (
    <span
      className={cn(
        "inline-block h-3 w-3 rounded-full flex-shrink-0",
        ok === null
          ? "bg-gray-300"
          : ok
            ? "bg-green-500"
            : "bg-red-500"
      )}
    />
  );
}

function DependencyCard({
  title,
  subtitle,
  icon: Icon,
  ok,
  latency,
}: {
  title: string;
  subtitle: string;
  icon: any;
  ok: boolean | null;
  latency: string;
}) {
  return (
    <div className="bg-white rounded-lg shadow-card p-5">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div
            className={cn(
              "h-10 w-10 rounded-lg flex items-center justify-center",
              ok === null
                ? "bg-gray-100"
                : ok
                  ? "bg-green-100"
                  : "bg-red-100"
            )}
          >
            <Icon
              className={cn(
                "h-5 w-5",
                ok === null
                  ? "text-gray-400"
                  : ok
                    ? "text-green-600"
                    : "text-red-600"
              )}
            />
          </div>
          <div>
            <p className="font-medium text-dreams-textPrimary">{title}</p>
            <p className="text-xs text-dreams-textSecondary">{subtitle}</p>
          </div>
        </div>
        <StatusDot ok={ok} />
      </div>
      <div className="mt-4 flex items-center justify-between">
        <span
          className={cn(
            "text-sm font-medium",
            ok === null
              ? "text-dreams-textSecondary"
              : ok
                ? "text-green-600"
                : "text-red-600"
          )}
        >
          {ok === null ? "Unknown" : ok ? "Healthy" : "Down"}
        </span>
        <span className="text-xs text-dreams-textSecondary">
          {latency}
        </span>
      </div>
    </div>
  );
}

function CountCard({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: number | undefined;
  icon: any;
}) {
  return (
    <div className="bg-white rounded-lg shadow-card p-5">
      <div className="flex items-center gap-3">
        <div className="h-10 w-10 rounded-lg bg-dreams-blue/10 flex items-center justify-center">
          <Icon className="h-5 w-5 text-dreams-blue" />
        </div>
        <div>
          <p className="text-sm text-dreams-textSecondary">{label}</p>
          <p className="text-2xl font-bold text-dreams-textPrimary">
            {value === undefined ? "—" : value.toLocaleString()}
          </p>
        </div>
      </div>
    </div>
  );
}

export default function AdminSystemPage() {
  const healthQuery = useQuery({
    queryKey: ["system-public-health"],
    queryFn: fetchHealthWithRtt,
    refetchInterval: REFRESH_INTERVAL_MS,
  });

  const statusQuery = useQuery({
    queryKey: ["admin-system-status"],
    queryFn: getSystemStatus,
    refetchInterval: REFRESH_INTERVAL_MS,
    retry: 1,
  });

  const health = healthQuery.data?.health ?? null;
  const apiRtt = healthQuery.data?.rttMs ?? null;
  const status = statusQuery.data;

  // Dependency status: prefer admin-endpoint latency, fall back to the
  // public /health probe when the admin endpoint is unavailable (e.g. the
  // admin auth path itself needs the DB, so a DB outage also fails auth).
  const deps = status?.dependencies;
  const dbOk = deps ? deps.db.status === "ok" : health ? health.db === "ok" : null;
  const medDbOk = deps
    ? deps.medicine_db.status === "ok"
    : health
      ? health.medicine_db === "ok"
      : null;
  const redisOk = deps
    ? deps.redis.status === "ok"
    : health
      ? health.redis === "ok"
      : null;
  const apiOk = healthQuery.data ? health !== null : null;

  const overallOk =
    apiOk === true && dbOk === true && medDbOk === true && redisOk === true;
  const anyDown =
    apiOk === false || dbOk === false || medDbOk === false || redisOk === false;

  const isLoading = healthQuery.isLoading && statusQuery.isLoading;

  return (
    <div className="space-y-6">
      <Breadcrumb
        items={[{ label: "System" }, { label: "System Health" }]}
      />

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-dreams-textPrimary">
            System Health
          </h1>
          <p className="text-dreams-textSecondary mt-1">
            Live status of platform dependencies — auto-refreshes every 30s
          </p>
        </div>
        <div className="flex items-center gap-3">
          {status?.checked_at && (
            <span className="text-xs text-dreams-textSecondary">
              Checked {formatDateTime(status.checked_at)}
            </span>
          )}
          <button
            onClick={() => {
              healthQuery.refetch();
              statusQuery.refetch();
            }}
            disabled={healthQuery.isFetching || statusQuery.isFetching}
            className="flex items-center gap-2 h-10 px-4 rounded-lg border border-dreams-border bg-white text-sm font-medium text-dreams-textPrimary hover:bg-dreams-lightBg transition-colors disabled:opacity-50"
          >
            <RefreshCw
              className={cn(
                "h-4 w-4",
                (healthQuery.isFetching || statusQuery.isFetching) &&
                  "animate-spin"
              )}
            />
            Refresh
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
        </div>
      ) : (
        <>
          {/* Overall status banner */}
          <div
            className={cn(
              "rounded-lg border p-4 flex items-center gap-3",
              overallOk
                ? "bg-green-50 border-green-200"
                : anyDown
                  ? "bg-red-50 border-red-200"
                  : "bg-amber-50 border-amber-200"
            )}
          >
            {overallOk ? (
              <CheckCircle2 className="h-5 w-5 text-green-600 flex-shrink-0" />
            ) : anyDown ? (
              <XCircle className="h-5 w-5 text-red-600 flex-shrink-0" />
            ) : (
              <Activity className="h-5 w-5 text-amber-600 flex-shrink-0" />
            )}
            <div className="flex-1">
              <p
                className={cn(
                  "text-sm font-medium",
                  overallOk
                    ? "text-green-800"
                    : anyDown
                      ? "text-red-800"
                      : "text-amber-800"
                )}
              >
                {overallOk
                  ? "All systems operational"
                  : anyDown
                    ? "One or more dependencies are down"
                    : "Status unknown — probes still loading or unreachable"}
              </p>
              {status && (
                <p className="text-xs text-dreams-textSecondary mt-0.5">
                  API v{status.version} · uptime {formatUptime(status.uptime_seconds)} ·
                  started {formatDateTime(status.started_at)}
                </p>
              )}
            </div>
          </div>

          {/* Dependency status cards */}
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <DependencyCard
              title="API"
              subtitle="GET /health probe"
              icon={Server}
              ok={apiOk}
              latency={apiRtt !== null ? `${apiRtt} ms rtt` : "—"}
            />
            <DependencyCard
              title="PostgreSQL"
              subtitle="Main application DB"
              icon={Database}
              ok={dbOk}
              latency={formatLatency(deps?.db.latency_ms)}
            />
            <DependencyCard
              title="Medicine DB"
              subtitle="Pharmaceutical catalog"
              icon={Tablets}
              ok={medDbOk}
              latency={formatLatency(deps?.medicine_db.latency_ms)}
            />
            <DependencyCard
              title="Redis"
              subtitle="Cache · rate limit · queue"
              icon={HardDrive}
              ok={redisOk}
              latency={formatLatency(deps?.redis.latency_ms)}
            />
          </div>

          {statusQuery.isError && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 flex items-center gap-3">
              <Activity className="h-5 w-5 text-amber-600 flex-shrink-0" />
              <p className="text-sm text-amber-800">
                Admin diagnostics endpoint (
                <code className="text-xs">/api/v1/admin/system/status</code>)
                is unreachable — showing the public /health probe only. A main-DB
                outage also blocks admin auth, so this usually means the API or
                database is down.
              </p>
            </div>
          )}

          {/* Worker queue + counts */}
          <div className="grid gap-4 lg:grid-cols-3">
            <div className="bg-white rounded-lg shadow-card p-6">
              <h2 className="text-lg font-bold text-dreams-textPrimary mb-4">
                Worker Queue (ARQ)
              </h2>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-dreams-textSecondary">
                    Pending jobs
                  </span>
                  <span className="text-sm font-semibold text-dreams-textPrimary">
                    {status?.queue.pending ?? "—"}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-dreams-textSecondary">
                    Deferred (scheduled reminders)
                  </span>
                  <span className="text-sm font-semibold text-dreams-textPrimary">
                    {status?.queue.deferred ?? "—"}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-dreams-textSecondary">
                    In progress
                  </span>
                  <span className="text-sm font-semibold text-dreams-textPrimary">
                    {status?.queue.in_progress ?? "—"}
                  </span>
                </div>
                <div className="pt-3 border-t border-dreams-border">
                  <p className="text-xs text-dreams-textSecondary">
                    Worker last heartbeat
                  </p>
                  <p className="text-sm font-medium text-dreams-textPrimary mt-0.5">
                    {formatDateTime(status?.queue.worker_last_heartbeat)}
                  </p>
                </div>
              </div>
            </div>

            <div className="lg:col-span-2 grid gap-4 sm:grid-cols-2">
              <CountCard
                label="Total Users"
                value={status?.counts?.users}
                icon={Users}
              />
              <CountCard
                label="Patients"
                value={status?.counts?.patients}
                icon={Users}
              />
              <CountCard
                label="Doctors"
                value={status?.counts?.doctors}
                icon={Stethoscope}
              />
              <CountCard
                label="Clinics"
                value={status?.counts?.clinics}
                icon={Building2}
              />
              <CountCard
                label="Appointments Today"
                value={status?.counts?.appointments_today}
                icon={Calendar}
              />
              <div className="bg-white rounded-lg shadow-card p-5">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-lg bg-dreams-blue/10 flex items-center justify-center">
                    <Activity className="h-5 w-5 text-dreams-blue" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm text-dreams-textSecondary">
                      Last Audit Event
                    </p>
                    <p className="text-sm font-semibold text-dreams-textPrimary truncate">
                      {formatDateTime(status?.last_audit_at)}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Metrics note */}
          <div className="bg-white rounded-lg shadow-card p-5">
            <p className="text-sm text-dreams-textSecondary">
              Prometheus metrics are exposed at{" "}
              <code className="text-xs bg-dreams-lightBg px-1.5 py-0.5 rounded">
                {API_URL}/metrics
              </code>{" "}
              (scraped in-cluster only — not publicly routable). Shallow liveness
              probe:{" "}
              <code className="text-xs bg-dreams-lightBg px-1.5 py-0.5 rounded">
                {API_URL}/livez
              </code>
              .
            </p>
          </div>
        </>
      )}
    </div>
  );
}
