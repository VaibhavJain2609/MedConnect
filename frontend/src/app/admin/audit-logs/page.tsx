"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import api from "@/lib/api";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { Badge } from "@/components/ui/badge";

const TABLE_OPTIONS = [
  { value: "all", label: "All Tables" },
  { value: "medical_records", label: "Medical Records" },
  { value: "prescriptions", label: "Prescriptions" },
  { value: "users", label: "Users" },
  { value: "patient_clinic_links", label: "Patient Clinic Links" },
];

const ACTION_VARIANTS: Record<string, string> = {
  INSERT: "completed",
  UPDATE: "inProgress",
  DELETE: "overdue",
};

function formatRelativeTime(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffSec < 60) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHour < 24) return `${diffHour}h ago`;
  if (diffDay < 7) return `${diffDay}d ago`;
  return date.toLocaleDateString();
}

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
  const [tableFilter, setTableFilter] = useState("all");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [userSearch, setUserSearch] = useState("");
  const [page, setPage] = useState(1);
  const limit = 50;

  const { data, isLoading, error } = useQuery<AuditLogsResponse>({
    queryKey: ["admin-audit", tableFilter, fromDate, toDate, userSearch, page],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (tableFilter !== "all") params.set("table_name", tableFilter);
      if (fromDate) params.set("from_date", new Date(fromDate).toISOString());
      if (toDate) params.set("to_date", new Date(toDate).toISOString());
      if (userSearch) params.set("changed_by_name", userSearch);
      params.set("page", String(page));
      params.set("limit", String(limit));
      const res = await api.get(`/api/v1/admin/audit?${params}`);
      return res.data;
    },
  });

  const logs = data?.data ?? [];
  const totalPages = data?.totalPages ?? 1;

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12 space-y-4">
        <p className="text-red-600 font-medium">Failed to load audit logs</p>
        <p className="text-dreams-textSecondary text-sm">
          {error instanceof Error ? error.message : "An error occurred"}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Breadcrumb
        items={[
          { label: "Dashboard", href: "/admin/dashboard" },
          { label: "Audit Trail" },
        ]}
      />

      <div className="flex items-center gap-3">
        <ShieldCheck className="h-7 w-7 text-dreams-blue" />
        <div>
          <h1 className="text-3xl font-bold text-dreams-textPrimary">Audit Trail</h1>
          <p className="text-dreams-textSecondary mt-0.5">
            Immutable log of all data changes in the system
          </p>
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
              {opt.label}
            </option>
          ))}
        </select>

        <div className="flex items-center gap-2">
          <label className="text-sm text-dreams-textSecondary">From</label>
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
          <label className="text-sm text-dreams-textSecondary">To</label>
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
          placeholder="Search by user name..."
          value={userSearch}
          onChange={(e) => {
            setUserSearch(e.target.value);
            setPage(1);
          }}
          className="h-10 px-3 rounded-lg border border-dreams-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue min-w-[200px]"
        />

        {(tableFilter !== "all" || fromDate || toDate || userSearch) && (
          <button
            onClick={() => {
              setTableFilter("all");
              setFromDate("");
              setToDate("");
              setUserSearch("");
              setPage(1);
            }}
            className="h-10 px-3 rounded-lg border border-dreams-border bg-white text-sm text-dreams-textSecondary hover:bg-dreams-lightBg transition-colors"
          >
            Clear filters
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
                <th className="px-5 py-3 text-left font-semibold text-dreams-textSecondary">
                  When
                </th>
                <th className="px-5 py-3 text-left font-semibold text-dreams-textSecondary">
                  Action
                </th>
                <th className="px-5 py-3 text-left font-semibold text-dreams-textSecondary">
                  Table
                </th>
                <th className="px-5 py-3 text-left font-semibold text-dreams-textSecondary">
                  Record ID
                </th>
                <th className="px-5 py-3 text-left font-semibold text-dreams-textSecondary">
                  Changed By
                </th>
                <th className="px-5 py-3 text-left font-semibold text-dreams-textSecondary">
                  Changes
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-dreams-border">
              {logs.length === 0 ? (
                <tr>
                  <td
                    colSpan={6}
                    className="px-5 py-12 text-center text-dreams-textSecondary"
                  >
                    No audit logs found
                  </td>
                </tr>
              ) : (
                logs.map((log) => (
                  <tr key={log.id} className="hover:bg-dreams-lightBg transition-colors">
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
                    <td className="px-5 py-3 font-mono text-xs text-dreams-textSecondary">
                      {log.record_id_short}…
                    </td>
                    <td className="px-5 py-3 text-dreams-textPrimary">
                      {log.changed_by_name ?? (
                        <span className="text-dreams-textSecondary italic">System</span>
                      )}
                    </td>
                    <td className="px-5 py-3 text-dreams-textSecondary text-xs max-w-xs truncate">
                      {log.changes_summary ?? "—"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-dreams-textSecondary">
            Page {page} of {totalPages} · {data?.total} total
          </p>
          <div className="flex gap-2">
            <button
              disabled={page === 1}
              onClick={() => setPage((p) => p - 1)}
              className="px-4 py-2 text-sm rounded-lg border border-dreams-border bg-white disabled:opacity-40 hover:bg-dreams-lightBg transition-colors"
            >
              Previous
            </button>
            <button
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="px-4 py-2 text-sm rounded-lg border border-dreams-border bg-white disabled:opacity-40 hover:bg-dreams-lightBg transition-colors"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
