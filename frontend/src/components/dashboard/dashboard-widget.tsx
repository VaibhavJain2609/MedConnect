"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { AlertCircle, RefreshCw, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

export interface DashboardWidgetProps {
  title: string;
  icon: LucideIcon;
  /** Optional right-aligned header element (e.g. a "View all →" link). */
  headerAction?: React.ReactNode;
  isLoading?: boolean;
  isError?: boolean;
  /** Called when the user clicks the Retry button in the error state. */
  onRetry?: () => void;
  errorMessage?: string;
  /** Custom loading placeholder; defaults to a few skeleton rows. */
  skeleton?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}

/**
 * DashboardWidget
 *
 * Shared card shell for doctor-dashboard widgets. Renders a header
 * (icon + title + optional action) and swaps the body between a loading
 * skeleton, an error state with retry, and the widget content.
 */
export function DashboardWidget({
  title,
  icon: Icon,
  headerAction,
  isLoading = false,
  isError = false,
  onRetry,
  errorMessage,
  skeleton,
  className,
  children,
}: DashboardWidgetProps) {
  const t = useTranslations("common");
  const resolvedErrorMessage = errorMessage ?? t("loadFailed");
  return (
    <section
      className={cn("bg-white rounded-lg shadow-card p-6", className)}
      aria-busy={isLoading}
    >
      <div className="flex items-center justify-between mb-4">
        <h2 className="flex items-center gap-2 text-lg font-semibold text-dreams-textPrimary">
          <Icon className="h-5 w-5 text-dreams-blue" aria-hidden />
          {title}
        </h2>
        {headerAction}
      </div>

      {isLoading ? (
        (skeleton ?? (
          <div className="space-y-3" aria-hidden>
            <Skeleton className="h-8 w-24" />
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        ))
      ) : isError ? (
        <div className="flex flex-col items-center justify-center py-10 text-center">
          <AlertCircle className="h-8 w-8 text-status-overdue mb-3" aria-hidden />
          <p className="text-sm font-medium text-dreams-textPrimary">
            {resolvedErrorMessage}
          </p>
          {onRetry && (
            <Button
              variant="outline"
              size="sm"
              className="mt-4"
              onClick={onRetry}
            >
              <RefreshCw className="h-4 w-4" />
              {t("retry")}
            </Button>
          )}
        </div>
      ) : (
        children
      )}
    </section>
  );
}
