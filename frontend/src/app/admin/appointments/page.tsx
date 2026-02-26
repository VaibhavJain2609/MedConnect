"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ColumnDef } from "@tanstack/react-table";
import { Plus, Search } from "lucide-react";
import { getAppointments, Appointment } from "@/lib/api/appointments";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { DataTable, DataTableColumnHeader } from "@/components/ui/data-table";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";

export default function AdminAppointmentsPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [page, setPage] = useState(1);
  const [limit] = useState(10);

  // Fetch appointments from backend
  const { data, isLoading, error } = useQuery({
    queryKey: ["admin-appointments", searchQuery, statusFilter, page, limit],
    queryFn: () =>
      getAppointments({
        search: searchQuery || undefined,
        status: statusFilter !== "all" ? statusFilter : undefined,
        page,
        limit,
      }),
  });

  const appointments = data?.appointments;
  const totalPages = data?.totalPages || 1;

  // Table columns definition
  const columns: ColumnDef<Appointment>[] = [
    {
      accessorKey: "patient_id",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Patient ID" />
      ),
      cell: ({ row }) => (
        <a
          href={`/admin/patients/${row.getValue("patient_id")}`}
          className="font-medium text-dreams-blue hover:underline"
        >
          {row.getValue("patient_id")}
        </a>
      ),
    },
    {
      accessorKey: "patient_name",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Patient Name" />
      ),
      cell: ({ row }) => (
        <div className="flex items-center gap-3">
          <Avatar
            src={row.original.patient_photo}
            fallback={row.getValue("patient_name")}
            size="sm"
          />
          <span className="font-medium">{row.getValue("patient_name")}</span>
        </div>
      ),
    },
    {
      accessorKey: "doctor_name",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Doctor Name" />
      ),
      cell: ({ row }) => (
        <div className="flex items-center gap-3">
          <Avatar
            src={row.original.doctor_photo}
            fallback={row.getValue("doctor_name")}
            size="sm"
          />
          <span className="font-medium">{row.getValue("doctor_name")}</span>
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
      accessorKey: "appointment_date",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Appointment Date" />
      ),
      cell: ({ row }) => (
        <div>
          <p className="font-medium">
            {new Date(row.getValue("appointment_date")).toLocaleDateString(
              "en-US",
              {
                month: "short",
                day: "numeric",
                year: "numeric",
              }
            )}
          </p>
          <p className="text-xs text-dreams-textSecondary">
            {row.original.appointment_time}
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
          in_progress: "In Progress",
          completed: "Completed",
          cancelled: "Cancelled",
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

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12 space-y-4">
        <p className="text-red-600 font-medium">Failed to load appointments</p>
        <p className="text-dreams-textSecondary text-sm">
          {error instanceof Error ? error.message : "An error occurred"}
        </p>
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
          <option value="in_progress">In Progress</option>
          <option value="completed">Completed</option>
          <option value="cancelled">Cancelled</option>
        </select>
      </div>

      {/* Data Table */}
      {appointments && (
        <DataTable
          columns={columns}
          data={appointments}
          pageSize={limit}
          searchColumn="patient_name"
          searchPlaceholder="Search appointments..."
        />
      )}
    </div>
  );
}
