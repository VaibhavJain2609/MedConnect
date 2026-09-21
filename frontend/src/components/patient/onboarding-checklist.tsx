"use client";

import { useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, ChevronDown, X } from "lucide-react";
import api from "@/lib/api";
import { getMedicalHistory, getMyClinicLinks } from "@/lib/api/patients";
import { getMyVitals } from "@/lib/api/vitals";
import { cn } from "@/lib/utils";

const DISMISSED_KEY = "pt-onboarding-dismissed";
export const PREFS_VISITED_KEY = "pt-onboarding-prefs-visited";

function readFlag(key: string): boolean {
  try {
    return window.localStorage.getItem(key) === "1";
  } catch {
    return false;
  }
}

function writeFlag(key: string) {
  try {
    window.localStorage.setItem(key, "1");
  } catch {
    // localStorage unavailable (private mode etc.) — non-fatal
  }
}

interface ChecklistItem {
  id: string;
  label: string;
  href: string;
  done: boolean;
  onOpen?: () => void;
}

/**
 * First-run onboarding checklist for the patient landing page.
 *
 * Each item is checked against real backend data (one lightweight query per
 * signal); the notification-preferences item is tracked via a localStorage
 * flag set when the patient visits /patient/preferences. The card is
 * dismissible (`pt-onboarding-dismissed`) and auto-hides once every item is
 * complete.
 */
// Hydration-safe "is client" signal: the server snapshot renders nothing,
// then the client snapshot flips to true after hydration — no effect needed.
const subscribeNoop = () => () => {};

export function OnboardingChecklist() {
  // Mounted gate: localStorage reads must happen client-side only, so the
  // card renders nothing until after hydration (avoids SSR mismatch/flash).
  const mounted = useSyncExternalStore(
    subscribeNoop,
    () => true,
    () => false
  );
  const [dismissed, setDismissed] = useState(() => readFlag(DISMISSED_KEY));
  const [collapsed, setCollapsed] = useState(false);
  const [prefsVisited, setPrefsVisited] = useState(() =>
    readFlag(PREFS_VISITED_KEY)
  );

  const enabled = mounted && !dismissed;

  const { data: medicalHistory } = useQuery({
    queryKey: ["onboarding-medical-history"],
    queryFn: getMedicalHistory,
    enabled,
    staleTime: 60_000,
  });

  const { data: vitalsData } = useQuery({
    queryKey: ["onboarding-vitals"],
    queryFn: () => getMyVitals({ days: 365, limit: 1 }),
    enabled,
    staleTime: 60_000,
  });

  const { data: clinicLinks } = useQuery({
    queryKey: ["onboarding-clinic-links"],
    queryFn: getMyClinicLinks,
    enabled,
    staleTime: 60_000,
  });

  const { data: appointments } = useQuery({
    queryKey: ["onboarding-appointments"],
    queryFn: async () => {
      const res = await api.get("/api/v1/appointments?limit=1");
      return res.data;
    },
    enabled,
    staleTime: 60_000,
  });

  const historyDone = Boolean(
    medicalHistory &&
      (medicalHistory.blood_group ||
        (medicalHistory.allergies?.length ?? 0) > 0 ||
        (medicalHistory.chronic_conditions?.length ?? 0) > 0 ||
        medicalHistory.height_cm ||
        medicalHistory.weight_kg)
  );
  const vitalsDone = (vitalsData?.total ?? vitalsData?.data?.length ?? 0) > 0;
  const clinicDone =
    (clinicLinks?.data ?? []).some((l) => l.consent_status !== "revoked");
  const appointmentDone =
    (appointments?.total ?? appointments?.data?.length ?? 0) > 0;

  const items: ChecklistItem[] = [
    {
      id: "medical-history",
      label: "Complete your medical history",
      href: "/patient/medical-history",
      done: historyDone,
    },
    {
      id: "vitals",
      label: "Log your first vitals",
      href: "/patient/vitals",
      done: vitalsDone,
    },
    {
      id: "clinic",
      label: "Link a clinic",
      href: "/patient/clinics",
      done: clinicDone,
    },
    {
      id: "appointment",
      label: "Book your first appointment",
      href: "/patient/appointments",
      done: appointmentDone,
    },
    {
      id: "preferences",
      label: "Set notification preferences",
      href: "/patient/preferences",
      done: prefsVisited,
      onOpen: () => {
        writeFlag(PREFS_VISITED_KEY);
        setPrefsVisited(true);
      },
    },
  ];

  const doneCount = items.filter((i) => i.done).length;
  const allDone = doneCount === items.length;

  if (!mounted || dismissed || allDone) return null;

  return (
    <div className="bg-white rounded-lg shadow-card border border-dreams-border">
      <div className="flex items-center gap-3 p-4">
        <button
          type="button"
          onClick={() => setCollapsed((c) => !c)}
          className="flex flex-1 items-center gap-3 text-left"
          aria-expanded={!collapsed}
        >
          <div className="flex-1">
            <div className="flex items-center justify-between gap-4">
              <h2 className="text-lg font-semibold text-dreams-textPrimary">
                Getting started
              </h2>
              <span className="text-xs font-medium text-dreams-textSecondary">
                {doneCount} of {items.length} complete
              </span>
            </div>
            <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-gray-100">
              <div
                className="h-full rounded-full bg-dreams-blue transition-all"
                style={{ width: `${(doneCount / items.length) * 100}%` }}
              />
            </div>
          </div>
          <ChevronDown
            className={cn(
              "h-5 w-5 flex-shrink-0 text-dreams-textSecondary transition-transform",
              collapsed && "-rotate-90"
            )}
          />
        </button>
        <button
          type="button"
          onClick={() => {
            writeFlag(DISMISSED_KEY);
            setDismissed(true);
          }}
          className="flex-shrink-0 rounded-md p-1 text-dreams-textSecondary hover:bg-gray-100 hover:text-dreams-textPrimary"
          aria-label="Dismiss checklist"
          title="Dismiss"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {!collapsed && (
        <ul className="divide-y divide-dreams-border border-t border-dreams-border">
          {items.map((item) => (
            <li key={item.id}>
              <Link
                href={item.href}
                onClick={item.onOpen}
                className="flex items-center gap-3 px-4 py-3 transition hover:bg-dreams-lightBg"
              >
                {item.done ? (
                  <CheckCircle2 className="h-5 w-5 flex-shrink-0 text-green-500" />
                ) : (
                  <span className="h-5 w-5 flex-shrink-0 rounded-full border-2 border-dreams-border" />
                )}
                <span
                  className={cn(
                    "flex-1 text-sm",
                    item.done
                      ? "text-dreams-textSecondary line-through"
                      : "font-medium text-dreams-textPrimary"
                  )}
                >
                  {item.label}
                </span>
                <svg
                  className="h-4 w-4 text-gray-400"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 5l7 7-7 7"
                  />
                </svg>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
