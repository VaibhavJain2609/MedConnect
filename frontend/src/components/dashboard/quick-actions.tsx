"use client";

import Link from "next/link";
import { CalendarCheck, FilePlus, FileText, Zap } from "lucide-react";

import { DashboardWidget } from "@/components/dashboard/dashboard-widget";
import { Button } from "@/components/ui/button";

const ACTIONS = [
  {
    href: "/doctor/prescriptions/new",
    label: "New Prescription",
    description: "Write a prescription",
    icon: FilePlus,
  },
  {
    href: "/doctor/records/new",
    label: "New Record",
    description: "Create a medical record",
    icon: FileText,
  },
  {
    href: "/doctor/appointments",
    label: "Check Schedule",
    description: "View your appointments",
    icon: CalendarCheck,
  },
];

/**
 * Quick Actions — primary shortcuts for the doctor's most common tasks.
 */
export function QuickActions() {
  return (
    <DashboardWidget title="Quick Actions" icon={Zap}>
      <div className="grid gap-3 sm:grid-cols-3">
        {ACTIONS.map(({ href, label, description, icon: Icon }) => (
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
                  {label}
                </span>
                <span className="block whitespace-normal text-xs font-normal text-dreams-textSecondary">
                  {description}
                </span>
              </span>
            </Link>
          </Button>
        ))}
      </div>
    </DashboardWidget>
  );
}
