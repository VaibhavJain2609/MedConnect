"use client";

import * as React from "react";
import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  RowSelectionState,
  SortingState,
  useReactTable,
  getPaginationRowModel,
  ColumnFiltersState,
  getFilteredRowModel,
} from "@tanstack/react-table";
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  SearchX,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Checkbox } from "@/components/ui/checkbox";
import { EmptyState } from "@/components/ui/empty-state";

export interface DataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[];
  data: TData[];
  pageSize?: number;
  searchColumn?: string;
  searchPlaceholder?: string;
  className?: string;
  /** Hide the built-in client-side pager — use when the parent renders
   *  server-side pagination controls instead. */
  hidePagination?: boolean;
  /** Prepend a checkbox column and track selected rows. */
  enableRowSelection?: boolean;
  /** Called with the selected rows' original data whenever selection changes. */
  onSelectionChange?: (selectedRows: TData[]) => void;
  /**
   * Custom content for the empty state. Defaults to an EmptyState with a
   * "No results found" message.
   */
  emptyState?: React.ReactNode;
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
  hidePagination = false,
  enableRowSelection = false,
  onSelectionChange,
  emptyState,
}: DataTableProps<TData, TValue>) {
  const [sorting, setSorting] = React.useState<SortingState>([]);
  const [columnFilters, setColumnFilters] = React.useState<ColumnFiltersState>(
    []
  );
  const [rowSelection, setRowSelection] = React.useState<RowSelectionState>({});

  const allColumns = React.useMemo<ColumnDef<TData, TValue>[]>(() => {
    if (!enableRowSelection) return columns;
    const selectionColumn: ColumnDef<TData, TValue> = {
      id: "select",
      enableSorting: false,
      enableHiding: false,
      header: ({ table }) => (
        <Checkbox
          checked={
            table.getIsAllPageRowsSelected() ||
            (table.getIsSomePageRowsSelected() && "indeterminate")
          }
          onCheckedChange={(value) =>
            table.toggleAllPageRowsSelected(!!value)
          }
          aria-label="Select all rows"
        />
      ),
      cell: ({ row }) => (
        <Checkbox
          checked={row.getIsSelected()}
          onCheckedChange={(value) => row.toggleSelected(!!value)}
          aria-label="Select row"
        />
      ),
    };
    return [selectionColumn, ...columns];
  }, [columns, enableRowSelection]);

  const table = useReactTable({
    data,
    columns: allColumns,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    onSortingChange: setSorting,
    getSortedRowModel: getSortedRowModel(),
    onColumnFiltersChange: setColumnFilters,
    getFilteredRowModel: getFilteredRowModel(),
    enableRowSelection,
    onRowSelectionChange: setRowSelection,
    state: {
      sorting,
      columnFilters,
      rowSelection,
    },
    initialState: {
      pagination: {
        pageSize,
      },
    },
  });

  const selectedCount = Object.keys(rowSelection).length;
  const onSelectionChangeRef = React.useRef(onSelectionChange);
  onSelectionChangeRef.current = onSelectionChange;
  React.useEffect(() => {
    onSelectionChangeRef.current?.(
      table.getSelectedRowModel().rows.map((row) => row.original)
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCount]);

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
          <table className="w-full min-w-[640px]">
            <thead className="bg-dreams-lightBg border-b border-dreams-border">
              {table.getHeaderGroups().map((headerGroup) => (
                <tr key={headerGroup.id}>
                  {headerGroup.headers.map((header) => (
                    <th
                      key={header.id}
                      scope="col"
                      aria-sort={
                        header.column.getIsSorted() === "asc"
                          ? "ascending"
                          : header.column.getIsSorted() === "desc"
                            ? "descending"
                            : undefined
                      }
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
                    data-state={row.getIsSelected() ? "selected" : undefined}
                    className={cn(
                      "hover:bg-dreams-lightBg/50 transition-colors",
                      row.getIsSelected() && "bg-dreams-lightBg/60"
                    )}
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
                  <td colSpan={allColumns.length} className="px-4 py-8">
                    {emptyState ?? (
                      <EmptyState
                        icon={SearchX}
                        title="No results found"
                        description="Try adjusting your search or filters."
                        className="py-4"
                      />
                    )}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination */}
      {!hidePagination && (
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
      )}
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

  const sorted = column.getIsSorted();

  return (
    <button
      type="button"
      className={cn(
        "flex items-center gap-2 select-none hover:text-dreams-blue transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-dreams-blue rounded-sm",
        className
      )}
      onClick={() => column.toggleSorting(sorted === "asc")}
      aria-label={`Sort by ${title}`}
    >
      {title}
      {sorted === "asc" ? (
        <ArrowUp className="h-4 w-4" aria-hidden="true" />
      ) : sorted === "desc" ? (
        <ArrowDown className="h-4 w-4" aria-hidden="true" />
      ) : (
        <ArrowUpDown className="h-4 w-4" aria-hidden="true" />
      )}
    </button>
  );
}
