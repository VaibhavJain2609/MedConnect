"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Users } from "lucide-react";

import { getDoctorPatients, type DoctorPatient } from "@/lib/api/doctors";
import { DashboardWidget } from "@/components/dashboard/dashboard-widget";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";

const PATIENT_LIMIT = 6;

function PatientsSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" aria-hidden>
      {[0, 1, 2, 3, 4, 5].map((i) => (
        <Skeleton key={i} className="h-24 w-full" />
      ))}
    </div>
  );
}

/**
 * Your Patients widget — patients linked to the current doctor via
 * GET /api/v1/doctors/patients, with per-patient shortcuts.
 */
export function PatientsWidget() {
  const query = useQuery({
    queryKey: ["doctor-dashboard-patients"],
    queryFn: () => getDoctorPatients({ limit: PATIENT_LIMIT }),
  });

  const patients: DoctorPatient[] = query.data?.data ?? [];

  return (
    <DashboardWidget
      title="Your Patients"
      icon={Users}
      headerAction={
        <Link
          href="/doctor/patients"
          className="inline-flex items-center gap-1 text-sm font-medium text-dreams-blue hover:underline"
        >
          View all
          <ArrowRight className="h-3.5 w-3.5" aria-hidden />
        </Link>
      }
      isLoading={query.isLoading}
      isError={query.isError}
      onRetry={() => query.refetch()}
      errorMessage="Couldn't load your patients."
      skeleton={<PatientsSkeleton />}
    >
      {patients.length === 0 ? (
        <EmptyState
          icon={Users}
          title="No patients yet"
          description="Create a medical record or prescription to add your first patient."
          className="py-8"
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {patients.map((patient) => (
            <div
              key={patient.id}
              className="rounded-lg border border-dreams-border p-4 hover:border-dreams-blue/50 hover:bg-dreams-lightBg/50 transition-all"
            >
              <h3 className="truncate font-medium text-dreams-textPrimary">
                {patient.full_name}
              </h3>
              <p className="mt-0.5 truncate text-sm text-dreams-textSecondary">
                {patient.email || patient.phone || "—"}
              </p>
              <div className="mt-3 flex items-center gap-3">
                <Link
                  href={`/doctor/patients/${patient.id}`}
                  className="text-xs font-medium text-dreams-blue hover:underline"
                >
                  View →
                </Link>
                <Link
                  href={`/doctor/records/new?patient_id=${patient.id}`}
                  className="text-xs text-dreams-textSecondary hover:text-dreams-blue hover:underline"
                >
                  Add record →
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </DashboardWidget>
  );
}
