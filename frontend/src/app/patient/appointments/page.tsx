"use client";

import * as React from "react";
import { useState, useRef, useCallback, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { Calendar, CalendarClock, Clock, Stethoscope, Building2, XCircle, Plus, X, Link2, Video, BadgeCheck } from "lucide-react";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { Badge } from "@/components/ui/badge";
import { Pagination } from "@/components/ui/pagination";
import { getAppointments, updateAppointmentStatus, createAppointment, generateMeetingLink, rescheduleAppointment, type Appointment } from "@/lib/api/appointments";
import { getDoctorSlots, type AvailabilitySlot } from "@/lib/api/availability";
import { joinWaitlist, getMyWaitlist, cancelWaitlistEntry, type WaitlistEntry } from "@/lib/api/waitlist";
import { SlotPicker, slotDurationMinutes } from "@/components/appointments/slot-picker";
import { useAuthStore } from "@/stores/auth-store";
import { toast } from "@/hooks/use-toast";
import api from "@/lib/api";
import { useFormatter, useTranslations } from "next-intl";

// Values double as message keys under appointments.types / appointments.status
// — keep them in sync with messages/en.json + hi.json (see docs/i18n.md).
type EnMessages = typeof import("../../../../messages/en.json");
type AppointmentTypeKey = keyof EnMessages["appointments"]["types"];
type AppointmentStatusKey = keyof EnMessages["appointments"]["status"];

const TYPE_KEYS: Record<string, AppointmentTypeKey> = {
  "in-person": "in-person",
  "teleconsult": "teleconsult",
  "follow-up": "follow-up",
};

type BadgeVariant = "upcoming" | "inProgress" | "completed" | "overdue" | "pending";

const STATUS_VARIANT_MAP: Record<string, BadgeVariant> = {
  scheduled: "upcoming",
  arrived: "inProgress",
  "in-progress": "inProgress",
  completed: "completed",
  cancelled: "overdue",
  "no-show": "pending",
};

const STATUS_KEYS: Record<string, AppointmentStatusKey> = {
  scheduled: "scheduled",
  arrived: "arrived",
  "in-progress": "in-progress",
  completed: "completed",
  cancelled: "cancelled",
  "no-show": "no-show",
};

/** Local date formatted as YYYY-MM-DD (toISOString is UTC and rolls back a day in IST). */
function formatDateInput(d: Date) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function isUpcoming(appt: Appointment) {
  return (
    (appt.status === "scheduled" || appt.status === "arrived" || appt.status === "in-progress") &&
    new Date(appt.scheduled_at) >= new Date()
  );
}

/** Patients may join a teleconsult call starting ~10 minutes before the scheduled time. */
const TELECONSULT_JOIN_WINDOW_MS = 10 * 60 * 1000;

function canJoinTeleconsult(appt: Appointment, now: number) {
  return now >= new Date(appt.scheduled_at).getTime() - TELECONSULT_JOIN_WINDOW_MS;
}

const ACTIVE_STATUSES = ["scheduled", "arrived", "in-progress"];

/**
 * Fetch every appointment for the list view. The page splits results into
 * upcoming/past tabs client-side (the backend only supports upcoming/date
 * filtering for doctors and clinic staff), so it needs the full set — the
 * endpoint paginates with limit/offset (max 100 per request) and returns a
 * total, so we walk the offset until all rows are fetched.
 */
async function fetchAllAppointments(): Promise<Appointment[]> {
  const PAGE = 100;
  const MAX_PAGES = 10; // safety cap: 1000 appointments
  const all: Appointment[] = [];
  for (let i = 0; i < MAX_PAGES; i++) {
    const res = await getAppointments({ limit: PAGE, offset: i * PAGE });
    all.push(...res.data);
    if (all.length >= res.total || res.data.length < PAGE) break;
  }
  return all;
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
  verified?: boolean;
}

function DoctorSearchInput({
  onSelect,
  id,
}: {
  onSelect: (d: DoctorSuggestion) => void;
  id?: string;
}) {
  const t = useTranslations("appointments");
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
        id={id}
        type="text"
        value={query}
        onChange={handleChange}
        placeholder={t("booking.doctorSearchPlaceholder")}
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
                <p className="flex items-center gap-1.5 text-sm font-medium text-dreams-textPrimary">
                  {d.full_name}
                  {d.verified && <BadgeCheck className="h-4 w-4 text-dreams-blue" aria-label={t("booking.verifiedDoctor")} />}
                </p>
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
          {t("booking.noDoctorsFound")}
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
  const t = useTranslations("appointments");
  const [selectedClinicId, setSelectedClinicId] = useState("");
  const [selectedDoctor, setSelectedDoctor] = useState<DoctorSuggestion | null>(null);
  const [date, setDate] = useState(formatDateInput(new Date()));
  const [time, setTime] = useState("09:00");
  const [duration, setDuration] = useState(30);
  const [type, setType] = useState<"in-person" | "teleconsult" | "follow-up">("in-person");
  const [chiefComplaint, setChiefComplaint] = useState("");
  const [selectedSlot, setSelectedSlot] = useState<AvailabilitySlot | null>(null);
  const [customTime, setCustomTime] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  // Double-submit protection: one key per form-mount; regenerated after a
  // successful submit so a deliberate second booking is a fresh operation.
  const [idempotencyKey, setIdempotencyKey] = useState(() => crypto.randomUUID());
  const [waitlistState, setWaitlistState] = useState<"idle" | "joining" | "joined" | "already">("idle");
  const [waitlistError, setWaitlistError] = useState("");

  // Close modal on Escape
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  // Load patient's approved clinic links
  const { data: clinicLinksData, isLoading: clinicLinksLoading } = useQuery({
    queryKey: ["patient-clinic-links"],
    queryFn: () => api.get("/api/v1/patients/clinic-links").then((r) => r.data),
  });
  const approvedClinics: { id: string; clinic_id: string; clinic_name: string }[] =
    (clinicLinksData?.data ?? []).filter((l: any) => l.consent_status === "approved");
  const noLinkedClinics = !clinicLinksLoading && approvedClinics.length === 0;

  // Load doctors at selected clinic
  const { data: clinicDoctorsData } = useQuery({
    queryKey: ["clinic-doctors", selectedClinicId],
    queryFn: () =>
      api.get(`/api/v1/clinics/${selectedClinicId}/doctors`).then((r) => r.data),
    enabled: !!selectedClinicId,
  });
  const clinicDoctors: DoctorSuggestion[] = clinicDoctorsData?.data ?? [];

  // Fetch bookable slots once doctor + date are known. Scoped to the selected
  // clinic so only that clinic's availability windows are used.
  const slotsQuery = useQuery({
    queryKey: ["doctor-slots", selectedDoctor?.id, date, selectedClinicId],
    queryFn: () =>
      getDoctorSlots(selectedDoctor!.id, date, selectedClinicId || undefined),
    enabled: !!selectedDoctor && !!date,
  });
  const slots: AvailabilitySlot[] = slotsQuery.data?.slots ?? [];
  const slotsEnabled = !!selectedDoctor && !!date;
  // Manual time/duration entry is the fallback: no doctor picked yet, user
  // opted for a custom time, slots failed to load, or none were published.
  const showManualTime =
    !slotsEnabled ||
    customTime ||
    slotsQuery.isError ||
    (slotsQuery.isFetched && slots.length === 0);
  // Slot picker governs scheduled_at/duration whenever it's shown and the
  // user hasn't fallen back to manual entry.
  const requireSlot = slotsEnabled && !showManualTime;
  // The waitlist offer only makes sense once we KNOW the day has no bookable
  // slots (fetch completed, no error, empty list).
  const noSlotsForDay = slotsEnabled && slotsQuery.isFetched && !slotsQuery.isError && slots.length === 0;

  const resetTimeSelection = () => {
    setSelectedSlot(null);
    setCustomTime(false);
    setWaitlistState("idle");
    setWaitlistError("");
  };

  const handleJoinWaitlist = async () => {
    if (!selectedDoctor) return;
    setWaitlistState("joining");
    setWaitlistError("");
    try {
      await joinWaitlist({
        doctor_id: selectedDoctor.id,
        desired_date: date,
        clinic_id: selectedClinicId || undefined,
      });
      setWaitlistState("joined");
    } catch (err: any) {
      // 409 = already waiting on this doctor+day — show the friendly state.
      if (err?.response?.status === 409) {
        setWaitlistState("already");
      } else {
        setWaitlistState("idle");
        setWaitlistError(t("waitlist.joinError"));
      }
    }
  };

  // Reset doctor when clinic changes
  const handleClinicChange = (clinicId: string) => {
    setSelectedClinicId(clinicId);
    setSelectedDoctor(null);
    resetTimeSelection();
  };

  const handleDoctorChange = (d: DoctorSuggestion | null) => {
    setSelectedDoctor(d);
    resetTimeSelection();
  };

  const handleDateChange = (value: string) => {
    setDate(value);
    resetTimeSelection();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!selectedDoctor) {
      setError(t("booking.errorSelectDoctor"));
      return;
    }
    if (requireSlot && !selectedSlot) {
      setError(t("booking.errorSelectSlot"));
      return;
    }
    setSubmitting(true);
    try {
      // A picked slot supplies the exact scheduled_at/duration the backend
      // computed (slot.start is the bookable instant verbatim), plus the
      // clinic/branch of the underlying availability window. Manual entry
      // falls back to the date+time inputs.
      const scheduledAt = selectedSlot
        ? selectedSlot.start
        : new Date(`${date}T${time}:00`).toISOString();
      const durationMinutes = selectedSlot
        ? slotDurationMinutes(selectedSlot)
        : duration;
      await createAppointment({
        patient_id: patientId,
        doctor_id: selectedDoctor.id,
        clinic_id: selectedSlot?.clinic_id ?? (selectedClinicId || undefined),
        branch_id: selectedSlot?.branch_id ?? undefined,
        scheduled_at: scheduledAt,
        duration_minutes: durationMinutes,
        type,
        chief_complaint: chiefComplaint || undefined,
      }, idempotencyKey);
      setIdempotencyKey(crypto.randomUUID());
      onSuccess();
      onClose();
    } catch (err: any) {
      const msg =
        err.response?.data?.detail?.error?.message ||
        err.response?.data?.detail ||
        t("booking.errorFailed");
      setError(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={t("booking.ariaLabel")}
        className="w-[calc(100%-2rem)] sm:w-full sm:max-w-lg rounded-xl bg-white shadow-xl max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-dreams-border px-6 py-4">
          <h2 className="text-lg font-semibold text-dreams-textPrimary">{t("booking.title")}</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("booking.close")}
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
          {noLinkedClinics && (
            <div className="flex items-start gap-3 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3">
              <Link2 className="h-4 w-4 mt-0.5 flex-shrink-0 text-blue-600" />
              <p className="text-sm text-blue-800">
                {t.rich("booking.noLinkedClinics", {
                  link: (chunks) => (
                    <Link href="/patient/clinics" className="font-medium underline" onClick={onClose}>
                      {chunks}
                    </Link>
                  ),
                })}
              </p>
            </div>
          )}
          {approvedClinics.length > 0 && (
            <div>
              <label
                htmlFor="booking-clinic"
                className="mb-1 block text-sm font-medium text-dreams-textPrimary"
              >
                {t("booking.clinic")}
              </label>
              <select
                id="booking-clinic"
                value={selectedClinicId}
                onChange={(e) => handleClinicChange(e.target.value)}
                className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20 bg-white"
              >
                <option value="">{t("booking.anyClinic")}</option>
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
            <label
              htmlFor="booking-doctor"
              className="mb-1 block text-sm font-medium text-dreams-textPrimary"
            >
              {t("booking.doctor")}
            </label>
            {selectedClinicId ? (
              // Clinic selected → show dropdown of that clinic's doctors
              clinicDoctors.length === 0 ? (
                <p className="text-sm text-dreams-textSecondary py-2">{t("booking.noClinicDoctors")}</p>
              ) : (
                <select
                  id="booking-doctor"
                  value={selectedDoctor?.id ?? ""}
                  onChange={(e) => {
                    const doc = clinicDoctors.find((d) => d.id === e.target.value) ?? null;
                    handleDoctorChange(doc);
                  }}
                  className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20 bg-white"
                >
                  <option value="">{t("booking.selectDoctor")}</option>
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
                  <p className="flex items-center gap-1.5 text-sm font-semibold text-dreams-textPrimary">
                    {selectedDoctor.full_name}
                    {selectedDoctor.verified && <BadgeCheck className="h-4 w-4 text-dreams-blue" aria-label={t("booking.verifiedDoctor")} />}
                  </p>
                  {selectedDoctor.specialization && (
                    <p className="text-xs text-dreams-textSecondary">{selectedDoctor.specialization}</p>
                  )}
                  {selectedDoctor.facility_name && (
                    <p className="text-xs text-dreams-textSecondary">{selectedDoctor.facility_name}</p>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => handleDoctorChange(null)}
                  aria-label={t("booking.clearDoctor")}
                  className="text-dreams-textSecondary hover:text-red-500 transition-colors"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ) : (
              <DoctorSearchInput id="booking-doctor" onSelect={handleDoctorChange} />
            )}
          </div>

          {/* Date */}
          <div>
            <label htmlFor="booking-date" className="mb-1 block text-sm font-medium text-dreams-textPrimary">{t("booking.date")}</label>
            <input
              id="booking-date"
              type="date"
              value={date}
              onChange={(e) => handleDateChange(e.target.value)}
              min={formatDateInput(new Date())}
              required
              className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
            />
          </div>

          {/* Available slots (doctor + date chosen) */}
          {slotsEnabled && (
            <SlotPicker
              slots={slotsQuery.data?.slots}
              isLoading={slotsQuery.isLoading}
              isError={slotsQuery.isError}
              isRetrying={slotsQuery.isFetching && !slotsQuery.isLoading}
              customTime={customTime}
              selected={selectedSlot}
              onSelect={setSelectedSlot}
              onRetry={() => slotsQuery.refetch()}
              onPickCustomTime={() => {
                setCustomTime(true);
                setSelectedSlot(null);
              }}
              onShowSlots={() => setCustomTime(false)}
            />
          )}

          {/* Waitlist offer — only when the day has no bookable slots */}
          {noSlotsForDay && (
            <div className="rounded-lg border border-dreams-border bg-dreams-lightBg px-4 py-3">
              {waitlistState === "joined" || waitlistState === "already" ? (
                <p className="flex items-center gap-2 text-sm text-dreams-textSecondary">
                  <CalendarClock className="h-4 w-4 flex-shrink-0 text-dreams-blue" />
                  {waitlistState === "joined"
                    ? t("waitlist.joined")
                    : t("waitlist.alreadyJoined")}
                </p>
              ) : (
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm text-dreams-textSecondary">
                    {t("waitlist.offerHint")}
                  </p>
                  <button
                    type="button"
                    onClick={handleJoinWaitlist}
                    disabled={waitlistState === "joining"}
                    className="flex-shrink-0 rounded-lg bg-dreams-blue px-3 py-1.5 text-xs font-medium text-white hover:opacity-90 disabled:opacity-50 transition-opacity"
                  >
                    {waitlistState === "joining" ? t("waitlist.joining") : t("waitlist.joinForDay")}
                  </button>
                </div>
              )}
              {waitlistError && (
                <p className="mt-1.5 text-xs text-red-600">{waitlistError}</p>
              )}
            </div>
          )}

          {/* Manual time + duration fallback */}
          {showManualTime && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label htmlFor="booking-time" className="mb-1 block text-sm font-medium text-dreams-textPrimary">{t("booking.time")}</label>
                <input
                  id="booking-time"
                  type="time"
                  value={time}
                  onChange={(e) => setTime(e.target.value)}
                  required
                  className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
                />
              </div>
              <div>
                <label htmlFor="booking-duration" className="mb-1 block text-sm font-medium text-dreams-textPrimary">{t("booking.duration")}</label>
                <select
                  id="booking-duration"
                  value={duration}
                  onChange={(e) => setDuration(Number(e.target.value))}
                  className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
                >
                  {[15, 30, 45, 60].map((mins) => (
                    <option key={mins} value={mins}>
                      {t("booking.durationOption", { count: mins })}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          )}

          {/* Type */}
          <div>
            <label htmlFor="booking-type" className="mb-1 block text-sm font-medium text-dreams-textPrimary">{t("booking.type")}</label>
            <select
              id="booking-type"
              value={type}
              onChange={(e) => setType(e.target.value as typeof type)}
              className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
            >
              {(Object.keys(TYPE_KEYS) as AppointmentTypeKey[]).map((key) => (
                <option key={key} value={key}>
                  {t(`types.${key}`)}
                </option>
              ))}
            </select>
          </div>

          {/* Chief Complaint */}
          <div>
            <label htmlFor="booking-complaint" className="mb-1 block text-sm font-medium text-dreams-textPrimary">
              {t("booking.chiefComplaint")}
            </label>
            <input
              id="booking-complaint"
              type="text"
              value={chiefComplaint}
              onChange={(e) => setChiefComplaint(e.target.value)}
              placeholder={t("booking.chiefComplaintPlaceholder")}
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
              {submitting ? t("booking.submitting") : t("booking.submit")}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-dreams-border px-4 py-2.5 text-sm font-medium text-dreams-textPrimary hover:bg-dreams-lightBg transition-colors"
            >
              {t("booking.cancel")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// RescheduleModal — patient moves a 'scheduled' appointment to a new time.
// Doctor/clinic/type stay fixed; only date/time (+ optional duration) change.
// ---------------------------------------------------------------------------

function RescheduleModal({
  appt,
  onClose,
  onSuccess,
}: {
  appt: Appointment;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const t = useTranslations("appointments.rescheduleDialog");
  const tBooking = useTranslations("appointments.booking");
  // Pre-fill with the current slot so an accidental open+submit is a no-op.
  const [date, setDate] = useState(() => formatDateInput(new Date(appt.scheduled_at)));
  const [time, setTime] = useState(() => {
    const d = new Date(appt.scheduled_at);
    return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  });
  const [duration, setDuration] = useState(appt.duration_minutes);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  // Close modal on Escape
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await rescheduleAppointment(appt.id, {
        scheduled_at: new Date(`${date}T${time}:00`).toISOString(),
        duration_minutes: duration,
      });
      toast({ title: t("success") });
      onSuccess();
      onClose();
    } catch (err: any) {
      const msg =
        err.response?.data?.error?.message ||
        err.response?.data?.detail?.error?.message ||
        err.response?.data?.detail ||
        t("errorFailed");
      setError(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={t("ariaLabel")}
        className="w-[calc(100%-2rem)] sm:w-full sm:max-w-md rounded-xl bg-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-dreams-border px-6 py-4">
          <h2 className="text-lg font-semibold text-dreams-textPrimary">{t("title")}</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label={tBooking("close")}
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

          {/* Doctor (read-only) */}
          {appt.doctor_name && (
            <div className="flex items-center gap-1.5 text-sm text-dreams-textSecondary">
              <Stethoscope className="h-4 w-4 flex-shrink-0" />
              {t("withDoctor", { doctor: appt.doctor_name })}
            </div>
          )}

          {/* Date + Time */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label htmlFor="reschedule-date" className="mb-1 block text-sm font-medium text-dreams-textPrimary">
                {t("date")}
              </label>
              <input
                id="reschedule-date"
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                min={formatDateInput(new Date())}
                required
                className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
              />
            </div>
            <div>
              <label htmlFor="reschedule-time" className="mb-1 block text-sm font-medium text-dreams-textPrimary">
                {t("time")}
              </label>
              <input
                id="reschedule-time"
                type="time"
                value={time}
                onChange={(e) => setTime(e.target.value)}
                required
                className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
              />
            </div>
          </div>

          {/* Duration */}
          <div>
            <label htmlFor="reschedule-duration" className="mb-1 block text-sm font-medium text-dreams-textPrimary">
              {t("duration")}
            </label>
            <select
              id="reschedule-duration"
              value={duration}
              onChange={(e) => setDuration(Number(e.target.value))}
              className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
            >
              {[15, 30, 45, 60].map((mins) => (
                <option key={mins} value={mins}>
                  {tBooking("durationOption", { count: mins })}
                </option>
              ))}
            </select>
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-2">
            <button
              type="submit"
              disabled={submitting}
              className="flex-1 rounded-lg bg-dreams-blue px-4 py-2.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50 transition-opacity"
            >
              {submitting ? t("submitting") : t("submit")}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-dreams-border px-4 py-2.5 text-sm font-medium text-dreams-textPrimary hover:bg-dreams-lightBg transition-colors"
            >
              {tBooking("cancel")}
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
  onGenerateLink,
  isGeneratingLink,
  onReschedule,
}: {
  appt: Appointment;
  onCancel: (id: string) => void;
  isCancelling: boolean;
  onGenerateLink: (id: string) => void;
  isGeneratingLink: boolean;
  onReschedule: (appt: Appointment) => void;
}) {
  const t = useTranslations("appointments");
  const format = useFormatter();
  const scheduledAt = new Date(appt.scheduled_at);
  const date = format.dateTime(scheduledAt, {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
  });
  const time = format.dateTime(scheduledAt, {
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  });
  const typeKey = TYPE_KEYS[appt.type];
  const statusKey = STATUS_KEYS[appt.status];
  const canCancel = appt.status === "scheduled";
  const isTeleconsult = appt.type === "teleconsult" && ACTIVE_STATUSES.includes(appt.status);
  // Tick every 30s so the Join button unlocks when the window opens
  const [now, setNow] = React.useState(() => Date.now());
  React.useEffect(() => {
    if (!isTeleconsult) return;
    const t = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(t);
  }, [isTeleconsult]);
  const joinable = isTeleconsult && canJoinTeleconsult(appt, now);

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
            <p className="text-xs text-dreams-textSecondary mt-0.5">
              {t("durationMinutes", { count: appt.duration_minutes })}
            </p>
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
                {typeKey ? t(`types.${typeKey}`) : appt.type}
              </Badge>
            </div>

            {appt.chief_complaint && (
              <p className="mt-1.5 text-sm text-dreams-textSecondary">
                {appt.chief_complaint}
              </p>
            )}

            {/* Teleconsult join */}
            {isTeleconsult &&
              ((appt.teleconsult_url ?? appt.meeting_url) ? (
                joinable ? (
                  <a
                    href={(appt.teleconsult_url ?? appt.meeting_url)!}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-2 inline-flex items-center gap-1 rounded-md bg-dreams-blue px-2.5 py-1 text-xs font-medium text-white hover:opacity-90 transition-opacity"
                  >
                    <Video className="h-3.5 w-3.5" />
                    {t("joinVideoConsult")}
                  </a>
                ) : (
                  <span
                    className="mt-2 inline-flex items-center gap-1 rounded-md bg-gray-100 px-2.5 py-1 text-xs font-medium text-dreams-textSecondary cursor-not-allowed"
                    title={t("joinCallLockedHint")}
                  >
                    <Video className="h-3.5 w-3.5" />
                    {t("joinCallLocked")}
                  </span>
                )
              ) : (
                <button
                  disabled={isGeneratingLink}
                  onClick={() => onGenerateLink(appt.id)}
                  className="mt-2 flex items-center gap-1 rounded-md border border-dreams-blue px-2.5 py-1 text-xs font-medium text-dreams-blue hover:bg-dreams-blue/10 disabled:opacity-50 transition-colors"
                >
                  <Video className="h-3.5 w-3.5" />
                  {isGeneratingLink ? t("generatingLink") : t("getCallLink")}
                </button>
              ))}

            {/* Reschedule + Cancel — only while still 'scheduled' */}
            {canCancel && (
              <div className="mt-2 flex items-center gap-2">
                <button
                  onClick={() => onReschedule(appt)}
                  className="flex items-center gap-1 rounded-md border border-dreams-blue px-2.5 py-1 text-xs font-medium text-dreams-blue hover:bg-dreams-blue/10 transition-colors"
                >
                  <CalendarClock className="h-3.5 w-3.5" />
                  {t("reschedule")}
                </button>
                <button
                  disabled={isCancelling}
                  onClick={() => onCancel(appt.id)}
                  className="flex items-center gap-1 rounded-md bg-red-50 px-2.5 py-1 text-xs font-medium text-red-700 hover:bg-red-100 disabled:opacity-50 transition-colors"
                >
                  <XCircle className="h-3.5 w-3.5" />
                  {t("cancelAppointment")}
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Status badge */}
        <div className="flex-shrink-0">
          <Badge variant={STATUS_VARIANT_MAP[appt.status] ?? "pending"}>
            {statusKey ? t(`status.${statusKey}`) : appt.status}
          </Badge>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Waitlist section
// ---------------------------------------------------------------------------

const WAITLIST_WINDOW_KEYS: Record<string, "morning" | "afternoon" | "any"> = {
  morning: "morning",
  afternoon: "afternoon",
  any: "any",
};

function WaitlistSection({
  entries,
  onCancel,
  cancellingId,
}: {
  entries: WaitlistEntry[];
  onCancel: (id: string) => void;
  cancellingId: string | null;
}) {
  const t = useTranslations("appointments.waitlist");
  const format = useFormatter();

  if (entries.length === 0) return null;

  return (
    <div className="rounded-xl border border-dreams-border bg-white p-4 shadow-card">
      <div className="flex items-center gap-2">
        <CalendarClock className="h-4 w-4 text-dreams-blue" />
        <h2 className="text-sm font-semibold text-dreams-textPrimary">{t("sectionTitle")}</h2>
      </div>
      <p className="mt-0.5 text-xs text-dreams-textSecondary">{t("sectionHint")}</p>
      <ul className="mt-3 divide-y divide-dreams-border">
        {entries.map((entry) => {
          const dateLabel = format.dateTime(new Date(`${entry.desired_date}T00:00:00`), {
            weekday: "short",
            day: "numeric",
            month: "short",
            year: "numeric",
          });
          const windowKey = WAITLIST_WINDOW_KEYS[entry.slot_window] ?? "any";
          return (
            <li key={entry.id} className="flex items-center justify-between gap-3 py-2.5">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-dreams-textPrimary">
                  {entry.doctor_name ?? t("unknownDoctor")}
                </p>
                <p className="text-xs text-dreams-textSecondary">
                  {dateLabel} · {t(`window.${windowKey}`)}
                </p>
              </div>
              <div className="flex flex-shrink-0 items-center gap-2">
                <Badge variant={entry.status === "notified" ? "inProgress" : "pending"} className="text-xs">
                  {entry.status === "notified" ? t("statusNotified") : t("statusPending")}
                </Badge>
                <button
                  type="button"
                  disabled={cancellingId === entry.id}
                  onClick={() => onCancel(entry.id)}
                  className="rounded-md bg-red-50 px-2.5 py-1 text-xs font-medium text-red-700 hover:bg-red-100 disabled:opacity-50 transition-colors"
                >
                  {cancellingId === entry.id ? t("cancelling") : t("cancelRequest")}
                </button>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

const PAGE_SIZE = 10;

export default function PatientAppointmentsPage() {
  const t = useTranslations("appointments");
  const tNav = useTranslations("nav");
  const [tab, setTab] = useState<"upcoming" | "past">("upcoming");
  const [page, setPage] = useState(1);
  const [showBooking, setShowBooking] = useState(false);
  const [cancelTarget, setCancelTarget] = useState<string | null>(null);
  const [rescheduleTarget, setRescheduleTarget] = useState<Appointment | null>(null);
  const [linkError, setLinkError] = useState<string | null>(null);
  const { user } = useAuthStore();
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["patient-appointments"],
    queryFn: fetchAllAppointments,
  });

  const waitlistQuery = useQuery({
    queryKey: ["patient-waitlist"],
    queryFn: () => getMyWaitlist(),
  });
  const activeWaitlist = (waitlistQuery.data ?? []).filter(
    (e) => e.status === "pending" || e.status === "notified"
  );

  const cancelWaitlistMutation = useMutation({
    mutationFn: (id: string) => cancelWaitlistEntry(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["patient-waitlist"] });
    },
  });

  const cancelMutation = useMutation({
    mutationFn: (id: string) =>
      updateAppointmentStatus(id, { status: "cancelled", cancelled_reason: "Cancelled by patient" }),
    onSuccess: () => {
      setCancelTarget(null);
      queryClient.invalidateQueries({ queryKey: ["patient-appointments"] });
    },
  });

  const meetingLinkMutation = useMutation({
    mutationFn: (id: string) => generateMeetingLink(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["patient-appointments"] });
    },
    onError: (err: unknown) => {
      const msg =
        (err as { userMessage?: string })?.userMessage ??
        (err as { response?: { data?: { detail?: { error?: { message?: string } } } } })
          ?.response?.data?.detail?.error?.message ??
        t("meetingLinkError");
      setLinkError(msg);
    },
  });

  // Close cancel-confirm dialog on Escape
  useEffect(() => {
    if (!cancelTarget) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setCancelTarget(null);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [cancelTarget]);

  const allAppointments: Appointment[] = data ?? [];
  const upcomingAppointments = allAppointments.filter(isUpcoming).sort(
    (a, b) => new Date(a.scheduled_at).getTime() - new Date(b.scheduled_at).getTime()
  );
  const pastAppointments = allAppointments
    .filter((a) => !isUpcoming(a))
    .sort((a, b) => new Date(b.scheduled_at).getTime() - new Date(a.scheduled_at).getTime());

  const displayedAppointments = tab === "upcoming" ? upcomingAppointments : pastAppointments;
  const totalPages = Math.ceil(displayedAppointments.length / PAGE_SIZE);
  // Clamp in case the list shrank (e.g. a cancellation) while on a later page
  const currentPage = Math.min(page, Math.max(totalPages, 1));
  const pagedAppointments = displayedAppointments.slice(
    (currentPage - 1) * PAGE_SIZE,
    currentPage * PAGE_SIZE
  );

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

      {rescheduleTarget && (
        <RescheduleModal
          appt={rescheduleTarget}
          onClose={() => setRescheduleTarget(null)}
          onSuccess={() => {
            queryClient.invalidateQueries({ queryKey: ["patient-appointments"] });
          }}
        />
      )}

      <Breadcrumb
        items={[
          { label: tNav("healthTimeline"), href: "/patient/timeline" },
          { label: tNav("appointments") },
        ]}
      />

      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-dreams-textPrimary">{t("title")}</h1>
        <button
          onClick={() => setShowBooking(true)}
          className="flex items-center gap-2 rounded-lg bg-dreams-blue px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
        >
          <Plus className="h-4 w-4" />
          {t("bookAppointment")}
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-lg border border-dreams-border bg-gray-100 p-1 w-fit">
        {[
          { key: "upcoming", label: t("tabs.upcoming", { count: upcomingAppointments.length }) },
          { key: "past", label: t("tabs.past", { count: pastAppointments.length }) },
        ].map(({ key, label }) => (
          <button
            key={key}
            onClick={() => {
              setTab(key as "upcoming" | "past");
              setPage(1);
            }}
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
            {tab === "upcoming" ? t("empty.upcomingTitle") : t("empty.pastTitle")}
          </p>
          <p className="mt-1 text-sm text-dreams-textSecondary">
            {tab === "upcoming" ? t("empty.upcomingHint") : t("empty.pastHint")}
          </p>
        </div>
      )}

      {linkError && (
        <div className="rounded-lg border border-status-overdue/30 bg-status-overdue/10 px-4 py-2 text-sm text-red-800">
          {linkError}
        </div>
      )}

      {/* Appointment list */}
      {!isLoading && displayedAppointments.length > 0 && (
        <div className="space-y-3">
          {pagedAppointments.map((appt) => (
            <AppointmentCard
              key={appt.id}
              appt={appt}
              onCancel={(id) => setCancelTarget(id)}
              isCancelling={cancelMutation.isPending && cancelTarget === appt.id}
              onGenerateLink={(id) => { setLinkError(null); meetingLinkMutation.mutate(id); }}
              isGeneratingLink={meetingLinkMutation.isPending && meetingLinkMutation.variables === appt.id}
              onReschedule={(a) => setRescheduleTarget(a)}
            />
          ))}
          <Pagination
            page={currentPage}
            totalPages={totalPages}
            total={displayedAppointments.length}
            onPageChange={setPage}
          />
        </div>
      )}

      {/* Waitlist — pending/notified requests with cancel */}
      <WaitlistSection
        entries={activeWaitlist}
        onCancel={(id) => cancelWaitlistMutation.mutate(id)}
        cancellingId={
          cancelWaitlistMutation.isPending
            ? cancelWaitlistMutation.variables ?? null
            : null
        }
      />

      {/* Cancel confirmation dialog */}
      {cancelTarget && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={() => setCancelTarget(null)}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-label={t("cancelDialog.ariaLabel")}
            className="w-full max-w-sm rounded-xl bg-white shadow-xl p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-lg font-semibold text-dreams-textPrimary">
              {t("cancelDialog.title")}
            </h2>
            <p className="mt-2 text-sm text-dreams-textSecondary">
              {t("cancelDialog.body")}
            </p>
            <div className="mt-6 flex gap-3">
              <button
                type="button"
                onClick={() => setCancelTarget(null)}
                className="flex-1 rounded-lg border border-dreams-border px-4 py-2 text-sm font-medium text-dreams-textPrimary hover:bg-dreams-lightBg transition-colors"
              >
                {t("cancelDialog.keep")}
              </button>
              <button
                type="button"
                disabled={cancelMutation.isPending}
                onClick={() => cancelMutation.mutate(cancelTarget)}
                className="flex-1 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50 transition-colors"
              >
                {cancelMutation.isPending ? t("cancelDialog.cancelling") : t("cancelDialog.confirm")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
