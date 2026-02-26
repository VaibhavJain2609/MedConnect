"use client";

/**
 * Patient Prescriptions Page (Doctor View)
 *
 * Shows all prescriptions for a specific patient that were created by:
 * - The current doctor, OR
 * - Doctors from the same facility/clinic
 *
 * This ensures doctors only see prescriptions from their own practice.
 */

import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { Navbar } from "@/components/layout/navbar";
import { AuthGuard } from "@/components/layout/auth-guard";
import { PrescriptionCard } from "@/components/prescription/PrescriptionCard";

export default function PatientPrescriptionsPage() {
  const params = useParams();
  const router = useRouter();
  const patientId = params.patientId as string;

  // Fetch patient info
  const { data: patientData } = useQuery({
    queryKey: ["patient-info", patientId],
    queryFn: async () => {
      try {
        // Try to get patient from the doctor's patient list
        const res = await api.get(`/api/v1/doctors/patients`);
        const patients = res.data.data || [];
        return patients.find((p: any) => p.id === patientId);
      } catch (err) {
        console.error("Error fetching patient info:", err);
        return null;
      }
    },
  });

  // Fetch prescriptions
  const { data: prescriptionsData, isLoading } = useQuery({
    queryKey: ["patient-prescriptions", patientId],
    queryFn: async () => {
      const res = await api.get(`/api/v1/doctors/patients/${patientId}/prescriptions`);
      return res.data;
    },
  });

  return (
    <AuthGuard requiredRole="doctor">
      <Navbar />
      <main className="mx-auto max-w-4xl px-4 py-6">
        {/* Header with patient info */}
        <div className="mb-6">
          <button
            onClick={() => router.back()}
            className="mb-3 flex items-center gap-1 text-sm text-gray-600 hover:text-primary-700"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Back to Dashboard
          </button>

          <div className="rounded-xl border bg-gradient-to-r from-blue-50 to-indigo-50 p-6">
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-blue-100 text-2xl">
                👤
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">
                  {patientData?.full_name || "Patient"}
                </h1>
                <p className="text-sm text-gray-600">
                  {patientData?.email || patientData?.phone || `ID: ${patientId}`}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Prescriptions section */}
        <section>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-700">
              Prescription History
            </h2>
            {prescriptionsData?.total > 0 && (
              <span className="rounded-full bg-blue-100 px-3 py-1 text-sm font-medium text-blue-700">
                {prescriptionsData.total} prescription{prescriptionsData.total !== 1 ? 's' : ''}
              </span>
            )}
          </div>

          {isLoading ? (
            <div className="flex justify-center py-12">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
            </div>
          ) : prescriptionsData?.data?.length === 0 ? (
            <div className="rounded-xl border bg-white p-12 text-center">
              <p className="text-gray-500">No prescriptions found.</p>
              <p className="mt-1 text-sm text-gray-400">
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
        </section>

        {/* Info banner */}
        <div className="mt-6 rounded-lg bg-blue-50 p-4">
          <div className="flex items-start gap-2">
            <span className="text-lg">ℹ️</span>
            <div className="text-sm text-blue-900">
              <p className="font-medium">Prescription Access</p>
              <p className="mt-1 text-blue-700">
                You can view prescriptions created by you or other doctors from your facility.
                This ensures coordinated care within your practice.
              </p>
            </div>
          </div>
        </div>
      </main>
    </AuthGuard>
  );
}
