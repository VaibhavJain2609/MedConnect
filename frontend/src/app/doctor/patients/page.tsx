"use client";

import Link from "next/link";
import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, Users, ChevronRight } from "lucide-react";
import { useTranslations } from "next-intl";
import { getDoctorPatients, DoctorPatient } from "@/lib/api/doctors";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { LoadMoreButton } from "@/components/ui/pagination";
import { Avatar } from "@/components/ui/avatar";

const PAGE_SIZE = 20;

export default function DoctorPatientsPage() {
  const t = useTranslations("doctorPatients");
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [page, setPage] = useState(1);
  const [cursors, setCursors] = useState<Record<number, string | null>>({ 1: null });
  const [allPatients, setAllPatients] = useState<DoctorPatient[]>([]);

  // Debounce search input so we don't fire a request per keystroke. When the
  // debounced value commits, also reset to the first page (the endpoint
  // paginates by cursor, so each page's cursor is recorded as it is fetched).
  useEffect(() => {
    const t = setTimeout(() => {
      setDebouncedQuery(searchQuery.trim());
      setPage(1);
      setCursors({ 1: null });
      setAllPatients([]);
    }, 300);
    return () => clearTimeout(t);
  }, [searchQuery]);

  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: ["doctor-patients-list", debouncedQuery, page],
    queryFn: async () => {
      const res = await getDoctorPatients({
        search: debouncedQuery || undefined,
        limit: PAGE_SIZE,
        cursor: cursors[page] ?? undefined,
      });
      const nextCursor = res.pagination?.next_cursor ?? null;
      if (nextCursor) {
        setCursors((prev) => ({ ...prev, [page + 1]: nextCursor }));
      }
      if (page === 1) {
        setAllPatients(res.data || []);
      } else {
        setAllPatients((prev) => [...prev, ...(res.data || [])]);
      }
      return res;
    },
  });

  const patients = allPatients;

  return (
    <div className="space-y-6">
      <Breadcrumb items={[{ label: t("breadcrumb") }]} />

      <div>
        <h1 className="text-3xl font-bold text-dreams-textPrimary">{t("title")}</h1>
        <p className="text-dreams-textSecondary mt-1">
          {t("subtitle")}
        </p>
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
        <input
          type="text"
          placeholder={t("searchPlaceholder")}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full h-10 pl-10 pr-4 rounded-lg border border-dreams-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
        />
      </div>

      {/* Content */}
      {isLoading && patients.length === 0 ? (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
        </div>
      ) : error ? (
        <div className="flex flex-col items-center justify-center py-12 space-y-2">
          <p className="text-red-600 font-medium">{t("loadError")}</p>
          <p className="text-dreams-textSecondary text-sm">
            {error instanceof Error ? error.message : t("loadErrorGeneric")}
          </p>
        </div>
      ) : patients.length === 0 ? (
        <div className="bg-white rounded-xl border border-dreams-border shadow-card p-12 flex flex-col items-center justify-center text-center">
          <div className="p-4 rounded-full bg-dreams-lightBg mb-4">
            <Users className="h-10 w-10 text-dreams-textSecondary" />
          </div>
          <h2 className="text-xl font-semibold text-dreams-textPrimary mb-2">
            {debouncedQuery ? t("emptySearchTitle") : t("emptyTitle")}
          </h2>
          <p className="text-dreams-textSecondary max-w-sm">
            {debouncedQuery ? t("emptySearchHint") : t("emptyHint")}
          </p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-dreams-border shadow-card overflow-hidden">
          <div className="px-6 py-4 border-b border-dreams-border flex items-center justify-between">
            <h2 className="font-semibold text-dreams-textPrimary">
              {t("count", { count: patients.length })}
            </h2>
          </div>
          <ul className="divide-y divide-dreams-border">
            {patients.map((patient: DoctorPatient) => (
              <li key={patient.id}>
                <Link
                  href={`/doctor/patients/${patient.id}`}
                  className="flex items-center gap-4 px-6 py-4 hover:bg-dreams-lightBg transition-colors group"
                >
                  <Avatar fallback={patient.full_name} size="sm" />
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-dreams-textPrimary truncate">
                      {patient.full_name}
                    </p>
                    <p className="text-sm text-dreams-textSecondary truncate">
                      {patient.email ?? patient.phone ?? t("noContact")}
                    </p>
                  </div>
                  <ChevronRight className="h-4 w-4 text-dreams-textSecondary group-hover:text-dreams-blue transition-colors flex-shrink-0" />
                </Link>
              </li>
            ))}
          </ul>
          <LoadMoreButton
            hasMore={!!data?.pagination?.has_more}
            loading={isFetching}
            loadedCount={patients.length}
            onClick={() => setPage((p) => p + 1)}
            className="border-t border-dreams-border py-4"
          />
        </div>
      )}
    </div>
  );
}
