"use client";

import { useState } from "react";
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
    <div className="space-y-6">
      <Breadcrumb items={[{ label: "Health Timeline" }]} />

      <div>
        <h1 className="text-3xl font-bold text-dreams-textPrimary">Health Timeline</h1>
        <p className="text-dreams-textSecondary mt-1">Your complete health record history</p>
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
            Your health records will appear here when a doctor creates them for you.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {data?.data?.map((record: any) => {
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
                    </div>
                    <h3 className="font-medium text-dreams-textPrimary">{record.title}</h3>
                    {record.doctor_name && (
                      <p className="mt-0.5 text-sm text-dreams-textSecondary">
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
            );
          })}
        </div>
      )}

      {data?.pagination?.has_more && (
        <div className="text-center">
          <button className="text-sm text-dreams-blue hover:underline">
            Load more
          </button>
        </div>
      )}
    </div>
  );
}
