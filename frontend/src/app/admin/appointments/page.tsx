"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ColumnDef } from "@tanstack/react-table";
import { Plus, Search } from "lucide-react";
import { getAppointments, type Appointment } from "@/lib/api/appointments";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { DataTable, DataTableColumnHeader } from "@/components/ui/data-table";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";

const STATUS_VARIANT_MAP: Record<string, string> = {
  scheduled: "upcoming",
  arrived: "inProgress",
  "in-progress": "inProgress",
  completed: "completed",
  cancelled: "overdue",
  "no-show": "pending",
};

const STATUS_LABELS: Record<string, string> = {
  scheduled: "Scheduled",
  arrived: "Arrived",
  "in-progress": "In Progress",
  completed: "Completed",
  cancelled: "Cancelled",
  "no-show": "No Show",
};

const TYPE_LABELS: Record<string, string> = {
  "in-person": "In Person",
  "teleconsult": "Teleconsult",
  "follow-up": "Follow-up",
};

export default function AdminAppointmentsPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  const { data, isLoading, error } = useQuery({
    queryKey: ["admin-appointments", statusFilter],
    queryFn: () =>
      getAppointments({
        status: statusFilter !== "all" ? statusFilter : undefined,
        all: true,
      }),
  });

  const allAppointments: Appointment[] = data?.data ?? [];

  // Client-side search filter
  const appointments = searchQuery
    ? allAppointments.filter(
        (a) =>
          (a.patient_name ?? "").toLowerCase().includes(searchQuery.toLowerCase()) ||
          (a.doctor_name ?? "").toLowerCase().includes(searchQuery.toLowerCase()) ||
          a.id.includes(searchQuery)
      )
    : allAppointments;

  const columns: ColumnDef<Appointment>[] = [
    {
      accessorKey: "patient_name",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Patient" />
      ),
      cell: ({ row }) => (
        <div className="flex items-center gap-3">
          <Avatar
            fallback={row.getValue("patient_name") as string}
            size="sm"
          />
          <div>
            <span className="font-medium">{row.getValue("patient_name") ?? "—"}</span>
          </div>
        </div>
      ),
    },
    {
      accessorKey: "doctor_name",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Doctor" />
      ),
      cell: ({ row }) => (
        <div className="flex items-center gap-3">
          <Avatar
            fallback={row.getValue("doctor_name") as string}
            size="sm"
          />
          <span className="font-medium">{row.getValue("doctor_name") ?? "—"}</span>
        </div>
      ),
    },
    {
      accessorKey: "clinic_name",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Clinic" />
      ),
      cell: ({ row }) => (
        <span className="text-dreams-textSecondary">{row.getValue("clinic_name") ?? "—"}</span>
      ),
    },
    {
      accessorKey: "type",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Type" />
      ),
      cell: ({ row }) => (
        <span>{TYPE_LABELS[row.getValue("type") as string] ?? row.getValue("type")}</span>
      ),
    },
    {
      accessorKey: "scheduled_at",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Scheduled At" />
      ),
      cell: ({ row }) => {
        const d = new Date(row.getValue("scheduled_at") as string);
        return (
          <div>
            <p className="font-medium">
              {d.toLocaleDateString("en-IN", { month: "short", day: "numeric", year: "numeric" })}
            </p>
            <p className="text-xs text-dreams-textSecondary">
              {d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: true })}
            </p>
          </div>
        );
      },
    },
    {
      accessorKey: "status",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Status" />
      ),
      cell: ({ row }) => {
        const s = row.getValue("status") as string;
        return (
          <Badge variant={STATUS_VARIANT_MAP[s] as any}>
            {STATUS_LABELS[s] ?? s}
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
      <Breadcrumb items={[{ label: "Appointments" }]} />

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-dreams-textPrimary">Appointments</h1>
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

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="h-10 px-4 rounded-lg border border-dreams-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
        >
          <option value="all">All Status</option>
          <option value="scheduled">Scheduled</option>
          <option value="arrived">Arrived</option>
          <option value="in-progress">In Progress</option>
          <option value="completed">Completed</option>
          <option value="cancelled">Cancelled</option>
          <option value="no-show">No Show</option>
        </select>
      </div>

      {/* Data Table */}
      <DataTable
        columns={columns}
        data={appointments}
        pageSize={10}
        searchColumn="patient_name"
        searchPlaceholder="Search appointments..."
      />
    </div>
  );
}
