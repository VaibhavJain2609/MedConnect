"use client";

/**
 * Doctor Prescriptions List Page
 *
 * Shows all prescriptions created by the logged-in doctor
 * with interactive prescription cards.
 */

import { useState, useEffect } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { PrescriptionCard } from "@/components/prescription/PrescriptionCard";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { FilePlus, Printer, Search } from "lucide-react";

export default function DoctorPrescriptionsPage() {
  const [search, setSearch] = useState("");

  const [page, setPage] = useState(1);
  const [allRecords, setAllRecords] = useState<any[]>([]);

  // Reset to page 1 when search changes
  useEffect(() => { setPage(1); setAllRecords([]); }, [search]);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["doctor-prescriptions", search, page],
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set("limit", "50");
      params.set("offset", String((page - 1) * 50));
      if (search) params.set("q", search);

      const res = await api.get(`/api/v1/doctors/prescriptions?${params}`);
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
      <Breadcrumb items={[{ label: "My Prescriptions" }]} />

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-dreams-textPrimary">My Prescriptions</h1>
          <p className="text-dreams-textSecondary mt-1">All prescriptions you have created</p>
        </div>
        <Link
          href="/doctor/prescriptions/new"
          className="flex items-center gap-2 px-4 py-2 bg-dreams-blue text-white rounded-lg hover:opacity-90 transition-opacity text-sm font-medium"
        >
          <FilePlus className="h-4 w-4" />
          New Prescription
        </Link>
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
        <input
          type="text"
          placeholder="Search by patient name or diagnosis..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full h-10 pl-10 pr-4 rounded-lg border border-dreams-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
        />
      </div>

      {isLoading ? (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
        </div>
      ) : isError ? (
        <div className="bg-white rounded-lg shadow-card p-12 text-center">
          <p className="text-red-500 font-medium">Failed to load prescriptions.</p>
          <p className="mt-1 text-sm text-dreams-textSecondary">
            {error instanceof Error ? error.message : "Please try again later."}
          </p>
        </div>
      ) : allRecords.length === 0 ? (
        <div className="bg-white rounded-lg shadow-card p-12 text-center">
          <FilePlus className="h-12 w-12 text-dreams-textSecondary mx-auto mb-4" />
          <p className="text-dreams-textSecondary">No prescriptions found.</p>
          <p className="mt-1 text-sm text-dreams-textSecondary/70">
            Create your first prescription using the button above.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {allRecords.map((record: any) => {
            // Map Prescription.medicines JSONB → PrescriptionCard shape
            const rawMeds: any[] = record.medicines ?? [];
            const medicines = rawMeds.length > 0
              ? rawMeds.map((m: any) => ({
                  name: m.brand_name || m.name || "Unknown",
                  dosage: m.dose || m.dosage || "",
                  frequency: m.frequency || "",
                  duration: m.duration || "",
                  timing: m.instructions || m.timing || undefined,
                  notes: m.notes || undefined,
                }))
              : [{ name: "Prescription data not available", dosage: "", frequency: "N/A", duration: "N/A" }];

            const prescriptionData = {
              id: record.id,
              medicines,
              diagnosis: record.title?.replace("Prescription — ", "") || undefined,
              notes: record.description,
              created_at: record.created_at,
              doctor_name: undefined,
            };

            return (
              <div key={record.id} className="relative">
                <div className="mb-2 flex items-center justify-between">
                  {record.patient_name && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-700">
                      Patient: {record.patient_name}
                    </span>
                  )}
                  <Link
                    href={`/doctor/prescriptions/${record.id}/print`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="ml-auto inline-flex items-center gap-1.5 rounded-lg bg-dreams-blue px-3 py-1 text-xs font-medium text-white hover:opacity-90 transition-opacity"
                  >
                    <Printer className="h-3 w-3" />
                    Print
                  </Link>
                </div>
                <PrescriptionCard
                  prescription={prescriptionData}
                  variant="doctor"
                  collapsible={true}
                  defaultExpanded={false}
                />
              </div>
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
