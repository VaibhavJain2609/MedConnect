"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ColumnDef } from "@tanstack/react-table";
import { Plus, Search } from "lucide-react";
import api from "@/lib/api";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { DataTable, DataTableColumnHeader } from "@/components/ui/data-table";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";

interface Visit {
  id: string;
  patientName: string;
  patientPhoto: string | null;
  department: string;
  doctorName: string;
  doctorPhoto: string | null;
  visitDate: string;
  status: "inProgress" | "completed" | "pending";
}

export default function AdminVisitsPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  // Fetch visits
  const { data: visits, isLoading } = useQuery({
    queryKey: ["admin-visits"],
    queryFn: async () => {
      // TODO: Replace with actual API call to /api/v1/admin/visits
      // Mock data for now
      return [
        {
          id: "V-001",
          patientName: "John Doe",
          patientPhoto: null,
          department: "Cardiology",
          doctorName: "Dr. Sarah Smith",
          doctorPhoto: null,
          visitDate: "2026-02-26 10:00 AM",
          status: "completed",
        },
        {
          id: "V-002",
          patientName: "Jane Smith",
          patientPhoto: null,
          department: "Neurology",
          doctorName: "Dr. Michael Johnson",
          doctorPhoto: null,
          visitDate: "2026-02-26 2:30 PM",
          status: "completed",
        },
        {
          id: "V-003",
          patientName: "Mike Wilson",
          patientPhoto: null,
          department: "Orthopedics",
          doctorName: "Dr. Emily Davis",
          doctorPhoto: null,
          visitDate: "2026-02-27 11:00 AM",
          status: "inProgress",
        },
        {
          id: "V-004",
          patientName: "Sarah Johnson",
          patientPhoto: null,
          department: "Pediatrics",
          doctorName: "Dr. James Wilson",
          doctorPhoto: null,
          visitDate: "2026-02-28 3:00 PM",
          status: "pending",
        },
        {
          id: "V-005",
          patientName: "Robert Brown",
          patientPhoto: null,
          department: "Dermatology",
          doctorName: "Dr. Linda Brown",
          doctorPhoto: null,
          visitDate: "2026-02-25 9:30 AM",
          status: "completed",
        },
        {
          id: "V-006",
          patientName: "Emily Davis",
          patientPhoto: null,
          department: "General Medicine",
          doctorName: "Dr. Robert Miller",
          doctorPhoto: null,
          visitDate: "2026-02-29 1:00 PM",
          status: "pending",
        },
        {
          id: "V-007",
          patientName: "David Martinez",
          patientPhoto: null,
          department: "Cardiology",
          doctorName: "Dr. Jennifer Garcia",
          doctorPhoto: null,
          visitDate: "2026-02-27 4:30 PM",
          status: "inProgress",
        },
        {
          id: "V-008",
          patientName: "Lisa Anderson",
          patientPhoto: null,
          department: "Neurology",
          doctorName: "Dr. David Martinez",
          doctorPhoto: null,
          visitDate: "2026-02-24 10:15 AM",
          status: "completed",
        },
      ] as Visit[];
    },
  });

  // Filter visits based on search and status
  const filteredVisits = visits?.filter((visit) => {
    const matchesSearch =
      visit.patientName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      visit.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      visit.doctorName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      visit.department.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus =
      statusFilter === "all" || visit.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  // Table columns definition
  const columns: ColumnDef<Visit>[] = [
    {
      accessorKey: "id",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Visit ID" />
      ),
      cell: ({ row }) => (
        <span className="font-medium text-dreams-blue">
          {row.getValue("id")}
        </span>
      ),
    },
    {
      accessorKey: "patientName",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Patient Name" />
      ),
      cell: ({ row }) => (
        <div className="flex items-center gap-3">
          <Avatar
            src={row.original.patientPhoto}
            fallback={row.getValue("patientName")}
            size="sm"
          />
          <span className="font-medium">{row.getValue("patientName")}</span>
        </div>
      ),
    },
    {
      accessorKey: "department",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Department" />
      ),
    },
    {
      accessorKey: "doctorName",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Doctor Name" />
      ),
      cell: ({ row }) => (
        <div className="flex items-center gap-3">
          <Avatar
            src={row.original.doctorPhoto}
            fallback={row.getValue("doctorName")}
            size="sm"
          />
          <span className="font-medium">{row.getValue("doctorName")}</span>
        </div>
      ),
    },
    {
      accessorKey: "visitDate",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Visit Date" />
      ),
      cell: ({ row }) => (
        <span className="text-sm">{row.getValue("visitDate")}</span>
      ),
    },
    {
      accessorKey: "status",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Status" />
      ),
      cell: ({ row }) => {
        const status = row.getValue("status") as string;
        const statusLabels: Record<string, string> = {
          inProgress: "In Progress",
          completed: "Completed",
          pending: "Pending",
        };

        return (
          <Badge variant={status as any}>
            {statusLabels[status] || status}
          </Badge>
        );
      },
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
      <Breadcrumb items={[{ label: "Visits" }]} />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold text-dreams-textPrimary">
              Visits
            </h1>
            <Badge variant="pending" className="text-base px-3 py-1">
              {visits?.length || 0}
            </Badge>
          </div>
          <p className="text-dreams-textSecondary mt-1">
            Manage patient visits and consultations
          </p>
        </div>

        <button className="flex items-center gap-2 px-4 py-2 bg-dreams-blue text-white rounded-lg hover:opacity-90 transition-opacity">
          <Plus className="h-5 w-5" />
          <span>New Visit</span>
        </button>
      </div>

      {/* Search and Filters */}
      <div className="flex items-center gap-4">
        {/* Search */}
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search by patient, doctor, or department..."
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
          <option value="pending">Pending</option>
          <option value="inProgress">In Progress</option>
          <option value="completed">Completed</option>
        </select>
      </div>

      {/* Data Table */}
      {filteredVisits && (
        <DataTable
          columns={columns}
          data={filteredVisits}
          pageSize={10}
          searchColumn="patientName"
          searchPlaceholder="Search visits..."
        />
      )}
    </div>
  );
}
