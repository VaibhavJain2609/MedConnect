"use client";

import { useTranslations } from "next-intl";
import { Fragment, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ShieldCheck, Download, ChevronDown, ChevronRight } from "lucide-react";
import api from "@/lib/api";
import { exportAuditLogsCsv } from "@/lib/api/admin-audit";
import { toast } from "@/hooks/use-toast";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { Badge } from "@/components/ui/badge";
import { AuditDiff } from "@/components/admin/audit-diff";

const TABLE_OPTIONS = [
  { value: "all", labelKey: "all" },
  { value: "medical_records", labelKey: "medical_records" },
  { value: "prescriptions", labelKey: "prescriptions" },
  { value: "users", labelKey: "users" },
  { value: "patient_clinic_links", labelKey: "patient_clinic_links" },
] as const;

const ACTION_VARIANTS: Record<string, string> = {
  INSERT: "completed",
  UPDATE: "inProgress",
  DELETE: "overdue",
};



interface AuditLogEntry {
  id: string;
  table_name: string;
  record_id: string;
  record_id_short: string;
  action: string;
  changed_by: string | null;
  changed_by_name: string | null;
  changed_at: string;
  old_values: Record<string, any> | null;
  new_values: Record<string, any> | null;
  changes_summary: string | null;
}

interface AuditLogsResponse {
  data: AuditLogEntry[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}

export default function AuditLogsPage() {
  const t = useTranslations("adminAudit");
  const tTime = useTranslations("adminAudit.time");
  const tCommon = useTranslations("common");
  const tPagination = useTranslations("pagination");
  const [tableFilter, setTableFilter] = useState("all");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [userSearch, setUserSearch] = useState("");
  const [recordSearch, setRecordSearch] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [page, setPage] = useState(1);
  const limit = 50;

  const { data, isLoading, error } = useQuery<AuditLogsResponse>({
    queryKey: ["admin-audit", tableFilter, fromDate, toDate, userSearch, recordSearch, page],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (tableFilter !== "all") params.set("table_name", tableFilter);
      if (fromDate) params.set("from_date", new Date(fromDate).toISOString());
      if (toDate) params.set("to_date", new Date(toDate).toISOString());
      if (userSearch) params.set("changed_by_name", userSearch);
      if (recordSearch) params.set("record_id", recordSearch);
      params.set("page", String(page));
      params.set("limit", String(limit));
      const res = await api.get(`/api/v1/admin/audit?${params}`);
      return res.data;
    },
  });

  // record_id is also filtered client-side as a fallback in case the API
  // does not support the record_id query param.
  const formatRelativeTime = (isoString: string): string => {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHour / 24);

    if (diffSec < 60) return tTime("justNow");
    if (diffMin < 60) return tTime("minutesAgo", { count: diffMin });
    if (diffHour < 24) return tTime("hoursAgo", { count: diffHour });
    if (diffDay < 7) return tTime("daysAgo", { count: diffDay });
    return date.toLocaleDateString();
  };

  const logs = (data?.data ?? []).filter(
    (log) =>
      !recordSearch ||
      log.record_id.toLowerCase().includes(recordSearch.toLowerCase())
  );
  const totalPages = data?.totalPages ?? 1;

  // Server-side export — honors the same filters as the list and downloads
  // audit-logs-<date>.csv via the authenticated download helper.
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
        title: t("exportFailedTitle"),
        description: t("exportFailedBody"),
        variant: "destructive",
      });
    } finally {
      setExporting(false);
    }
  };

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12 space-y-4">
        <p className="text-red-600 font-medium">{t("loadError")}</p>
        <p className="text-dreams-textSecondary text-sm">
          {error instanceof Error ? error.message : tCommon("errorGeneric")}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Breadcrumb
        items={[
          { label: t("breadcrumbDashboard"), href: "/admin/dashboard" },
          { label: t("breadcrumb") },
        ]}
      />

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <ShieldCheck className="h-7 w-7 text-dreams-blue" />
          <div>
            <h1 className="text-3xl font-bold text-dreams-textPrimary">{t("title")}</h1>
            <p className="text-dreams-textSecondary mt-0.5">
              {t("subtitle")}
            </p>
          </div>
        </div>
      </div>

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
          {TABLE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {t(`tables.${opt.labelKey}`)}
            </option>
          ))}
        </select>

        <div className="flex items-center gap-2">
          <label className="text-sm text-dreams-textSecondary">{t("filters.from")}</label>
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
          <label className="text-sm text-dreams-textSecondary">{t("filters.to")}</label>
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
          placeholder={t("filters.filterRecord")}
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

        <button
          onClick={handleExport}
          disabled={exporting}
          className="flex items-center gap-2 h-10 px-4 rounded-lg border border-dreams-border bg-white text-sm font-medium text-dreams-textPrimary hover:bg-dreams-lightBg transition-colors disabled:opacity-50 ml-auto"
        >
          <Download className="h-4 w-4" />
          {exporting ? t("exporting") : t("export")}
        </button>
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
                    {t("empty")}
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
                          {formatRelativeTime(log.changed_at)}
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
                            <span className="text-dreams-textSecondary italic">{t("system")}</span>
                          )}
                        </td>
                        <td className="px-5 py-3 text-dreams-textSecondary text-xs max-w-xs truncate">
                          {log.changes_summary ?? "—"}
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr className="bg-dreams-lightBg/40">
                          <td colSpan={7} className="px-5 py-4">
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
