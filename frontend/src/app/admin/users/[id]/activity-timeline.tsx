"use client";

import { Fragment, useState } from "react";
import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import {
  getAdminAuditLogs,
  type AdminAuditLogEntry,
} from "@/lib/api/admin-audit";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";

const PAGE_SIZE = 10;

const ACTION_VARIANTS: Record<string, string> = {
  INSERT: "completed",
  UPDATE: "inProgress",
  DELETE: "overdue",
  READ: "pending",
};

function isScalar(v: unknown): boolean {
  return v === null || v === undefined || typeof v !== "object";
}

function ScalarValue({ value }: { value: unknown }) {
  if (value === null || value === undefined) {
    return <span className="text-gray-400">—</span>;
  }
  return <>{String(value)}</>;
}

/**
 * Field-level old → new diff. Scalar fields render inline as `old → new`;
 * object/array values (JSON blobs) are hidden behind an expandable
 * <details> element.
 */
function FieldDiff({
  oldValues,
  newValues,
}: {
  oldValues: Record<string, any> | null;
  newValues: Record<string, any> | null;
}) {
  const t = useTranslations("adminUserDetail.activityTimeline");
  const keys = Array.from(
    new Set([
      ...Object.keys(oldValues ?? {}),
      ...Object.keys(newValues ?? {}),
    ])
  ).filter((k) => !["id", "created_at", "updated_at", "deleted_at"].includes(k));

  if (keys.length === 0) {
    return (
      <p className="text-xs text-dreams-textSecondary">
        {t("noFieldValues")}
      </p>
    );
  }

  return (
    <div className="rounded-lg border border-dreams-border divide-y divide-dreams-border text-xs">
      {keys.map((k) => {
        const oldV = oldValues?.[k];
        const newV = newValues?.[k];
        const blob = !isScalar(oldV) || !isScalar(newV);
        if (blob) {
          return (
            <details key={k} className="group px-3 py-2">
              <summary className="cursor-pointer list-none flex items-center gap-2 text-dreams-textPrimary">
                <ChevronRight className="h-3.5 w-3.5 text-dreams-textSecondary transition-transform group-open:rotate-90" />
                <span className="font-mono">{k}</span>
                <span className="text-dreams-textSecondary">(JSON)</span>
              </summary>
              <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-2">
                <div>
                  <p className="mb-1 font-semibold text-dreams-textSecondary uppercase tracking-wider text-[10px]">
                    {t("old")}
                  </p>
                  <pre className="max-h-48 overflow-auto rounded bg-dreams-lightBg p-2 font-mono text-[11px] text-dreams-textSecondary">
                    {oldV === undefined
                      ? "—"
                      : JSON.stringify(oldV, null, 2)}
                  </pre>
                </div>
                <div>
                  <p className="mb-1 font-semibold text-dreams-textSecondary uppercase tracking-wider text-[10px]">
                    {t("new")}
                  </p>
                  <pre className="max-h-48 overflow-auto rounded bg-dreams-lightBg p-2 font-mono text-[11px] text-dreams-textPrimary">
                    {newV === undefined
                      ? "—"
                      : JSON.stringify(newV, null, 2)}
                  </pre>
                </div>
              </div>
            </details>
          );
        }
        const changed = String(oldV ?? "") !== String(newV ?? "");
        return (
          <div
            key={k}
            className={`flex flex-wrap items-baseline gap-x-2 px-3 py-2 ${
              changed ? "bg-amber-50/40" : ""
            }`}
          >
            <span className="font-mono text-dreams-textPrimary">{k}</span>
            <span className="text-dreams-textSecondary">
              <ScalarValue value={oldV} />
            </span>
            <span className="text-dreams-textSecondary">→</span>
            <span className="text-dreams-textPrimary font-medium">
              <ScalarValue value={newV} />
            </span>
          </div>
        );
      })}
    </div>
  );
}

/**
 * Paginated audit-trail timeline for a single user (actor). Used on the
 * admin user detail page and the admin doctor detail page.
 */
