"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Pill, CheckCircle2, Circle, Loader2 } from "lucide-react";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import {
  getMyPrescriptions,
  type PatientPrescription,
  type PrescriptionMedicine,
} from "@/lib/api/patient-portal";
import { cn } from "@/lib/utils";

interface MedicationEntry {
  key: string;
  name: string;
  dose: string;
  frequency: string;
  duration: string;
  route?: string;
  instructions?: string;
  prescriber: string | null;
  diagnosis: string | null;
  prescribed_on: string;
  valid_until: string | null;
  expired: boolean;
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function isExpired(validUntil: string | null): boolean {
  if (!validUntil) return false;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return new Date(validUntil) < today;
}

function flattenMedications(prescriptions: PatientPrescription[]): MedicationEntry[] {
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
        prescribed_on: p.created_at,
        valid_until: p.valid_until,
        expired: isExpired(p.valid_until),
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
  const [taken, setTaken] = useState<Set<string>>(new Set());

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(storageKey);
      if (raw) setTaken(new Set(JSON.parse(raw)));
    } catch {
      // ignore malformed storage
    }
  }, [storageKey]);

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

export default function PatientMedicationsPage() {
  const [showExpired, setShowExpired] = useState(false);
  const { taken, toggle } = useTakenToday();

  const { data, isLoading, isError } = useQuery({
    queryKey: ["patient-medications"],
    queryFn: () => getMyPrescriptions({ limit: 100 }),
  });

  const medications = useMemo(
    () => flattenMedications(data?.data ?? []),
    [data]
  );

  const active = medications.filter((m) => !m.expired);
  const expired = medications.filter((m) => m.expired);
  const visible = showExpired ? medications : active;

  return (
    <div className="space-y-6">
      <Breadcrumb items={[{ label: "Medications" }]} />

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-dreams-textPrimary">
            Medications
          </h1>
          <p className="text-dreams-textSecondary mt-1">
            Medicines from your prescriptions
          </p>
        </div>
        {expired.length > 0 && (
          <label className="flex items-center gap-2 text-sm text-dreams-textSecondary cursor-pointer">
            <input
              type="checkbox"
              checked={showExpired}
              onChange={(e) => setShowExpired(e.target.checked)}
              className="rounded border-dreams-border"
            />
            Show expired ({expired.length})
          </label>
        )}
      </div>

      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-dreams-blue" />
        </div>
      ) : isError ? (
        <div className="bg-white rounded-lg shadow-card p-12 text-center">
          <p className="text-red-500 font-medium">Failed to load medications.</p>
          <p className="mt-1 text-sm text-dreams-textSecondary">
            Please refresh the page or try again later.
          </p>
        </div>
      ) : visible.length === 0 ? (
        <div className="bg-white rounded-lg shadow-card p-12 text-center">
          <Pill className="h-12 w-12 text-dreams-textSecondary mx-auto mb-4" />
          <p className="text-dreams-textSecondary font-medium">
            {medications.length === 0
              ? "No medications found."
              : "No active medications."}
          </p>
          <p className="mt-1 text-sm text-dreams-textSecondary/70">
            {medications.length === 0
              ? "Medicines from your prescriptions will appear here."
              : "Enable “Show expired” to view past medications."}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {visible.map((med) => {
            const isTaken = taken.has(med.key);
            return (
              <div
                key={med.key}
                className={cn(
                  "bg-white rounded-lg shadow-card border p-4 flex items-start gap-3",
                  med.expired
                    ? "border-dreams-border opacity-70"
                    : "border-dreams-border"
                )}
              >
                <div
                  className={cn(
                    "p-2 rounded-lg flex-shrink-0 mt-0.5",
                    med.expired ? "bg-gray-100" : "bg-dreams-lightBg"
                  )}
                >
                  <Pill
                    className={cn(
                      "h-4 w-4",
                      med.expired ? "text-gray-400" : "text-dreams-blue"
                    )}
                  />
                </div>

                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="font-semibold text-dreams-textPrimary">
                      {med.name}
                    </p>
                    {med.expired && (
                      <span className="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600">
                        Expired
                      </span>
                    )}
                    {med.route && (
                      <span className="rounded-full bg-dreams-lightBg px-2.5 py-0.5 text-xs text-dreams-textSecondary capitalize">
                        {med.route}
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-dreams-textSecondary mt-0.5">
                    {med.dose} · {med.frequency} · {med.duration}
                  </p>
                  <p className="text-xs text-dreams-textSecondary/80 mt-1">
                    {med.prescriber ? `Dr. ${med.prescriber}` : "Prescriber unknown"}
                    {" · "}Prescribed {formatDate(med.prescribed_on)}
                    {med.valid_until
                      ? ` · Valid until ${formatDate(med.valid_until)}`
                      : ""}
                    {med.diagnosis ? ` · ${med.diagnosis}` : ""}
                  </p>
                  {med.instructions && (
                    <p className="text-xs text-dreams-textSecondary mt-1 italic">
                      {med.instructions}
                    </p>
                  )}
                </div>

                {!med.expired && (
                  <button
                    type="button"
                    onClick={() => toggle(med.key)}
                    className={cn(
                      "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex-shrink-0",
                      isTaken
                        ? "bg-green-100 text-green-700"
                        : "bg-dreams-lightBg text-dreams-textSecondary hover:text-dreams-textPrimary"
                    )}
                    title="Client-side only — resets daily and is not shared with your doctor"
                  >
                    {isTaken ? (
                      <CheckCircle2 className="h-4 w-4" />
                    ) : (
                      <Circle className="h-4 w-4" />
                    )}
                    {isTaken ? "Taken today" : "Mark taken"}
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
