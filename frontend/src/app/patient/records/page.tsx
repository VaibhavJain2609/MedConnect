"use client";

import { Suspense, useState, useEffect } from "react";
import Link from "next/link";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import api from "@/lib/api";
import { downloadFile } from "@/lib/download";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { LoadMoreButton } from "@/components/ui/pagination";
import { formatDate, recordTypeLabel, recordTypeColor } from "@/lib/utils";
import { FileText, Search, FilePlus, Download, X } from "lucide-react";

// Values double as message keys under the "records.filters" namespace —
// keep them in sync with messages/en.json + hi.json (see docs/i18n.md).
// Mirrors VALID_RECORD_TYPES in backend/app/schemas/record.py.
const RECORD_TYPES = [
  "prescription",
  "lab_report",
  "diagnostic_report",
  "discharge_summary",
  "opd_note",
  "imaging",
  "immunization",
  "other",
] as const;

const PAGE_SIZE = 20;

function PatientRecordsContent() {
  const t = useTranslations("records");
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  // Initial state is read from the URL so filters survive refresh/share.
  const [typeFilter, setTypeFilter] = useState(searchParams.get("type") ?? "");
  const [search, setSearch] = useState(searchParams.get("q") ?? "");
  const [debouncedSearch, setDebouncedSearch] = useState(
    (searchParams.get("q") ?? "").trim()
  );
  const [fromDate, setFromDate] = useState(searchParams.get("from") ?? "");
  const [toDate, setToDate] = useState(searchParams.get("to") ?? "");
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState("");
  const [page, setPage] = useState(1);
  const [cursors, setCursors] = useState<Record<number, string | null>>({ 1: null });
  const [allRecords, setAllRecords] = useState<any[]>([]);

  // Debounce search input so we don't fire a request per keystroke
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search.trim()), 300);
    return () => clearTimeout(t);
  }, [search]);

  const hasActiveFilters = !!(typeFilter || debouncedSearch || fromDate || toDate);

  // Keep the URL in sync with the active filters so a refresh or shared link
  // restores the same view.
  useEffect(() => {
    const params = new URLSearchParams();
    if (typeFilter) params.set("type", typeFilter);
    if (debouncedSearch) params.set("q", debouncedSearch);
    if (fromDate) params.set("from", fromDate);
    if (toDate) params.set("to", toDate);
    const next = params.toString();
    if (next !== searchParams.toString()) {
      router.replace(next ? `${pathname}?${next}` : pathname, { scroll: false });
    }
  }, [typeFilter, debouncedSearch, fromDate, toDate, pathname, router, searchParams]);

  // Reset to page 1 when filters change (adjusted during render). The endpoint
  // paginates by cursor, so each page's cursor is recorded as it is fetched.
  const filterKey = `${typeFilter}|${debouncedSearch}|${fromDate}|${toDate}`;
  const [prevFilterKey, setPrevFilterKey] = useState(filterKey);
  if (prevFilterKey !== filterKey) {
    setPrevFilterKey(filterKey);
    setPage(1);
    setCursors({ 1: null });
    setAllRecords([]);
  }

  const { data, isLoading, isError, isFetching } = useQuery({
    queryKey: ["patient-records", typeFilter, debouncedSearch, fromDate, toDate, page],
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set("limit", String(PAGE_SIZE));
      if (typeFilter) params.set("record_type", typeFilter);
      if (debouncedSearch) params.set("q", debouncedSearch);
      if (fromDate) params.set("from_date", fromDate);
      if (toDate) params.set("to_date", toDate);
      const cursor = cursors[page] ?? null;
      if (cursor) params.set("cursor", cursor);
      const res = await api.get(`/api/v1/patients/records?${params}`);
      const nextCursor = res.data.pagination?.next_cursor ?? null;
      if (nextCursor) {
        setCursors((prev) => ({ ...prev, [page + 1]: nextCursor }));
      }
      if (page === 1) {
        setAllRecords(res.data.data || []);
      } else {
        setAllRecords((prev) => [...prev, ...(res.data.data || [])]);
      }
      return res.data;
    },
  });

  const records: any[] = allRecords;

  const resetFilters = () => {
    setTypeFilter("");
    setSearch("");
    setDebouncedSearch("");
    setFromDate("");
    setToDate("");
  };

  // Authenticated blob download — the Authorization header is only
  // attached by the axios interceptor, so a plain <a href> would 401.
  const handleExport = async () => {
    if (exporting) return;
    setExporting(true);
    setExportError("");
    try {
      await downloadFile("/api/v1/patients/records/export?format=json");
    } catch {
      setExportError(t("exportError"));
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="space-y-6">
      <Breadcrumb items={[{ label: t("breadcrumb") }]} />

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-dreams-textPrimary">{t("title")}</h1>
          <p className="text-dreams-textSecondary mt-1">{t("subtitle")}</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleExport}
            disabled={exporting}
            className="flex items-center gap-2 px-4 py-2 bg-white border border-dreams-border text-dreams-textPrimary rounded-lg hover:border-dreams-blue/50 transition-colors text-sm font-medium disabled:opacity-50"
          >
            <Download className="h-4 w-4" />
            {exporting ? t("exporting") : t("export")}
          </button>
          <Link
            href="/patient/records/new"
            className="flex items-center gap-2 px-4 py-2 bg-dreams-blue text-white rounded-lg hover:opacity-90 transition-opacity text-sm font-medium"
          >
            <FilePlus className="h-4 w-4" />
            {t("addRecord")}
          </Link>
        </div>
      </div>

      {exportError && <p className="text-sm text-red-600">{exportError}</p>}

      {/* Filter bar */}
      <div className="space-y-3 rounded-lg border border-dreams-border bg-white p-4 shadow-card">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <input
              type="text"
              placeholder={t("searchPlaceholder")}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full h-10 pl-10 pr-4 rounded-lg border border-dreams-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
            />
          </div>
          <div className="flex items-center gap-2">
            <label
              htmlFor="records-from-date"
              className="text-sm text-dreams-textSecondary whitespace-nowrap"
            >
              {t("filters.from")}
            </label>
            <input
              id="records-from-date"
              type="date"
              value={fromDate}
              max={toDate || undefined}
              onChange={(e) => setFromDate(e.target.value)}
              className="h-10 rounded-lg border border-dreams-border bg-white px-3 text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
            />
            <label
              htmlFor="records-to-date"
              className="text-sm text-dreams-textSecondary whitespace-nowrap"
            >
              {t("filters.to")}
            </label>
            <input
              id="records-to-date"
              type="date"
              value={toDate}
              min={fromDate || undefined}
              onChange={(e) => setToDate(e.target.value)}
              className="h-10 rounded-lg border border-dreams-border bg-white px-3 text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
            />
          </div>
          {hasActiveFilters && (
            <button
              type="button"
              onClick={resetFilters}
              className="flex items-center gap-1.5 self-start rounded-lg border border-dreams-border px-3 h-10 text-sm font-medium text-dreams-textSecondary hover:border-dreams-blue/50 hover:text-dreams-blue transition-colors sm:self-auto"
            >
              <X className="h-3.5 w-3.5" />
              {t("filters.reset")}
            </button>
          )}
        </div>

        {/* Type chips — single-select, matches the backend `record_type` filter */}
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setTypeFilter("")}
            className={`rounded-full px-3.5 py-1.5 text-xs font-medium transition-colors border ${
              typeFilter === ""
                ? "bg-dreams-blue text-white border-dreams-blue"
                : "bg-white text-dreams-textSecondary border-dreams-border hover:border-dreams-blue/50 hover:text-dreams-blue"
            }`}
          >
            {t("filters.all")}
          </button>
          {RECORD_TYPES.map((rt) => (
            <button
              key={rt}
              type="button"
              onClick={() => setTypeFilter((prev) => (prev === rt ? "" : rt))}
              className={`rounded-full px-3.5 py-1.5 text-xs font-medium transition-colors border ${
                typeFilter === rt
                  ? "bg-dreams-blue text-white border-dreams-blue"
                  : "bg-white text-dreams-textSecondary border-dreams-border hover:border-dreams-blue/50 hover:text-dreams-blue"
              }`}
            >
              {t(`filters.${rt}`)}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      {isLoading && records.length === 0 ? (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
        </div>
      ) : isError ? (
        <div className="bg-white rounded-lg shadow-card p-12 text-center">
          <p className="text-red-500 font-medium">{t("loadError")}</p>
          <p className="mt-1 text-sm text-dreams-textSecondary">{t("loadErrorHint")}</p>
        </div>
      ) : records.length === 0 ? (
        <div className="bg-white rounded-lg shadow-card p-12 text-center">
          <FileText className="h-12 w-12 text-dreams-textSecondary mx-auto mb-4" />
          <p className="text-dreams-textSecondary font-medium">
            {hasActiveFilters ? t("emptyFilteredTitle") : t("emptyTitle")}
          </p>
          <p className="mt-1 text-sm text-dreams-textSecondary/70">
            {hasActiveFilters ? t("emptyFilteredHint") : t("emptyHint")}
          </p>
          {hasActiveFilters && (
            <button
              type="button"
              onClick={resetFilters}
              className="mt-4 inline-flex items-center gap-1.5 rounded-lg border border-dreams-border px-4 py-2 text-sm font-medium text-dreams-textSecondary hover:border-dreams-blue/50 hover:text-dreams-blue transition-colors"
            >
              <X className="h-3.5 w-3.5" />
              {t("filters.reset")}
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          {records.map((record: any) => (
            <Link
              key={record.id}
              href={`/patient/records/${record.id}`}
              className="block bg-white rounded-lg shadow-card p-5 border border-dreams-border hover:border-dreams-blue/50 hover:shadow-md transition-all"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-3 min-w-0">
                  <div className="mt-0.5 p-2 rounded-lg bg-dreams-lightBg flex-shrink-0">
                    <FileText className="h-4 w-4 text-dreams-blue" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span
                        className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${recordTypeColor(record.record_type)}`}
                      >
                        {recordTypeLabel(record.record_type)}
                      </span>
                    </div>
                    <p className="mt-1 font-semibold text-dreams-textPrimary truncate">
                      {record.title}
                    </p>
                    {record.doctor_name && (
                      <p className="mt-0.5 text-sm text-dreams-textSecondary">
                        {t("doctorPrefix", { name: record.doctor_name })}
                      </p>
                    )}
                  </div>
                </div>
                <p className="text-sm text-dreams-textSecondary flex-shrink-0">
                  {formatDate(record.created_at)}
                </p>
              </div>
            </Link>
          ))}

          <LoadMoreButton
            hasMore={!!data?.pagination?.has_more}
            loading={isFetching}
            loadedCount={records.length}
            onClick={() => setPage((p) => p + 1)}
          />
        </div>
      )}
    </div>
  );
}

export default function PatientRecordsPage() {
  // useSearchParams() requires a Suspense boundary during prerendering.
  return (
    <Suspense
      fallback={
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
        </div>
      }
    >
      <PatientRecordsContent />
    </Suspense>
  );
}
