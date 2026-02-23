"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { formatDate, recordTypeLabel, recordTypeColor } from "@/lib/utils";
import { Navbar } from "@/components/layout/navbar";
import { AuthGuard } from "@/components/layout/auth-guard";

const RECORD_TYPES = [
  { value: "", label: "All Types" },
  { value: "prescription", label: "Prescriptions" },
  { value: "opd_note", label: "OPD Notes" },
  { value: "lab_report", label: "Lab Reports" },
  { value: "diagnostic_report", label: "Diagnostic Reports" },
  { value: "discharge_summary", label: "Discharge Summaries" },
  { value: "imaging", label: "Imaging" },
  { value: "immunization", label: "Immunization" },
];

export default function TimelinePage() {
  const [type, setType] = useState("");
  const [search, setSearch] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["timeline", type, search],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (type) params.set("type", type);
      if (search) params.set("q", search);
      params.set("limit", "50");
      const res = await api.get(`/api/v1/patients/timeline?${params}`);
      return res.data;
    },
  });

  return (
    <AuthGuard requiredRole="patient">
      <Navbar />
      <main className="mx-auto max-w-3xl px-4 py-6">
        <h1 className="mb-6 text-2xl font-bold">Health Timeline</h1>

        <div className="mb-6 flex flex-col gap-3 sm:flex-row">
          <input
            type="text"
            placeholder="Search records..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="flex-1 rounded-lg border px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
          />
          <select
            value={type}
            onChange={(e) => setType(e.target.value)}
            className="rounded-lg border px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
          >
            {RECORD_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </div>

        {isLoading ? (
          <div className="flex justify-center py-12">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
          </div>
        ) : data?.data?.length === 0 ? (
          <div className="rounded-xl border bg-white p-12 text-center">
            <p className="text-gray-500">No records found.</p>
            <p className="mt-1 text-sm text-gray-400">
              Your health records will appear here when a doctor creates them for you.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {data?.data?.map((record: any) => (
              <Link
                key={record.id}
                href={`/patient/records/${record.id}`}
                className="block rounded-xl border bg-white p-4 transition hover:border-primary-200 hover:shadow-sm"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="mb-1 flex items-center gap-2">
                      <span
                        className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${recordTypeColor(record.record_type)}`}
                      >
                        {recordTypeLabel(record.record_type)}
                      </span>
                      <span className="text-xs text-gray-400">
                        {formatDate(record.created_at)}
                      </span>
                    </div>
                    <h3 className="font-medium text-gray-900">{record.title}</h3>
                    {record.doctor_name && (
                      <p className="mt-0.5 text-sm text-gray-500">
                        by {record.doctor_name}
                      </p>
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
            ))}
          </div>
        )}

        {data?.pagination?.has_more && (
          <div className="mt-4 text-center">
            <button className="text-sm text-primary-600 hover:underline">
              Load more
            </button>
          </div>
        )}
      </main>
    </AuthGuard>
  );
}
