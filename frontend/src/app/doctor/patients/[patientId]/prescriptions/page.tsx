"use client";

/**
 * Patient Prescriptions Page (Doctor View)
 *
 * Shows all prescriptions for a specific patient that were created by:
 * - The current doctor, OR
 * - Doctors from the same facility/clinic
 */

import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { PrescriptionCard } from "@/components/prescription/PrescriptionCard";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { Avatar } from "@/components/ui/avatar";
import { ArrowLeft, Pill } from "lucide-react";

export default function PatientPrescriptionsPage() {
  const params = useParams();
  const router = useRouter();
  const patientId = params.patientId as string;

  const { data: patientData } = useQuery({
    queryKey: ["patient-info", patientId],
    queryFn: async () => {
      try {
        const res = await api.get(`/api/v1/doctors/patients`);
        const patients = res.data.data || [];
        return patients.find((p: any) => p.id === patientId);
      } catch (err) {
        console.error("Error fetching patient info:", err);
        return null;
      }
    },
  });

  const { data: prescriptionsData, isLoading } = useQuery({
    queryKey: ["patient-prescriptions", patientId],
    queryFn: async () => {
      const res = await api.get(`/api/v1/doctors/patients/${patientId}/prescriptions`);
      return res.data;
    },
  });

  return (
    <div className="space-y-6">
      <Breadcrumb
        items={[
          { label: "Dashboard", href: "/doctor/dashboard" },
          { label: patientData?.full_name || "Patient" },
          { label: "Prescriptions" },
        ]}
      />

      <button
        onClick={() => router.back()}
        className="flex items-center gap-2 text-sm text-dreams-textSecondary hover:text-dreams-blue transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Dashboard
      </button>

      {/* Patient Header */}
      <div className="bg-white rounded-lg shadow-card p-6">
        <div className="flex items-center gap-4">
          <Avatar
            src={null}
            fallback={patientData?.full_name || "P"}
            size="xl"
          />
          <div>
            <h1 className="text-2xl font-bold text-dreams-textPrimary">
              {patientData?.full_name || "Patient"}
            </h1>
            <p className="text-sm text-dreams-textSecondary mt-0.5">
              {patientData?.email || patientData?.phone || `ID: ${patientId}`}
            </p>
          </div>
        </div>
      </div>

      {/* Prescriptions */}
      <div>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xl font-bold text-dreams-textPrimary">Prescription History</h2>
          {prescriptionsData?.total > 0 && (
            <span className="rounded-full bg-blue-50 border border-blue-200 px-3 py-1 text-sm font-medium text-blue-700">
              {prescriptionsData.total} prescription{prescriptionsData.total !== 1 ? "s" : ""}
            </span>
          )}
        </div>

        {isLoading ? (
          <div className="flex justify-center py-12">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
          </div>
        ) : prescriptionsData?.data?.length === 0 ? (
          <div className="bg-white rounded-lg shadow-card p-12 text-center">
            <Pill className="h-12 w-12 text-dreams-textSecondary mx-auto mb-4" />
            <p className="text-dreams-textSecondary">No prescriptions found.</p>
            <p className="mt-1 text-sm text-dreams-textSecondary/70">
              This patient has no prescriptions from you or your facility.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {prescriptionsData?.data?.map((prescription: any) => (
              <PrescriptionCard
                key={prescription.id}
                prescription={{
                  id: prescription.id,
                  medicines: prescription.medicines || [],
                  diagnosis: prescription.diagnosis,
                  notes: prescription.notes,
                  created_at: prescription.created_at,
                  valid_until: prescription.valid_until,
                  doctor_name: prescription.doctor_name,
                }}
                variant="doctor"
                collapsible={true}
                defaultExpanded={false}
              />
            ))}
          </div>
        )}
      </div>

      {/* Info Banner */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <Pill className="h-5 w-5 text-blue-500 mt-0.5 flex-shrink-0" />
          <div className="text-sm text-blue-900">
            <p className="font-medium">Prescription Access</p>
            <p className="mt-1 text-blue-700">
              You can view prescriptions created by you or other doctors from your facility.
              This ensures coordinated care within your practice.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
