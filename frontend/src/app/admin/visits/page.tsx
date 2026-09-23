"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ColumnDef } from "@tanstack/react-table";
import { Plus, Search, Trash2 } from "lucide-react";
import { deleteVisit, getVisits, Visit } from "@/lib/api/visits";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { DataTable, DataTableColumnHeader } from "@/components/ui/data-table";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";

function formatDateTime(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function AdminVisitsPage() {
  const t = useTranslations("adminVisits");
  const tCommon = useTranslations("common");
  const tPagination = useTranslations("pagination");
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState("");
  const [dateFilter, setDateFilter] = useState("");
  const [page, setPage] = useState(1);
  const [limit] = useState(10);

  // Fetch visits (encounters) from backend
  const { data, isLoading, error } = useQuery({
    queryKey: ["admin-visits", searchQuery, dateFilter, page, limit],
    queryFn: () =>
      getVisits({
        search: searchQuery || undefined,
        date: dateFilter || undefined,
        page,
        limit,
      }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteVisit(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-visits"] });
    },
  });

  const visits = data?.visits;
  const totalPages = data?.totalPages || 1;

  // Table columns definition
  const columns: ColumnDef<Visit>[] = [
    {
      accessorKey: "id",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title={t("table.visitId")} />
      ),
      cell: ({ row }) => (
        <span className="font-medium text-dreams-blue font-mono text-xs">
          {row.original.id.slice(0, 8)}
        </span>
      ),
    },
    {
      accessorKey: "patient_name",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title={t("table.patientName")} />
      ),
      cell: ({ row }) => (
        <div className="flex items-center gap-3">
          <Avatar
            fallback={row.original.patient_name ?? "?"}
            size="sm"
          />
          <span className="font-medium">
            {row.original.patient_name ?? t("unknown")}
          </span>
        </div>
      ),
    },
    {
      accessorKey: "doctor_name",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title={t("table.doctorName")} />
      ),
      cell: ({ row }) => (
        <div className="flex items-center gap-3">
          <Avatar
            fallback={row.original.doctor_name ?? "?"}
            size="sm"
          />
          <span className="font-medium">
            {row.original.doctor_name ?? t("unknown")}
          </span>
        </div>
      ),
    },
    {
      accessorKey: "clinic_name",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title={t("table.clinic")} />
      ),
      cell: ({ row }) => (
        <span className="text-sm">
          {row.original.clinic_name ?? "—"}
        </span>
      ),
    },
    {
      accessorKey: "created_at",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title={t("table.visitDate")} />
      ),
      cell: ({ row }) => (
        <span className="text-sm">{formatDateTime(row.original.created_at)}</span>
      ),
    },
    {
      accessorKey: "assessment",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title={t("table.assessment")} />
      ),
      cell: ({ row }) => {
        const assessment = row.original.assessment;
        return (
          <span className="text-sm text-dreams-textSecondary line-clamp-2 max-w-xs">
            {assessment ?? "—"}
          </span>
        );
      },
    },
    {
      id: "actions",
      header: "",
      cell: ({ row }) => (
        <button
          onClick={() => {
            if (
              window.confirm(t("deleteConfirm"))
            ) {
              deleteMutation.mutate(row.original.id);
            }
          }}
          disabled={deleteMutation.isPending}
          className="p-2 text-red-500 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-40"
          title={t("deleteTitle")}
        >
          <Trash2 className="h-4 w-4" />
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
        <p className="text-red-600 font-medium">{t("loadError")}</p>
        <p className="text-dreams-textSecondary text-sm">
          {error instanceof Error ? error.message : tCommon("errorGeneric")}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <Breadcrumb items={[{ label: t("breadcrumb") }]} />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold text-dreams-textPrimary">
              {t("title")}
            </h1>
            <Badge variant="pending" className="text-base px-3 py-1">
              {data?.total || 0}
            </Badge>
          </div>
          <p className="text-dreams-textSecondary mt-1">
            {t("subtitle")}
          </p>
        </div>

        <button
          disabled
          title={t("comingSoon")}
          className="flex items-center gap-2 px-4 py-2 bg-dreams-blue text-white rounded-lg opacity-50 cursor-not-allowed"
        >
          <Plus className="h-5 w-5" />
          <span>{t("newVisit")}</span>
        </button>
      </div>

      {/* Search and Filters */}
      <div className="flex items-center gap-4">
        {/* Search */}
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="text"
            placeholder={t("searchPlaceholder")}
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setPage(1);
            }}
            className="w-full h-10 pl-10 pr-4 rounded-lg border border-dreams-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
          />
        </div>

        {/* Date Filter */}
        <input
          type="date"
          value={dateFilter}
          onChange={(e) => {
            setDateFilter(e.target.value);
            setPage(1);
          }}
          className="h-10 px-4 rounded-lg border border-dreams-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
        />
      </div>

      {/* Data Table — server-paginated; internal pager hidden */}
      {visits && (
        <DataTable
          columns={columns}
          data={visits}
          pageSize={limit}
          hidePagination
        />
      )}

      {/* Server-side pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-dreams-textSecondary">
            {t("pageInfo", { page, totalPages, count: data?.total ?? 0 })}
          </p>
          <div className="flex gap-2">
            <button
              disabled={page === 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="px-4 py-2 text-sm rounded-lg border border-dreams-border bg-white disabled:opacity-40 hover:bg-dreams-lightBg transition-colors"
            >
              {tPagination("previous")}
            </button>
            <button
              disabled={page >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              className="px-4 py-2 text-sm rounded-lg border border-dreams-border bg-white disabled:opacity-40 hover:bg-dreams-lightBg transition-colors"
            >
              {tPagination("next")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
