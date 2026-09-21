"use client";

import { AlertCircle, CalendarX, RefreshCw } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";
import { Skeleton } from "@/components/ui/skeleton";
import type { AvailabilitySlot } from "@/lib/api/availability";

/** "HH:MM[:SS]" → "h:MM AM/PM" */
export function formatSlotLabel(time: string): string {
  const [h, m] = time.split(":").map(Number);
  const period = h >= 12 ? "PM" : "AM";
  const hour12 = h % 12 === 0 ? 12 : h % 12;
  return `${hour12}:${String(m).padStart(2, "0")} ${period}`;
}

/** Slot length in minutes, derived from the slot's start/end datetimes. */
export function slotDurationMinutes(slot: AvailabilitySlot): number {
  const ms = new Date(slot.end).getTime() - new Date(slot.start).getTime();
  return Math.max(1, Math.round(ms / 60000));
}

interface SlotPickerProps {
  /** Slots for the selected doctor + date. Undefined while no fetch has completed. */
  slots: AvailabilitySlot[] | undefined;
  isLoading: boolean;
  isError: boolean;
  isRetrying: boolean;
  /** True when the user explicitly opted for manual time entry despite slots existing. */
  customTime: boolean;
  selected: AvailabilitySlot | null;
  onSelect: (slot: AvailabilitySlot) => void;
  onRetry: () => void;
  onPickCustomTime: () => void;
  onShowSlots: () => void;
}

/**
 * Presentational time-slot grid for the booking form.
 * Data fetching lives in the parent (React Query) so the form can decide
 * whether to render the manual time/duration fallback.
 */
export function SlotPicker({
  slots,
  isLoading,
  isError,
  isRetrying,
  customTime,
  selected,
  onSelect,
  onRetry,
  onPickCustomTime,
  onShowSlots,
}: SlotPickerProps) {
  const t = useTranslations("appointments.slotPicker");
  const format = useFormatter();

  // User chose manual entry while slots are available — offer a way back.
  if (customTime && slots && slots.length > 0) {
    return (
      <div className="flex items-center justify-between rounded-lg border border-dreams-border bg-dreams-lightBg px-4 py-2.5">
        <p className="text-sm text-dreams-textSecondary">{t("enteringCustomTime")}</p>
        <button
          type="button"
          onClick={onShowSlots}
          className="text-xs font-medium text-dreams-blue hover:underline"
        >
          {t("showAvailableTimes")}
        </button>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div aria-busy="true" aria-label={t("loadingTimes")}>
        <span className="mb-1 block text-sm font-medium text-dreams-textPrimary">
          {t("availableTimes")}
        </span>
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-9 w-full" />
          ))}
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
        <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-amber-600" />
        <div className="flex-1">
          <p className="text-sm text-amber-800">
            {t("loadError")}
          </p>
          <button
            type="button"
            onClick={onRetry}
            disabled={isRetrying}
            className="mt-1.5 inline-flex items-center gap-1 text-xs font-medium text-amber-800 underline hover:text-amber-900 disabled:opacity-50"
          >
            <RefreshCw className={`h-3 w-3 ${isRetrying ? "animate-spin" : ""}`} />
            {isRetrying ? t("retrying") : t("retry")}
          </button>
        </div>
      </div>
    );
  }

  if (!slots || slots.length === 0) {
    return (
      <div className="flex items-start gap-3 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3">
        <CalendarX className="mt-0.5 h-4 w-4 flex-shrink-0 text-blue-600" />
        <p className="text-sm text-blue-800">
          {t("noAvailability")}
        </p>
      </div>
    );
  }

  return (
    <div>
      <span className="mb-1 block text-sm font-medium text-dreams-textPrimary">
        {t("availableTimesRequired")}
      </span>
      <div
        role="group"
        aria-label={t("availableTimesGroup")}
        className="grid grid-cols-3 gap-2 sm:grid-cols-4"
      >
        {slots.map((slot) => {
          const isSelected = selected?.start === slot.start;
          return (
            <button
              key={`${slot.start}-${slot.clinic_id ?? ""}-${slot.branch_id ?? ""}`}
              type="button"
              aria-pressed={isSelected}
              onClick={() => onSelect(slot)}
              className={`h-9 rounded-lg border px-2 text-sm font-medium transition-colors ${
                isSelected
                  ? "border-dreams-blue bg-dreams-blue text-white"
                  : "border-dreams-border bg-white text-dreams-textPrimary hover:border-dreams-blue hover:bg-dreams-blue/5"
              }`}
            >
              {format.dateTime(new Date(slot.start), {
                hour: "numeric",
                minute: "2-digit",
              })}
            </button>
          );
        })}
      </div>
      <button
        type="button"
        onClick={onPickCustomTime}
        className="mt-1.5 text-xs text-dreams-textSecondary underline hover:text-dreams-textPrimary"
      >
        {t("customTimeLink")}
      </button>
    </div>
  );
}
