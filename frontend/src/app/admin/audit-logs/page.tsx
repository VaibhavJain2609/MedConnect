"use client";

import { Fragment, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ShieldCheck, Download, ChevronDown, ChevronRight } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";
import {
  exportAuditLogsCsv,
  getAdminArchivedAuditLogs,
  getAdminAuditLogs,
  type AdminAuditLogEntry,
  type AdminAuditLogsResponse,
} from "@/lib/api/admin-audit";
import { toast } from "@/hooks/use-toast";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AuditDiff } from "@/components/admin/audit-diff";

const TABLE_OPTIONS = [
  "medical_records",
  "prescriptions",
  "users",
  "patient_clinic_links",
] as const;

const ACTION_VARIANTS: Record<string, string> = {
  INSERT: "completed",
  UPDATE: "inProgress",
  DELETE: "overdue",
};

type AuditView = "live" | "archive";

export default function AuditLogsPage() {
  const t = useTranslations("adminAuditLogs");
  const tPagination = useTranslations("pagination");
  const format = useFormatter();

  const [view, setView] = useState<AuditView>("live");
  const [tableFilter, setTableFilter] = useState("all");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [userSearch, setUserSearch] = useState("");
  const [recordSearch, setRecordSearch] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [page, setPage] = useState(1);
  const limit = 50;

  const { data, isLoading, error } = useQuery<AdminAuditLogsResponse>({
    queryKey: [
      "admin-audit",
      view,
      tableFilter,
      fromDate,
      toDate,
      userSearch,
      recordSearch,
      page,
    ],
    queryFn: async () => {
      const params = {
        table_name: tableFilter !== "all" ? tableFilter : undefined,
        from_date: fromDate ? new Date(fromDate).toISOString() : undefined,
        to_date: toDate ? new Date(toDate).toISOString() : undefined,
        changed_by_name: userSearch || undefined,
        record_id: recordSearch || undefined,
        page,
        limit,
      };
      return view === "archive"
        ? getAdminArchivedAuditLogs(params)
        : getAdminAuditLogs(params);
    },
  });

  // record_id is also filtered client-side as a fallback in case the API
  // does not support the record_id query param.
  const logs = (data?.data ?? []).filter(
    (log) =>
      !recordSearch ||
      log.record_id.toLowerCase().includes(recordSearch.toLowerCase())
  );
  const totalPages = data?.totalPages ?? 1;

  // Server-side export — honors the same filters as the live list and
  // downloads audit-logs-<date>.csv via the authenticated download helper.
  const handleExport = async () => {
    setExporting(true);
    try {
      await exportAuditLogsCsv({
        table_name: tableFilter !== "all" ? tableFilter : undefined,
        from_date: fromDate ? new Date(fromDate).toISOString() : undefined,
        to_date: toDate ? new Date(toDate).toISOString() : undefined,
        changed_by_name: userSearch || undefined,
        record_id: recordSearch || undefined,
      });
    } catch (err) {
      console.error("Audit log export failed:", err);
      toast({
        title: t("export.failedTitle"),
        description: t("export.failedDesc"),
        variant: "destructive",
      });
    } finally {
      setExporting(false);
    }
  };

  const handleViewChange = (value: string) => {
    setView(value as AuditView);
    setPage(1);
    setExpandedId(null);
  };

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12 space-y-4">
        <p className="text-red-600 font-medium">{t("error.loadFailed")}</p>
        <p className="text-dreams-textSecondary text-sm">
          {error instanceof Error ? error.message : t("error.generic")}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Breadcrumb
        items={[
          { label: t("breadcrumbDashboard"), href: "/admin/dashboard" },
          { label: t("breadcrumbCurrent") },
        ]}
      />

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <ShieldCheck className="h-7 w-7 text-dreams-blue" />
          <div>
            <h1 className="text-3xl font-bold text-dreams-textPrimary">
              {t("title")}
            </h1>
            <p className="text-dreams-textSecondary mt-0.5">{t("subtitle")}</p>
          </div>
        </div>
      </div>

      <Tabs value={view} onValueChange={handleViewChange}>
        <TabsList>
          <TabsTrigger value="live">{t("tabs.live")}</TabsTrigger>
          <TabsTrigger value="archive">{t("tabs.archive")}</TabsTrigger>
        </TabsList>
      </Tabs>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <select
          value={tableFilter}
          onChange={(e) => {
            setTableFilter(e.target.value);
            setPage(1);
          }}
          className="h-10 px-3 rounded-lg border border-dreams-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
        >
          <option value="all">{t("filters.allTables")}</option>
          {TABLE_OPTIONS.map((value) => (
            <option key={value} value={value}>
              {t(`tables.${value}`)}
            </option>
          ))}
        </select>

        <div className="flex items-center gap-2">
          <label className="text-sm text-dreams-textSecondary">
            {t("filters.from")}
          </label>
          <input
            type="date"
            value={fromDate}
            onChange={(e) => {
              setFromDate(e.target.value);
              setPage(1);
            }}
            className="h-10 px-3 rounded-lg border border-dreams-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
          />
        </div>

        <div className="flex items-center gap-2">
          <label className="text-sm text-dreams-textSecondary">
            {t("filters.to")}
          </label>
          <input
            type="date"
            value={toDate}
            onChange={(e) => {
              setToDate(e.target.value);
              setPage(1);
            }}
            className="h-10 px-3 rounded-lg border border-dreams-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
          />
        </div>

        <input
          type="text"
          placeholder={t("filters.searchUser")}
          value={userSearch}
          onChange={(e) => {
            setUserSearch(e.target.value);
            setPage(1);
          }}
          className="h-10 px-3 rounded-lg border border-dreams-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue min-w-[200px]"
        />

        <input
          type="text"
          placeholder={t("filters.filterRecordId")}
          value={recordSearch}
          onChange={(e) => {
            setRecordSearch(e.target.value);
            setPage(1);
          }}
          className="h-10 px-3 rounded-lg border border-dreams-border bg-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-dreams-blue min-w-[200px]"
        />

        {(tableFilter !== "all" || fromDate || toDate || userSearch || recordSearch) && (
          <button
            onClick={() => {
              setTableFilter("all");
              setFromDate("");
              setToDate("");
              setUserSearch("");
              setRecordSearch("");
              setPage(1);
            }}
            className="h-10 px-3 rounded-lg border border-dreams-border bg-white text-sm text-dreams-textSecondary hover:bg-dreams-lightBg transition-colors"
          >
            {t("filters.clear")}
          </button>
        )}

        {view === "live" && (
          <button
            onClick={handleExport}
            disabled={exporting}
            className="flex items-center gap-2 h-10 px-4 rounded-lg border border-dreams-border bg-white text-sm font-medium text-dreams-textPrimary hover:bg-dreams-lightBg transition-colors disabled:opacity-50 ml-auto"
          >
            <Download className="h-4 w-4" />
            {exporting ? t("export.exporting") : t("export.button")}
          </button>
        )}
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-dreams-border overflow-hidden shadow-card">
        {isLoading ? (
          <div className="flex justify-center py-12">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-dreams-lightBg border-b border-dreams-border">
              <tr>
                <th className="w-8 px-2 py-3" />
                <th className="px-5 py-3 text-left font-semibold text-dreams-textSecondary">
                  {t("table.when")}
                </th>
                <th className="px-5 py-3 text-left font-semibold text-dreams-textSecondary">
                  {t("table.action")}
                </th>
                <th className="px-5 py-3 text-left font-semibold text-dreams-textSecondary">
                  {t("table.table")}
                </th>
                <th className="px-5 py-3 text-left font-semibold text-dreams-textSecondary">
                  {t("table.recordId")}
                </th>
                <th className="px-5 py-3 text-left font-semibold text-dreams-textSecondary">
                  {t("table.changedBy")}
                </th>
                <th className="px-5 py-3 text-left font-semibold text-dreams-textSecondary">
                  {t("table.changes")}
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-dreams-border">
              {logs.length === 0 ? (
                <tr>
                  <td
                    colSpan={7}
                    className="px-5 py-12 text-center text-dreams-textSecondary"
                  >
                    {view === "archive"
                      ? t("table.emptyArchive")
                      : t("table.empty")}
                  </td>
                </tr>
              ) : (
                logs.map((log) => {
                  const isExpanded = expandedId === log.id;
                  return (
                    <Fragment key={log.id}>
                      <tr
                        className="hover:bg-dreams-lightBg transition-colors cursor-pointer"
                        onClick={() =>
                          setExpandedId(isExpanded ? null : log.id)
                        }
                      >
                        <td className="px-2 py-3 text-dreams-textSecondary">
                          {isExpanded ? (
                            <ChevronDown className="h-4 w-4" />
                          ) : (
                            <ChevronRight className="h-4 w-4" />
                          )}
                        </td>
                        <td className="px-5 py-3 text-dreams-textSecondary whitespace-nowrap">
                          {format.relativeTime(new Date(log.changed_at))}
                        </td>
                        <td className="px-5 py-3">
                          <Badge variant={ACTION_VARIANTS[log.action] as any}>
                            {log.action}
                          </Badge>
                        </td>
                        <td className="px-5 py-3 font-mono text-xs text-dreams-textSecondary">
                          {log.table_name}
                        </td>
                        <td
                          className="px-5 py-3 font-mono text-xs text-dreams-textSecondary"
                          title={log.record_id}
                        >
                          {log.record_id_short}…
                        </td>
                        <td className="px-5 py-3 text-dreams-textPrimary">
                          {log.changed_by_name ?? (
                            <span className="text-dreams-textSecondary italic">
                              {t("table.system")}
                            </span>
                          )}
                        </td>
                        <td className="px-5 py-3 text-dreams-textSecondary text-xs max-w-xs truncate">
                          {log.changes_summary ?? "—"}
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr className="bg-dreams-lightBg/40">
                          <td colSpan={7} className="px-5 py-4">
                            {view === "archive" && log.archived_at && (
                              <p className="mb-2 text-xs text-dreams-textSecondary">
                                {t("table.archivedAt", {
                                  time: format.relativeTime(
                                    new Date(log.archived_at)
                                  ),
                                })}
                              </p>
                            )}
                            <AuditDiff
                              oldValues={log.old_values}
                              newValues={log.new_values}
                            />
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })
              )}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-dreams-textSecondary">
            {tPagination("pageOf", { page, totalPages })}{" "}
            {tPagination("totalSuffix", { count: data?.total ?? 0 })}
          </p>
          <div className="flex gap-2">
            <button
              disabled={page === 1}
              onClick={() => setPage((p) => p - 1)}
              className="px-4 py-2 text-sm rounded-lg border border-dreams-border bg-white disabled:opacity-40 hover:bg-dreams-lightBg transition-colors"
            >
              {tPagination("previous")}
            </button>
            <button
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="px-4 py-2 text-sm rounded-lg border border-dreams-border bg-white disabled:opacity-40 hover:bg-dreams-lightBg transition-colors"
            >
              {tPagination("next")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
