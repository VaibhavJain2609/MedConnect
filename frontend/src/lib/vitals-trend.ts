/**
 * Vitals trend helpers — pure functions shared by the patient vitals page
 * (/patient/vitals) and the doctor patient-detail vitals panel. Kept free of
 * next-intl / recharts imports so the summary calculation is unit-testable
 * under plain jest.
 */

import type { Vital, VitalType } from "@/lib/api/vitals";

export type TrendDirection = "rising" | "falling" | "stable";

export interface VitalTrendSummary {
  /** Value of the earliest reading in the window. */
  first: number;
  /** Value of the most recent reading in the window. */
  last: number;
  /** last - first (signed). */
  delta: number;
  direction: TrendDirection;
  /** Total readings in the window. */
  count: number;
  /** Readings flagged abnormal (critical threshold crossed). */
  abnormalCount: number;
  firstRecordedAt: string;
  lastRecordedAt: string;
}

/**
 * A change smaller than this fraction of the baseline value is reported as
 * "stable" rather than rising/falling — absorbs day-to-day noise (e.g. BP
 * 120→123 is not a trend).
 */
export const STABLE_THRESHOLD_RATIO = 0.05;

/**
 * Absolute floor for the stable-band epsilon, for vitals whose baseline can be
 * near zero (keeps |delta| <= 0.5 flat when first ≈ 0).
 */
export const STABLE_MIN_EPSILON = 0.5;

/**
 * Compute a one-line trend summary for a series of readings of a single vital
 * type. Returns null when fewer than two readings exist — callers should not
 * render a trend chart in that case.
 */
export function computeTrendSummary(
  readings: ReadonlyArray<
    Pick<Vital, "value" | "recorded_at" | "abnormal_flag">
  >
): VitalTrendSummary | null {
  if (readings.length < 2) return null;

  const sorted = [...readings].sort(
    (a, b) =>
      new Date(a.recorded_at).getTime() - new Date(b.recorded_at).getTime()
  );

  const first = Number(sorted[0].value);
  const last = Number(sorted[sorted.length - 1].value);
  const delta = last - first;

  const epsilon = Math.max(
    Math.abs(first) * STABLE_THRESHOLD_RATIO,
    STABLE_MIN_EPSILON
  );
  const direction: TrendDirection =
    delta > epsilon ? "rising" : delta < -epsilon ? "falling" : "stable";

  return {
    first,
    last,
    delta,
    direction,
    count: sorted.length,
    abnormalCount: sorted.filter((r) => r.abnormal_flag).length,
    firstRecordedAt: sorted[0].recorded_at,
    lastRecordedAt: sorted[sorted.length - 1].recorded_at,
  };
}

/**
 * Group a mixed-type vital list (as returned by GET /patients/vitals without a
 * `type` filter) by vital_type. Each group is sorted chronologically
 * (oldest first) regardless of input order.
 */
export function groupVitalsByType(
  vitals: ReadonlyArray<Vital>
): Partial<Record<VitalType, Vital[]>> {
  const groups: Partial<Record<VitalType, Vital[]>> = {};
  for (const v of vitals) {
    const type = v.vital_type as VitalType;
    (groups[type] ??= []).push(v);
  }
  for (const list of Object.values(groups)) {
    list?.sort(
      (a, b) =>
        new Date(a.recorded_at).getTime() - new Date(b.recorded_at).getTime()
    );
  }
  return groups;
}
