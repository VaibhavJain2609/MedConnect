"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { Navbar } from "@/components/layout/navbar";
import { AuthGuard } from "@/components/layout/auth-guard";

export default function DoctorDashboard() {
  const { data, isLoading } = useQuery({
    queryKey: ["doctor-patients"],
    queryFn: async () => {
      const res = await api.get("/api/v1/doctors/patients?limit=50");
      return res.data;
    },
  });

  return (
    <AuthGuard requiredRole="doctor">
      <Navbar />
      <main className="mx-auto max-w-4xl px-4 py-6">
        <div className="mb-6">
          <h1 className="mb-4 text-2xl font-bold">Doctor Dashboard</h1>

          {/* Quick Actions */}
          <div className="grid gap-3 sm:grid-cols-3">
            <Link
              href="/doctor/records/new"
              className="rounded-lg border-2 border-primary-200 bg-primary-50 p-4 text-center transition hover:border-primary-300 hover:bg-primary-100"
            >
              <div className="text-2xl">📝</div>
              <div className="mt-2 text-sm font-medium text-primary-900">New Record</div>
            </Link>
            <Link
              href="/doctor/prescriptions/new"
              className="rounded-lg border-2 border-green-200 bg-green-50 p-4 text-center transition hover:border-green-300 hover:bg-green-100"
            >
              <div className="text-2xl">💊</div>
              <div className="mt-2 text-sm font-medium text-green-900">New Prescription</div>
            </Link>
            <Link
              href="/doctor/prescriptions"
              className="rounded-lg border-2 border-blue-200 bg-blue-50 p-4 text-center transition hover:border-blue-300 hover:bg-blue-100"
            >
              <div className="text-2xl">📋</div>
              <div className="mt-2 text-sm font-medium text-blue-900">View Prescriptions</div>
            </Link>
          </div>
        </div>

        <section>
          <h2 className="mb-4 text-lg font-semibold text-gray-700">Your Patients</h2>

          {isLoading ? (
            <div className="flex justify-center py-12">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
            </div>
          ) : data?.data?.length === 0 ? (
            <div className="rounded-xl border bg-white p-12 text-center">
              <p className="text-gray-500">No patients yet.</p>
              <p className="mt-1 text-sm text-gray-400">
                Create a medical record or prescription to add your first patient.
              </p>
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {data?.data?.map((patient: any) => (
                <div
                  key={patient.id}
                  className="rounded-xl border bg-white p-4 transition hover:shadow-sm"
                >
                  <h3 className="font-medium text-gray-900">{patient.full_name}</h3>
                  <p className="mt-0.5 text-sm text-gray-500">
                    {patient.email || patient.phone}
                  </p>
                  <div className="mt-3 flex flex-col gap-2">
                    <Link
                      href={`/doctor/records/new?patient_id=${patient.id}`}
                      className="inline-block text-xs text-primary-600 hover:underline"
                    >
                      Add record →
                    </Link>
                    <Link
                      href={`/doctor/patients/${patient.id}/prescriptions`}
                      className="inline-flex items-center gap-1 text-xs text-blue-600 hover:underline"
                    >
                      <span>💊</span>
                      View prescriptions →
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </main>
    </AuthGuard>
  );
}
