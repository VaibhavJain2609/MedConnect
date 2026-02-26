"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Plus, Search, Mail, Phone, Briefcase, Calendar } from "lucide-react";
import { getDoctors, getDoctorSpecialties, Doctor } from "@/lib/api/doctors";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";

export default function AdminDoctorsPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [specialtyFilter, setSpecialtyFilter] = useState("all");
  const [page, setPage] = useState(1);
  const [limit] = useState(12);

  // Fetch doctors from backend
  const { data, isLoading, error } = useQuery({
    queryKey: ["admin-doctors", searchQuery, specialtyFilter, page, limit],
    queryFn: () =>
      getDoctors({
        search: searchQuery || undefined,
        specialty: specialtyFilter !== "all" ? specialtyFilter : undefined,
        page,
        limit,
      }),
  });

  // Fetch specialties for filter dropdown
  const { data: specialties } = useQuery({
    queryKey: ["doctor-specialties"],
    queryFn: getDoctorSpecialties,
  });

  const doctors = data?.doctors;
  const totalPages = data?.totalPages || 1;

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12 space-y-4">
        <p className="text-red-600 font-medium">Failed to load doctors</p>
        <p className="text-dreams-textSecondary text-sm">
          {error instanceof Error ? error.message : "An error occurred"}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <Breadcrumb items={[{ label: "Doctors" }]} />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-dreams-textPrimary">
            Doctors
          </h1>
          <p className="text-dreams-textSecondary mt-1">
            Manage doctor profiles and information
          </p>
        </div>

        <button className="flex items-center gap-2 px-4 py-2 bg-dreams-blue text-white rounded-lg hover:opacity-90 transition-opacity">
          <Plus className="h-5 w-5" />
          <span>New Doctor</span>
        </button>
      </div>

      {/* Search and Filters */}
      <div className="flex items-center gap-4">
        {/* Search */}
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search by name, ID, or specialty..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full h-10 pl-10 pr-4 rounded-lg border border-dreams-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
          />
        </div>

        {/* Specialty Filter */}
        <select
          value={specialtyFilter}
          onChange={(e) => setSpecialtyFilter(e.target.value)}
          className="h-10 px-4 rounded-lg border border-dreams-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
        >
          <option value="all">All Specialties</option>
          {specialties?.map((specialty) => (
            <option key={specialty} value={specialty}>
              {specialty}
            </option>
          ))}
        </select>
      </div>

      {/* Grid View */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
        {doctors && doctors.length > 0 ? (
          doctors.map((doctor) => (
            <div
              key={doctor.id}
              className="bg-white rounded-lg shadow-card p-6 hover:shadow-lg transition-shadow"
            >
              {/* Profile Photo */}
              <div className="flex flex-col items-center mb-4">
                <Avatar
                  src={doctor.photo}
                  fallback={doctor.name}
                  size="2xl"
                  className="mb-3"
                />

                {/* Doctor ID */}
                <a
                  href={`/admin/doctors/${doctor.id}`}
                  className="text-sm font-medium text-dreams-blue hover:underline mb-1"
                >
                  {doctor.id}
                </a>

                {/* Name */}
                <h3 className="text-lg font-bold text-dreams-textPrimary text-center">
                  {doctor.name}
                </h3>

                {/* Specialty */}
                <Badge variant="upcoming" className="mt-2">
                  {doctor.specialty}
                </Badge>
              </div>

              {/* Stats */}
              <div className="grid grid-cols-2 gap-3 mb-4 pb-4 border-b border-dreams-border">
                <div className="text-center">
                  <div className="flex items-center justify-center gap-1 mb-1">
                    <Briefcase className="h-3 w-3 text-dreams-textSecondary" />
                    <p className="text-xs text-dreams-textSecondary">
                      Experience
                    </p>
                  </div>
                  <p className="text-sm font-bold text-dreams-textPrimary">
                    {doctor.experience} years
                  </p>
                </div>

                <div className="text-center">
                  <div className="flex items-center justify-center gap-1 mb-1">
                    <Calendar className="h-3 w-3 text-dreams-textSecondary" />
                    <p className="text-xs text-dreams-textSecondary">
                      Appointments
                    </p>
                  </div>
                  <p className="text-sm font-bold text-dreams-textPrimary">
                    {doctor.appointmentsCount.toLocaleString()}
                  </p>
                </div>
              </div>

              {/* Contact Info */}
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <Mail className="h-4 w-4 text-dreams-textSecondary flex-shrink-0" />
                  <p className="text-xs text-dreams-textSecondary truncate">
                    {doctor.email}
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <Phone className="h-4 w-4 text-dreams-textSecondary flex-shrink-0" />
                  <p className="text-xs text-dreams-textSecondary">
                    {doctor.phone}
                  </p>
                </div>
              </div>
            </div>
          ))
        ) : (
          <div className="col-span-full text-center py-12">
            <p className="text-dreams-textSecondary">No doctors found</p>
          </div>
        )}
      </div>
    </div>
  );
}
