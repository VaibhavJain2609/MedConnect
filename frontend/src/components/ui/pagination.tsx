import { ChevronLeft, ChevronRight, Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";

export interface PaginationProps {
  /** Current 1-based page number */
  page: number;
  totalPages: number;
  /** Optional total item count, shown as "· N total" */
  total?: number;
  onPageChange: (page: number) => void;
  className?: string;
}

/**
 * Page-number pagination control for lists backed by `{ data, total }`
 * endpoints (or fully-fetched client-side lists). Renders nothing when
 * there is only a single page.
 */
export function Pagination({
  page,
  totalPages,
  total,
  onPageChange,
  className,
}: PaginationProps) {
  if (totalPages <= 1) return null;

  return (
    <div className={cn("flex items-center justify-between", className)}>
      <p className="text-sm text-dreams-textSecondary">
        Page {page} of {totalPages}
        {typeof total === "number" ? ` · ${total} total` : ""}
      </p>
      <div className="flex gap-2">
        <button
          type="button"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
          aria-label="Previous page"
          className="flex items-center gap-1 px-4 py-2 text-sm rounded-lg border border-dreams-border bg-white text-dreams-textPrimary disabled:opacity-40 hover:bg-dreams-lightBg transition-colors"
        >
          <ChevronLeft className="h-4 w-4" />
          Previous
        </button>
        <button
          type="button"
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
          aria-label="Next page"
          className="flex items-center gap-1 px-4 py-2 text-sm rounded-lg border border-dreams-border bg-white text-dreams-textPrimary disabled:opacity-40 hover:bg-dreams-lightBg transition-colors"
        >
          Next
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

export interface LoadMoreButtonProps {
  /** Whether the endpoint reported more pages (pagination.has_more) */
  hasMore: boolean;
  /** Whether a fetch is currently in flight */
  loading?: boolean;
  onClick: () => void;
  /** Optional count of items loaded so far, shown above the button */
  loadedCount?: number;
  className?: string;
}

/**
 * "Load more" control for cursor-paginated endpoints
 * (`{ data, pagination: { next_cursor, has_more } }`) where the total is
 * unknown so page numbers cannot be computed. Renders nothing when the
 * endpoint reports no further pages.
 */
export function LoadMoreButton({
  hasMore,
  loading,
  onClick,
  loadedCount,
  className,
}: LoadMoreButtonProps) {
  if (!hasMore) return null;

  return (
    <div className={cn("space-y-1 text-center", className)}>
      {typeof loadedCount === "number" && (
        <p className="text-xs text-dreams-textSecondary">
          {loadedCount} loaded
        </p>
      )}
      <button
        type="button"
        onClick={onClick}
        disabled={loading}
        className="inline-flex items-center gap-2 text-sm text-dreams-blue hover:underline disabled:opacity-50"
      >
        {loading && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
        {loading ? "Loading…" : "Load more"}
      </button>
    </div>
  );
}
