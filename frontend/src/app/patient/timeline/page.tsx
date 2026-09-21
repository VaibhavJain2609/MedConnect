"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { formatDate, recordTypeLabel, recordTypeColor } from "@/lib/utils";
import { PrescriptionCard } from "@/components/prescription/PrescriptionCard";
import { extractPrescriptionFromRecord } from "@/lib/api/prescriptions";
import { useTranslations } from "next-intl";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { OnboardingChecklist } from "@/components/patient/onboarding-checklist";

// Values double as message keys under the "timeline.filters" namespace —
// keep them in sync with messages/en.json + hi.json (see docs/i18n.md).
const RECORD_TYPES = [
  "prescription",
  "opd_note",
  "lab_report",
  "diagnostic_report",
  "discharge_summary",
  "imaging",
  "immunization",
] as const;

export default function TimelinePage() {
  const t = useTranslations("timeline");
  const tFilters = useTranslations("timeline.filters");
  const [type, setType] = useState("");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [page, setPage] = useState(1);
  const [cursors, setCursors] = useState<Record<number, string | null>>({ 1: null });
  const [allRecords, setAllRecords] = useState<any[]>([]);

  // Debounce search input so we don't fire a request per keystroke
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search.trim()), 300);
    return () => clearTimeout(t);
  }, [search]);

  // Reset to page 1 when filters change
  useEffect(() => { setPage(1); setCursors({ 1: null }); setAllRecords([]); }, [type, debouncedSearch]);

  const { data, isLoading } = useQuery({
    queryKey: ["timeline", type, debouncedSearch, page],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (type) params.set("type", type);
      if (debouncedSearch) params.set("q", debouncedSearch);
      params.set("limit", "20");
      const cursor = cursors[page] ?? null;
      if (cursor) params.set("cursor", cursor);
      const res = await api.get(`/api/v1/patients/timeline?${params}`);
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

  // Map record_id → real prescription id so PrescriptionCard can offer
  // a PDF download (the PDF endpoint needs the Prescription id, not the
  // timeline record id).
  const { data: prescriptionsData } = useQuery({
    queryKey: ["patient-prescriptions-map"],
    queryFn: async () => {
      const res = await api.get("/api/v1/patients/prescriptions?limit=100");
      return res.data;
    },
    staleTime: 60_000,
  });
  const recordToPrescriptionId = new Map<string, string>(
    (prescriptionsData?.data ?? []).map((p: any) => [p.record_id, p.id])
  );

  return (
    <div className="space-y-6">
      <Breadcrumb items={[{ label: t("breadcrumb") }]} />

      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-dreams-textPrimary">{t("title")}</h1>
          <p className="text-dreams-textSecondary mt-1">{t("subtitle")}</p>
        </div>
        <Link
          href="/patient/records/new"
          className="flex flex-shrink-0 items-center gap-2 rounded-lg bg-dreams-blue px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
          </svg>
          {t("uploadRecord")}
        </Link>
      </div>

      <OnboardingChecklist />

      {/* Filters */}
      <div className="flex flex-col gap-3 sm:flex-row">
        <input
          type="text"
          placeholder={t("searchPlaceholder")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 h-10 rounded-lg border border-dreams-border px-3 py-2 text-sm bg-white focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
        />
        <select
          value={type}
          onChange={(e) => setType(e.target.value)}
          className="h-10 rounded-lg border border-dreams-border px-3 py-2 text-sm bg-white focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
        >
          <option value="">{tFilters("allTypes")}</option>
          {RECORD_TYPES.map((rt) => (
            <option key={rt} value={rt}>
              {tFilters(rt)}
            </option>
          ))}
        </select>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
        </div>
      ) : data?.data?.length === 0 ? (
        <div className="bg-white rounded-lg shadow-card p-12 text-center">
          <p className="text-dreams-textSecondary">{t("emptyTitle")}</p>
          <p className="mt-1 text-sm text-dreams-textSecondary/70">
            {t("emptyHint")}
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {allRecords.map((record: any) => {
            if (record.record_type === "prescription") {
              const prescriptionData = extractPrescriptionFromRecord(record);
              if (prescriptionData) {
                return (
                  <PrescriptionCard
                    key={record.id}
                    prescription={{
                      ...prescriptionData,
                      doctor_name: record.doctor_name,
                    }}
                    variant="patient"
                    collapsible={true}
                    defaultExpanded={false}
                    prescriptionId={recordToPrescriptionId.get(record.id)}
                  />
                );
              }
            }

            return (
              <Link
                key={record.id}
                href={`/patient/records/${record.id}`}
                className="block bg-white rounded-lg shadow-card p-4 transition hover:border-dreams-blue/30 hover:shadow-md border border-dreams-border"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="mb-1 flex items-center gap-2">
                      <span
                        className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${recordTypeColor(record.record_type)}`}
                      >
                        {recordTypeLabel(record.record_type)}
                      </span>
                      <span className="text-xs text-dreams-textSecondary">
                        {formatDate(record.created_at)}
                      </span>
                      {record.source === "patient_uploaded" && (
                        <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-dreams-textSecondary">
                          {t("selfUploaded")}
                        </span>
                      )}
                      {record.amended_from_id && (
                        <span className="rounded-full bg-purple-100 px-2 py-0.5 text-xs font-medium text-purple-700">
                          {t("amended")}
                        </span>
                      )}
                    </div>
                    <h3 className="font-medium text-dreams-textPrimary">{record.title}</h3>
                    {record.doctor_name && (
                      <p className="mt-0.5 text-sm text-dreams-textSecondary">
                        {t("byDoctor", { name: record.doctor_name })}
                      </p>
                    )}
                    {record.document_url && (
                      <div className="mt-1.5 flex items-center gap-1.5 text-xs text-dreams-blue">
                        <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                            d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                        </svg>
                        {t("documentAttached")}
                      </div>
                    )}
                  </div>
                  <svg
                    className="mt-1 h-5 w-5 text-gray-400"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9 5l7 7-7 7"
                    />
                  </svg>
                </div>
              </Link>
            );
          })}
        </div>
      )}

      {data?.pagination?.has_more && (
        <div className="text-center">
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={isLoading}
            className="text-sm text-dreams-blue hover:underline disabled:opacity-50"
          >
            {isLoading ? t("loading") : t("loadMore")}
          </button>
        </div>
      )}
    </div>
  );
}
