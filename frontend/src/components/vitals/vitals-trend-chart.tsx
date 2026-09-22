"use client";

/**
 * VitalsTrendChart — a single-vital-type line chart over a day window.
 *
 * - X axis: reading timestamp (numeric time scale, so multiple readings per
 *   day stay separated)
 * - Y axis: value in the vital's unit; the clinical normal range
 *   (VITAL_NORMAL_RANGES) is drawn as a shaded ReferenceArea band
 * - Abnormal readings (abnormal_flag or client-side threshold check) render
 *   as enlarged red dots
 * - Accessibility: the chart container is role="img" with an aria-label
 *   summarising the trend ("BP Systolic rising: 118 → 132 mmHg over 30
 *   days…"), and an sr-only <table> mirrors the data for screen readers.
 *
 * VitalsTrendsGrid — renders one VitalsTrendChart per vital type that has at
 * least MIN_READINGS readings in the window (shared by /patient/vitals and
 * the doctor patient-detail page).
 */

import { useMemo } from "react";
import { useTranslations } from "next-intl";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  VITAL_META,
  VITAL_NORMAL_RANGES,
  VITAL_TYPES,
  isVitalAbnormal,
  type Vital,
  type VitalType,
} from "@/lib/api/vitals";
import { computeTrendSummary, groupVitalsByType } from "@/lib/vitals-trend";
import { cn } from "@/lib/utils";

/** A vital type needs at least this many readings in the window to chart. */
export const MIN_TREND_READINGS = 2;

const NORMAL_BAND_FILL = "#16A34A"; // green-600
const ABNORMAL_DOT_FILL = "#DC2626"; // red-600
const ABNORMAL_DOT_STROKE = "#991B1B"; // red-800

interface ChartPoint {
  /** epoch ms — numeric x value */
  ts: number;
  value: number;
  abnormal: boolean;
  recordedAt: string;
  unit: string;
}

function formatAxisDate(ts: number) {
  return new Date(ts).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
  });
}