export function UserActivityTimeline({ userId }: { userId: string }) {
  const t = useTranslations("adminUserDetail.activityTimeline");
  const tNotif = useTranslations("notifications");
  const tPagination = useTranslations("pagination");
  const tCommon = useTranslations("common");
  const [page, setPage] = useState(1);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const formatRelativeTime = (isoString: string): string => {
    const date = new Date(isoString);
    const diffMs = Date.now() - date.getTime();
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHour / 24);

    if (diffSec < 60) return tNotif("justNow");
    if (diffMin < 60) return tNotif("minutesAgo", { count: diffMin });
    if (diffHour < 24) return tNotif("hoursAgo", { count: diffHour });
    if (diffDay < 7) return tNotif("daysAgo", { count: diffDay });
    return date.toLocaleDateString();
  };

  const { data, isLoading, error } = useQuery({
    queryKey: ["admin-user-activity", userId, page],
    queryFn: () =>
      getAdminAuditLogs({ user_id: userId, page, limit: PAGE_SIZE }),
    enabled: !!userId,
  });

  const logs: AdminAuditLogEntry[] = data?.data ?? [];
  const totalPages = data?.totalPages ?? 0;

  return (
    <div className="bg-white rounded-xl border border-dreams-border shadow-card overflow-hidden">
      <div className="flex items-center gap-2 px-6 pt-5 pb-4 border-b border-dreams-border">
        <Activity className="h-5 w-5 text-dreams-blue" />
        <h2 className="text-base font-semibold text-dreams-textPrimary">
          {t("title")}
        </h2>
        {data && data.total > 0 && (
          <span className="text-xs text-dreams-textSecondary">
            {t("countSuffix", { count: data.total })}
          </span>
        )}
      </div>

      {isLoading ? (
        <div className="p-6 space-y-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="flex items-center gap-3">
              <Skeleton className="h-4 w-20" />
              <Skeleton className="h-5 w-16 rounded-full" />
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-4 flex-1" />
            </div>
          ))}
        </div>
      ) : error ? (
        <div className="px-6 py-10 text-center">
          <p className="text-sm text-red-600 font-medium">
            {t("loadError")}
          </p>
          <p className="text-xs text-dreams-textSecondary mt-1">
            {error instanceof Error ? error.message : tCommon("errorGeneric")}
          </p>
        </div>
      ) : logs.length === 0 ? (
        <EmptyState
          icon={Activity}
          title={t("emptyTitle")}
          description={t("emptyDescription")}
        />
      ) : (
        <>
          <ul className="divide-y divide-dreams-border">
            {logs.map((log) => {
              const isExpanded = expandedId === log.id;
              const hasDiff = !!(log.old_values || log.new_values);
              return (
                <Fragment key={log.id}>
                  <li
                    className={`flex flex-wrap items-center gap-x-3 gap-y-1 px-6 py-3 text-sm transition-colors ${
                      hasDiff ? "cursor-pointer hover:bg-dreams-lightBg" : ""
                    }`}
                    onClick={() =>
                      hasDiff && setExpandedId(isExpanded ? null : log.id)
                    }
                  >
                    <span className="w-4 text-dreams-textSecondary">
                      {hasDiff ? (
                        isExpanded ? (
                          <ChevronDown className="h-4 w-4" />
                        ) : (
                          <ChevronRight className="h-4 w-4" />
                        )
                      ) : null}
                    </span>
                    <span
                      className="text-dreams-textSecondary whitespace-nowrap"
                      title={new Date(log.changed_at).toLocaleString()}
                    >
                      {formatRelativeTime(log.changed_at)}
                    </span>
                    <Badge variant={ACTION_VARIANTS[log.action] as any}>
                      {log.action}
                    </Badge>
                    <span className="font-mono text-xs text-dreams-textSecondary">
                      {log.table_name}
                    </span>
                    <span
                      className="font-mono text-xs text-dreams-textSecondary"
                      title={log.record_id}
                    >
                      #{log.record_id_short}
                    </span>
                    {log.changes_summary && (
                      <span className="text-xs text-dreams-textSecondary truncate max-w-[16rem]">
                        {log.changes_summary}
                      </span>
                    )}
                  </li>
                  {isExpanded && hasDiff && (
                    <li className="bg-dreams-lightBg/40 px-6 py-4">
                      <FieldDiff
                        oldValues={log.old_values}
                        newValues={log.new_values}
                      />
                    </li>
                  )}
                </Fragment>
              );
            })}
          </ul>

          {totalPages > 1 && (
            <div className="flex items-center justify-between px-6 py-3 border-t border-dreams-border">
              <p className="text-sm text-dreams-textSecondary">
                {tPagination("pageOf", { page, totalPages })}{" "}
                {tPagination("totalSuffix", { count: data?.total ?? 0 })}
              </p>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPage((p) => p - 1)}
                  disabled={page <= 1}
                  className="p-1.5 rounded-lg border border-dreams-border text-dreams-textSecondary hover:bg-dreams-lightBg disabled:opacity-40 disabled:cursor-not-allowed"
                  aria-label={tPagination("previousPage")}
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <button
                  onClick={() => setPage((p) => p + 1)}
                  disabled={page >= totalPages}
                  className="p-1.5 rounded-lg border border-dreams-border text-dreams-textSecondary hover:bg-dreams-lightBg disabled:opacity-40 disabled:cursor-not-allowed"
                  aria-label={tPagination("nextPage")}
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
