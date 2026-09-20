"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ClipboardList, Plus, Search } from "lucide-react";
import { getEncounters, Encounter } from "@/lib/api/encounters";
import { getDoctorPatients } from "@/lib/api/doctors";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { Badge } from "@/components/ui/badge";

function formatDateTime(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function DoctorVisitsPage() {
  const [patientFilter, setPatientFilter] = useState("");
  const [dateFilter, setDateFilter] = useState("");
  const [page, setPage] = useState(0);
  const limit = 20;

  const { data: patientsData } = useQuery({
    queryKey: ["doctor-patients-all"],
    queryFn: () => getDoctorPatients({ limit: 100 }),
  });
  const patients = patientsData?.data ?? [];

  const { data, isLoading, error } = useQuery({
    queryKey: ["doctor-encounters", patientFilter, dateFilter, page],
    queryFn: () =>
      getEncounters({
        patient_id: patientFilter || undefined,
        date: dateFilter || undefined,
        limit,
        offset: page * limit,
      }),
  });

  const encounters: Encounter[] = data?.data ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / limit));

  return (
    <div className="space-y-6">
      <Breadcrumb
        items={[
          { label: "Dashboard", href: "/doctor/dashboard" },
          { label: "Encounters" },
        ]}
      />

      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold text-dreams-textPrimary">
              Encounters
            </h1>
            <Badge variant="pending" className="text-base px-3 py-1">
              {total}
            </Badge>
          </div>
          <p className="text-dreams-textSecondary mt-1">
            SOAP notes for your patient visits
          </p>
        </div>

        <Link
          href="/doctor/visits/new"
          className="flex items-center gap-2 px-4 py-2 bg-dreams-blue text-white rounded-lg hover:opacity-90 transition-opacity"
        >
          <Plus className="h-5 w-5" />
          <span>New Encounter</span>
        </Link>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <select
            value={patientFilter}
            onChange={(e) => {
              setPatientFilter(e.target.value);
              setPage(0);
            }}
            className="w-full h-10 pl-10 pr-4 rounded-lg border border-dreams-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue appearance-none"
          >
            <option value="">All patients</option>
            {patients.map((p) => (
              <option key={p.id} value={p.id}>
                {p.full_name}
              </option>
            ))}
          </select>
        </div>

        <input
          type="date"
          value={dateFilter}
          onChange={(e) => {
            setDateFilter(e.target.value);
            setPage(0);
          }}
          className="h-10 px-4 rounded-lg border border-dreams-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
        />
      </div>

      {/* List */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-200 border-t-blue-600" />
        </div>
      ) : error ? (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          Failed to load encounters.
        </div>
      ) : encounters.length === 0 ? (
        <div className="text-center py-16 text-dreams-textSecondary">
          <ClipboardList className="h-10 w-10 mx-auto mb-3 text-gray-300" />
          <p>No encounters yet.</p>
          <p className="text-sm mt-1">
            Click &quot;New Encounter&quot; to write a SOAP note for a visit.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {encounters.map((enc) => (
            <Link
              key={enc.id}
              href={`/doctor/visits/${enc.id}`}
              className="block rounded-xl border border-dreams-border bg-white px-4 py-3 hover:border-dreams-blue/50 transition-colors"
            >
              <div className="flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <p className="font-medium text-dreams-textPrimary truncate">
                    {enc.patient_name ?? "Unknown patient"}
                  </p>
                  <p className="text-xs text-dreams-textSecondary truncate mt-0.5">
                    {enc.assessment
                      ? `Dx: ${enc.assessment}`
                      : enc.subjective ?? "No assessment recorded"}
                  </p>
                </div>
                <div className="flex items-center gap-3 flex-shrink-0">
                  {enc.clinic_name && (
                    <span className="hidden sm:block text-xs text-dreams-textSecondary">
                      {enc.clinic_name}
                    </span>
                  )}
                  <span className="text-xs text-dreams-textSecondary whitespace-nowrap">
                    {formatDateTime(enc.created_at)}
                  </span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-dreams-textSecondary">
            Page {page + 1} of {totalPages} · {total} encounters
          </p>
          <div className="flex gap-2">
            <button
              disabled={page === 0}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              className="px-4 py-2 text-sm rounded-lg border border-dreams-border bg-white disabled:opacity-40 hover:bg-dreams-lightBg transition-colors"
            >
              Previous
            </button>
            <button
              disabled={page + 1 >= totalPages}
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
