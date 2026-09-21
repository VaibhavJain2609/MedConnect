"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, CalendarDays } from "lucide-react";

import { getAppointments, type Appointment } from "@/lib/api/appointments";
import { DashboardWidget } from "@/components/dashboard/dashboard-widget";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/ui/status-badge";

const ACTIVE_STATUSES = new Set<Appointment["status"]>([
  "scheduled",
  "arrived",
  "in-progress",
]);

const TYPE_LABELS: Record<Appointment["type"], string> = {
  "in-person": "In-person",
  teleconsult: "Teleconsult",
  "follow-up": "Follow-up",
};

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString("en-IN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  });
}

function ScheduleSkeleton() {
  return (
    <div className="space-y-3" aria-hidden>
      <Skeleton className="h-9 w-28" />
      {[0, 1, 2].map((i) => (
        <div key={i} className="flex items-center gap-4">
          <Skeleton className="h-5 w-16" />
          <div className="flex-1 space-y-1.5">
            <Skeleton className="h-4 w-40" />
            <Skeleton className="h-3 w-24" />
          </div>
          <Skeleton className="h-5 w-20 rounded-full" />
        </div>
      ))}
    </div>
  );
}

/**
 * Today's Schedule widget — total appointments today plus the next three
 * upcoming ones (patient, time, type, status). Backed by
 * GET /api/v1/appointments?date=YYYY-MM-DD.
 */
export function TodaySchedule() {
  // Same convention as /doctor/appointments: UTC date string for the date filter.
  const today = new Date().toISOString().slice(0, 10);

  const query = useQuery({
    queryKey: ["doctor-dashboard-schedule", today],
    queryFn: () => getAppointments({ date: today }),
    refetchInterval: 60_000,
  });

  const appointments = query.data?.data ?? [];
  const total = query.data?.total ?? appointments.length;
  const now = Date.now();
  const nextUp = appointments
    .filter(
      (a) =>
        ACTIVE_STATUSES.has(a.status) &&
        new Date(a.scheduled_at).getTime() >= now
    )
    .slice(0, 3);

  return (
    <DashboardWidget
      title="Today's Schedule"
      icon={CalendarDays}
      headerAction={
        <Link
          href="/doctor/appointments"
          className="inline-flex items-center gap-1 text-sm font-medium text-dreams-blue hover:underline"
        >
          View all
          <ArrowRight className="h-3.5 w-3.5" aria-hidden />
        </Link>
      }
      isLoading={query.isLoading}
      isError={query.isError}
      onRetry={() => query.refetch()}
      errorMessage="Couldn't load today's schedule."
      skeleton={<ScheduleSkeleton />}
    >
      {appointments.length === 0 ? (
        <EmptyState
          icon={CalendarDays}
          title="No appointments today"
          description="Your schedule is clear. New bookings will appear here."
          className="py-8"
        />
      ) : (
        <div>
          <p className="text-sm text-dreams-textSecondary">
            <span className="text-2xl font-bold text-dreams-textPrimary">
              {total}
            </span>{" "}
            appointment{total === 1 ? "" : "s"} today
          </p>

          {nextUp.length > 0 ? (
            <ul className="mt-4 divide-y divide-dreams-border">
              {nextUp.map((appt) => (
                <li
                  key={appt.id}
                  className="flex items-center gap-4 py-3 first:pt-0 last:pb-0"
                >
                  <span className="w-16 shrink-0 text-sm font-medium tabular-nums text-dreams-textPrimary">
                    {formatTime(appt.scheduled_at)}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-dreams-textPrimary">
                      {appt.patient_name ?? "Unknown patient"}
                      {appt.is_provisional && (
                        <span className="ml-1.5 text-xs text-status-pending">
                          (walk-in)
                        </span>
                      )}
                    </p>
                    <p className="text-xs text-dreams-textSecondary">
                      {TYPE_LABELS[appt.type] ?? appt.type}
                    </p>
                  </div>
                  <StatusBadge status={appt.status} />
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm text-dreams-textSecondary">
              No upcoming appointments left today.
            </p>
          )}
        </div>
      )}
    </DashboardWidget>
  );
}
