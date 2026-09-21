"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, History } from "lucide-react";

import { getRecordVersions, type RecordVersion } from "@/lib/api/records";
import { formatDate, recordTypeLabel } from "@/lib/utils";

export interface FieldChange {
  label: string;
  before: string;
  after: string;
}

// Leaf keys inside fhir_bundle that change on every write (timestamps, not
// clinical content) — excluded from the diff so it only shows real changes.
const VOLATILE_FHIR_KEYS = new Set(["timestamp", "lastUpdated", "date", "id"]);

const EMPTY_VALUE = "—";
const MAX_VALUE_LEN = 200;

function truncate(value: string): string {
  return value.length > MAX_VALUE_LEN ? `${value.slice(0, MAX_VALUE_LEN)}…` : value;
}

function flattenLeaves(
  value: unknown,
  prefix: string,
  out: Record<string, string>
): void {
  if (value === null || value === undefined) return;
  if (typeof value !== "object") {
    out[prefix] = String(value);
    return;
  }
  if (Array.isArray(value)) {
    value.forEach((item, i) =>
      flattenLeaves(item, prefix ? `${prefix}[${i}]` : `[${i}]`, out)
    );
    return;
  }
  for (const [key, child] of Object.entries(value as Record<string, unknown>)) {
    flattenLeaves(child, prefix ? `${prefix}.${key}` : key, out);
  }
}

function leafKey(path: string): string {
  const seg = path.split(".").pop() ?? path;
  return seg.replace(/\[\d+\]$/, "");
}

/**
 * Field-level diff between two versions of a record. Compares the scalar
 * columns plus every leaf of the JSONB fhir_bundle (volatile timestamp
 * leaves excluded). Empty means the amendment only restamped metadata.
 */
export function diffRecordVersions(
  base: RecordVersion,
  amended: RecordVersion
): FieldChange[] {
  const changes: FieldChange[] = [];

  const scalarFields: [keyof RecordVersion, string][] = [
    ["title", "Title"],
    ["record_type", "Record type"],
    ["description", "Description"],
    ["document_url", "Document"],
  ];
  for (const [key, label] of scalarFields) {
    const a = base[key];
    const b = amended[key];
    const before =
      key === "record_type" && typeof a === "string" ? recordTypeLabel(a) : a;
    const after =
      key === "record_type" && typeof b === "string" ? recordTypeLabel(b) : b;
    if (before !== after) {
      changes.push({
        label,
        before: truncate(String(before ?? "") || EMPTY_VALUE),
        after: truncate(String(after ?? "") || EMPTY_VALUE),
      });
    }
  }

  const beforeLeaves: Record<string, string> = {};
  const afterLeaves: Record<string, string> = {};
  flattenLeaves(base.fhir_bundle, "", beforeLeaves);
  flattenLeaves(amended.fhir_bundle, "", afterLeaves);

  const paths = Array.from(
    new Set([...Object.keys(beforeLeaves), ...Object.keys(afterLeaves)])
  );
  for (const path of paths) {
    if (!path || VOLATILE_FHIR_KEYS.has(leafKey(path))) continue;
    const a = beforeLeaves[path];
    const b = afterLeaves[path];
    if (a !== b) {
      changes.push({
        label: `Details · ${path}`,
        before: truncate(a ?? EMPTY_VALUE),
        after: truncate(b ?? EMPTY_VALUE),
      });
    }
  }

  return changes;
}

function VersionDiff({ changes }: { changes: FieldChange[] }) {
  if (changes.length === 0) {
    return (
      <p className="mt-2 text-xs text-dreams-textSecondary italic">
        No field-level changes detected.
      </p>
    );
  }
  return (
    <dl className="mt-2 space-y-1.5">
      {changes.map((c) => (
        <div key={c.label} className="text-xs">
          <dt className="font-medium text-dreams-textSecondary">{c.label}</dt>
          <dd className="mt-0.5 flex flex-col gap-0.5 sm:flex-row sm:items-center sm:gap-2">
            <span className="rounded bg-red-50 px-1.5 py-0.5 text-red-700 line-through break-words">
              {c.before}
            </span>
            <span className="text-dreams-textSecondary">→</span>
            <span className="rounded bg-green-50 px-1.5 py-0.5 text-green-700 break-words">
              {c.after}
            </span>
          </dd>
        </div>
      ))}
    </dl>
  );
}

/**
 * Collapsible "Version history" section for a medical record. Renders
 * nothing when the record has no amendments.
 */
export function RecordVersionHistory({ recordId }: { recordId: string }) {
  const [open, setOpen] = useState(true);

  const { data } = useQuery({
    queryKey: ["record-versions", recordId],
    queryFn: () => getRecordVersions(recordId),
    staleTime: 60_000,
    retry: 1,
  });

  const versions = useMemo(() => data?.data ?? [], [data]);

  // Original + at least one amendment required — otherwise no history to show.
  if (versions.length <= 1) return null;

  const original = versions.find((v) => v.version === 1) ?? versions[0];
  const newestFirst = [...versions].sort((a, b) => b.version - a.version);

  return (
    <section className="bg-white rounded-lg shadow-card max-w-3xl">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between px-6 py-4 text-left"
      >
        <span className="flex items-center gap-2 text-sm font-semibold text-dreams-textPrimary">
          <History className="h-4 w-4 text-dreams-textSecondary" />
          Version history
          <span className="rounded-full bg-dreams-lightBg px-2 py-0.5 text-xs font-medium text-dreams-textSecondary">
            {versions.length}
          </span>
        </span>
        {open ? (
          <ChevronDown className="h-4 w-4 text-dreams-textSecondary" />
        ) : (
          <ChevronRight className="h-4 w-4 text-dreams-textSecondary" />
        )}
      </button>

      {open && (
        <ol className="border-t border-dreams-border px-6 py-4 space-y-4">
          {newestFirst.map((v) => {
            const changes =
              v.version === 1 ? [] : diffRecordVersions(original, v);
            return (
              <li
                key={v.id}
                className="border-l-2 border-dreams-border pl-4"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium text-dreams-textPrimary">
                    Version {v.version}
                  </span>
                  {v.version === 1 ? (
                    <span className="rounded-full bg-dreams-lightBg px-2 py-0.5 text-xs text-dreams-textSecondary">
                      Original
                    </span>
                  ) : (
                    <span className="rounded-full bg-amber-50 px-2 py-0.5 text-xs text-amber-700">
                      Amended
                    </span>
                  )}
                  {v.is_latest && (
                    <span className="rounded-full bg-dreams-blue/10 px-2 py-0.5 text-xs text-dreams-blue">
                      Latest
                    </span>
                  )}
                  <span className="text-xs text-dreams-textSecondary">
                    {formatDate(v.created_at)}
                    {v.doctor_name ? ` · by ${v.doctor_name}` : ""}
                  </span>
                </div>
                {v.version > 1 && <VersionDiff changes={changes} />}
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