function formatPointDate(iso: string) {
  return new Date(iso).toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

interface DotProps {
  cx?: number;
  cy?: number;
  payload?: ChartPoint;
}

export interface VitalsTrendChartProps {
  vitalType: VitalType;
  /** Readings of this vital type, any order — sorted internally. */
  readings: Vital[];
  /** Window length in days (used in the aria-label summary). */
  days: number;
  /** Chart height in px (default 200). */
  height?: number;
  /** Compact mode for embedded contexts (doctor patient profile). */
  compact?: boolean;
  className?: string;
}

export function VitalsTrendChart({
  vitalType,
  readings,
  days,
  height = 200,
  compact = false,
  className,
}: VitalsTrendChartProps) {
  const t = useTranslations("vitals");
  const meta = VITAL_META[vitalType];
  const normalRange = VITAL_NORMAL_RANGES[vitalType];

  const points = useMemo<ChartPoint[]>(
    () =>
      [...readings]
        .sort(
          (a, b) =>
            new Date(a.recorded_at).getTime() -
            new Date(b.recorded_at).getTime()
        )
        .map((r) => ({
          ts: new Date(r.recorded_at).getTime(),
          value: Number(r.value),
          abnormal:
            Boolean(r.abnormal_flag) ||
            isVitalAbnormal(vitalType, Number(r.value)),
          recordedAt: r.recorded_at,
          unit: r.unit,
        })),
    [readings, vitalType]
  );

  const summary = useMemo(() => computeTrendSummary(readings), [readings]);

  if (points.length < MIN_TREND_READINGS || !summary) return null;

  const ariaLabel = t("chartAriaLabel", {
    label: meta.label,
    direction: t(`direction.${summary.direction}`),
    first: summary.first,
    last: summary.last,
    unit: meta.unit,
    days,
    count: summary.count,
    abnormalCount: summary.abnormalCount,
  });

  const dataMin = Math.min(...points.map((p) => p.value));
  const dataMax = Math.max(...points.map((p) => p.value));

  // Shaded normal-range band. When only one bound exists (e.g. glucose_pp has
  // a max only), the band extends to the data extent on the open side.
  const showBand = Boolean(
    normalRange &&
      (normalRange.min !== undefined || normalRange.max !== undefined)
  );
  const bandY1 = normalRange?.min ?? Math.min(dataMin, normalRange?.max ?? dataMin);
  const bandY2 = normalRange?.max ?? Math.max(dataMax, normalRange?.min ?? dataMax);

  const yDomain: [number, number] = showBand
    ? [
        Math.floor(Math.min(dataMin, bandY1)),
        Math.ceil(Math.max(dataMax, bandY2)),
      ]
    : [Math.floor(dataMin), Math.ceil(dataMax)];

  const renderDot = (props: DotProps) => {
    const { cx, cy, payload } = props;
    if (cx === undefined || cy === undefined || !payload) {
      return <g key={payload?.ts ?? cx} />;
    }
    const abnormal = payload.abnormal;
    return (
      <circle
        key={payload.ts}
        cx={cx}
        cy={cy}
        r={abnormal ? 5 : 3}
        fill={abnormal ? ABNORMAL_DOT_FILL : meta.color}
        stroke={abnormal ? ABNORMAL_DOT_STROKE : "#fff"}
        strokeWidth={abnormal ? 2 : 1}
      />
    );
  };

  return (
    <figure className={cn("m-0", className)}>
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3
          className={cn(
            "font-semibold text-dreams-textPrimary",
            compact ? "text-sm" : "text-base"
          )}
        >
          {meta.label}
        </h3>
        <div className="flex items-center gap-2">
          {summary.abnormalCount > 0 && (
            <span className="inline-flex items-center rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
              {t("abnormalCount", { count: summary.abnormalCount })}
            </span>
          )}
          <span className="text-xs text-dreams-textSecondary">
            {t("readingCount", { count: summary.count })}
          </span>
        </div>
      </div>

      <div role="img" aria-label={ariaLabel} style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={points}
            margin={{ top: 4, right: 8, bottom: 0, left: compact ? -16 : -8 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="#E5E7EB"
              vertical={false}
            />
            {showBand && (
              <ReferenceArea
                y1={bandY1}
                y2={bandY2}
                fill={NORMAL_BAND_FILL}
                fillOpacity={0.08}
              />
            )}
            <XAxis
              dataKey="ts"
              type="number"
              domain={["dataMin", "dataMax"]}
              tickFormatter={formatAxisDate}
              tick={{ fontSize: 11, fill: "#6B7280" }}
              tickLine={false}
              minTickGap={24}
            />
            <YAxis
              domain={yDomain}
              tick={{ fontSize: 11, fill: "#6B7280" }}
              tickLine={false}
              axisLine={false}
              width={compact ? 32 : 44}
            />
            <Tooltip
              contentStyle={{
                border: "1px solid #E5E7EB",
                borderRadius: "8px",
                fontSize: "12px",
              }}
              labelFormatter={(ts) => formatPointDate(new Date(Number(ts)).toISOString())}
              formatter={(value: number, _name, item) => [
                `${value} ${meta.unit}${
                  (item?.payload as ChartPoint | undefined)?.abnormal
                    ? ` — ${t("abnormalTag")}`
                    : ""
                }`,
                meta.label,
              ]}
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke={meta.color}
              strokeWidth={2}
              dot={renderDot}
              activeDot={{ r: 5 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Screen-reader data table fallback — mirrors the plotted points. */}
      <table className="sr-only">
        <caption>{t("tableCaption", { label: meta.label })}</caption>
        <thead>
          <tr>
            <th>{t("colDate")}</th>
            <th>{t("colValue")}</th>
          </tr>
        </thead>
        <tbody>
          {points.map((p) => (
            <tr key={p.ts}>
              <td>{formatPointDate(p.recordedAt)}</td>
              <td>
                {p.value} {p.unit}
                {p.abnormal ? ` (${t("abnormalTag")})` : ""}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}

export interface VitalsTrendsGridProps {
  /** Mixed-type vital list (no `type` filter applied server-side). */
  vitals: Vital[];
  /** Window length in days. */
  days: number;
  /** Compact charts + tighter grid for embedded contexts. */
  compact?: boolean;
  /** Show the "not enough data" message when nothing is chartable (default true). */
  showEmptyState?: boolean;
  className?: string;
}

export function VitalsTrendsGrid({
  vitals,
  days,
  compact = false,
  showEmptyState = true,
  className,
}: VitalsTrendsGridProps) {
  const t = useTranslations("vitals");
  const groups = useMemo(() => groupVitalsByType(vitals), [vitals]);

  const chartableTypes = VITAL_TYPES.filter(
    (type) => (groups[type]?.length ?? 0) >= MIN_TREND_READINGS
  );

  if (chartableTypes.length === 0) {
    return showEmptyState ? (
      <p className="text-sm text-dreams-textSecondary">{t("notEnoughData")}</p>
    ) : null;
  }

  return (
    <div
      className={cn(
        "grid grid-cols-1 gap-4",
        compact ? "sm:grid-cols-2" : "md:grid-cols-2",
        className
      )}
    >
      {chartableTypes.map((type) => (
        <div
          key={type}
          className={cn(
            "rounded-lg border border-dreams-border",
            compact ? "p-3" : "p-4"
          )}
        >
          <VitalsTrendChart
            vitalType={type}
            readings={groups[type]!}
            days={days}
            compact={compact}
            height={compact ? 140 : 200}
          />
        </div>
      ))}
    </div>
  );
}
