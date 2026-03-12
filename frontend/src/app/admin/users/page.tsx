"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { getAdminUsers, AdminUserListItem } from "@/lib/api/admin-users";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";

const roleBadgeVariant: Record<string, string> = {
  admin: "overdue",
  doctor: "inProgress",
  patient: "completed",
};

const roleLabel: Record<string, string> = {
  admin: "Admin",
  doctor: "Doctor",
  patient: "Patient",
};

export default function AdminUsersPage() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState("all");
  const [activeFilter, setActiveFilter] = useState("all");
  const [page, setPage] = useState(1);
  const limit = 20;

  const { data, isLoading, error } = useQuery({
    queryKey: ["admin-users", searchQuery, roleFilter, activeFilter, page],
    queryFn: () =>
      getAdminUsers({
        search: searchQuery || undefined,
        role: roleFilter !== "all" ? roleFilter : undefined,
        is_active:
          activeFilter === "all"
            ? undefined
            : activeFilter === "true"
            ? true
            : false,
        page,
        limit,
      }),
  });

  const users = data?.data ?? [];
  const totalPages = data?.totalPages ?? 1;

  const handleRowClick = (id: string) => {
    router.push(`/admin/users/${id}`);
  };

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
        <p className="text-red-600 font-medium">Failed to load users</p>
        <p className="text-dreams-textSecondary text-sm">
          {error instanceof Error ? error.message : "An error occurred"}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Breadcrumb items={[{ label: "Users" }]} />

      <div>
        <h1 className="text-3xl font-bold text-dreams-textPrimary">Users</h1>
        <p className="text-dreams-textSecondary mt-1">
          Manage platform users and their access
        </p>
      </div>

      {/* Search and Filters */}
      <div className="flex items-center gap-4 flex-wrap">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search by name, email or phone..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setPage(1);
            }}
            className="w-full h-10 pl-10 pr-4 rounded-lg border border-dreams-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
          />
        </div>

        <select
          value={roleFilter}
          onChange={(e) => {
            setRoleFilter(e.target.value);
            setPage(1);
          }}
          className="h-10 px-4 rounded-lg border border-dreams-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
        >
          <option value="all">All Roles</option>
          <option value="patient">Patient</option>
          <option value="doctor">Doctor</option>
          <option value="admin">Admin</option>
        </select>

        <select
          value={activeFilter}
          onChange={(e) => {
            setActiveFilter(e.target.value);
            setPage(1);
          }}
          className="h-10 px-4 rounded-lg border border-dreams-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
        >
          <option value="all">All Status</option>
          <option value="true">Active</option>
          <option value="false">Inactive</option>
        </select>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-dreams-border overflow-hidden shadow-card">
        <table className="w-full text-sm">
          <thead className="bg-dreams-lightBg border-b border-dreams-border">
            <tr>
              <th className="px-6 py-3 text-left font-semibold text-dreams-textSecondary">
                Name
              </th>
              <th className="px-6 py-3 text-left font-semibold text-dreams-textSecondary">
                Email
              </th>
              <th className="px-6 py-3 text-left font-semibold text-dreams-textSecondary">
                Phone
              </th>
              <th className="px-6 py-3 text-left font-semibold text-dreams-textSecondary">
                Role
              </th>
              <th className="px-6 py-3 text-left font-semibold text-dreams-textSecondary">
                Status
              </th>
              <th className="px-6 py-3 text-left font-semibold text-dreams-textSecondary">
                Joined
              </th>
              <th className="px-6 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-dreams-border">
            {users.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-6 py-12 text-center text-dreams-textSecondary">
                  No users found
                </td>
              </tr>
            ) : (
              users.map((user: AdminUserListItem) => (
                <tr
                  key={user.id}
                  onClick={() => handleRowClick(user.id)}
                  className="hover:bg-dreams-lightBg cursor-pointer transition-colors"
                >
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <Avatar fallback={user.full_name} size="sm" />
                      <span className="font-medium text-dreams-textPrimary">
                        {user.full_name}
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-dreams-textSecondary">
                    {user.email ?? "—"}
                  </td>
                  <td className="px-6 py-4 text-dreams-textSecondary">
                    {user.phone ?? "—"}
                  </td>
                  <td className="px-6 py-4">
                    <Badge variant={roleBadgeVariant[user.role] as any}>
                      {roleLabel[user.role] ?? user.role}
                    </Badge>
                  </td>
                  <td className="px-6 py-4">
                    <Badge variant={user.is_active ? "completed" : "pending"}>
                      {user.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </td>
                  <td className="px-6 py-4 text-dreams-textSecondary">
                    {new Date(user.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleRowClick(user.id);
                      }}
                      className="text-dreams-blue text-sm font-medium hover:underline"
                    >
                      View
                    </button>
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
            Page {page} of {totalPages} · {data?.total} total
          </p>
          <div className="flex gap-2">
            <button
              disabled={page === 1}
              onClick={() => setPage((p) => p - 1)}
              className="px-4 py-2 text-sm rounded-lg border border-dreams-border bg-white disabled:opacity-40 hover:bg-dreams-lightBg transition-colors"
            >
              Previous
            </button>
            <button
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="px-4 py-2 text-sm rounded-lg border border-dreams-border bg-white disabled:opacity-40 hover:bg-dreams-lightBg transition-colors"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
