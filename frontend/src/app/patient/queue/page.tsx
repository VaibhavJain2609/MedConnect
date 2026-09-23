"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { Building2, Clock, RefreshCw, Stethoscope, Users } from "lucide-react";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { EmptyState } from "@/components/ui/empty-state";
import { getMyQueuePosition, type MyQueuePosition } from "@/lib/api/queue";
import { cn } from "@/lib/utils";

const STATUS_KEYS = [
  "waiting",
  "in_consultation",
  "completed",
  "cancelled",
] as const;

const STATUS_COLORS: Record<NonNullable<MyQueuePosition["status"]>, string> = {
  waiting: "bg-blue-100 text-blue-800",
  in_consultation: "bg-green-100 text-green-800",
  completed: "bg-gray-100 text-gray-600",
  cancelled: "bg-red-100 text-red-700",
};

export default function PatientQueuePage() {
  const t = useTranslations("patientQueue");

  function formatWait(minutes: number | null) {
    if (minutes == null) return "—";
    if (minutes < 1) return t("waitNow");
    if (minutes < 60) return t("waitMinutes", { minutes });
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    return m > 0 ? t("waitHoursMinutes", { hours: h, minutes: m }) : t("waitHours", { hours: h });
  }

  const { data, isLoading, isFetching, dataUpdatedAt } = useQuery({
    queryKey: ["my-queue-position"],
    queryFn: getMyQueuePosition,
    refetchInterval: 30_000,
  });

  const checkedIn = !!data?.queue_entry_id;
  const isActive = data?.status === "waiting" || data?.status === "in_consultation";

  return (
    <div className="space-y-6">
      <Breadcrumb
        items={[
          { label: "Patient Portal", href: "/patient/timeline" },
          { label: t("title") },
        ]}
      />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-dreams-textPrimary">
            {t("title")}
          </h1>
          <p className="text-dreams-textSecondary text-sm mt-1">
            {t("subtitle")}
          </p>
        </div>
        {checkedIn && (
          <div className="flex items-center gap-2 text-xs text-dreams-textSecondary">
            <RefreshCw
              className={cn("h-3.5 w-3.5", isFetching && "animate-spin")}
            />
            <span>
              {isFetching
                ? t("refreshing")
                : t("updated", {
                    time: new Date(dataUpdatedAt).toLocaleTimeString("en-IN", {
                      hour: "2-digit",
                      minute: "2-digit",
                    }),
                  })}
            </span>
          </div>
        )}
      </div>

      {isLoading ? (
        <div className="bg-white rounded-xl shadow-card border border-dreams-border p-12 flex items-center justify-center text-dreams-textSecondary">
          {t("loading")}
        </div>
      ) : !checkedIn ? (
        <div className="bg-white rounded-xl shadow-card border border-dreams-border">
          <EmptyState
            icon={Users}
            title={t("notCheckedInTitle")}
            description={t("notCheckedInDescription")}
            action={
              <Link
                href="/patient/appointments"
                className="inline-flex items-center gap-2 px-4 py-2 bg-dreams-blue text-white rounded-lg hover:bg-dreams-blue/90 transition-colors text-sm font-medium"
              >
                {t("viewAppointments")}
              </Link>
            }
          />
        </div>
      ) : (
        <>
          {/* Position card */}
          <div className="bg-white rounded-xl shadow-card border border-dreams-border p-6">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 text-sm text-dreams-textSecondary">
                  <Building2 className="h-4 w-4" />
                  <span>{data?.clinic_name ?? t("clinicFallback")}</span>
                </div>
                {data?.doctor_name && (
                  <div className="flex items-center gap-2 text-sm text-dreams-textSecondary mt-1">
                    <Stethoscope className="h-4 w-4" />
                    <span>{t("doctorLabel", { name: data.doctor_name })}</span>
                  </div>
                )}
              </div>
              {data?.status && STATUS_KEYS.includes(data.status) && (
                <span
                  className={cn(
                    "inline-flex items-center px-3 py-1 rounded-full text-xs font-medium w-fit",
                    STATUS_COLORS[data.status]
                  )}
                >
                  {t(`status.${data.status}`)}
                </span>
              )}
            </div>

            <div className="mt-6 flex items-end gap-3">
              {isActive ? (
                <>
                  <span className="text-6xl font-bold text-dreams-blue leading-none">
                    {data?.position ?? "—"}
                  </span>
                  <span className="text-sm text-dreams-textSecondary pb-1">
                    {data?.status === "in_consultation"
                      ? t("beingSeen")
                      : t("yourPosition")}
                  </span>
                </>
              ) : (
                <span className="text-lg font-semibold text-dreams-textPrimary">
                  {data?.status === "completed"
                    ? t("visitComplete")
                    : t("entryCancelled")}
                </span>
              )}
            </div>
            {data?.queue_number != null && (
              <p className="text-xs text-dreams-textSecondary mt-2">
                {t("tokenNumber", { number: data.queue_number })}
              </p>
            )}
          </div>

          {/* Stats */}
          {isActive && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="bg-white rounded-xl shadow-card border border-dreams-border p-5">
                <div className="flex items-center gap-2 text-sm text-dreams-textSecondary">
                  <Users className="h-4 w-4" />
                  <span>{t("peopleAhead")}</span>
                </div>
                <p className="text-3xl font-bold text-dreams-textPrimary mt-2">
                  {data?.ahead_count ?? 0}
                </p>
              </div>
              <div className="bg-white rounded-xl shadow-card border border-dreams-border p-5">
                <div className="flex items-center gap-2 text-sm text-dreams-textSecondary">
                  <Clock className="h-4 w-4" />
                  <span>{t("estimatedWait")}</span>
                </div>
                <p className="text-3xl font-bold text-dreams-textPrimary mt-2">
                  {formatWait(data?.estimated_wait_minutes ?? null)}
                </p>
              </div>
            </div>
          )}

          <p className="text-xs text-dreams-textSecondary">
            {t("refreshNote")}
          </p>
        </>
      )}
    </div>
  );
}
