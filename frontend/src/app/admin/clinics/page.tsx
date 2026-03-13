"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Search, Building2, Users, MapPin } from "lucide-react";
import { getAdminClinics, type AdminClinicListItem } from "@/lib/api/clinics";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { Badge } from "@/components/ui/badge";

export default function AdminClinicsPage() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState("");
  const [activeFilter, setActiveFilter] = useState("all");
  const [page, setPage] = useState(1);
  const limit = 20;

  const { data, isLoading } = useQuery({
    queryKey: ["admin-clinics", searchQuery, activeFilter, page],
    queryFn: () =>
      getAdminClinics({
        search: searchQuery || undefined,
        is_active:
          activeFilter === "all" ? undefined : activeFilter === "true",
        page,
        limit,
      }),
  });

  const clinics: AdminClinicListItem[] = data?.data ?? [];
  const totalPages = data?.totalPages ?? 1;

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-200 border-t-dreams-blue" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Breadcrumb
        items={[
          { label: "Dashboard", href: "/admin/dashboard" },
          { label: "Clinics" },
        ]}
      />

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-dreams-textPrimary">Clinics</h1>
          <p className="text-sm text-dreams-textSecondary mt-1">
            Manage all registered clinics
          </p>
        </div>
        <span className="text-sm text-dreams-textSecondary">
          {data?.total ?? 0} total
        </span>
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-dreams-textSecondary" />
          <input
            type="text"
            placeholder="Search clinics..."
            value={searchQuery}
            onChange={(e) => { setSearchQuery(e.target.value); setPage(1); }}
            className="w-full rounded-lg border border-dreams-border bg-white py-2 pl-10 pr-4 text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
          />
        </div>
        <select
          value={activeFilter}
          onChange={(e) => { setActiveFilter(e.target.value); setPage(1); }}
          className="rounded-lg border border-dreams-border bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
        >
          <option value="all">All Status</option>
          <option value="true">Active</option>
          <option value="false">Inactive</option>
        </select>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-dreams-border bg-white overflow-hidden shadow-card">
        <table className="w-full text-sm">
          <thead className="border-b border-dreams-border bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-dreams-textSecondary">Clinic</th>
              <th className="px-4 py-3 text-left font-medium text-dreams-textSecondary">Location</th>
              <th className="px-4 py-3 text-left font-medium text-dreams-textSecondary">Members</th>
              <th className="px-4 py-3 text-left font-medium text-dreams-textSecondary">Sharing Mode</th>
              <th className="px-4 py-3 text-left font-medium text-dreams-textSecondary">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-dreams-border">
            {clinics.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-10 text-center text-dreams-textSecondary">
                  No clinics found
                </td>
              </tr>
            ) : (
              clinics.map((clinic) => (
                <tr
                  key={clinic.id}
                  className="cursor-pointer hover:bg-gray-50 transition-colors"
                  onClick={() => router.push(`/admin/clinics/${clinic.id}`)}
                >
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-50">
                        <Building2 className="h-4 w-4 text-dreams-blue" />
                      </div>
                      <span className="font-medium text-dreams-textPrimary">{clinic.name}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-dreams-textSecondary">
                    <div className="flex items-center gap-1">
                      <MapPin className="h-3.5 w-3.5" />
                      {[clinic.city, clinic.state].filter(Boolean).join(", ") || "—"}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1 text-dreams-textSecondary">
                      <Users className="h-3.5 w-3.5" />
                      {clinic.member_count}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-dreams-textSecondary">
                      {clinic.record_sharing_mode === "per_clinic" ? "Per Clinic" : "Per Doctor"}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant={clinic.is_active ? "completed" : "overdue"}>
                      {clinic.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-dreams-textSecondary">
            Page {page} of {totalPages}
          </p>
          <div className="flex gap-2">
            <button
              disabled={page === 1}
              onClick={() => setPage((p) => p - 1)}
              className="rounded-lg border border-dreams-border px-3 py-1.5 text-sm disabled:opacity-40 hover:bg-gray-50"
            >
              Previous
            </button>
            <button
              disabled={page === totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="rounded-lg border border-dreams-border px-3 py-1.5 text-sm disabled:opacity-40 hover:bg-gray-50"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
