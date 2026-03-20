"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { formatDate, recordTypeLabel, recordTypeColor } from "@/lib/utils";
import { PrescriptionCard } from "@/components/prescription/PrescriptionCard";
import { extractPrescriptionFromRecord } from "@/lib/api/prescriptions";
import { Breadcrumb } from "@/components/ui/breadcrumb";

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
  const [page, setPage] = useState(1);
  const [allRecords, setAllRecords] = useState<any[]>([]);

  // Reset to page 1 when filters change
  useEffect(() => { setPage(1); setAllRecords([]); }, [type, search]);

  const { data, isLoading } = useQuery({
    queryKey: ["timeline", type, search, page],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (type) params.set("type", type);
      if (search) params.set("q", search);
      params.set("limit", "50");
      params.set("offset", String((page - 1) * 50));
      const res = await api.get(`/api/v1/patients/timeline?${params}`);
      if (page === 1) {
        setAllRecords(res.data.data || []);
      } else {
        setAllRecords((prev) => [...prev, ...(res.data.data || [])]);
      }
      return res.data;
    },
  });

  return (
    <div className="space-y-6">
      <Breadcrumb items={[{ label: "Health Timeline" }]} />

      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-dreams-textPrimary">Health Timeline</h1>
          <p className="text-dreams-textSecondary mt-1">Your complete health record history</p>
        </div>
        <Link
          href="/patient/records/new"
          className="flex flex-shrink-0 items-center gap-2 rounded-lg bg-dreams-blue px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
          </svg>
          Upload Record
        </Link>
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-3 sm:flex-row">
        <input
          type="text"
          placeholder="Search records..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 h-10 rounded-lg border border-dreams-border px-3 py-2 text-sm bg-white focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
        />
        <select
          value={type}
          onChange={(e) => setType(e.target.value)}
          className="h-10 rounded-lg border border-dreams-border px-3 py-2 text-sm bg-white focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
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
        <div className="bg-white rounded-lg shadow-card p-12 text-center">
          <p className="text-dreams-textSecondary">No records found.</p>
          <p className="mt-1 text-sm text-dreams-textSecondary/70">
            Your health records will appear here when a doctor creates them for you, or when you upload one.
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
                          Self-uploaded
                        </span>
                      )}
                      {record.amended_from_id && (
                        <span className="rounded-full bg-purple-100 px-2 py-0.5 text-xs font-medium text-purple-700">
                          Amended
                        </span>
                      )}
                    </div>
                    <h3 className="font-medium text-dreams-textPrimary">{record.title}</h3>
                    {record.doctor_name && (
                      <p className="mt-0.5 text-sm text-dreams-textSecondary">
                        by {record.doctor_name}
                      </p>
                    )}
                    {record.document_url && (
                      <div className="mt-1.5 flex items-center gap-1.5 text-xs text-dreams-blue">
                        <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                            d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                        </svg>
                        Document attached
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
            {isLoading ? "Loading..." : "Load more"}
          </button>
        </div>
      )}
    </div>
  );
}
