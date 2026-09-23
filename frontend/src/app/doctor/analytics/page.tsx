"use client";

import { useMemo } from "react";
import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  BarChart3,
  CalendarCheck2,
  ListOrdered,
  Pill,
  Timer,
} from "lucide-react";

import { Breadcrumb } from "@/components/ui/breadcrumb";
import { DashboardWidget } from "@/components/dashboard/dashboard-widget";
import { StatCard } from "@/components/dashboard/stat-card";
import { getDoctorAnalytics } from "@/lib/api/doctors";
import { useClinicStore } from "@/stores/clinic-store";

const STATUS_ORDER = [
  "scheduled",
  "arrived",
  "in-progress",
  "completed",
  "cancelled",
  "no-show",
];

const BLUE = "#4169E1";
const GREEN = "#10B981";

function formatWeekLabel(isoDate: string) {
  return new Date(`${isoDate}T00:00:00`).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
  });
}

export default function DoctorAnalyticsPage() {
  const t = useTranslations("doctorAnalytics");
  const clinicId = useClinicStore((s) => s.activeClinicId);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["doctor-analytics", clinicId],
    queryFn: getDoctorAnalytics,
  });

  const statusRows = useMemo(() => {
    if (!data) return [];
    // Backend status string → localized label (keys are statically
    // referenced so next-intl's typed message keys stay valid).
    const statusLabels: Record<string, string> = {
      scheduled: t("statuses.scheduled"),
      arrived: t("statuses.arrived"),
      "in-progress": t("statuses.inProgress"),
      completed: t("statuses.completed"),
      cancelled: t("statuses.cancelled"),
      "no-show": t("statuses.noShow"),
    };
    const rows = STATUS_ORDER.map((status) => ({
      status,
      label: statusLabels[status],
      count: data.appointments_by_status[status] ?? 0,
    }));
    // Surface any unexpected status values rather than dropping them.
    for (const [status, count] of Object.entries(data.appointments_by_status)) {
      if (!STATUS_ORDER.includes(status)) {
        rows.push({ status, label: status, count });
      }
    }
    return rows;
  }, [data, t]);

  const weeklyRows = useMemo(
    () =>
      (data?.weekly_completions ?? []).map((w) => ({
        week: formatWeekLabel(w.week_start),
        weekStart: w.week_start,
        count: w.count,
      })),
    [data]
  );

  const totalAppointments = statusRows.reduce((sum, r) => sum + r.count, 0);

  const statusAriaSummary = statusRows
    .filter((r) => r.count > 0)
    .map((r) => `${r.label} ${r.count}`)
    .join(", ");

  return (
    <div className="space-y-6">
      <Breadcrumb items={[{ label: t("breadcrumb") }]} />

      <div>
        <h1 className="text-3xl font-bold text-dreams-textPrimary">
          {t("title")}
        </h1>
        <p className="text-dreams-textSecondary mt-1">{t("subtitle")}</p>
      </div>

      {/* Stat cards */}
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard
          title={t("totalAppointments")}
          value={isLoading ? "—" : totalAppointments}
          icon={CalendarCheck2}
          color="blue"
        />
        {data?.avg_consult_minutes !== undefined && (
          <StatCard
            title={t("avgConsult")}
            value={t("avgConsultValue", {
              minutes: data.avg_consult_minutes,
            })}
            icon={Timer}
            color="purple"
          />
        )}
        {data?.queue_today && (
          <StatCard
            title={t("queueWaiting")}
            value={data.queue_today.waiting + data.queue_today.in_consultation}
            icon={ListOrdered}
            color="orange"
          />
        )}
      </div>

      {/* Charts */}
      <div className="grid gap-6 lg:grid-cols-2">
        <DashboardWidget
          title={t("byStatus.title")}
          icon={BarChart3}
          isLoading={isLoading}
          isError={isError}
          onRetry={() => refetch()}
          errorMessage={t("loadError")}
        >
          {totalAppointments === 0 ? (
            <p className="text-sm text-dreams-textSecondary">
              {t("byStatus.empty")}
            </p>
          ) : (
            <figure className="m-0">
              <div
                role="img"
                aria-label={t("byStatus.ariaLabel", {
                  summary: statusAriaSummary,
                })}
                style={{ height: 260 }}
              >
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={statusRows}
                    margin={{ top: 4, right: 8, bottom: 0, left: -16 }}
                  >
                    <CartesianGrid
                      strokeDasharray="3 3"
                      stroke="#E5E7EB"
                      vertical={false}
                    />
                    <XAxis
                      dataKey="label"
                      tick={{ fontSize: 11, fill: "#6B7280" }}
                      tickLine={false}
                    />
                    <YAxis
                      allowDecimals={false}
                      tick={{ fontSize: 11, fill: "#6B7280" }}
                      tickLine={false}
                      axisLine={false}
                    />
                    <Tooltip
                      contentStyle={{
                        border: "1px solid #E5E7EB",
                        borderRadius: "8px",
                        fontSize: "12px",
                      }}
                    />
                    <Bar
                      dataKey="count"
                      fill={BLUE}
                      radius={[4, 4, 0, 0]}
                      isAnimationActive={false}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              {/* Screen-reader data table fallback. */}
              <table className="sr-only">
                <caption>{t("byStatus.tableCaption")}</caption>
                <thead>
                  <tr>
                    <th>{t("byStatus.colStatus")}</th>
                    <th>{t("byStatus.colCount")}</th>
                  </tr>
                </thead>
                <tbody>
                  {statusRows.map((r) => (
                    <tr key={r.status}>
                      <td>{r.label}</td>
                      <td>{r.count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </figure>
          )}
        </DashboardWidget>

        <DashboardWidget
          title={t("weekly.title")}
          icon={CalendarCheck2}
          isLoading={isLoading}
          isError={isError}
          onRetry={() => refetch()}
          errorMessage={t("loadError")}
        >
          <figure className="m-0">
            <div
              role="img"
              aria-label={t("weekly.ariaLabel")}
              style={{ height: 260 }}
            >
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={weeklyRows}
                  margin={{ top: 4, right: 8, bottom: 0, left: -16 }}
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="#E5E7EB"
                    vertical={false}
                  />
                  <XAxis
                    dataKey="week"
                    tick={{ fontSize: 11, fill: "#6B7280" }}
                    tickLine={false}
                  />
                  <YAxis
                    allowDecimals={false}
                    tick={{ fontSize: 11, fill: "#6B7280" }}
                    tickLine={false}
                    axisLine={false}
                  />
                  <Tooltip
                    contentStyle={{
                      border: "1px solid #E5E7EB",
                      borderRadius: "8px",
                      fontSize: "12px",
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="count"
                    name={t("weekly.seriesLabel")}
                    stroke={GREEN}
                    strokeWidth={2}
                    dot={{ fill: GREEN, r: 4 }}
                    isAnimationActive={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <table className="sr-only">
              <caption>{t("weekly.tableCaption")}</caption>
              <thead>
                <tr>
                  <th>{t("weekly.colWeek")}</th>
                  <th>{t("weekly.colCount")}</th>
                </tr>
              </thead>
              <tbody>
                {weeklyRows.map((r) => (
                  <tr key={r.weekStart}>
                    <td>{r.week}</td>
                    <td>{r.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </figure>
        </DashboardWidget>
      </div>

      {/* Top medicines */}
      <DashboardWidget
        title={t("medicines.title")}
        icon={Pill}
        isLoading={isLoading}
        isError={isError}
        onRetry={() => refetch()}
        errorMessage={t("loadError")}
      >
        {!data || data.top_medicines.length === 0 ? (
          <p className="text-sm text-dreams-textSecondary">
            {t("medicines.empty")}
          </p>
        ) : (
          <ol className="divide-y divide-dreams-border">
            {data.top_medicines.map((med, i) => (
              <li
                key={med.name}
                className="flex items-center justify-between py-2.5"
              >
                <span className="flex items-center gap-3 text-sm text-dreams-textPrimary">
                  <span className="w-6 text-xs font-semibold text-dreams-textSecondary">
                    {i + 1}
                  </span>
                  {med.name}
                </span>
                <span className="text-sm font-medium text-dreams-textSecondary">
                  {t("medicines.countSuffix", { count: med.count })}
                </span>
              </li>
            ))}
          </ol>
        )}
      </DashboardWidget>
    </div>
  );
}
