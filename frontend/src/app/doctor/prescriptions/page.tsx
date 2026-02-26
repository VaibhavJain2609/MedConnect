"use client";

/**
 * Doctor Prescriptions List Page
 *
 * Shows all prescriptions created by the logged-in doctor
 * with interactive prescription cards.
 */

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { Navbar } from "@/components/layout/navbar";
import { AuthGuard } from "@/components/layout/auth-guard";
import { PrescriptionCard } from "@/components/prescription/PrescriptionCard";

export default function DoctorPrescriptionsPage() {
  const [search, setSearch] = useState("");
  const [patientFilter, setPatientFilter] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["doctor-prescriptions", search, patientFilter],
    queryFn: async () => {
      // Note: This endpoint may need to be created in the backend
      // For now, we'll fetch all medical records and filter prescriptions
      const params = new URLSearchParams();
      params.set("limit", "50");
      if (search) params.set("q", search);

      try {
        // Try to get doctor's prescriptions
        const res = await api.get(`/api/v1/doctors/prescriptions?${params}`);
        return res.data;
      } catch (err) {
        // Fallback: Get all records and filter for prescriptions
        console.warn("Doctor prescriptions endpoint not available, using fallback");
        const res = await api.get(`/api/v1/doctors/records?${params}`);
        const records = res.data.data || [];
        return {
          data: records.filter((r: any) => r.record_type === 'prescription'),
          pagination: res.data.pagination,
        };
      }
    },
  });

  return (
    <AuthGuard requiredRole="doctor">
      <Navbar />
      <main className="mx-auto max-w-4xl px-4 py-6">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-2xl font-bold">My Prescriptions</h1>
          <Link
            href="/doctor/prescriptions/new"
            className="rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700"
          >
            + New Prescription
          </Link>
        </div>

        {/* Search and Filter */}
        <div className="mb-6 flex flex-col gap-3 sm:flex-row">
          <input
            type="text"
            placeholder="Search by patient name or diagnosis..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="flex-1 rounded-lg border px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
          />
        </div>

        {isLoading ? (
          <div className="flex justify-center py-12">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
          </div>
        ) : data?.data?.length === 0 ? (
          <div className="rounded-xl border bg-white p-12 text-center">
            <p className="text-gray-500">No prescriptions found.</p>
            <p className="mt-1 text-sm text-gray-400">
              Create your first prescription using the button above.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {data?.data?.map((record: any) => {
              // Extract prescription data from FHIR bundle
              let medicines: any[] = [];

              if (record.fhir_bundle?.entry) {
                const medicationRequests = record.fhir_bundle.entry.filter(
                  (e: any) => e.resource?.resourceType === 'MedicationRequest'
                );

                medicines = medicationRequests.map((entry: any) => {
                  const resource = entry.resource;
                  const dosageInstruction = resource.dosageInstruction?.[0] || {};

                  return {
                    name: resource.medicationCodeableConcept?.text || 'Unknown',
                    dosage: dosageInstruction.doseAndRate?.[0]?.doseQuantity?.value || '',
                    frequency: dosageInstruction.timing?.code?.text || '',
                    duration: '', // Extract from text if needed
                    timing: dosageInstruction.additionalInstruction?.[0]?.text,
                    notes: resource.note?.[0]?.text,
                  };
                });
              }

              // Fallback if no medicines found
              if (medicines.length === 0) {
                medicines = [{
                  name: 'Prescription data not available',
                  dosage: '',
                  frequency: 'N/A',
                  duration: 'N/A',
                }];
              }

              const prescriptionData = {
                id: record.id,
                medicines,
                diagnosis: record.title?.replace('Prescription — ', '') || undefined,
                notes: record.description,
                created_at: record.created_at,
                doctor_name: undefined, // Don't show doctor name in doctor's own view
              };

              return (
                <div key={record.id} className="relative">
                  {/* Patient name badge */}
                  {record.patient_name && (
                    <div className="mb-2 flex items-center gap-2">
                      <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-700">
                        <span>👤</span>
                        Patient: {record.patient_name}
                      </span>
                    </div>
                  )}

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
