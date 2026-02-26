"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ColumnDef } from "@tanstack/react-table";
import { Plus, Search } from "lucide-react";
import api from "@/lib/api";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { ViewToggle, useViewMode, ViewMode } from "@/components/ui/view-toggle";
import { ProfileCard } from "@/components/cards/profile-card";
import { DataTable, DataTableColumnHeader } from "@/components/ui/data-table";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";

interface Patient {
  id: string;
  name: string;
  photo: string | null;
  status: "inProgress" | "completed" | "pending";
  statusLabel: string;
  lastVisit: string;
  gender: string;
  location: string;
  doctor: string;
  department: string;
  age: number;
}

export default function AdminPatientsPage() {
  const [viewMode, setViewMode] = useViewMode("admin-patients-view", "grid");
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  // Fetch patients
  const { data: patients, isLoading } = useQuery({
    queryKey: ["admin-patients"],
    queryFn: async () => {
      // TODO: Replace with actual API call to /api/v1/admin/patients
      // Mock data for now
      return [
        {
          id: "P-001",
          name: "John Doe",
          photo: null,
          status: "inProgress" as const,
          statusLabel: "In Patient",
          lastVisit: "2 days ago",
          gender: "Male",
          location: "New York",
          doctor: "Dr. Smith",
          department: "Cardiology",
          age: 45,
        },
        {
          id: "P-002",
          name: "Jane Smith",
          photo: null,
          status: "completed" as const,
          statusLabel: "Out Patient",
          lastVisit: "1 week ago",
          gender: "Female",
          location: "Los Angeles",
          doctor: "Dr. Johnson",
          department: "Neurology",
          age: 32,
        },
        {
          id: "P-003",
          name: "Mike Wilson",
          photo: null,
          status: "pending" as const,
          statusLabel: "Scheduled",
          lastVisit: "3 days ago",
          gender: "Male",
          location: "Chicago",
          doctor: "Dr. Brown",
          department: "Orthopedics",
          age: 58,
        },
        {
          id: "P-004",
          name: "Sarah Johnson",
          photo: null,
          status: "inProgress" as const,
          statusLabel: "In Patient",
          lastVisit: "Today",
          gender: "Female",
          location: "Houston",
          doctor: "Dr. Davis",
          department: "Pediatrics",
          age: 8,
        },
        {
          id: "P-005",
          name: "Robert Brown",
          photo: null,
          status: "completed" as const,
          statusLabel: "Out Patient",
          lastVisit: "5 days ago",
          gender: "Male",
          location: "Phoenix",
          doctor: "Dr. Miller",
          department: "Dermatology",
          age: 52,
        },
        {
          id: "P-006",
          name: "Emily Davis",
          photo: null,
          status: "inProgress" as const,
          statusLabel: "In Patient",
          lastVisit: "1 day ago",
          gender: "Female",
          location: "Philadelphia",
          doctor: "Dr. Wilson",
          department: "Cardiology",
          age: 67,
        },
      ] as Patient[];
    },
  });

  // Filter patients based on search and status
  const filteredPatients = patients?.filter((patient) => {
    const matchesSearch =
      patient.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      patient.id.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus =
      statusFilter === "all" || patient.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  // Table columns definition
  const columns: ColumnDef<Patient>[] = [
    {
      accessorKey: "id",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Patient ID" />
      ),
      cell: ({ row }) => (
        <span className="font-medium text-dreams-blue">
          {row.getValue("id")}
        </span>
      ),
    },
    {
      accessorKey: "name",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Patient Name" />
      ),
      cell: ({ row }) => (
        <div className="flex items-center gap-3">
          <Avatar
            src={row.original.photo}
            fallback={row.getValue("name")}
            size="sm"
          />
          <span className="font-medium">{row.getValue("name")}</span>
        </div>
      ),
    },
    {
      accessorKey: "status",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Status" />
      ),
      cell: ({ row }) => (
        <Badge variant={row.getValue("status")}>
          {row.original.statusLabel}
        </Badge>
      ),
    },
    {
      accessorKey: "lastVisit",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Last Visit" />
      ),
    },
    {
      accessorKey: "gender",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Gender" />
      ),
    },
    {
      accessorKey: "doctor",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Doctor" />
      ),
    },
    {
      accessorKey: "department",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Department" />
      ),
    },
  ];

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
      <Breadcrumb items={[{ label: "Patients" }]} />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-dreams-textPrimary">
            Patients
          </h1>
          <p className="text-dreams-textSecondary mt-1">
            Manage patient records and information
          </p>
        </div>

        <div className="flex items-center gap-3">
          <ViewToggle value={viewMode} onChange={setViewMode} />
          <button className="flex items-center gap-2 px-4 py-2 bg-dreams-blue text-white rounded-lg hover:opacity-90 transition-opacity">
            <Plus className="h-5 w-5" />
            <span>New Patient</span>
          </button>
        </div>
      </div>

      {/* Search and Filters */}
      <div className="flex items-center gap-4">
        {/* Search */}
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search by name or ID..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full h-10 pl-10 pr-4 rounded-lg border border-dreams-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
          />
        </div>

        {/* Status Filter */}
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="h-10 px-4 rounded-lg border border-dreams-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
        >
          <option value="all">All Status</option>
          <option value="inProgress">In Patient</option>
          <option value="completed">Out Patient</option>
          <option value="pending">Scheduled</option>
        </select>
      </div>

      {/* Grid View */}
      {viewMode === "grid" && (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {filteredPatients && filteredPatients.length > 0 ? (
            filteredPatients.map((patient) => (
              <ProfileCard
                key={patient.id}
                id={patient.id}
                name={patient.name}
                photo={patient.photo}
                status={patient.status}
                statusLabel={patient.statusLabel}
                infoItems={[
                  { label: "Last Visit", value: patient.lastVisit },
                  { label: "Gender", value: patient.gender },
                  { label: "Location", value: patient.location },
                ]}
                href={`/admin/patients/${patient.id}`}
                ctaLabel="View Profile"
              />
            ))
          ) : (
            <div className="col-span-full text-center py-12">
              <p className="text-dreams-textSecondary">No patients found</p>
            </div>
          )}
        </div>
      )}

      {/* Table View */}
      {viewMode === "table" && filteredPatients && (
        <DataTable
          columns={columns}
          data={filteredPatients}
          pageSize={10}
          searchColumn="name"
          searchPlaceholder="Search patients..."
        />
      )}
    </div>
  );
}
