"use client";

import { AlertTriangle, Bell, BellRing, CheckCircle2, Circle, Infinity as InfinityIcon, Pill, RefreshCcw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { PrescriptionAdherence } from "@/lib/api/prescriptions";
import type { PrescriptionMedicine } from "@/lib/api/patient-portal";
import type { RefillStatus } from "@/lib/api/refills";

/**
 * One flattened medicine item from a prescription's `medicines` JSONB array,
 * joined with the prescription-level fields the card needs.
 */
export interface MedicationEntry {
  /** `${prescriptionId}:${itemIndex}` — stable React key + localStorage key. */
  key: string;
  /** Owning prescription — refill requests are per-prescription. */
  prescriptionId: string;
  /** Index of this item inside the prescription's medicines array. */
  itemIndex: number;
  name: string;
  dose: string;
  frequency: string;
  duration: string;
  route?: string;
  instructions?: string;
  prescriber: string | null;
  diagnosis: string | null;
  prescribedOn: string;
  validUntil: string | null;
  adherence: PrescriptionAdherence;
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function daysRemainingLabel(days: number, endSource: PrescriptionAdherence["endSource"]) {
  const noun = endSource === "valid_until" ? "Expires" : "Course ends";
  if (days <= 0) return `${noun} today`;
  if (days === 1) return `${noun} tomorrow`;
  return `${noun} in ${days} days`;
}

interface MedicationCardProps {
  entry: MedicationEntry;
  /** Whether the patient has marked this item taken today (client-side only). */
  takenToday: boolean;
  onToggleTaken?: (key: string) => void;
  /**
   * Prescription-level refill affordance — rendered only when provided
   * (the page passes it on the first medicine card of each prescription).
   */
  refillStatus?: RefillStatus | null;
  refillPending?: boolean;
  onRequestRefill?: () => void;
  /** i18n labels — optional so the card stays usable without intl context. */
  refillLabels?: {
    request: string;
    pending: string;
    approved: string;
    declined: string;
  };
  /**
   * Medication-reminder affordance — rendered only when provided (the page
   * passes it on the first medicine card of each prescription).
   */
  reminderActive?: boolean;
  onManageReminders?: () => void;
  reminderLabels?: {
    remind: string;
    on: string;
  };
}

/**
 * Adherence-oriented card for a single prescribed medicine:
 * dose/frequency/duration, course progress bar, days remaining and an
 * expiry warning badge when `valid_until` is within the backend
 * notification window (3 days).
 */
export function MedicationCard({
  entry,
  takenToday,
  onToggleTaken,
  refillStatus,
  refillPending,
  onRequestRefill,
  refillLabels,
  reminderActive,
  onManageReminders,
  reminderLabels,
}: MedicationCardProps) {
  const { adherence } = entry;
  const expired = adherence.status === "expired";
  const expiring = adherence.status === "expiring";

  return (
    <div
      className={cn(
        "bg-white rounded-lg shadow-card border border-dreams-border p-4 flex items-start gap-3",
        expired && "opacity-70"
      )}
    >
      <div
        className={cn(
          "p-2 rounded-lg flex-shrink-0 mt-0.5",
          expired ? "bg-gray-100" : "bg-dreams-lightBg"
        )}
      >
        <Pill
          className={cn("h-4 w-4", expired ? "text-gray-400" : "text-dreams-blue")}
        />
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 flex-wrap">
          <p className="font-semibold text-dreams-textPrimary">{entry.name}</p>
          {expired && <Badge variant="cancelled">Expired</Badge>}
          {expiring && (
            <Badge variant="pending" className="gap-1">
              <AlertTriangle className="h-3 w-3" aria-hidden />
              {daysRemainingLabel(adherence.daysRemaining ?? 0, adherence.endSource)}
            </Badge>
          )}
          {adherence.ongoing && !expired && (
            <Badge variant="secondary" className="gap-1">
              <InfinityIcon className="h-3 w-3" aria-hidden />
              Ongoing
            </Badge>
          )}
          {entry.route && (
            <span className="rounded-full bg-dreams-lightBg px-2.5 py-0.5 text-xs text-dreams-textSecondary capitalize">
              {entry.route}
            </span>
          )}
        </div>

        <p className="text-sm text-dreams-textSecondary mt-0.5">
          {entry.dose} · {entry.frequency} · {entry.duration}
        </p>

        <p className="text-xs text-dreams-textSecondary/80 mt-1">
          {entry.prescriber ? `Dr. ${entry.prescriber}` : "Prescriber unknown"}
          {" · "}Prescribed {formatDate(entry.prescribedOn)}
          {entry.validUntil ? ` · Valid until ${formatDate(entry.validUntil)}` : ""}
          {entry.diagnosis ? ` · ${entry.diagnosis}` : ""}
        </p>

        {entry.instructions && (
          <p className="text-xs text-dreams-textSecondary mt-1 italic">
            {entry.instructions}
          </p>
        )}

        {/* Course progress — only for finite courses (valid_until or duration-derived) */}
        {adherence.percentComplete != null && (
          <div className="mt-3">
            <div className="h-1.5 w-full rounded-full bg-dreams-lightBg overflow-hidden">
              <div
                className={cn(
                  "h-full rounded-full transition-all",
                  expired
                    ? "bg-gray-300"
                    : expiring
                      ? "bg-status-pending"
                      : "bg-dreams-blue"
                )}
                style={{ width: `${adherence.percentComplete}%` }}
                role="progressbar"
                aria-valuenow={adherence.percentComplete}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={`Course completion for ${entry.name}`}
              />
            </div>
            <p className="text-xs text-dreams-textSecondary/80 mt-1">
              {expired
                ? "Course finished"
                : `Day ${adherence.elapsedDays} of ${adherence.totalDays}`}
              {!expired && adherence.daysRemaining != null && !expiring && (
                <>{" · "}{adherence.daysRemaining} {adherence.daysRemaining === 1 ? "day" : "days"} left</>
              )}
            </p>
          </div>
        )}

        {/* Prescription-level affordances — shown on the first card:
            refill request + medication-reminder toggle */}
        {(onRequestRefill || onManageReminders) && (
          <div className="mt-3 flex items-center gap-2 flex-wrap">
            {onRequestRefill &&
              (refillStatus === "pending" ? (
                <Badge variant="pending" className="gap-1">
                  <RefreshCcw className="h-3 w-3" aria-hidden />
                  {refillLabels?.pending ?? "Refill requested"}
                </Badge>
              ) : (
                <>
                  <button
                    type="button"
                    onClick={onRequestRefill}
                    disabled={refillPending}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-dreams-lightBg text-dreams-blue hover:bg-dreams-blue hover:text-white transition-colors disabled:opacity-50"
                  >
                    <RefreshCcw className="h-3.5 w-3.5" aria-hidden />
                    {refillLabels?.request ?? "Request refill"}
                  </button>
                  {refillStatus === "approved" && (
                    <Badge variant="completed">{refillLabels?.approved ?? "Refill approved"}</Badge>
                  )}
                  {refillStatus === "declined" && (
                    <Badge variant="cancelled">{refillLabels?.declined ?? "Refill declined"}</Badge>
                  )}
                </>
              ))}
            {onManageReminders && (
              <button
                type="button"
                onClick={onManageReminders}
                aria-pressed={reminderActive ?? false}
                className={cn(
                  "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors",
                  reminderActive
                    ? "bg-dreams-blue text-white hover:bg-dreams-blue/90"
                    : "bg-dreams-lightBg text-dreams-textSecondary hover:text-dreams-textPrimary"
                )}
              >
                {reminderActive ? (
                  <BellRing className="h-3.5 w-3.5" aria-hidden />
                ) : (
                  <Bell className="h-3.5 w-3.5" aria-hidden />
                )}
                {reminderActive
                  ? reminderLabels?.on ?? "Reminders on"
                  : reminderLabels?.remind ?? "Remind me"}
              </button>
            )}
          </div>
        )}
      </div>

      {!expired && onToggleTaken && (
        <button
          type="button"
          onClick={() => onToggleTaken(entry.key)}
          className={cn(
            "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex-shrink-0",
            takenToday
              ? "bg-green-100 text-green-700"
              : "bg-dreams-lightBg text-dreams-textSecondary hover:text-dreams-textPrimary"
          )}
          title="Client-side only — resets daily and is not shared with your doctor"
        >
          {takenToday ? (
            <CheckCircle2 className="h-4 w-4" />
          ) : (
            <Circle className="h-4 w-4" />
          )}
          {takenToday ? "Taken today" : "Mark taken"}
        </button>
      )}
    </div>
  );
}
