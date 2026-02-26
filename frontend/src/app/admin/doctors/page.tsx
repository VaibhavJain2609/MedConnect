"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Plus, Search, Mail, Phone, Briefcase, Calendar } from "lucide-react";
import api from "@/lib/api";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";

interface Doctor {
  id: string;
  name: string;
  photo: string | null;
  specialty: string;
  experience: number;
  appointmentsCount: number;
  email: string;
  phone: string;
  department: string;
}

export default function AdminDoctorsPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [specialtyFilter, setSpecialtyFilter] = useState("all");

  // Fetch doctors
  const { data: doctors, isLoading } = useQuery({
    queryKey: ["admin-doctors"],
    queryFn: async () => {
      // TODO: Replace with actual API call to /api/v1/admin/doctors
      // Mock data for now
      return [
        {
          id: "D-001",
          name: "Dr. Sarah Smith",
          photo: null,
          specialty: "Cardiology",
          experience: 15,
          appointmentsCount: 1234,
          email: "sarah.smith@medconnect.com",
          phone: "+1 (555) 123-4567",
          department: "Cardiology",
        },
        {
          id: "D-002",
          name: "Dr. Michael Johnson",
          photo: null,
          specialty: "Neurology",
          experience: 12,
          appointmentsCount: 987,
          email: "michael.johnson@medconnect.com",
          phone: "+1 (555) 234-5678",
          department: "Neurology",
        },
        {
          id: "D-003",
          name: "Dr. Emily Davis",
          photo: null,
          specialty: "Orthopedics",
          experience: 10,
          appointmentsCount: 856,
          email: "emily.davis@medconnect.com",
          phone: "+1 (555) 345-6789",
          department: "Orthopedics",
        },
        {
          id: "D-004",
          name: "Dr. James Wilson",
          photo: null,
          specialty: "Pediatrics",
          experience: 18,
          appointmentsCount: 1456,
          email: "james.wilson@medconnect.com",
          phone: "+1 (555) 456-7890",
          department: "Pediatrics",
        },
        {
          id: "D-005",
          name: "Dr. Linda Brown",
          photo: null,
          specialty: "Dermatology",
          experience: 8,
          appointmentsCount: 654,
          email: "linda.brown@medconnect.com",
          phone: "+1 (555) 567-8901",
          department: "Dermatology",
        },
        {
          id: "D-006",
          name: "Dr. Robert Miller",
          photo: null,
          specialty: "General Medicine",
          experience: 20,
          appointmentsCount: 2103,
          email: "robert.miller@medconnect.com",
          phone: "+1 (555) 678-9012",
          department: "General Medicine",
        },
        {
          id: "D-007",
          name: "Dr. Jennifer Garcia",
          photo: null,
          specialty: "Cardiology",
          experience: 14,
          appointmentsCount: 1089,
          email: "jennifer.garcia@medconnect.com",
          phone: "+1 (555) 789-0123",
          department: "Cardiology",
        },
        {
          id: "D-008",
          name: "Dr. David Martinez",
          photo: null,
          specialty: "Neurology",
          experience: 11,
          appointmentsCount: 892,
          email: "david.martinez@medconnect.com",
          phone: "+1 (555) 890-1234",
          department: "Neurology",
        },
      ] as Doctor[];
    },
  });

  // Filter doctors based on search and specialty
  const filteredDoctors = doctors?.filter((doctor) => {
    const matchesSearch =
      doctor.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      doctor.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      doctor.specialty.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesSpecialty =
      specialtyFilter === "all" || doctor.specialty === specialtyFilter;
    return matchesSearch && matchesSpecialty;
  });

  // Get unique specialties for filter
  const specialties = Array.from(
    new Set(doctors?.map((d) => d.specialty) || [])
  );

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
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
          {specialties.map((specialty) => (
            <option key={specialty} value={specialty}>
              {specialty}
            </option>
          ))}
        </select>
      </div>

      {/* Grid View */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
        {filteredDoctors && filteredDoctors.length > 0 ? (
          filteredDoctors.map((doctor) => (
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
