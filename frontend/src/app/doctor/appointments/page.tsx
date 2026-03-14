"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Calendar, Clock, User, FileText, FilePlus, CheckCircle, XCircle, UserCheck } from "lucide-react";
import Link from "next/link";
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

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString("en-IN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  });
}

function formatDateInput(d: Date) {
  return d.toISOString().slice(0, 10);
}

interface StatusActionButtonProps {
  appt: Appointment;
  onAction: (apptId: string, newStatus: string) => void;
  isPending: boolean;
}

function StatusActionButtons({ appt, onAction, isPending }: StatusActionButtonProps) {
  const actions: { label: string; nextStatus: string; icon: React.ReactNode; className: string }[] = [];

  if (appt.status === "scheduled") {
    actions.push({
      label: "Mark Arrived",
      nextStatus: "arrived",
      icon: <UserCheck className="h-3.5 w-3.5" />,
      className: "bg-blue-50 text-blue-700 hover:bg-blue-100",
    });
    actions.push({
      label: "No Show",
      nextStatus: "no-show",
      icon: <XCircle className="h-3.5 w-3.5" />,
      className: "bg-gray-50 text-gray-600 hover:bg-gray-100",
    });
  }
  if (appt.status === "arrived") {
    actions.push({
      label: "Start",
      nextStatus: "in-progress",
      icon: <Clock className="h-3.5 w-3.5" />,
      className: "bg-yellow-50 text-yellow-700 hover:bg-yellow-100",
    });
  }
  if (appt.status === "in-progress") {
    actions.push({
      label: "Complete",
      nextStatus: "completed",
      icon: <CheckCircle className="h-3.5 w-3.5" />,
      className: "bg-green-50 text-green-700 hover:bg-green-100",
    });
  }

  if (actions.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-1.5 mt-2">
      {actions.map((a) => (
        <button
          key={a.nextStatus}
          disabled={isPending}
          onClick={() => onAction(appt.id, a.nextStatus)}
          className={`flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-medium transition-colors disabled:opacity-50 ${a.className}`}
        >
          {a.icon}
          {a.label}
        </button>
      ))}
    </div>
  );
}

export default function DoctorAppointmentsPage() {
  const today = formatDateInput(new Date());
  const [selectedDate, setSelectedDate] = useState(today);
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["doctor-appointments", selectedDate],
    queryFn: () => getAppointments({ date: selectedDate }),
  });

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      updateAppointmentStatus(id, { status: status as any }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["doctor-appointments", selectedDate] });
    },
  });

  const appointments: Appointment[] = data?.data ?? [];

  const isToday = selectedDate === today;
  const displayDate = new Date(selectedDate + "T00:00:00").toLocaleDateString("en-IN", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  return (
    <div className="space-y-6">
      <Breadcrumb
        items={[
          { label: "Dashboard", href: "/doctor/dashboard" },
          { label: "Appointments" },
        ]}
      />

      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-dreams-textPrimary">Appointments</h1>
          <p className="text-sm text-dreams-textSecondary mt-0.5">
            {isToday ? "Today's schedule" : displayDate}
          </p>
        </div>

        {/* Date picker */}
        <div className="flex items-center gap-2">
          <Calendar className="h-4 w-4 text-dreams-textSecondary" />
          <input
            type="date"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
            className="rounded-lg border border-dreams-border bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
          />
          {!isToday && (
            <button
              onClick={() => setSelectedDate(today)}
              className="rounded-lg border border-dreams-border bg-white px-3 py-2 text-sm text-dreams-textSecondary hover:bg-gray-50"
            >
              Today
            </button>
          )}
        </div>
      </div>

      {/* Summary */}
      {!isLoading && (
        <div className="flex items-center gap-2 text-sm text-dreams-textSecondary">
          <span className="font-medium text-dreams-textPrimary">{appointments.length}</span>
          {appointments.length === 1 ? " appointment" : " appointments"} scheduled
        </div>
      )}

      {/* Loading */}
      {isLoading && (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-200 border-t-dreams-blue" />
        </div>
      )}

      {/* Empty state */}
      {!isLoading && appointments.length === 0 && (
        <div className="rounded-xl border border-dreams-border bg-white p-12 text-center shadow-card">
          <Calendar className="mx-auto h-10 w-10 text-dreams-textSecondary opacity-50" />
          <p className="mt-3 font-medium text-dreams-textPrimary">No appointments</p>
          <p className="mt-1 text-sm text-dreams-textSecondary">
            {isToday ? "You have no appointments scheduled for today." : `No appointments on ${displayDate}.`}
          </p>
        </div>
      )}

      {/* Appointment cards */}
      {!isLoading && appointments.length > 0 && (
        <div className="space-y-3">
          {appointments.map((appt) => (
            <div
              key={appt.id}
              className="rounded-xl border border-dreams-border bg-white p-4 shadow-card"
            >
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                {/* Left: time + patient info */}
                <div className="flex gap-4">
                  {/* Time slot */}
                  <div className="flex-shrink-0 text-center">
                    <p className="text-base font-bold text-dreams-textPrimary">
                      {formatTime(appt.scheduled_at)}
                    </p>
                    <p className="text-xs text-dreams-textSecondary">{appt.duration_minutes}min</p>
                  </div>

                  {/* Patient & complaint */}
                  <div>
                    <div className="flex items-center gap-2">
                      <User className="h-4 w-4 text-dreams-textSecondary flex-shrink-0" />
                      <span className="font-semibold text-dreams-textPrimary">
                        {appt.patient_name ?? "Unknown Patient"}
                      </span>
                      <Badge variant={TYPE_LABELS[appt.type] ? "upcoming" : "pending"} className="text-xs">
                        {TYPE_LABELS[appt.type] ?? appt.type}
                      </Badge>
                    </div>

                    {appt.chief_complaint && (
                      <p className="mt-1 text-sm text-dreams-textSecondary">
                        Chief complaint: {appt.chief_complaint}
                      </p>
                    )}

                    {appt.clinic_name && (
                      <p className="mt-0.5 text-xs text-dreams-textSecondary">{appt.clinic_name}</p>
                    )}

                    {/* Status actions */}
                    <StatusActionButtons
                      appt={appt}
                      onAction={(id, status) => statusMutation.mutate({ id, status })}
                      isPending={statusMutation.isPending}
                    />

                    {/* Quick links */}
                    {(appt.status === "in-progress" || appt.status === "arrived") && (
                      <div className="flex gap-3 mt-2">
                        <Link
                          href="/doctor/prescriptions/new"
                          className="flex items-center gap-1 text-xs text-dreams-blue hover:underline"
                        >
                          <FilePlus className="h-3.5 w-3.5" />
                          New Prescription
                        </Link>
                        <Link
                          href="/doctor/records/new"
                          className="flex items-center gap-1 text-xs text-dreams-blue hover:underline"
                        >
                          <FileText className="h-3.5 w-3.5" />
                          New Record
                        </Link>
                      </div>
                    )}
                  </div>
                </div>

                {/* Right: status badge */}
                <div className="flex-shrink-0">
                  <Badge variant={STATUS_VARIANT_MAP[appt.status] as any}>
                    {STATUS_LABELS[appt.status] ?? appt.status}
                  </Badge>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
