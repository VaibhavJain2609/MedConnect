"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

export type DiffStatus = "added" | "removed" | "changed" | "unchanged";

export interface DiffRow {
  /** Field key; nested objects are flattened one level as `parent.child`. */
  key: string;
  status: DiffStatus;
  /** True when the key exists on the (flattened) old_values object. */
  hasOld: boolean;
  /** True when the key exists on the (flattened) new_values object. */
  hasNew: boolean;
  oldValue: unknown;
  newValue: unknown;
}

function isPlainObject(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

/**
 * Flatten nested objects one level: `{ a: { b: 1 } }` → `{ "a.b": 1 }`.
 * Deeper nesting (and arrays) stays as a leaf value. Empty objects are
 * kept as their own key so they still show up in the diff.
 */
function flattenOneLevel(
  values: Record<string, unknown>
): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(values)) {
    if (isPlainObject(value) && Object.keys(value).length > 0) {
      for (const [childKey, childValue] of Object.entries(value)) {
        out[`${key}.${childKey}`] = childValue;
      }
    } else {
      out[key] = value;
    }
  }
  return out;
}

/** Deep-ish equality via JSON serialization — fine for JSONB audit payloads. */
function valuesEqual(a: unknown, b: unknown): boolean {
  if (Object.is(a, b)) return true;
  return JSON.stringify(a) === JSON.stringify(b);
}

/**
 * Pure field-level diff between old_values and new_values.
 * Returns one row per key in the union of both (flattened one level),
 * ordered old-keys-first then new-only keys.
 */
export function diffValues(
  oldValues: Record<string, unknown> | null | undefined,
  newValues: Record<string, unknown> | null | undefined
): DiffRow[] {
  const flatOld = flattenOneLevel(oldValues ?? {});
  const flatNew = flattenOneLevel(newValues ?? {});

  const keys: string[] = [];
  const seen = new Set<string>();
  for (const k of [...Object.keys(flatOld), ...Object.keys(flatNew)]) {
    if (!seen.has(k)) {
      seen.add(k);
      keys.push(k);
    }
  }

  return keys.map((key) => {
    const hasOld = Object.prototype.hasOwnProperty.call(flatOld, key);
    const hasNew = Object.prototype.hasOwnProperty.call(flatNew, key);
    const oldValue = flatOld[key];
    const newValue = flatNew[key];
    let status: DiffStatus;
    if (!hasOld) status = "added";
    else if (!hasNew) status = "removed";
    else status = valuesEqual(oldValue, newValue) ? "unchanged" : "changed";
    return { key, status, hasOld, hasNew, oldValue, newValue };
  });
}

/** Values longer than this are collapsed behind a "Show more" toggle. */
const TRUNCATE_AT = 160;

function formatValue(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function TruncatedValue({
  text,
  className,
}: {
  text: string;
  className?: string;
}) {
  const t = useTranslations("adminAudit.diff");
  const [expanded, setExpanded] = useState(false);
  const isLong = text.length > TRUNCATE_AT;
  return (
    <span className={className}>
      {isLong && !expanded ? `${text.slice(0, TRUNCATE_AT)}…` : text}
      {isLong && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            setExpanded((v) => !v);
          }}
          className="ml-1.5 text-dreams-blue hover:underline whitespace-nowrap"
        >
          {expanded ? t("showLess") : t("showMore")}
        </button>
      )}
    </span>
  );
}

const ROW_STYLES: Record<DiffStatus, string> = {
  added: "bg-green-50/50",
  removed: "bg-red-50/50",
  changed: "bg-amber-50/40",
  unchanged: "",
};

const BADGE: Record<
  DiffStatus,
  { labelKey: "added" | "removed" | "changed"; className: string } | null
> = {
  added: { labelKey: "added", className: "bg-green-100 text-green-700" },
  removed: { labelKey: "removed", className: "bg-red-100 text-red-700" },
  changed: { labelKey: "changed", className: "bg-amber-100 text-amber-700" },
  unchanged: null,
};

/**
 * Two-column old → new field-level diff for an audit log row.
 * Renders a "no field changes" note when the row carries no values
 * (e.g. READ actions).
 */
export function AuditDiff({
  oldValues,
  newValues,
}: {
  oldValues: Record<string, unknown> | null;
  newValues: Record<string, unknown> | null;
}) {
  const t = useTranslations("adminAudit.diff");
  const rows = diffValues(oldValues, newValues);

  if (rows.length === 0) {
    return (
      <p className="text-xs text-dreams-textSecondary italic">
        {t("noChanges")}
      </p>
    );
  }

  return (
    <div className="rounded-lg border border-dreams-border overflow-hidden">
      <table className="w-full text-xs">
        <thead className="bg-dreams-lightBg">
          <tr>
            <th className="px-3 py-2 text-left font-semibold text-dreams-textSecondary w-1/4">
              {t("field")}
            </th>
            <th className="px-3 py-2 text-left font-semibold text-dreams-textSecondary">
              {t("oldValue")}
            </th>
            <th className="px-3 py-2 text-left font-semibold text-dreams-textSecondary">
              {t("newValue")}
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-dreams-border">
          {rows.map((row) => {
            const badge = BADGE[row.status];
            const oldText = formatValue(row.oldValue);
            const newText = formatValue(row.newValue);
            const dimmed = "text-dreams-textSecondary opacity-70";
            return (
              <tr key={row.key} className={ROW_STYLES[row.status]}>
                <td className="px-3 py-1.5 font-mono text-dreams-textPrimary">
                  {row.key}
                  {badge && (
                    <span
                      className={`ml-2 inline-block rounded px-1.5 py-0.5 text-[10px] font-medium font-sans ${badge.className}`}
                    >
                      {t(badge.labelKey)}
                    </span>
                  )}
                </td>
                <td className="px-3 py-1.5 break-all max-w-md">
                  {row.hasOld ? (
                    <TruncatedValue
                      text={oldText}
                      className={
                        row.status === "unchanged"
                          ? dimmed
                          : "text-red-700 line-through decoration-red-400"
                      }
                    />
                  ) : (
                    <span className={dimmed}>—</span>
                  )}
                </td>
                <td className="px-3 py-1.5 break-all max-w-md">
                  {row.hasNew ? (
                    <TruncatedValue
                      text={newText}
                      className={
                        row.status === "unchanged"
                          ? dimmed
                          : row.status === "removed"
                            ? dimmed
                            : "text-green-700 font-medium"
                      }
                    />
                  ) : (
                    <span className={dimmed}>—</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
