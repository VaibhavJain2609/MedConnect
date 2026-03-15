"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ColumnDef } from "@tanstack/react-table";
import { Plus, Search } from "lucide-react";
import { getPatients, Patient } from "@/lib/api/patients";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { ViewToggle, useViewMode, ViewMode } from "@/components/ui/view-toggle";
import { ProfileCard } from "@/components/cards/profile-card";
import { DataTable, DataTableColumnHeader } from "@/components/ui/data-table";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { PatientDetailDrawer } from "@/components/admin/patient-detail-drawer";
import { useClinicStore } from "@/stores/clinic-store";
import api from "@/lib/api";

// ---------------------------------------------------------------------------
// CreatePatientModal
// ---------------------------------------------------------------------------

interface CreatePatientModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  clinicId: string | null;
}

function CreatePatientModal({
  isOpen,
  onClose,
  onSuccess,
  clinicId,
}: CreatePatientModalProps) {
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const response = await api.post("/api/v1/admin/users", {
        full_name: fullName,
        phone: phone || undefined,
        email: email || undefined,
        role: "patient",
      });
      const newUser = response.data;

      if (clinicId && newUser.id) {
        await api.post(`/api/v1/admin/clinics/${clinicId}/patients`, {
          patient_id: newUser.id,
        });
      }

      // Reset form
      setFullName("");
      setPhone("");
      setEmail("");
      onSuccess();
    } catch (err: unknown) {
      const message =
        err instanceof Error
          ? err.message
          : "Failed to create patient. Please try again.";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/40 z-50"
        onClick={onClose}
        aria-hidden="true"
      />
      {/* Modal */}
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div
          className="bg-white rounded-xl shadow-2xl w-full max-w-md p-6 space-y-5"
          onClick={(e) => e.stopPropagation()}
        >
          <h2 className="text-lg font-semibold text-dreams-textPrimary">
            New Patient
          </h2>

          {error && (
            <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-2">
              {error}
            </p>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-dreams-textPrimary mb-1">
                Full Name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Enter full name"
                className="w-full h-10 px-3 rounded-lg border border-dreams-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-dreams-textPrimary mb-1">
                Phone
              </label>
              <input
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="Enter phone number"
                className="w-full h-10 px-3 rounded-lg border border-dreams-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-dreams-textPrimary mb-1">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Enter email address"
                className="w-full h-10 px-3 rounded-lg border border-dreams-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
              />
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={onClose}
                disabled={loading}
                className="px-4 py-2 text-sm font-medium text-dreams-textSecondary border border-dreams-border rounded-lg hover:bg-dreams-lightBg transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading || !fullName.trim()}
                className="flex items-center gap-2 px-4 py-2 bg-dreams-blue text-white text-sm font-medium rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {loading ? (
                  <>
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                    Creating...
                  </>
                ) : (
                  "Create Patient"
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// AdminPatientsPage
// ---------------------------------------------------------------------------

export default function AdminPatientsPage() {
  const [viewMode, setViewMode] = useViewMode("admin-patients-view", "grid");
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [page, setPage] = useState(1);
  const [selectedPatientId, setSelectedPatientId] = useState<string | null>(null);
  const [limit] = useState(viewMode === "table" ? 10 : 12);
  const [showModal, setShowModal] = useState(false);

  const { activeClinicId } = useClinicStore();
  const queryClient = useQueryClient();

  // Fetch patients from backend
  const { data, isLoading, error } = useQuery({
    queryKey: ["admin-patients", searchQuery, statusFilter, page, limit, activeClinicId],
    queryFn: () =>
      getPatients({
        search: searchQuery || undefined,
        status: statusFilter !== "all" ? statusFilter : undefined,
        page,
        limit,
        clinic_id: activeClinicId || undefined,
      }),
  });

  const patients = data?.patients;
  const totalPages = data?.totalPages || 1;

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
    {
      id: "actions",
      header: () => null,
      cell: ({ row }) => (
        <button
          onClick={() => setSelectedPatientId(row.original.id)}
          className="px-3 py-1.5 text-xs font-medium text-dreams-blue border border-dreams-blue rounded-md hover:bg-blue-50 transition-colors"
        >
          View Profile
        </button>
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

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12 space-y-4">
        <p className="text-red-600 font-medium">Failed to load patients</p>
        <p className="text-dreams-textSecondary text-sm">
          {error instanceof Error ? error.message : "An error occurred"}
        </p>
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
          <button
            onClick={() => setShowModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-dreams-blue text-white rounded-lg hover:opacity-90 transition-opacity"
          >
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
          {patients && patients.length > 0 ? (
            patients.map((patient) => (
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
                onCtaClick={() => setSelectedPatientId(patient.id)}
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
      {viewMode === "table" && patients && (
        <DataTable
          columns={columns}
          data={patients}
          pageSize={limit}
          searchColumn="name"
          searchPlaceholder="Search patients..."
        />
      )}

      <CreatePatientModal
        isOpen={showModal}
        onClose={() => setShowModal(false)}
        onSuccess={() => {
          setShowModal(false);
          queryClient.invalidateQueries({ queryKey: ["admin-patients"] });
        }}
        clinicId={activeClinicId || null}
      />

      <PatientDetailDrawer
        patientId={selectedPatientId}
        onClose={() => setSelectedPatientId(null)}
        clinicId={activeClinicId || undefined}
        consentStatus={patients?.find((p) => p.id === selectedPatientId)?.consent_status}
      />
    </div>
  );
}
