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

interface Appointment {
  id: string;
  patientId: string;
  patientName: string;
  patientPhoto: string | null;
  doctorName: string;
  doctorPhoto: string | null;
  department: string;
  appointmentDate: string;
  appointmentTime: string;
  status: "upcoming" | "inProgress" | "completed";
}

export default function AdminAppointmentsPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  // Fetch appointments
  const { data: appointments, isLoading } = useQuery({
    queryKey: ["admin-appointments"],
    queryFn: async () => {
      // TODO: Replace with actual API call to /api/v1/admin/appointments
      // Mock data for now
      return [
        {
          id: "A-001",
          patientId: "P-001",
          patientName: "John Doe",
          patientPhoto: null,
          doctorName: "Dr. Sarah Smith",
          doctorPhoto: null,
          department: "Cardiology",
          appointmentDate: "2026-02-28",
          appointmentTime: "10:00 AM",
          status: "upcoming",
        },
        {
          id: "A-002",
          patientId: "P-002",
          patientName: "Jane Smith",
          patientPhoto: null,
          doctorName: "Dr. Michael Johnson",
          doctorPhoto: null,
          department: "Neurology",
          appointmentDate: "2026-02-28",
          appointmentTime: "2:30 PM",
          status: "upcoming",
        },
        {
          id: "A-003",
          patientId: "P-003",
          patientName: "Mike Wilson",
          patientPhoto: null,
          doctorName: "Dr. Emily Davis",
          doctorPhoto: null,
          department: "Orthopedics",
          appointmentDate: "2026-02-27",
          appointmentTime: "11:00 AM",
          status: "inProgress",
        },
        {
          id: "A-004",
          patientId: "P-004",
          patientName: "Sarah Johnson",
          patientPhoto: null,
          doctorName: "Dr. James Wilson",
          doctorPhoto: null,
          department: "Pediatrics",
          appointmentDate: "2026-02-26",
          appointmentTime: "3:00 PM",
          status: "completed",
        },
        {
          id: "A-005",
          patientId: "P-005",
          patientName: "Robert Brown",
          patientPhoto: null,
          doctorName: "Dr. Linda Brown",
          doctorPhoto: null,
          department: "Dermatology",
          appointmentDate: "2026-02-25",
          appointmentTime: "9:30 AM",
          status: "completed",
        },
        {
          id: "A-006",
          patientId: "P-006",
          patientName: "Emily Davis",
          patientPhoto: null,
          doctorName: "Dr. Robert Miller",
          doctorPhoto: null,
          department: "General Medicine",
          appointmentDate: "2026-02-29",
          appointmentTime: "1:00 PM",
          status: "upcoming",
        },
        {
          id: "A-007",
          patientId: "P-001",
          patientName: "John Doe",
          patientPhoto: null,
          doctorName: "Dr. Jennifer Garcia",
          doctorPhoto: null,
          department: "Cardiology",
          appointmentDate: "2026-02-27",
          appointmentTime: "4:30 PM",
          status: "inProgress",
        },
        {
          id: "A-008",
          patientId: "P-002",
          patientName: "Jane Smith",
          patientPhoto: null,
          doctorName: "Dr. David Martinez",
          doctorPhoto: null,
          department: "Neurology",
          appointmentDate: "2026-02-24",
          appointmentTime: "10:15 AM",
          status: "completed",
        },
      ] as Appointment[];
    },
  });

  // Filter appointments based on search and status
  const filteredAppointments = appointments?.filter((appointment) => {
    const matchesSearch =
      appointment.patientName
        .toLowerCase()
        .includes(searchQuery.toLowerCase()) ||
      appointment.patientId.toLowerCase().includes(searchQuery.toLowerCase()) ||
      appointment.doctorName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      appointment.id.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus =
      statusFilter === "all" || appointment.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  // Table columns definition
  const columns: ColumnDef<Appointment>[] = [
    {
      accessorKey: "patientId",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Patient ID" />
      ),
      cell: ({ row }) => (
        <a
          href={`/admin/patients/${row.getValue("patientId")}`}
          className="font-medium text-dreams-blue hover:underline"
        >
          {row.getValue("patientId")}
        </a>
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
      accessorKey: "department",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Department" />
      ),
    },
    {
      accessorKey: "appointmentDate",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Appointment Date" />
      ),
      cell: ({ row }) => (
        <div>
          <p className="font-medium">
            {new Date(row.getValue("appointmentDate")).toLocaleDateString(
              "en-US",
              {
                month: "short",
                day: "numeric",
                year: "numeric",
              }
            )}
          </p>
          <p className="text-xs text-dreams-textSecondary">
            {row.original.appointmentTime}
          </p>
        </div>
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
          upcoming: "Upcoming",
          inProgress: "In Progress",
          completed: "Completed",
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
      <Breadcrumb items={[{ label: "Appointments" }]} />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-dreams-textPrimary">
            Appointments
          </h1>
          <p className="text-dreams-textSecondary mt-1">
            Manage patient appointments and schedules
          </p>
        </div>

        <button className="flex items-center gap-2 px-4 py-2 bg-dreams-blue text-white rounded-lg hover:opacity-90 transition-opacity">
          <Plus className="h-5 w-5" />
          <span>New Appointment</span>
        </button>
      </div>

      {/* Search and Filters */}
      <div className="flex items-center gap-4">
        {/* Search */}
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search by patient, doctor, or ID..."
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
          <option value="upcoming">Upcoming</option>
          <option value="inProgress">In Progress</option>
          <option value="completed">Completed</option>
        </select>
      </div>

      {/* Data Table */}
      {filteredAppointments && (
        <DataTable
          columns={columns}
          data={filteredAppointments}
          pageSize={10}
          searchColumn="patientName"
          searchPlaceholder="Search appointments..."
        />
      )}
    </div>
  );
}
