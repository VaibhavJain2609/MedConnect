"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { ColumnDef } from "@tanstack/react-table";
import { Plus, Search } from "lucide-react";
import { getLabResults, LabResult } from "@/lib/api/lab-results";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { DataTable, DataTableColumnHeader } from "@/components/ui/data-table";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";

export default function AdminLabResultsPage() {
  const t = useTranslations("adminLabResults");
  const tStatus = useTranslations("statusBadge");
  const tCommon = useTranslations("common");
  const tPagination = useTranslations("pagination");
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [page, setPage] = useState(1);
  const [limit] = useState(10);

  // Fetch lab results from backend
  const { data, isLoading, error } = useQuery({
    queryKey: ["admin-lab-results", searchQuery, statusFilter, page, limit],
    queryFn: () =>
      getLabResults({
        search: searchQuery || undefined,
        status: statusFilter !== "all" ? statusFilter : undefined,
        page,
        limit,
      }),
  });

  const labResults = data?.results;
  const totalPages = data?.totalPages || 1;

  // Table columns definition
  const columns: ColumnDef<LabResult>[] = [
    {
      accessorKey: "test_id",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title={t("table.testId")} />
      ),
      cell: ({ row }) => (
        <span className="font-medium text-dreams-blue">
          {row.getValue("test_id")}
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
            src={row.original.patient_photo}
            fallback={row.getValue("patient_name")}
            size="sm"
          />
          <span className="font-medium">{row.getValue("patient_name")}</span>
        </div>
      ),
    },
    {
      accessorKey: "gender",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title={t("table.gender")} />
      ),
    },
    {
      accessorKey: "appointment_date",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title={t("table.appointmentDate")} />
      ),
      cell: ({ row }) => (
        <span className="text-sm">
          {new Date(row.getValue("appointment_date")).toLocaleDateString(
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
      accessorKey: "doctor_name",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title={t("table.referredBy")} />
      ),
      cell: ({ row }) => (
        <div className="flex items-center gap-3">
          <Avatar
            src={row.original.doctor_photo}
            fallback={row.getValue("doctor_name")}
            size="sm"
          />
          <span className="font-medium text-sm">
            {row.getValue("doctor_name")}
          </span>
        </div>
      ),
    },
    {
      accessorKey: "test_name",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title={t("table.testName")} />
      ),
    },
    {
      accessorKey: "status",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title={t("table.status")} />
      ),
      cell: ({ row }) => {
        const status = row.getValue("status") as string;
        const i18nKey = status.replace(/[_-]+(.)/g, (_, c) => c.toUpperCase());

        return (
          <Badge variant={status as any}>
            {tStatus.has(i18nKey as never) ? tStatus(i18nKey as never) : status}
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
          <h1 className="text-3xl font-bold text-dreams-textPrimary">
            {t("title")}
          </h1>
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
          <span>{t("newTest")}</span>
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

        {/* Status Filter */}
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
          className="h-10 px-4 rounded-lg border border-dreams-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
        >
          <option value="all">{t("allStatus")}</option>
          <option value="pending">{tStatus("pending")}</option>
          <option value="in_progress">{tStatus("inProgress")}</option>
          <option value="received">{tStatus("received")}</option>
          <option value="completed">{tStatus("completed")}</option>
        </select>
      </div>

      {/* Data Table — server-paginated; internal pager hidden */}
      {labResults && (
        <DataTable
          columns={columns}
          data={labResults}
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
