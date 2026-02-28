"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { FilePlus, FileText, Pill, Users } from "lucide-react";

export default function DoctorDashboard() {
  const { data, isLoading } = useQuery({
    queryKey: ["doctor-patients"],
    queryFn: async () => {
      const res = await api.get("/api/v1/doctors/patients?limit=50");
      return res.data;
    },
  });

  return (
    <div className="space-y-6">
      <Breadcrumb items={[{ label: "Dashboard" }]} />

      <div>
        <h1 className="text-3xl font-bold text-dreams-textPrimary">Dashboard</h1>
        <p className="text-dreams-textSecondary mt-1">Welcome back, Doctor</p>
      </div>

      {/* Quick Actions */}
      <div className="grid gap-4 sm:grid-cols-3">
        <Link
          href="/doctor/records/new"
          className="bg-white rounded-lg shadow-card p-5 flex items-center gap-4 border border-dreams-border hover:border-dreams-blue/50 hover:shadow-md transition-all group"
        >
          <div className="p-3 rounded-lg bg-primary-50 text-primary-600 group-hover:bg-primary-100 transition-colors">
            <FileText className="h-6 w-6" />
          </div>
          <div>
            <p className="font-semibold text-dreams-textPrimary">New Record</p>
            <p className="text-xs text-dreams-textSecondary mt-0.5">Create a medical record</p>
          </div>
        </Link>

        <Link
          href="/doctor/prescriptions/new"
          className="bg-white rounded-lg shadow-card p-5 flex items-center gap-4 border border-dreams-border hover:border-green-400/50 hover:shadow-md transition-all group"
        >
          <div className="p-3 rounded-lg bg-green-50 text-green-600 group-hover:bg-green-100 transition-colors">
            <FilePlus className="h-6 w-6" />
          </div>
          <div>
            <p className="font-semibold text-dreams-textPrimary">New Prescription</p>
            <p className="text-xs text-dreams-textSecondary mt-0.5">Write a prescription</p>
          </div>
        </Link>

        <Link
          href="/doctor/prescriptions"
          className="bg-white rounded-lg shadow-card p-5 flex items-center gap-4 border border-dreams-border hover:border-blue-400/50 hover:shadow-md transition-all group"
        >
          <div className="p-3 rounded-lg bg-blue-50 text-blue-600 group-hover:bg-blue-100 transition-colors">
            <Pill className="h-6 w-6" />
          </div>
          <div>
            <p className="font-semibold text-dreams-textPrimary">View Prescriptions</p>
            <p className="text-xs text-dreams-textSecondary mt-0.5">All your prescriptions</p>
          </div>
        </Link>
      </div>

      {/* Patients Section */}
      <div className="bg-white rounded-lg shadow-card p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold text-dreams-textPrimary">Your Patients</h2>
          <div className="flex items-center gap-2 text-dreams-textSecondary">
            <Users className="h-4 w-4" />
            <span className="text-sm">{data?.data?.length || 0} patients</span>
          </div>
        </div>

        {isLoading ? (
          <div className="flex justify-center py-12">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
          </div>
        ) : data?.data?.length === 0 ? (
          <div className="py-12 text-center">
            <Users className="h-12 w-12 text-dreams-textSecondary mx-auto mb-4" />
            <p className="text-dreams-textSecondary">No patients yet.</p>
            <p className="mt-1 text-sm text-dreams-textSecondary/70">
              Create a medical record or prescription to add your first patient.
            </p>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {data?.data?.map((patient: any) => (
              <div
                key={patient.id}
                className="rounded-lg border border-dreams-border p-4 hover:border-dreams-blue/50 hover:bg-dreams-lightBg/50 transition-all"
              >
                <h3 className="font-medium text-dreams-textPrimary">{patient.full_name}</h3>
                <p className="mt-0.5 text-sm text-dreams-textSecondary">
                  {patient.email || patient.phone}
                </p>
                <div className="mt-3 flex flex-col gap-2">
                  <Link
                    href={`/doctor/records/new?patient_id=${patient.id}`}
                    className="inline-block text-xs text-dreams-blue hover:underline"
                  >
                    Add record →
                  </Link>
                  <Link
                    href={`/doctor/patients/${patient.id}/prescriptions`}
                    className="inline-flex items-center gap-1 text-xs text-green-600 hover:underline"
                  >
                    <Pill className="h-3 w-3" />
                    View prescriptions →
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
