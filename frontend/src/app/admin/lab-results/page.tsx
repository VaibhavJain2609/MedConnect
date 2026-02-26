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

interface LabResult {
  id: string;
  patientName: string;
  patientPhoto: string | null;
  gender: string;
  appointmentDate: string;
  referredBy: string;
  referredByPhoto: string | null;
  testName: string;
  status: "completed" | "inProgress" | "pending";
}

export default function AdminLabResultsPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  // Fetch lab results
  const { data: labResults, isLoading } = useQuery({
    queryKey: ["admin-lab-results"],
    queryFn: async () => {
      // TODO: Replace with actual API call to /api/v1/admin/lab-results
      // Mock data for now
      return [
        {
          id: "LR-001",
          patientName: "John Doe",
          patientPhoto: null,
          gender: "Male",
          appointmentDate: "2026-02-26",
          referredBy: "Dr. Sarah Smith",
          referredByPhoto: null,
          testName: "Complete Blood Count (CBC)",
          status: "completed",
        },
        {
          id: "LR-002",
          patientName: "Jane Smith",
          patientPhoto: null,
          gender: "Female",
          appointmentDate: "2026-02-27",
          referredBy: "Dr. Michael Johnson",
          referredByPhoto: null,
          testName: "Lipid Profile",
          status: "inProgress",
        },
        {
          id: "LR-003",
          patientName: "Mike Wilson",
          patientPhoto: null,
          gender: "Male",
          appointmentDate: "2026-02-28",
          referredBy: "Dr. Emily Davis",
          referredByPhoto: null,
          testName: "X-Ray (Chest)",
          status: "pending",
        },
        {
          id: "LR-004",
          patientName: "Sarah Johnson",
          patientPhoto: null,
          gender: "Female",
          appointmentDate: "2026-02-25",
          referredBy: "Dr. James Wilson",
          referredByPhoto: null,
          testName: "Urinalysis",
          status: "completed",
        },
        {
          id: "LR-005",
          patientName: "Robert Brown",
          patientPhoto: null,
          gender: "Male",
          appointmentDate: "2026-02-29",
          referredBy: "Dr. Linda Brown",
          referredByPhoto: null,
          testName: "Thyroid Function Test",
          status: "inProgress",
        },
        {
          id: "LR-006",
          patientName: "Emily Davis",
          patientPhoto: null,
          gender: "Female",
          appointmentDate: "2026-02-24",
          referredBy: "Dr. Robert Miller",
          referredByPhoto: null,
          testName: "ECG",
          status: "completed",
        },
        {
          id: "LR-007",
          patientName: "David Martinez",
          patientPhoto: null,
          gender: "Male",
          appointmentDate: "2026-03-01",
          referredBy: "Dr. Jennifer Garcia",
          referredByPhoto: null,
          testName: "Blood Sugar (Fasting)",
          status: "pending",
        },
        {
          id: "LR-008",
          patientName: "Lisa Anderson",
          patientPhoto: null,
          gender: "Female",
          appointmentDate: "2026-02-23",
          referredBy: "Dr. David Martinez",
          referredByPhoto: null,
          testName: "MRI Scan",
          status: "completed",
        },
      ] as LabResult[];
    },
  });

  // Filter lab results based on search and status
  const filteredLabResults = labResults?.filter((result) => {
    const matchesSearch =
      result.patientName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      result.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      result.testName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      result.referredBy.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus =
      statusFilter === "all" || result.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  // Table columns definition
  const columns: ColumnDef<LabResult>[] = [
    {
      accessorKey: "id",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Test ID" />
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
      accessorKey: "gender",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Gender" />
      ),
    },
    {
      accessorKey: "appointmentDate",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Appointment Date" />
      ),
      cell: ({ row }) => (
        <span className="text-sm">
          {new Date(row.getValue("appointmentDate")).toLocaleDateString(
            "en-US",
            {
              month: "short",
              day: "numeric",
              year: "numeric",
            }
          )}
        </span>
      ),
    },
    {
      accessorKey: "referredBy",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Referred By" />
      ),
      cell: ({ row }) => (
        <div className="flex items-center gap-3">
          <Avatar
            src={row.original.referredByPhoto}
            fallback={row.getValue("referredBy")}
            size="sm"
          />
          <span className="font-medium text-sm">
            {row.getValue("referredBy")}
          </span>
        </div>
      ),
    },
    {
      accessorKey: "testName",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Test Name" />
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
          completed: "Received",
          inProgress: "In Progress",
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
      <Breadcrumb items={[{ label: "Lab Results" }]} />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-dreams-textPrimary">
            Lab Results
          </h1>
          <p className="text-dreams-textSecondary mt-1">
            Manage laboratory test results and reports
          </p>
        </div>

        <button className="flex items-center gap-2 px-4 py-2 bg-dreams-blue text-white rounded-lg hover:opacity-90 transition-opacity">
          <Plus className="h-5 w-5" />
          <span>New Test</span>
        </button>
      </div>

      {/* Search and Filters */}
      <div className="flex items-center gap-4">
        {/* Search */}
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search by patient, test, or ID..."
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
          <option value="completed">Received</option>
        </select>
      </div>

      {/* Data Table */}
      {filteredLabResults && (
        <DataTable
          columns={columns}
          data={filteredLabResults}
          pageSize={10}
          searchColumn="patientName"
          searchPlaceholder="Search lab results..."
        />
      )}
    </div>
  );
}
