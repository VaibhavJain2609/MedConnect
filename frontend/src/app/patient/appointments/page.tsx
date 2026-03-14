"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Calendar, Clock, Stethoscope, Building2, XCircle, Plus } from "lucide-react";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { Badge } from "@/components/ui/badge";
import { getAppointments, updateAppointmentStatus, type Appointment } from "@/lib/api/appointments";

const TYPE_LABELS: Record<string, string> = {
  "in-person": "In Person",
  "teleconsult": "Teleconsult",
  "follow-up": "Follow-up",
};

const STATUS_VARIANT_MAP: Record<string, string> = {
  scheduled: "upcoming",
  arrived: "inProgress",
  "in-progress": "inProgress",
  completed: "completed",
  cancelled: "overdue",
  "no-show": "pending",
};

const STATUS_LABELS: Record<string, string> = {
  scheduled: "Scheduled",
  arrived: "Arrived",
  "in-progress": "In Progress",
  completed: "Completed",
  cancelled: "Cancelled",
  "no-show": "No Show",
};

function formatDateTime(iso: string) {
  const d = new Date(iso);
  return {
    date: d.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short", year: "numeric" }),
    time: d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: true }),
  };
}

function isUpcoming(appt: Appointment) {
  return (
    (appt.status === "scheduled" || appt.status === "arrived" || appt.status === "in-progress") &&
    new Date(appt.scheduled_at) >= new Date()
  );
}

function AppointmentCard({
  appt,
  onCancel,
  isCancelling,
}: {
  appt: Appointment;
  onCancel: (id: string) => void;
  isCancelling: boolean;
}) {
  const { date, time } = formatDateTime(appt.scheduled_at);
  const canCancel = appt.status === "scheduled";

  return (
    <div className="rounded-xl border border-dreams-border bg-white p-4 shadow-card">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        {/* Left content */}
        <div className="flex gap-4">
          {/* Date/time block */}
          <div className="flex-shrink-0 min-w-[80px]">
            <p className="text-sm font-bold text-dreams-textPrimary">{date}</p>
            <p className="flex items-center gap-1 text-sm text-dreams-textSecondary mt-0.5">
              <Clock className="h-3.5 w-3.5" />
              {time}
            </p>
            <p className="text-xs text-dreams-textSecondary mt-0.5">{appt.duration_minutes}min</p>
          </div>

          {/* Details */}
          <div>
            {appt.doctor_name && (
              <div className="flex items-center gap-1.5">
                <Stethoscope className="h-4 w-4 text-dreams-textSecondary flex-shrink-0" />
                <span className="font-semibold text-dreams-textPrimary">{appt.doctor_name}</span>
              </div>
            )}

            {appt.clinic_name && (
              <div className="flex items-center gap-1.5 mt-1">
                <Building2 className="h-3.5 w-3.5 text-dreams-textSecondary flex-shrink-0" />
                <span className="text-sm text-dreams-textSecondary">{appt.clinic_name}</span>
              </div>
            )}

            <div className="mt-1.5 flex items-center gap-2">
              <Badge variant="upcoming" className="text-xs">
                {TYPE_LABELS[appt.type] ?? appt.type}
              </Badge>
            </div>

            {appt.chief_complaint && (
              <p className="mt-1.5 text-sm text-dreams-textSecondary">
                {appt.chief_complaint}
              </p>
            )}

            {/* Cancel button */}
            {canCancel && (
              <button
                disabled={isCancelling}
                onClick={() => onCancel(appt.id)}
                className="mt-2 flex items-center gap-1 rounded-md bg-red-50 px-2.5 py-1 text-xs font-medium text-red-700 hover:bg-red-100 disabled:opacity-50 transition-colors"
              >
                <XCircle className="h-3.5 w-3.5" />
                Cancel Appointment
              </button>
            )}
          </div>
        </div>

        {/* Status badge */}
        <div className="flex-shrink-0">
          <Badge variant={STATUS_VARIANT_MAP[appt.status] as any}>
            {STATUS_LABELS[appt.status] ?? appt.status}
          </Badge>
        </div>
      </div>
    </div>
  );
}

export default function PatientAppointmentsPage() {
  const [tab, setTab] = useState<"upcoming" | "past">("upcoming");
  const [showBooking, setShowBooking] = useState(false);
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["patient-appointments"],
    queryFn: () => getAppointments({}),
  });

  const cancelMutation = useMutation({
    mutationFn: (id: string) =>
      updateAppointmentStatus(id, { status: "cancelled", cancelled_reason: "Cancelled by patient" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["patient-appointments"] });
    },
  });

  const allAppointments: Appointment[] = data?.data ?? [];
  const upcomingAppointments = allAppointments.filter(isUpcoming).sort(
    (a, b) => new Date(a.scheduled_at).getTime() - new Date(b.scheduled_at).getTime()
  );
  const pastAppointments = allAppointments
    .filter((a) => !isUpcoming(a))
    .sort((a, b) => new Date(b.scheduled_at).getTime() - new Date(a.scheduled_at).getTime());

  const displayedAppointments = tab === "upcoming" ? upcomingAppointments : pastAppointments;

  return (
    <div className="space-y-6">
      <Breadcrumb
        items={[
          { label: "Health Timeline", href: "/patient/timeline" },
          { label: "Appointments" },
        ]}
      />

      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-dreams-textPrimary">My Appointments</h1>
        <button
          onClick={() => setShowBooking(!showBooking)}
          className="flex items-center gap-2 rounded-lg bg-dreams-blue px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
        >
          <Plus className="h-4 w-4" />
          Book Appointment
        </button>
      </div>

      {/* "Book Appointment" coming-soon banner */}
      {showBooking && (
        <div className="rounded-xl border border-dreams-border bg-blue-50 p-4 shadow-card">
          <p className="font-medium text-dreams-textPrimary">Book Appointment</p>
          <p className="mt-1 text-sm text-dreams-textSecondary">
            Online appointment booking is coming soon. Please contact your doctor or clinic to schedule an appointment.
          </p>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 rounded-lg border border-dreams-border bg-gray-100 p-1 w-fit">
        {[
          { key: "upcoming", label: `Upcoming (${upcomingAppointments.length})` },
          { key: "past", label: `Past (${pastAppointments.length})` },
        ].map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setTab(key as "upcoming" | "past")}
            className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
              tab === key
                ? "bg-white shadow-sm text-dreams-textPrimary"
                : "text-dreams-textSecondary hover:text-dreams-textPrimary"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-200 border-t-dreams-blue" />
        </div>
      )}

      {/* Empty state */}
      {!isLoading && displayedAppointments.length === 0 && (
        <div className="rounded-xl border border-dreams-border bg-white p-12 text-center shadow-card">
          <Calendar className="mx-auto h-10 w-10 text-dreams-textSecondary opacity-50" />
          <p className="mt-3 font-medium text-dreams-textPrimary">
            {tab === "upcoming" ? "No upcoming appointments" : "No past appointments"}
          </p>
          <p className="mt-1 text-sm text-dreams-textSecondary">
            {tab === "upcoming"
              ? "You have no scheduled appointments. Use 'Book Appointment' to schedule one."
              : "Your completed and cancelled appointments will appear here."}
          </p>
        </div>
      )}

      {/* Appointment list */}
      {!isLoading && displayedAppointments.length > 0 && (
        <div className="space-y-3">
          {displayedAppointments.map((appt) => (
            <AppointmentCard
              key={appt.id}
              appt={appt}
              onCancel={(id) => cancelMutation.mutate(id)}
              isCancelling={cancelMutation.isPending}
            />
          ))}
        </div>
      )}
    </div>
  );
}
