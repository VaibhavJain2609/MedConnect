"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import { MonitorPlay, Users } from "lucide-react";
import { getQueueDisplay } from "@/lib/api/queue";
import { useClinicStore } from "@/stores/clinic-store";

const REFRESH_MS = 12_000;
const UP_NEXT_LIMIT = 10;

/**
 * Clinic waiting-room display board — meant to run on a TV or a monitor at
 * reception. Read-only: shows anonymized token numbers only (never patient
 * names — the backend payload carries no patient identifiers at all) and
 * auto-refreshes via React Query polling.
 */
export default function QueueDisplayPage() {
  const t = useTranslations("queueDisplay");
  const locale = useLocale();
  // The axios interceptor attaches the persisted clinic id as X-Clinic-Id.
  const clinicId = useClinicStore((s) => s.activeClinicId) ?? "";
  const clinics = useClinicStore((s) => s.clinics);
  const clinicName = clinics.find((c) => c.id === clinicId)?.name;

  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => {
    setNow(new Date());
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const { data, isLoading, isError, dataUpdatedAt } = useQuery({
    queryKey: ["queue-display", clinicId],
    queryFn: () => getQueueDisplay(UP_NEXT_LIMIT),
    enabled: !!clinicId,
    refetchInterval: REFRESH_MS,
    refetchIntervalInBackground: true, // TVs keep polling even unfocused
  });

  const timeFmt = (d: Date | number) =>
    new Date(d).toLocaleTimeString(locale === "hi" ? "hi-IN" : "en-IN", {
      hour: "2-digit",
      minute: "2-digit",
    });

  if (!clinicId) {
    return (
      <div className="rounded-2xl bg-dreams-darkSidebar text-white p-10 min-h-[70vh] flex items-center justify-center">
        <p className="text-lg text-white/70">{t("noClinic")}</p>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="rounded-2xl bg-dreams-darkSidebar text-white p-10 min-h-[70vh] flex items-center justify-center">
        <p className="text-lg text-red-300">{t("loadFailed")}</p>
      </div>
    );
  }

  const nowServing = data?.now_serving ?? [];
  const upNext = data?.up_next ?? [];
  const extraWaiting = Math.max(0, (data?.waiting_count ?? 0) - upNext.length);
  const isEmpty = !isLoading && nowServing.length === 0 && upNext.length === 0;

  return (
    <div className="rounded-2xl bg-dreams-darkSidebar text-white p-6 md:p-10 min-h-[80vh] flex flex-col gap-8">
      {/* Header */}
      <header className="flex items-center justify-between gap-4">
        <div>
          <p className="text-sm uppercase tracking-widest text-white/50">
            {clinicName ?? t("clinicFallback")}
          </p>
          <h1 className="text-3xl md:text-4xl font-bold mt-1">{t("title")}</h1>
        </div>
        <div className="text-right">
          <p className="text-3xl md:text-4xl font-mono tabular-nums">
            {now ? timeFmt(now) : "--:--"}
          </p>
          <p className="text-xs text-white/50 mt-1 flex items-center justify-end gap-1">
            <MonitorPlay className="h-3.5 w-3.5" />
            {t("autoRefresh", { seconds: REFRESH_MS / 1000 })}
            {dataUpdatedAt ? ` · ${t("updated", { time: timeFmt(dataUpdatedAt) })}` : ""}
          </p>
        </div>
      </header>

      {isLoading ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-white/20 border-t-white" />
        </div>
      ) : isEmpty ? (
        <div className="flex-1 flex flex-col items-center justify-center gap-3 text-center">
          <Users className="h-12 w-12 text-white/30" />
          <p className="text-2xl font-semibold text-white/80">{t("emptyTitle")}</p>
          <p className="text-sm text-white/50">{t("emptyHint")}</p>
        </div>
      ) : (
        <>
          {/* Now serving */}
          <section>
            <h2 className="text-sm md:text-base font-semibold uppercase tracking-widest text-emerald-300 mb-4">
              {t("nowServing")}
            </h2>
            {nowServing.length === 0 ? (
              <p className="text-white/40 text-lg">{t("noneServing")}</p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {nowServing.map((entry) => (
                  <div
                    key={entry.token}
                    className="rounded-2xl bg-emerald-500/15 border border-emerald-400/40 px-6 py-8 text-center"
                  >
                    <p className="text-5xl md:text-7xl font-bold font-mono tabular-nums text-emerald-300">
                      {entry.token}
                    </p>
                    <p className="text-xs uppercase tracking-widest text-emerald-200/70 mt-3">
                      {t("proceedInside")}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Up next */}
          {upNext.length > 0 && (
            <section>
              <h2 className="text-sm md:text-base font-semibold uppercase tracking-widest text-white/60 mb-4">
                {t("upNext")}
              </h2>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
                {upNext.map((entry) => (
                  <div
                    key={entry.token}
                    className="rounded-xl bg-white/5 border border-white/10 px-4 py-5 text-center"
                  >
                    <p className="text-3xl md:text-4xl font-bold font-mono tabular-nums text-white">
                      {entry.token}
                    </p>
                    {entry.position != null && (
                      <p className="text-xs text-white/40 mt-2">
                        {t("position", { position: entry.position })}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}
        </>
      )}

      {/* Footer */}
      <footer className="mt-auto pt-4 border-t border-white/10 flex items-center justify-between text-sm text-white/50">
        <span>{t("waitingTotal", { count: data?.waiting_count ?? 0 })}</span>
        {extraWaiting > 0 && <span>{t("moreWaiting", { count: extraWaiting })}</span>}
      </footer>
    </div>
  );
}
