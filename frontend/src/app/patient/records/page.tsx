"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { formatDate, recordTypeLabel, recordTypeColor } from "@/lib/utils";
import { FileText, Search, FilePlus } from "lucide-react";

const RECORD_TYPES = [
  { value: "", label: "All Records" },
  { value: "prescription", label: "Prescriptions" },
  { value: "lab_report", label: "Lab Reports" },
  { value: "diagnostic_report", label: "Diagnostic Reports" },
  { value: "discharge_summary", label: "Discharge Summaries" },
  { value: "opd_note", label: "OPD Notes" },
  { value: "imaging", label: "Imaging" },
  { value: "immunization", label: "Immunizations" },
  { value: "other", label: "Other" },
];

export default function PatientRecordsPage() {
  const [typeFilter, setTypeFilter] = useState("");
  const [search, setSearch] = useState("");

  const { data, isLoading, isError } = useQuery({
    queryKey: ["patient-records", typeFilter, search],
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set("limit", "50");
      if (typeFilter) params.set("type", typeFilter);
      if (search) params.set("q", search);
      const res = await api.get(`/api/v1/patients/records?${params}`);
      return res.data;
    },
  });

  const records: any[] = data?.data ?? [];

  return (
    <div className="space-y-6">
      <Breadcrumb items={[{ label: "My Records" }]} />

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-dreams-textPrimary">My Records</h1>
          <p className="text-dreams-textSecondary mt-1">All your medical records in one place</p>
        </div>
        <Link
          href="/patient/records/new"
          className="flex items-center gap-2 px-4 py-2 bg-dreams-blue text-white rounded-lg hover:opacity-90 transition-opacity text-sm font-medium"
        >
          <FilePlus className="h-4 w-4" />
          Add Record
        </Link>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search records..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full h-10 pl-10 pr-4 rounded-lg border border-dreams-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
          />
        </div>
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="h-10 px-3 rounded-lg border border-dreams-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
        >
          {RECORD_TYPES.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
        </div>
      ) : isError ? (
        <div className="bg-white rounded-lg shadow-card p-12 text-center">
          <p className="text-red-500 font-medium">Failed to load records.</p>
          <p className="mt-1 text-sm text-dreams-textSecondary">Please refresh the page or try again later.</p>
        </div>
      ) : records.length === 0 ? (
        <div className="bg-white rounded-lg shadow-card p-12 text-center">
          <FileText className="h-12 w-12 text-dreams-textSecondary mx-auto mb-4" />
          <p className="text-dreams-textSecondary font-medium">No records found.</p>
          <p className="mt-1 text-sm text-dreams-textSecondary/70">
            {typeFilter || search
              ? "Try changing your filters."
              : "Your medical records will appear here once added."}
          </p>
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
                      <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${recordTypeColor(record.record_type)}`}>
                        {recordTypeLabel(record.record_type)}
                      </span>
                    </div>
                    <p className="mt-1 font-semibold text-dreams-textPrimary truncate">{record.title}</p>
                    {record.doctor_name && (
                      <p className="mt-0.5 text-sm text-dreams-textSecondary">Dr. {record.doctor_name}</p>
                    )}
                  </div>
                </div>
                <p className="text-sm text-dreams-textSecondary flex-shrink-0">{formatDate(record.created_at)}</p>
              </div>
            </Link>
          ))}

          {data?.pagination?.has_more && (
            <p className="text-center text-sm text-dreams-textSecondary py-2">
              Showing first 50 records.{" "}
              <Link href="/patient/timeline" className="text-dreams-blue hover:underline">
                Use the timeline for full history →
              </Link>
            </p>
          )}
        </div>
      )}
    </div>
  );
}
