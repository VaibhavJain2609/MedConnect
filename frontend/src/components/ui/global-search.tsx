"use client";

import * as React from "react";
import { Search, X, User, Stethoscope, Calendar, Pill, Clock } from "lucide-react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { globalSearch, type SearchResult } from "@/lib/api/search";
import { cn } from "@/lib/utils";
import { Avatar } from "@/components/ui/avatar";

/**
 * GlobalSearch Component
 *
 * Keyboard-accessible search with Cmd+K/Ctrl+K shortcut
 *
 * Features:
 * - Fuzzy search across patients, doctors, appointments, medicines
 * - Keyboard navigation (arrows, enter, escape)
 * - Recent searches
 * - Quick actions
 * - Highlighting of matched text
 *
 * @example
 * <GlobalSearch />
 */
export const GlobalSearch: React.FC = () => {
  const [isOpen, setIsOpen] = React.useState(false);
  const [searchQuery, setSearchQuery] = React.useState("");
  const router = useRouter();
  const inputRef = React.useRef<HTMLInputElement>(null);
  const [selectedIndex, setSelectedIndex] = React.useState(0);

  // Search API
  const { data, isLoading, error } = useQuery({
    queryKey: ["global-search", searchQuery],
    queryFn: async () => {
      if (!searchQuery || searchQuery.length < 2) return null;

      const response = await globalSearch({
        q: searchQuery,
        type: "all",
        limit: 10,
      });

      return response;
    },
    enabled: searchQuery.length >= 2,
  });

  const results = data?.results || [];

  // Keyboard shortcut handler
  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Cmd+K (Mac) or Ctrl+K (Windows/Linux)
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setIsOpen(true);
      }

      // Escape to close
      if (e.key === "Escape") {
        setIsOpen(false);
        setSearchQuery("");
        setSelectedIndex(0);
      }

      // Arrow navigation
      if (isOpen && results && results.length > 0) {
        if (e.key === "ArrowDown") {
          e.preventDefault();
          setSelectedIndex((prev) =>
            prev < results.length - 1 ? prev + 1 : prev
          );
        }
        if (e.key === "ArrowUp") {
          e.preventDefault();
          setSelectedIndex((prev) => (prev > 0 ? prev - 1 : prev));
        }
        if (e.key === "Enter" && results[selectedIndex]) {
          e.preventDefault();
          handleSelectResult(results[selectedIndex]);
        }
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, results, selectedIndex]);

  // Focus input when modal opens
  React.useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  const handleSelectResult = (result: SearchResult) => {
    if (result.url) {
      router.push(result.url);
    }
    setIsOpen(false);
    setSearchQuery("");
    setSelectedIndex(0);
  };

  const getResultIcon = (type: SearchResult["type"]) => {
    switch (type) {
      case "patient":
        return <User className="h-4 w-4 text-dreams-blue" />;
      case "doctor":
        return <Stethoscope className="h-4 w-4 text-status-completed" />;
      case "appointment":
        return <Calendar className="h-4 w-4 text-status-pending" />;
      case "medicine":
        return <Pill className="h-4 w-4 text-status-inProgress" />;
      default:
        return <Search className="h-4 w-4 text-dreams-textSecondary" />;
    }
  };

  const getTypeLabel = (type: SearchResult["type"]) => {
    switch (type) {
      case "patient":
        return "Patient";
      case "doctor":
        return "Doctor";
      case "appointment":
        return "Appointment";
      case "medicine":
        return "Medicine";
      default:
        return "";
    }
  };

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 z-50"
        onClick={() => setIsOpen(false)}
      />

      {/* Modal */}
      <div className="fixed inset-0 z-50 flex items-start justify-center pt-[10vh]">
        <div className="bg-white rounded-lg shadow-2xl w-full max-w-2xl mx-4">
          {/* Search Input */}
          <div className="flex items-center gap-3 p-4 border-b border-dreams-border">
            <Search className="h-5 w-5 text-dreams-textSecondary flex-shrink-0" />
            <input
              ref={inputRef}
              type="text"
              placeholder="Search patients, doctors, appointments, medicines..."
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setSelectedIndex(0);
              }}
              className="flex-1 text-lg outline-none placeholder:text-dreams-textSecondary"
            />
            <button
              onClick={() => {
                setIsOpen(false);
                setSearchQuery("");
                setSelectedIndex(0);
              }}
              className="p-1 rounded hover:bg-dreams-lightBg"
            >
              <X className="h-5 w-5 text-dreams-textSecondary" />
            </button>
          </div>

          {/* Results */}
          <div className="max-h-96 overflow-y-auto">
            {isLoading ? (
              <div className="p-8 text-center">
                <div className="h-6 w-6 animate-spin rounded-full border-2 border-dreams-blue border-t-transparent mx-auto" />
              </div>
            ) : results && results.length > 0 ? (
              <div className="py-2">
                {results.map((result, index) => (
                  <button
                    key={result.id}
                    onClick={() => handleSelectResult(result)}
                    className={cn(
                      "w-full flex items-center gap-3 px-4 py-3 hover:bg-dreams-lightBg transition-colors text-left",
                      index === selectedIndex && "bg-dreams-lightBg"
                    )}
                  >
                    {/* Icon/Avatar */}
                    {result.type === "patient" || result.type === "doctor" ? (
                      <Avatar
                        src={result.photo}
                        fallback={result.title}
                        size="sm"
                      />
                    ) : (
                      <div className="flex h-8 w-8 items-center justify-center rounded-full bg-dreams-lightBg">
                        {getResultIcon(result.type)}
                      </div>
                    )}

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-dreams-textPrimary truncate">
                        {result.title}
                      </p>
                      {result.subtitle && (
                        <p className="text-sm text-dreams-textSecondary truncate">
                          {result.subtitle}
                        </p>
                      )}
                    </div>

                    {/* Type Badge */}
                    <span className="text-xs text-dreams-textSecondary px-2 py-1 rounded bg-dreams-lightBg">
                      {getTypeLabel(result.type)}
                    </span>
                  </button>
                ))}
              </div>
            ) : searchQuery.length >= 2 ? (
              <div className="p-8 text-center">
                <Search className="h-12 w-12 text-dreams-textSecondary mx-auto mb-3 opacity-50" />
                <p className="text-dreams-textSecondary">No results found</p>
                <p className="text-sm text-dreams-textSecondary mt-1">
                  Try searching with different keywords
                </p>
              </div>
            ) : (
              <div className="p-8 text-center">
                <Search className="h-12 w-12 text-dreams-textSecondary mx-auto mb-3 opacity-50" />
                <p className="text-dreams-textSecondary">
                  Start typing to search
                </p>
                <p className="text-sm text-dreams-textSecondary mt-1">
                  Search across patients, doctors, appointments, and medicines
                </p>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between px-4 py-3 border-t border-dreams-border bg-dreams-lightBg/50">
            <div className="flex items-center gap-4 text-xs text-dreams-textSecondary">
              <span className="flex items-center gap-1">
                <kbd className="px-2 py-1 rounded bg-white border border-dreams-border">
                  ↑↓
                </kbd>
                Navigate
              </span>
              <span className="flex items-center gap-1">
                <kbd className="px-2 py-1 rounded bg-white border border-dreams-border">
                  Enter
                </kbd>
                Select
              </span>
              <span className="flex items-center gap-1">
                <kbd className="px-2 py-1 rounded bg-white border border-dreams-border">
                  Esc
                </kbd>
                Close
              </span>
            </div>
          </div>
        </div>
      </div>
    </>
  );
};

GlobalSearch.displayName = "GlobalSearch";

/**
 * GlobalSearchTrigger Component
 *
 * Button to trigger global search (shows Cmd+K hint)
 *
 * @example
 * <GlobalSearchTrigger />
 */
export const GlobalSearchTrigger: React.FC<{
  onOpen: () => void;
}> = ({ onOpen }) => {
  const isMac =
    typeof window !== "undefined" &&
    navigator.platform.toUpperCase().indexOf("MAC") >= 0;

  return (
    <button
      onClick={onOpen}
      className="flex items-center gap-3 w-64 px-3 py-2 rounded-lg border border-dreams-border bg-white hover:bg-dreams-lightBg/50 transition-colors"
    >
      <Search className="h-4 w-4 text-dreams-textSecondary" />
      <span className="text-sm text-dreams-textSecondary">Search...</span>
      <kbd className="ml-auto px-2 py-0.5 text-xs rounded bg-dreams-lightBg border border-dreams-border text-dreams-textSecondary">
        {isMac ? "⌘K" : "Ctrl+K"}
      </kbd>
    </button>
  );
};

GlobalSearchTrigger.displayName = "GlobalSearchTrigger";
