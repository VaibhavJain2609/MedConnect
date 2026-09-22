"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { ArrowRight, ListOrdered } from "lucide-react";

import api from "@/lib/api";
import { getQueue } from "@/lib/api/queue";
import { useClinicStore } from "@/stores/clinic-store";
import { DashboardWidget } from "@/components/dashboard/dashboard-widget";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";

function QueueSkeleton() {
  return (
    <div className="space-y-3" aria-hidden>
      <Skeleton className="h-9 w-32" />
      <Skeleton className="h-12 w-full" />
      <Skeleton className="h-4 w-40" />
    </div>
  );
}

/**
 * Queue widget — number of patients waiting for this doctor at the active
 * clinic, plus who's next. Backed by GET /api/v1/queue?status=waiting
 * (clinic comes from the persisted clinic store; the axios interceptor
 * attaches it as X-Clinic-Id).
 *
 * Renders a setup hint instead of data when no clinic is selected.
 */
export function QueueWidget() {
  const t = useTranslations("doctorDashboard.queue");
  const tCommon = useTranslations("common");
  const clinicId = useClinicStore((s) => s.activeClinicId);

  const query = useQuery({
    queryKey: ["doctor-dashboard-queue", clinicId],
    enabled: !!clinicId,
    refetchInterval: 30_000,
    queryFn: async () => {
      // Resolve the doctor profile id so the queue is scoped to this doctor,
      // not the whole clinic.
      const profileRes = await api.get("/api/v1/doctors/profile");
      const doctorId = profileRes.data?.id as string | undefined;
      return getQueue(clinicId!, {
        status: "waiting",
        doctor_id: doctorId,
      });
    },
  });

  if (!clinicId) {
    return (
      <DashboardWidget title={t("title")} icon={ListOrdered}>
        <EmptyState
          icon={ListOrdered}
          title={t("noClinicTitle")}
          description={t("noClinicHint")}
          className="py-8"
          action={
            <Link
              href="/doctor/clinic"
              className="text-sm font-medium text-dreams-blue hover:underline"
            >
              {t("noClinicAction")}
            </Link>
          }
        />
      </DashboardWidget>
    );
  }

  const waiting = query.data?.data ?? [];
  const waitingCount = query.data?.total ?? waiting.length;
  const nextPatient = waiting[0] ?? null;

  return (
    <DashboardWidget
      title={t("title")}
      icon={ListOrdered}
      headerAction={
        <Link
          href="/doctor/queue"
          className="inline-flex items-center gap-1 text-sm font-medium text-dreams-blue hover:underline"
        >
          {t("openQueue")}
          <ArrowRight className="h-3.5 w-3.5" aria-hidden />
        </Link>
      }
      isLoading={query.isLoading}
      isError={query.isError}
      onRetry={() => query.refetch()}
      errorMessage={t("loadError")}
      skeleton={<QueueSkeleton />}
    >
      {waitingCount === 0 ? (
        <EmptyState
          icon={ListOrdered}
          title={t("emptyTitle")}
          description={t("emptyHint")}
          className="py-8"
        />
      ) : (
        <div>
          <p className="text-sm text-dreams-textSecondary">
            <span className="text-2xl font-bold text-dreams-textPrimary">
              {waitingCount}
            </span>{" "}
            {t("waitingSuffix", { count: waitingCount })}
          </p>

          {nextPatient && (
            <div className="mt-4 flex items-center gap-4 rounded-lg border border-dreams-border bg-dreams-lightBg/60 px-4 py-3">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-dreams-blue text-xs font-bold text-white">
                #{nextPatient.queue_number}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-xs text-dreams-textSecondary">{t("nextUp")}</p>
                <p className="truncate text-sm font-medium text-dreams-textPrimary">
                  {nextPatient.patient_name ?? tCommon("unknownPatient")}
                </p>
              </div>
            </div>
          )}
        </div>
      )}
    </DashboardWidget>
  );
}
