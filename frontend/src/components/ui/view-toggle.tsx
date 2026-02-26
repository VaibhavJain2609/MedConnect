"use client";

import * as React from "react";
import { Grid, List, LayoutGrid } from "lucide-react";
import { cn } from "@/lib/utils";

export type ViewMode = "grid" | "table" | "list";

export interface ViewToggleProps {
  value: ViewMode;
  onChange: (value: ViewMode) => void;
  modes?: ViewMode[];
  className?: string;
}

/**
 * ViewToggle Component
 *
 * Toggle between different view modes (grid, table, list)
 *
 * Features:
 * - Grid view (cards)
 * - Table view (data table)
 * - List view (compact list)
 * - State persisted in localStorage
 *
 * @example
 * const [viewMode, setViewMode] = useState<ViewMode>("grid");
 * <ViewToggle value={viewMode} onChange={setViewMode} />
 */
export const ViewToggle: React.FC<ViewToggleProps> = ({
  value,
  onChange,
  modes = ["grid", "table"],
  className,
}) => {
  const icons = {
    grid: LayoutGrid,
    table: Grid,
    list: List,
  };

  const labels = {
    grid: "Grid View",
    table: "Table View",
    list: "List View",
  };

  return (
    <div
      className={cn(
        "inline-flex items-center rounded-lg border border-dreams-border bg-white p-1",
        className
      )}
    >
      {modes.map((mode) => {
        const Icon = icons[mode];
        return (
          <button
            key={mode}
            onClick={() => onChange(mode)}
            className={cn(
              "flex items-center justify-center h-8 w-8 rounded-md transition-colors",
              value === mode
                ? "bg-dreams-blue text-white"
                : "text-dreams-textSecondary hover:text-dreams-textPrimary hover:bg-dreams-lightBg"
            )}
            title={labels[mode]}
            aria-label={labels[mode]}
          >
            <Icon className="h-4 w-4" />
          </button>
        );
      })}
    </div>
  );
};

ViewToggle.displayName = "ViewToggle";

/**
 * useViewMode Hook
 *
 * Manages view mode state with localStorage persistence
 *
 * @example
 * const [viewMode, setViewMode] = useViewMode("patients-view", "grid");
 * <ViewToggle value={viewMode} onChange={setViewMode} />
 */
export function useViewMode(
  key: string,
  defaultMode: ViewMode = "grid"
): [ViewMode, (mode: ViewMode) => void] {
  const [viewMode, setViewMode] = React.useState<ViewMode>(defaultMode);

  // Load from localStorage on mount
  React.useEffect(() => {
    const stored = localStorage.getItem(key);
    if (stored && ["grid", "table", "list"].includes(stored)) {
      setViewMode(stored as ViewMode);
    }
  }, [key]);

  // Save to localStorage on change
  const handleChange = React.useCallback(
    (mode: ViewMode) => {
      setViewMode(mode);
      localStorage.setItem(key, mode);
    },
    [key]
  );

  return [viewMode, handleChange];
}
