"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Archive, ChevronDown, Pill } from "lucide-react";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import {
  MedicationCard,
  type MedicationEntry,
} from "@/components/medications/medication-card";
import {
  computePrescriptionAdherence,
  getAllMyPrescriptions,
  type PatientPrescription,
  type PrescriptionMedicine,
} from "@/lib/api/prescriptions";
import { cn } from "@/lib/utils";

function flattenMedications(
  prescriptions: PatientPrescription[]
): MedicationEntry[] {
  const entries: MedicationEntry[] = [];
  for (const p of prescriptions) {
    (p.medicines ?? []).forEach((m: PrescriptionMedicine, idx: number) => {
      entries.push({
        key: `${p.id}:${idx}`,
        name: m.brand_name ?? m.name ?? "Medication",
        dose: m.dose ?? m.dosage ?? "—",
        frequency: m.frequency ?? "—",
        duration: m.duration ?? "—",
        route: m.route,
        instructions: m.instructions ?? m.notes ?? m.timing,
        prescriber: p.doctor_name ?? null,
        diagnosis: p.diagnosis,
        prescribedOn: p.created_at,
        validUntil: p.valid_until,
        adherence: computePrescriptionAdherence({
          createdAt: p.created_at,
          validUntil: p.valid_until,
          duration: m.duration,
        }),
      });
    });
  }
  return entries;
}

/**
 * "Taken today" adherence is a client-side only convenience — there is no
 * backend adherence field yet. Stored in localStorage keyed by calendar day
 * so the checkboxes reset each day.
 */
function useTakenToday() {
  const storageKey = `medconnect:taken:${new Date().toISOString().slice(0, 10)}`;
  // Lazy initializer — reads localStorage once (guarded for SSR).
  const [taken, setTaken] = useState<Set<string>>(() => {
    try {
      const raw = window.localStorage.getItem(storageKey);
      return raw ? new Set<string>(JSON.parse(raw)) : new Set();
    } catch {
      // ignore malformed storage / SSR
      return new Set();
    }
  });

  const toggle = (key: string) => {
    setTaken((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      try {
        window.localStorage.setItem(storageKey, JSON.stringify(Array.from(next)));
      } catch {
        // storage may be unavailable; state still updates for the session
      }
      return next;
    });
  };

  return { taken, toggle };
}

function sortActive(a: MedicationEntry, b: MedicationEntry): number {
  // Most urgent first: expiring -> soonest end date -> ongoing last.
  const rank = (e: MedicationEntry) =>
    e.adherence.status === "expiring" ? 0 : e.adherence.endDate ? 1 : 2;
  const r = rank(a) - rank(b);
  if (r !== 0) return r;
  const aEnd = a.adherence.endDate?.getTime() ?? Number.POSITIVE_INFINITY;
  const bEnd = b.adherence.endDate?.getTime() ?? Number.POSITIVE_INFINITY;
  if (aEnd !== bEnd) return aEnd - bEnd;
  return a.name.localeCompare(b.name);
}

function sortPast(a: MedicationEntry, b: MedicationEntry): number {
  // Most recently finished first.
  const aEnd = a.adherence.endDate?.getTime() ?? 0;
  const bEnd = b.adherence.endDate?.getTime() ?? 0;
  return bEnd - aEnd;
}

function SectionHeader({
  title,
  count,
}: {
  title: string;
  count: number;
}) {
  return (
    <div className="flex items-center gap-2">
      <h2 className="text-lg font-semibold text-dreams-textPrimary">{title}</h2>
      <span className="rounded-full bg-dreams-lightBg px-2 py-0.5 text-xs font-medium text-dreams-textSecondary">
        {count}
      </span>
    </div>
  );
}

export default function PatientMedicationsPage() {
  const [showPast, setShowPast] = useState(false);
  const { taken, toggle } = useTakenToday();

  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ["patient-medications"],
    queryFn: () => getAllMyPrescriptions(),
    staleTime: 60_000,
  });

  const medications = useMemo(() => flattenMedications(data ?? []), [data]);

  const active = useMemo(
    () => medications.filter((m) => m.adherence.status !== "expired").sort(sortActive),
    [medications]
  );
  const past = useMemo(
    () => medications.filter((m) => m.adherence.status === "expired").sort(sortPast),
    [medications]
  );

  return (
    <div className="space-y-6">
      <Breadcrumb items={[{ label: "Medications" }]} />

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-dreams-textPrimary">
            Medications
          </h1>
          <p className="text-dreams-textSecondary mt-1">
            Track your prescriptions and how far along each course you are
          </p>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-3" aria-busy="true" aria-label="Loading medications">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="bg-white rounded-lg shadow-card border border-dreams-border p-4 flex items-start gap-3"
            >
              <Skeleton className="h-8 w-8 rounded-lg flex-shrink-0" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-4 w-40" />
                <Skeleton className="h-3 w-56" />
                <Skeleton className="h-1.5 w-full rounded-full" />
              </div>
            </div>
          ))}
        </div>
      ) : isError ? (
        <div className="bg-white rounded-lg shadow-card">
          <EmptyState
            icon={Pill}
            title="Failed to load medications"
            description="Please check your connection and try again."
            action={
              <Button onClick={() => refetch()} disabled={isFetching}>
                {isFetching ? "Retrying…" : "Try again"}
              </Button>
            }
          />
        </div>
      ) : medications.length === 0 ? (
        <div className="bg-white rounded-lg shadow-card">
          <EmptyState
            icon={Pill}
            title="No medications found"
            description="Medicines from your prescriptions will appear here."
          />
        </div>
      ) : (
        <div className="space-y-6">
          {/* ─── Active now ─────────────────────────────────────────── */}
          <section className="space-y-3">
            <SectionHeader title="Active now" count={active.length} />
            {active.length === 0 ? (
              <div className="bg-white rounded-lg shadow-card">
                <EmptyState
                  icon={Pill}
                  title="No active medications"
                  description={
                    past.length > 0
                      ? "All your courses have finished — see past medications below."
                      : "Medicines from your prescriptions will appear here."
                  }
                />
              </div>
            ) : (
              <div className="space-y-3">
                {active.map((med) => (
                  <MedicationCard
                    key={med.key}
                    entry={med}
                    takenToday={taken.has(med.key)}
                    onToggleTaken={toggle}
                  />
                ))}
              </div>
            )}
          </section>

          {/* ─── Expired / finished ─────────────────────────────────── */}
          {past.length > 0 && (
            <section className="space-y-3">
              <button
                type="button"
                onClick={() => setShowPast((v) => !v)}
                className="flex items-center gap-2 text-left group"
                aria-expanded={showPast}
              >
                <Archive className="h-4 w-4 text-dreams-textSecondary" />
                <h2 className="text-lg font-semibold text-dreams-textPrimary group-hover:text-dreams-blue transition-colors">
                  Expired / finished
                </h2>
                <span className="rounded-full bg-dreams-lightBg px-2 py-0.5 text-xs font-medium text-dreams-textSecondary">
                  {past.length}
                </span>
                <ChevronDown
                  className={cn(
                    "h-4 w-4 text-dreams-textSecondary transition-transform",
                    showPast && "rotate-180"
                  )}
                />
              </button>
              {showPast && (
                <div className="space-y-3">
                  {past.map((med) => (
                    <MedicationCard
                      key={med.key}
                      entry={med}
                      takenToday={false}
                    />
                  ))}
                </div>
              )}
            </section>
          )}
        </div>
      )}
    </div>
  );
}
