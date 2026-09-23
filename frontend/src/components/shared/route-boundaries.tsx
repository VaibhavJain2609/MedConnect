"use client";

import { useEffect } from "react";
import { useTranslations } from "next-intl";
import { AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

/**
 * Shared building blocks for Next.js route boundaries.
 *
 * Each portal (`app/admin`, `app/doctor`, `app/patient`) re-exports these
 * from its own `loading.tsx` / `error.tsx` so the pending and error states
 * stay visually consistent across portals.
 */

/**
 * RouteLoading — default skeleton rendered by `loading.tsx` while a route
 * segment streams in. Mirrors the common page shape (title + stat cards +
 * content block) used across portal pages.
 */
export function RouteLoading() {
  const t = useTranslations("routeBoundaries");
  return (
    <div
      className="space-y-6 p-6"
      role="status"
      aria-busy="true"
      aria-label={t("loadingAria")}
    >
      <span className="sr-only">{t("loading")}</span>
      <Skeleton className="h-8 w-56" />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-24 rounded-xl" />
        ))}
      </div>
      <Skeleton className="h-72 rounded-xl" />
    </div>
  );
}

export interface RouteErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
  /** Where the secondary button sends the user. Defaults to "/". */
  homeHref?: string;
  homeLabel?: string;
}

/**
 * RouteError — default fallback rendered by `error.tsx` when a route segment
 * throws. Logs the error and offers retry + navigation recovery.
 */
export function RouteError({
  error,
  reset,
  homeHref = "/",
  homeLabel,
}: RouteErrorProps) {
  const t = useTranslations("routeBoundaries");
  useEffect(() => {
    console.error("Route error:", error);
  }, [error]);

  return (
    <div className="flex min-h-[50vh] items-center justify-center px-4">
      <div className="w-full max-w-md space-y-6 rounded-xl border border-dreams-border bg-white p-8 text-center shadow-card">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-red-50">
          <AlertTriangle className="h-6 w-6 text-red-600" aria-hidden="true" />
        </div>
        <div className="space-y-2">
          <h2 className="text-xl font-bold text-dreams-textPrimary">
            {t("errorTitle")}
          </h2>
          <p className="text-sm text-dreams-textSecondary">
            {t("errorDesc")}
          </p>
        </div>

        {error.message && (
          <div className="rounded-lg bg-red-50 p-3 text-left">
            <p className="text-sm text-red-800 break-words">{error.message}</p>
          </div>
        )}

        <div className="flex gap-3">
          <Button onClick={reset} className="flex-1">
            {t("tryAgain")}
          </Button>
          <Button
            variant="outline"
            className="flex-1"
            onClick={() => (window.location.href = homeHref)}
          >
            {homeLabel ?? t("goHome")}
          </Button>
        </div>
      </div>
    </div>
  );
}
