"use client";

import * as React from "react";
import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  SortingState,
  useReactTable,
  getPaginationRowModel,
  ColumnFiltersState,
  getFilteredRowModel,
} from "@tanstack/react-table";
import { ArrowUpDown, ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

export interface DataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[];
  data: TData[];
  pageSize?: number;
  searchColumn?: string;
  searchPlaceholder?: string;
  className?: string;
}

/**
 * Rich DataTable Component
 *
 * Advanced data table with sorting, filtering, and pagination
 *
 * Features:
 * - Sortable columns with indicator icons
 * - Built-in pagination
 * - Optional global search
 * - Avatar and badge support in columns
 * - Responsive design
 *
 * @example
 * const columns: ColumnDef<Patient>[] = [
 *   {
 *     accessorKey: "name",
 *     header: ({ column }) => (
 *       <DataTableColumnHeader column={column} title="Name" />
 *     ),
 *     cell: ({ row }) => (
 *       <div className="flex items-center gap-2">
 *         <Avatar src={row.original.photo} fallback={row.original.name} size="sm" />
 *         <span>{row.getValue("name")}</span>
 *       </div>
 *     ),
 *   },
 *   ...
 * ];
 *
 * <DataTable columns={columns} data={patients} pageSize={10} />
 */
export function DataTable<TData, TValue>({
  columns,
  data,
  pageSize = 10,
  searchColumn,
  searchPlaceholder = "Search...",
  className,
}: DataTableProps<TData, TValue>) {
  const [sorting, setSorting] = React.useState<SortingState>([]);
  const [columnFilters, setColumnFilters] = React.useState<ColumnFiltersState>(
    []
  );

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    onSortingChange: setSorting,
    getSortedRowModel: getSortedRowModel(),
    onColumnFiltersChange: setColumnFilters,
    getFilteredRowModel: getFilteredRowModel(),
    state: {
      sorting,
      columnFilters,
    },
    initialState: {
      pagination: {
        pageSize,
      },
    },
  });

  return (
    <div className={cn("space-y-4", className)}>
      {/* Search Input */}
      {searchColumn && (
        <div className="flex items-center">
          <input
            type="text"
            placeholder={searchPlaceholder}
            value={
              (table.getColumn(searchColumn)?.getFilterValue() as string) ?? ""
            }
            onChange={(event) =>
              table.getColumn(searchColumn)?.setFilterValue(event.target.value)
            }
            className="h-10 px-3 rounded-md border border-dreams-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue max-w-sm"
          />
        </div>
      )}

      {/* Table */}
      <div className="rounded-lg border border-dreams-border bg-white overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-dreams-lightBg border-b border-dreams-border">
              {table.getHeaderGroups().map((headerGroup) => (
                <tr key={headerGroup.id}>
                  {headerGroup.headers.map((header) => (
                    <th
                      key={header.id}
                      className="px-4 py-3 text-left text-xs font-semibold text-dreams-textPrimary uppercase tracking-wider"
                    >
                      {header.isPlaceholder
                        ? null
                        : flexRender(
                            header.column.columnDef.header,
                            header.getContext()
                          )}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody className="divide-y divide-dreams-border">
              {table.getRowModel().rows?.length ? (
                table.getRowModel().rows.map((row) => (
                  <tr
                    key={row.id}
                    className="hover:bg-dreams-lightBg/50 transition-colors"
                  >
                    {row.getVisibleCells().map((cell) => (
                      <td key={cell.id} className="px-4 py-4 text-sm">
                        {flexRender(
                          cell.column.columnDef.cell,
                          cell.getContext()
                        )}
                      </td>
                    ))}
                  </tr>
                ))
              ) : (
                <tr>
                  <td
                    colSpan={columns.length}
                    className="px-4 py-8 text-center text-dreams-textSecondary"
                  >
                    No results found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between px-2">
        <div className="text-sm text-dreams-textSecondary">
          Showing{" "}
          <span className="font-medium">
            {table.getState().pagination.pageIndex *
              table.getState().pagination.pageSize +
              1}
          </span>{" "}
          to{" "}
          <span className="font-medium">
            {Math.min(
              (table.getState().pagination.pageIndex + 1) *
                table.getState().pagination.pageSize,
              table.getFilteredRowModel().rows.length
            )}
          </span>{" "}
          of{" "}
          <span className="font-medium">
            {table.getFilteredRowModel().rows.length}
          </span>{" "}
          results
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
            className="p-2 rounded-md border border-dreams-border bg-white hover:bg-dreams-lightBg disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="text-sm text-dreams-textSecondary">
            Page{" "}
            <span className="font-medium">
              {table.getState().pagination.pageIndex + 1}
            </span>{" "}
            of <span className="font-medium">{table.getPageCount()}</span>
          </span>
          <button
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
            className="p-2 rounded-md border border-dreams-border bg-white hover:bg-dreams-lightBg disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * DataTableColumnHeader Component
 *
 * Sortable column header with indicator icon
 *
 * @example
 * {
 *   accessorKey: "name",
 *   header: ({ column }) => (
 *     <DataTableColumnHeader column={column} title="Name" />
 *   ),
 * }
 */
interface DataTableColumnHeaderProps<TData, TValue>
  extends React.HTMLAttributes<HTMLDivElement> {
  column: any;
  title: string;
}

export function DataTableColumnHeader<TData, TValue>({
  column,
  title,
  className,
}: DataTableColumnHeaderProps<TData, TValue>) {
  if (!column.getCanSort()) {
    return <div className={cn(className)}>{title}</div>;
  }

  return (
    <div
      className={cn(
        "flex items-center gap-2 cursor-pointer select-none hover:text-dreams-blue transition-colors",
        className
      )}
      onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
    >
      {title}
      <ArrowUpDown className="h-4 w-4" />
    </div>
  );
}
