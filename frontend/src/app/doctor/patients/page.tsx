"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, Users, ChevronRight } from "lucide-react";
import { getDoctorPatients, DoctorPatient } from "@/lib/api/doctors";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { Avatar } from "@/components/ui/avatar";

export default function DoctorPatientsPage() {
  const [searchQuery, setSearchQuery] = useState("");

  const { data, isLoading, error } = useQuery({
    queryKey: ["doctor-patients-list", searchQuery],
    queryFn: () =>
      getDoctorPatients({ search: searchQuery || undefined, limit: 100 }),
  });

  const patients = data?.data ?? [];

  return (
    <div className="space-y-6">
      <Breadcrumb items={[{ label: "My Patients" }]} />

      <div>
        <h1 className="text-3xl font-bold text-dreams-textPrimary">My Patients</h1>
        <p className="text-dreams-textSecondary mt-1">
          Patients linked to your profile
        </p>
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
        <input
          type="text"
          placeholder="Search by name, email or phone..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full h-10 pl-10 pr-4 rounded-lg border border-dreams-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
        />
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
        </div>
      ) : error ? (
        <div className="flex flex-col items-center justify-center py-12 space-y-2">
          <p className="text-red-600 font-medium">Failed to load patients</p>
          <p className="text-dreams-textSecondary text-sm">
            {error instanceof Error ? error.message : "An error occurred"}
          </p>
        </div>
      ) : patients.length === 0 ? (
        <div className="bg-white rounded-xl border border-dreams-border shadow-card p-12 flex flex-col items-center justify-center text-center">
          <div className="p-4 rounded-full bg-dreams-lightBg mb-4">
            <Users className="h-10 w-10 text-dreams-textSecondary" />
          </div>
          <h2 className="text-xl font-semibold text-dreams-textPrimary mb-2">
            {searchQuery ? "No patients found" : "No patients yet"}
          </h2>
          <p className="text-dreams-textSecondary max-w-sm">
            {searchQuery
              ? "Try a different search term."
              : "Create a medical record or prescription to add your first patient."}
          </p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-dreams-border shadow-card overflow-hidden">
          <div className="px-6 py-4 border-b border-dreams-border flex items-center justify-between">
            <h2 className="font-semibold text-dreams-textPrimary">
              {patients.length} {patients.length === 1 ? "patient" : "patients"}
            </h2>
          </div>
          <ul className="divide-y divide-dreams-border">
            {patients.map((patient: DoctorPatient) => (
              <li key={patient.id}>
                <Link
                  href={`/doctor/patients/${patient.id}`}
                  className="flex items-center gap-4 px-6 py-4 hover:bg-dreams-lightBg transition-colors group"
                >
                  <Avatar fallback={patient.full_name} size="sm" />
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-dreams-textPrimary truncate">
                      {patient.full_name}
                    </p>
                    <p className="text-sm text-dreams-textSecondary truncate">
                      {patient.email ?? patient.phone ?? "No contact info"}
                    </p>
                  </div>
                  <ChevronRight className="h-4 w-4 text-dreams-textSecondary group-hover:text-dreams-blue transition-colors flex-shrink-0" />
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
