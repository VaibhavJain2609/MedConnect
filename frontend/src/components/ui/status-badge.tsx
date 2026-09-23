import * as React from "react";
import { useTranslations } from "next-intl";

import { cn } from "@/lib/utils";

/**
 * StatusBadge
 *
 * Single status → color map for the whole app. Consolidates the per-page
 * STATUS_VARIANT_MAP / STATUS_COLORS tables (appointments, queue, billing,
 * clinic links, lab results, vitals, record types).
 *
 * Colors use `*-100` backgrounds with `*-800` text — every combination meets
 * WCAG AA contrast (>= 4.5:1) for small text, unlike the old
 * "bg-status-X/10 + text-status-X" pairing where amber-500/violet-500 text on
 * near-white backgrounds fails AA.
 *
 * @example
 * <StatusBadge status={appt.status} />            // "Scheduled", "In Progress"…
 * <StatusBadge status="no-show" />
 * <StatusBadge status={bill.status} label="Paid" />
 */

type StatusTone =
  | "success"
  | "info"
  | "warning"
  | "danger"
  | "purple"
  | "indigo"
  | "pink"
  | "neutral";

// All tone pairs pass WCAG AA on their own background.
const TONE_CLASSES: Record<StatusTone, string> = {
  success: "bg-green-100 text-green-800 border-green-200",
  info: "bg-blue-100 text-blue-800 border-blue-200",
  warning: "bg-amber-100 text-amber-800 border-amber-200",
  danger: "bg-red-100 text-red-800 border-red-200",
  purple: "bg-purple-100 text-purple-800 border-purple-200",
  indigo: "bg-indigo-100 text-indigo-800 border-indigo-200",
  pink: "bg-pink-100 text-pink-800 border-pink-200",
  neutral: "bg-gray-100 text-gray-700 border-gray-200",
};

const STATUS_TONE: Record<string, StatusTone> = {
  // Appointment lifecycle (scheduled → arrived → in-progress → completed)
  scheduled: "info",
  upcoming: "info",
  confirmed: "info",
  arrived: "purple",
  "in-progress": "purple",
  in_progress: "purple",
  completed: "success",
  cancelled: "neutral",
  canceled: "neutral",
  "no-show": "warning",
  no_show: "warning",
  // Queue
  waiting: "info",
  in_consultation: "purple",
  // Billing
  pending: "warning",
  paid: "success",
  unpaid: "warning",
  refunded: "purple",
  overdue: "danger",
  draft: "neutral",
  failed: "danger",
  partial: "warning",
  // Patient–clinic links, consent, record-access requests
  approved: "success",
  rejected: "danger",
  revoked: "danger",
  expired: "danger",
  requested: "warning",
  // Lab results
  received: "info",
  // Vitals
  normal: "success",
  warning: "warning",
  critical: "danger",
  // Generic account / record states
  active: "success",
  inactive: "neutral",
  verified: "success",
  unverified: "warning",
  provisional: "warning",
  discontinued: "neutral",
  // Medical record types
  prescription: "info",
  diagnostic_report: "purple",
  discharge_summary: "danger",
  opd_note: "success",
  immunization: "warning",
  lab_report: "indigo",
  lab_result: "purple",
  imaging: "pink",
  clinical_note: "warning",
  other: "neutral",
};

function normalize(status: string): string {
  return status.trim().toLowerCase();
}

/** Normalized status → camelCase message key ("in-progress" → "inProgress"). */
function messageKey(status: string): string {
  return status.replace(/[_-]+(.)/g, (_, c) => c.toUpperCase());
}

function humanize(status: string): string {
  return status
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export interface StatusBadgeProps
  extends React.HTMLAttributes<HTMLSpanElement> {
  /** Raw status string (e.g. "in-progress", "paid", "approved"). */
  status: string;
  /** Override the auto-generated label. */
  label?: string;
}

function StatusBadge({
  status,
  label,
  className,
  ...props
}: StatusBadgeProps) {
  const t = useTranslations("statusBadge");
  const key = normalize(status);
  const tone = STATUS_TONE[key] ?? "neutral";
  const i18nKey = messageKey(key);
  // i18nKey is derived from arbitrary API status strings — cast to the
  // typed key union; `t.has` guards against statuses without a translation.
  const text =
    label ??
    (t.has(i18nKey as never) ? t(i18nKey as never) : humanize(key));

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold",
        TONE_CLASSES[tone],
        className
      )}
      {...props}
    >
      {text}
    </span>
  );
}

export { StatusBadge, STATUS_TONE };
export type { StatusTone };
