"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  FlaskConical,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Download,
  Loader2,
} from "lucide-react";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { LoadMoreButton } from "@/components/ui/pagination";
import { getMyLabResults, type PatientLabResult } from "@/lib/api/patient-portal";
import { cn } from "@/lib/utils";

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

const STATUS_STYLES: Record<string, string> = {
  completed: "bg-green-100 text-green-800",
  received: "bg-blue-100 text-blue-800",
  in_progress: "bg-yellow-100 text-yellow-800",
  pending: "bg-gray-100 text-gray-600",
};

function statusLabel(status: string) {
  return status.replace(/_/g, " ");
}

/**
 * Client-side download of a lab result report.
 * NOTE: there is no server-side lab-result PDF endpoint yet, so we
 * generate a plain-text report blob in the browser instead.
 */
function downloadLabResultReport(lr: PatientLabResult) {
  const lines = [
    "MedConnect — Lab Result Report",
    "================================",
    `Test ID:        ${lr.test_id}`,
    `Test:           ${lr.test_name}`,
    `Category:       ${lr.test_category ?? "—"}`,
    `Date:           ${formatDate(lr.appointment_date)}`,
    `Status:         ${statusLabel(lr.status)}`,
    `Ordered by:     ${lr.doctor_name ? `Dr. ${lr.doctor_name}` : "—"}`,
    "",
    `Result:         ${lr.result_value ?? "—"} ${lr.result_unit ?? ""}`.trimEnd(),
    `Normal range:   ${lr.normal_range ?? "—"}`,
    `Flag:           ${lr.abnormal_flag ? "ABNORMAL" : "Normal"}`,
    "",
    `Notes:          ${lr.notes ?? "—"}`,
    "",
    `Generated:      ${new Date().toLocaleString("en-IN")}`,
  ];
  const blob = new Blob([lines.join("\n")], { type: "text/plain" });
  const blobUrl = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = blobUrl;
  anchor.download = `lab-result-${lr.test_id}.txt`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => window.URL.revokeObjectURL(blobUrl), 10_000);
}

