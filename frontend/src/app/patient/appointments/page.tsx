"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Calendar, Clock, Stethoscope, Building2, XCircle, Plus, X } from "lucide-react";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { Badge } from "@/components/ui/badge";
import { getAppointments, updateAppointmentStatus, createAppointment, type Appointment } from "@/lib/api/appointments";
import { useAuthStore } from "@/stores/auth-store";
import api from "@/lib/api";

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

function formatDateInput(d: Date) {
  return d.toISOString().slice(0, 10);
}

function isUpcoming(appt: Appointment) {
  return (
    (appt.status === "scheduled" || appt.status === "arrived" || appt.status === "in-progress") &&
    new Date(appt.scheduled_at) >= new Date()
  );
}

// ---------------------------------------------------------------------------
// Doctor search typeahead
// ---------------------------------------------------------------------------

interface DoctorSuggestion {
  id: string;
  full_name: string;
  specialization: string | null;
  facility_name: string | null;
  facility_city: string | null;
}

function DoctorSearchInput({
  onSelect,
}: {
  onSelect: (d: DoctorSuggestion) => void;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<DoctorSuggestion[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const search = useCallback((q: string) => {
    if (q.length < 2) {
      setResults([]);
      setOpen(false);
      return;
    }
    setLoading(true);
    api
      .get(`/api/v1/patients/doctors/search?q=${encodeURIComponent(q)}`)
      .then((res) => {
        setResults(res.data.data || []);
        setOpen(true);
      })
      .catch(() => setResults([]))
      .finally(() => setLoading(false));
  }, []);

  // Cleanup pending debounce on unmount to prevent state updates on unmounted component
  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setQuery(val);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => search(val), 400);
  };

  return (
    <div className="relative">
      <input
        type="text"
        value={query}
        onChange={handleChange}
        placeholder="Search doctor by name or specialization..."
        className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
        onFocus={() => results.length > 0 && setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
      />
      {loading && (
        <div className="absolute right-3 top-1/2 -translate-y-1/2">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-dreams-blue border-t-transparent" />
        </div>
      )}
      {open && results.length > 0 && (
        <div className="absolute z-50 mt-1 w-full rounded-lg border border-dreams-border bg-white shadow-lg">
          {results.map((d) => (
            <button
              key={d.id}
              type="button"
              className="flex w-full items-start gap-3 px-4 py-3 text-left hover:bg-dreams-lightBg transition-colors"
              onMouseDown={() => {
                onSelect(d);
                setQuery("");
                setOpen(false);
              }}
            >
              <div className="flex-1">
                <p className="text-sm font-medium text-dreams-textPrimary">{d.full_name}</p>
                {d.specialization && (
                  <p className="text-xs text-dreams-textSecondary">{d.specialization}</p>
                )}
                {d.facility_name && (
                  <p className="text-xs text-dreams-textSecondary">{d.facility_name}{d.facility_city ? `, ${d.facility_city}` : ""}</p>
                )}
              </div>
            </button>
          ))}
        </div>
      )}
      {open && results.length === 0 && !loading && query.length >= 2 && (
        <div className="absolute z-50 mt-1 w-full rounded-lg border border-dreams-border bg-white px-4 py-3 text-sm text-dreams-textSecondary shadow-lg">
          No doctors found.
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// BookAppointmentModal
// ---------------------------------------------------------------------------

interface BookAppointmentModalProps {
  onClose: () => void;
  onSuccess: () => void;
  patientId: string;
}

function BookAppointmentModal({ onClose, onSuccess, patientId }: BookAppointmentModalProps) {
  const [selectedClinicId, setSelectedClinicId] = useState("");
  const [selectedDoctor, setSelectedDoctor] = useState<DoctorSuggestion | null>(null);
  const [date, setDate] = useState(formatDateInput(new Date()));
  const [time, setTime] = useState("09:00");
  const [duration, setDuration] = useState(30);
  const [type, setType] = useState<"in-person" | "teleconsult" | "follow-up">("in-person");
  const [chiefComplaint, setChiefComplaint] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  // Load patient's approved clinic links
  const { data: clinicLinksData } = useQuery({
    queryKey: ["patient-clinic-links"],
    queryFn: () => api.get("/api/v1/patients/clinic-links").then((r) => r.data),
  });
  const approvedClinics: { id: string; clinic_id: string; clinic_name: string }[] =
    (clinicLinksData?.data ?? []).filter((l: any) => l.consent_status === "approved");

  // Load doctors at selected clinic
  const { data: clinicDoctorsData } = useQuery({
    queryKey: ["clinic-doctors", selectedClinicId],
    queryFn: () =>
      api.get(`/api/v1/clinics/${selectedClinicId}/doctors`).then((r) => r.data),
    enabled: !!selectedClinicId,
  });
  const clinicDoctors: DoctorSuggestion[] = clinicDoctorsData?.data ?? [];

  // Reset doctor when clinic changes
  const handleClinicChange = (clinicId: string) => {
    setSelectedClinicId(clinicId);
    setSelectedDoctor(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!selectedDoctor) {
      setError("Please select a doctor");
      return;
    }
    setSubmitting(true);
    try {
      const scheduledAt = new Date(`${date}T${time}:00`).toISOString();
      await createAppointment({
        patient_id: patientId,
        doctor_id: selectedDoctor.id,
        clinic_id: selectedClinicId || undefined,
        scheduled_at: scheduledAt,
        duration_minutes: duration,
        type,
        chief_complaint: chiefComplaint || undefined,
      });
      onSuccess();
      onClose();
    } catch (err: any) {
      const msg =
        err.response?.data?.detail?.error?.message ||
        err.response?.data?.detail ||
        "Failed to book appointment";
      setError(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-[calc(100%-2rem)] sm:w-full sm:max-w-lg rounded-xl bg-white shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-dreams-border px-6 py-4">
          <h2 className="text-lg font-semibold text-dreams-textPrimary">Book Appointment</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-dreams-textSecondary hover:text-dreams-textPrimary"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-4 space-y-4">
          {error && (
            <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-2 text-sm text-red-700">
              {error}
            </div>
          )}

          {/* Clinic */}
          {approvedClinics.length > 0 && (
            <div>
              <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">
                Clinic
              </label>
              <select
                value={selectedClinicId}
                onChange={(e) => handleClinicChange(e.target.value)}
                className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20 bg-white"
              >
                <option value="">Any clinic / search by name</option>
                {approvedClinics.map((c) => (
                  <option key={c.clinic_id} value={c.clinic_id}>
                    {c.clinic_name}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Doctor */}
          <div>
            <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">
              Doctor *
            </label>
            {selectedClinicId ? (
              // Clinic selected → show dropdown of that clinic's doctors
              clinicDoctors.length === 0 ? (
                <p className="text-sm text-dreams-textSecondary py-2">No verified doctors at this clinic yet.</p>
              ) : (
                <select
                  value={selectedDoctor?.id ?? ""}
                  onChange={(e) => {
                    const doc = clinicDoctors.find((d) => d.id === e.target.value) ?? null;
                    setSelectedDoctor(doc);
                  }}
                  className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20 bg-white"
                >
                  <option value="">Select doctor…</option>
                  {clinicDoctors.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.full_name}{d.specialization ? ` — ${d.specialization}` : ""}
                    </option>
                  ))}
                </select>
              )
            ) : selectedDoctor ? (
              <div className="flex items-center gap-3 rounded-lg border border-dreams-blue bg-dreams-blue/5 px-4 py-2.5">
                <div className="flex-1">
                  <p className="text-sm font-semibold text-dreams-textPrimary">{selectedDoctor.full_name}</p>
                  {selectedDoctor.specialization && (
                    <p className="text-xs text-dreams-textSecondary">{selectedDoctor.specialization}</p>
                  )}
                  {selectedDoctor.facility_name && (
                    <p className="text-xs text-dreams-textSecondary">{selectedDoctor.facility_name}</p>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedDoctor(null)}
                  className="text-dreams-textSecondary hover:text-red-500 transition-colors"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ) : (
              <DoctorSearchInput onSelect={setSelectedDoctor} />
            )}
          </div>

          {/* Date + Time */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">Date *</label>
              <input
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                min={formatDateInput(new Date())}
                required
                className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">Time *</label>
              <input
                type="time"
                value={time}
                onChange={(e) => setTime(e.target.value)}
                required
                className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
              />
            </div>
          </div>

          {/* Duration + Type */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">Duration</label>
              <select
                value={duration}
                onChange={(e) => setDuration(Number(e.target.value))}
                className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
              >
                <option value={15}>15 min</option>
                <option value={30}>30 min</option>
                <option value={45}>45 min</option>
                <option value={60}>60 min</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">Type *</label>
              <select
                value={type}
                onChange={(e) => setType(e.target.value as typeof type)}
                className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
              >
                <option value="in-person">In Person</option>
                <option value="teleconsult">Teleconsult</option>
                <option value="follow-up">Follow-up</option>
              </select>
            </div>
          </div>

          {/* Chief Complaint */}
          <div>
            <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">
              Chief Complaint
            </label>
            <input
              type="text"
              value={chiefComplaint}
              onChange={(e) => setChiefComplaint(e.target.value)}
              placeholder="e.g., Fever, headache for 2 days"
              className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
            />
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-2">
            <button
              type="submit"
              disabled={submitting || !selectedDoctor}
              className="flex-1 rounded-lg bg-dreams-blue px-4 py-2.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50 transition-opacity"
            >
              {submitting ? "Booking..." : "Book Appointment"}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-dreams-border px-4 py-2.5 text-sm font-medium text-dreams-textPrimary hover:bg-dreams-lightBg transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Appointment card
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function PatientAppointmentsPage() {
  const [tab, setTab] = useState<"upcoming" | "past">("upcoming");
  const [showBooking, setShowBooking] = useState(false);
  const { user } = useAuthStore();
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
      {showBooking && user && (
        <BookAppointmentModal
          patientId={user.id}
          onClose={() => setShowBooking(false)}
          onSuccess={() => {
            queryClient.invalidateQueries({ queryKey: ["patient-appointments"] });
          }}
        />
      )}

      <Breadcrumb
        items={[
          { label: "Health Timeline", href: "/patient/timeline" },
          { label: "Appointments" },
        ]}
      />

      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-dreams-textPrimary">My Appointments</h1>
        <button
          onClick={() => setShowBooking(true)}
          className="flex items-center gap-2 rounded-lg bg-dreams-blue px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
        >
          <Plus className="h-4 w-4" />
          Book Appointment
        </button>
      </div>

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
