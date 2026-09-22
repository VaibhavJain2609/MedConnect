"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { CalendarCheck, FilePlus, FileText, Zap } from "lucide-react";

import { DashboardWidget } from "@/components/dashboard/dashboard-widget";
import { Button } from "@/components/ui/button";

// Keys under the "doctorDashboard.quickActions" namespace — keep in sync
// with messages/en.json + hi.json (see docs/i18n.md).
const ACTIONS = [
  {
    href: "/doctor/prescriptions/new",
    labelKey: "newPrescription",
    descriptionKey: "newPrescriptionHint",
    icon: FilePlus,
  },
  {
    href: "/doctor/records/new",
    labelKey: "newRecord",
    descriptionKey: "newRecordHint",
    icon: FileText,
  },
  {
    href: "/doctor/appointments",
    labelKey: "checkSchedule",
    descriptionKey: "checkScheduleHint",
    icon: CalendarCheck,
  },
] as const;

/**
 * Quick Actions — primary shortcuts for the doctor's most common tasks.
 */
export function QuickActions() {
  const t = useTranslations("doctorDashboard.quickActions");

  return (
    <DashboardWidget title={t("title")} icon={Zap}>
      <div className="grid gap-3 sm:grid-cols-3">
        {ACTIONS.map(({ href, labelKey, descriptionKey, icon: Icon }) => (
          <Button
            key={href}
            asChild
            variant="outline"
            className="h-auto justify-start gap-3 border-dreams-border p-4 text-left hover:border-dreams-blue/50 hover:bg-dreams-lightBg/60"
          >
            <Link href={href}>
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-dreams-blue/10 text-dreams-blue">
                <Icon className="h-5 w-5" aria-hidden />
              </span>
              <span className="min-w-0">
                <span className="block whitespace-normal text-sm font-semibold text-dreams-textPrimary">
                  {t(labelKey)}
                </span>
                <span className="block whitespace-normal text-xs font-normal text-dreams-textSecondary">
                  {t(descriptionKey)}
                </span>
              </span>
            </Link>
          </Button>
        ))}
      </div>
    </DashboardWidget>
  );
}