function LabResultRow({ lr }: { lr: PatientLabResult }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className={cn(
        "bg-white rounded-lg shadow-card border transition-colors",
        lr.abnormal_flag ? "border-red-300" : "border-dreams-border"
      )}
    >
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center gap-3 p-4 text-left"
        aria-expanded={expanded}
      >
        <div
          className={cn(
            "p-2 rounded-lg flex-shrink-0",
            lr.abnormal_flag ? "bg-red-50" : "bg-dreams-lightBg"
          )}
        >
          <FlaskConical
            className={cn(
              "h-4 w-4",
              lr.abnormal_flag ? "text-red-500" : "text-dreams-blue"
            )}
          />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="font-semibold text-dreams-textPrimary">{lr.test_name}</p>
            <span
              className={cn(
                "rounded-full px-2.5 py-0.5 text-xs font-medium capitalize",
                STATUS_STYLES[lr.status] ?? "bg-gray-100 text-gray-600"
              )}
            >
              {statusLabel(lr.status)}
            </span>
            {lr.abnormal_flag && (
              <span className="flex items-center gap-1 rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-700">
                <AlertTriangle className="h-3 w-3" />
                Abnormal
              </span>
            )}
          </div>
          <p className="text-xs text-dreams-textSecondary mt-0.5">
            {lr.test_id} · {formatDate(lr.appointment_date)}
            {lr.doctor_name ? ` · Dr. ${lr.doctor_name}` : ""}
          </p>
        </div>
        {expanded ? (
          <ChevronDown className="h-4 w-4 text-dreams-textSecondary flex-shrink-0" />
        ) : (
          <ChevronRight className="h-4 w-4 text-dreams-textSecondary flex-shrink-0" />
        )}
      </button>

      {expanded && (
        <div className="border-t border-dreams-border px-4 py-4 space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <p className="text-xs font-medium text-dreams-textSecondary uppercase tracking-wide">
                Result
              </p>
              <p
                className={cn(
                  "mt-1 text-sm font-semibold",
                  lr.abnormal_flag ? "text-red-600" : "text-dreams-textPrimary"
                )}
              >
                {lr.result_value
                  ? `${lr.result_value}${lr.result_unit ? ` ${lr.result_unit}` : ""}`
                  : "—"}
              </p>
            </div>
            <div>
              <p className="text-xs font-medium text-dreams-textSecondary uppercase tracking-wide">
                Normal Range
              </p>
              <p className="mt-1 text-sm text-dreams-textPrimary">
                {lr.normal_range ?? "—"}
              </p>
            </div>
            <div>
              <p className="text-xs font-medium text-dreams-textSecondary uppercase tracking-wide">
                Ordered By
              </p>
              <p className="mt-1 text-sm text-dreams-textPrimary">
                {lr.doctor_name ? `Dr. ${lr.doctor_name}` : "—"}
              </p>
            </div>
          </div>
          {lr.notes && (
            <div>
              <p className="text-xs font-medium text-dreams-textSecondary uppercase tracking-wide">
                Notes
              </p>
              <p className="mt-1 text-sm text-dreams-textPrimary whitespace-pre-wrap">
                {lr.notes}
              </p>
            </div>
          )}
          <div className="pt-1">
            <button
              type="button"
              onClick={() => downloadLabResultReport(lr)}
              className="flex items-center gap-2 px-3 py-1.5 text-sm border border-dreams-border rounded-lg text-dreams-textPrimary hover:bg-dreams-lightBg transition-colors"
            >
              <Download className="h-4 w-4" />
              Download Report
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

const PAGE_SIZE = 50;

export default function PatientLabResultsPage() {
  const [categoryFilter, setCategoryFilter] = useState("");
  const [page, setPage] = useState(1);
  const [cursors, setCursors] = useState<Record<number, string | null>>({ 1: null });
  const [allResults, setAllResults] = useState<PatientLabResult[]>([]);

  // Reset to the first page when the category filter changes (the endpoint
  // paginates by cursor, so each page's cursor is recorded as it is fetched).
  useEffect(() => {
    setPage(1);
    setCursors({ 1: null });
    setAllResults([]);
  }, [categoryFilter]);

  const { data, isLoading, isError, isFetching } = useQuery({
    queryKey: ["patient-lab-results", categoryFilter, page],
    queryFn: async () => {
      const res = await getMyLabResults({
        limit: PAGE_SIZE,
        category: categoryFilter || undefined,
        cursor: cursors[page] ?? undefined,
      });
      const nextCursor = res.pagination?.next_cursor ?? null;
      if (nextCursor) {
        setCursors((prev) => ({ ...prev, [page + 1]: nextCursor }));
      }
      if (page === 1) {
        setAllResults(res.data || []);
      } else {
        setAllResults((prev) => [...prev, ...(res.data || [])]);
      }
      return res;
    },
  });

  const results = useMemo(() => allResults, [allResults]);

  // Category options come from an UNFILTERED query — deriving them from the
  // filtered result would collapse the dropdown to the current selection.
  const { data: allData } = useQuery({
    queryKey: ["patient-lab-results", "all-categories"],
    queryFn: () => getMyLabResults({ limit: 100 }),
    staleTime: 60_000,
  });
  const categories = useMemo(() => {
    const set = new Set<string>();
    (allData?.data ?? []).forEach((r) => r.test_category && set.add(r.test_category));
    return Array.from(set).sort();
  }, [allData]);

  // Group by category, preserving date-desc order within each group
  const grouped = useMemo(() => {
    const map = new Map<string, PatientLabResult[]>();
    for (const r of results) {
      const key = r.test_category || "Other";
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(r);
    }
    return Array.from(map.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [results]);

  return (
    <div className="space-y-6">
      <Breadcrumb items={[{ label: "Lab Results" }]} />

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-dreams-textPrimary">
            Lab Results
          </h1>
          <p className="text-dreams-textSecondary mt-1">
            Your laboratory test results, grouped by category
          </p>
        </div>
        {categories.length > 0 && (
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="h-10 px-3 rounded-lg border border-dreams-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
          >
            <option value="">All Categories</option>
            {categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        )}
      </div>

      {isLoading && results.length === 0 ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-dreams-blue" />
        </div>
      ) : isError ? (
        <div className="bg-white rounded-lg shadow-card p-12 text-center">
          <p className="text-red-500 font-medium">Failed to load lab results.</p>
          <p className="mt-1 text-sm text-dreams-textSecondary">
            Please refresh the page or try again later.
          </p>
        </div>
      ) : results.length === 0 ? (
        <div className="bg-white rounded-lg shadow-card p-12 text-center">
          <FlaskConical className="h-12 w-12 text-dreams-textSecondary mx-auto mb-4" />
          <p className="text-dreams-textSecondary font-medium">
            No lab results found.
          </p>
          <p className="mt-1 text-sm text-dreams-textSecondary/70">
            {categoryFilter
              ? "Try a different category filter."
              : "Your lab results will appear here once available."}
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {grouped.map(([category, items]) => (
            <section key={category}>
              <h2 className="text-sm font-semibold text-dreams-textSecondary uppercase tracking-wider mb-2 px-1">
                {category}
              </h2>
              <div className="space-y-3">
                {items.map((lr) => (
                  <LabResultRow key={lr.id} lr={lr} />
                ))}
              </div>
            </section>
          ))}
          <LoadMoreButton
            hasMore={!!data?.pagination?.has_more}
            loading={isFetching}
            loadedCount={results.length}
            onClick={() => setPage((p) => p + 1)}
          />
        </div>
      )}
    </div>
  );
}
