"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { Search, X, User, Stethoscope, Calendar, Pill, Clock, Building2, FileText, FlaskConical, ClipboardList } from "lucide-react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { globalSearch, type SearchResult } from "@/lib/api/search";
import { isRateLimitError } from "@/lib/rate-limit";
import { cn } from "@/lib/utils";
import { Avatar } from "@/components/ui/avatar";
import { EmptyState } from "@/components/ui/empty-state";
import { Spinner } from "@/components/ui/spinner";
import { useUiStore } from "@/stores/ui-store";

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
  const t = useTranslations("search");
  const tCommon = useTranslations("common");
  // Open state lives in the shared ui-store so header trigger buttons
  // and the ⌘K/Ctrl+K shortcut drive the same modal.
  const isOpen = useUiStore((s) => s.searchOpen);
  const setIsOpen = useUiStore((s) => s.setSearchOpen);
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

  // Kept as the query's stable array reference (no `|| []`) so the keydown
  // effect below doesn't re-subscribe on every render.
  const results = data?.results;

  const handleSelectResult = React.useCallback(
    (result: SearchResult) => {
      if (result.url) {
        router.push(result.url);
      }
      setIsOpen(false);
      setSearchQuery("");
      setSelectedIndex(0);
    },
    [router, setIsOpen]
  );

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
  }, [isOpen, results, selectedIndex, setIsOpen, handleSelectResult]);

  // Focus input when modal opens
  React.useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

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
      case "clinic":
        return <Building2 className="h-4 w-4 text-dreams-blue" />;
      case "record":
        return <FileText className="h-4 w-4 text-status-completed" />;
      case "lab_result":
        return <FlaskConical className="h-4 w-4 text-status-inProgress" />;
      case "prescription":
        return <ClipboardList className="h-4 w-4 text-dreams-blue" />;
      default:
        return <Search className="h-4 w-4 text-dreams-textSecondary" />;
    }
  };

  const getTypeLabel = (type: SearchResult["type"]) => {
    switch (type) {
      case "patient":
        return t("types.patient");
      case "doctor":
        return t("types.doctor");
      case "appointment":
        return t("types.appointment");
      case "medicine":
        return t("types.medicine");
      case "clinic":
        return t("types.clinic");
      case "record":
        return t("types.record");
      case "lab_result":
        return t("types.lab_result");
      case "prescription":
        return t("types.prescription");
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
        <div
          role="dialog"
          aria-modal="true"
          aria-label={t("ariaLabel")}
          className="bg-white rounded-lg shadow-2xl w-full max-w-2xl mx-4"
        >
          {/* Search Input */}
          <div className="flex items-center gap-3 p-4 border-b border-dreams-border">
            <Search className="h-5 w-5 text-dreams-textSecondary flex-shrink-0" />
            <input
              ref={inputRef}
              type="text"
              placeholder={t("placeholder")}
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
              aria-label={t("close")}
            >
              <X className="h-5 w-5 text-dreams-textSecondary" />
            </button>
          </div>

          {/* Results */}
          <div className="max-h-96 overflow-y-auto">
            {error ? (
              isRateLimitError(error) ? (
                <EmptyState
                  icon={Clock}
                  title={tCommon("rateLimitedTitle")}
                  description={error.userMessage}
                />
              ) : (
                <EmptyState
                  icon={Search}
                  title={t("errorTitle")}
                  description={t("errorDescription")}
                />
              )
            ) : isLoading ? (
              <div className="p-8 text-center">
                <Spinner className="mx-auto" label={t("searching")} />
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
              <EmptyState
                icon={Search}
                title={t("noResultsTitle")}
                description={t("noResultsDescription")}
              />
            ) : (
              <EmptyState
                icon={Search}
                title={t("emptyTitle")}
                description={t("emptyDescription")}
              />
            )}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between px-4 py-3 border-t border-dreams-border bg-dreams-lightBg/50">
            <div className="flex items-center gap-4 text-xs text-dreams-textSecondary">
              <span className="flex items-center gap-1">
                <kbd className="px-2 py-1 rounded bg-white border border-dreams-border">
                  ↑↓
                </kbd>
                {t("navigate")}
              </span>
              <span className="flex items-center gap-1">
                <kbd className="px-2 py-1 rounded bg-white border border-dreams-border">
                  Enter
                </kbd>
                {t("select")}
              </span>
              <span className="flex items-center gap-1">
                <kbd className="px-2 py-1 rounded bg-white border border-dreams-border">
                  Esc
                </kbd>
                {t("closeKey")}
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
  onOpen?: () => void;
}> = ({ onOpen }) => {
  const t = useTranslations("search");
  const openSearch = useUiStore((s) => s.openSearch);
  const isMac =
    typeof window !== "undefined" &&
    navigator.platform.toUpperCase().indexOf("MAC") >= 0;

  return (
    <button
      onClick={() => {
        onOpen?.();
        openSearch();
      }}
      aria-label={t("triggerAriaLabel")}
      className="flex items-center gap-3 w-64 px-3 py-2 rounded-lg border border-dreams-border bg-white hover:bg-dreams-lightBg/50 transition-colors"
    >
      <Search className="h-4 w-4 text-dreams-textSecondary" />
      <span className="text-sm text-dreams-textSecondary">{t("triggerLabel")}</span>
      <kbd className="ml-auto px-2 py-0.5 text-xs rounded bg-dreams-lightBg border border-dreams-border text-dreams-textSecondary">
        {isMac ? "⌘K" : "Ctrl+K"}
      </kbd>
    </button>
  );
};

GlobalSearchTrigger.displayName = "GlobalSearchTrigger";
