"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useFormatter, useTranslations } from "next-intl";
import { Calendar, CalendarDays, ChevronLeft, ChevronRight, Clock, List, User, FileText, FilePlus, CheckCircle, XCircle, UserCheck, Plus, X, Pencil, Video } from "lucide-react";
import Link from "next/link";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { Badge } from "@/components/ui/badge";
import {
  getAppointments,
  updateAppointmentStatus,
  updateAppointment,
  cancelAppointment,
  createAppointment,
  createGuestAppointment,
  linkProvisionalPatient,
  generateMeetingLink,
  type Appointment,
  type UpdateAppointmentData,
} from "@/lib/api/appointments";
import { getClinicBranches } from "@/lib/api/clinics";
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

// Keys into messages/en.json — en.json is the source of truth; keep the
// `doctorAppointments` / `appointments` namespaces in sync with hi.json.
type EnMessages = typeof import("../../../../messages/en.json");
type AppointmentTypeKey = keyof EnMessages["appointments"]["types"];
type AppointmentStatusKey = keyof EnMessages["appointments"]["status"];

const TYPE_KEYS: Record<string, AppointmentTypeKey> = {
  "in-person": "in-person",
  "teleconsult": "teleconsult",
  "follow-up": "follow-up",
};

const STATUS_KEYS: Record<string, AppointmentStatusKey> = {
  scheduled: "scheduled",
  arrived: "arrived",
  "in-progress": "in-progress",
  completed: "completed",
  cancelled: "cancelled",
  "no-show": "no-show",
};

// Appointment status → tailwind `status-*` accent token for the calendar
// card's left border. Full class names are spelled out so Tailwind's static
// scanner emits them (dynamic `border-l-status-${x}` would be purged).
const STATUS_ACCENT_CLASSES: Record<string, string> = {
  scheduled: "border-l-status-upcoming",
  arrived: "border-l-status-inProgress",
  "in-progress": "border-l-status-inProgress",
  completed: "border-l-status-completed",
  cancelled: "border-l-status-overdue",
  "no-show": "border-l-status-pending",
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

// ---------------------------------------------------------------------------
// Week calendar helpers (local-time Monday-start weeks)
// ---------------------------------------------------------------------------

function startOfWeekMonday(d: Date): Date {
  const copy = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const dow = (copy.getDay() + 6) % 7; // Monday = 0
  copy.setDate(copy.getDate() - dow);
  return copy;
}

function addDays(d: Date, n: number): Date {
  const copy = new Date(d);
  copy.setDate(copy.getDate() + n);
  return copy;
}

/** Local YYYY-MM-DD — toISOString() is UTC and rolls back a day in IST. */
function formatLocalDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

// ---------------------------------------------------------------------------
// Patient search typeahead (reused from prescriptions/new)
// ---------------------------------------------------------------------------

interface PatientSuggestion {
  id: string;
  full_name: string;
  phone: string | null;
  last_visit_at: string | null;
}

function PatientSearchInput({
  onSelect,
  id,
}: {
  onSelect: (p: PatientSuggestion) => void;
  id?: string;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<PatientSuggestion[]>([]);
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
      .get(`/api/v1/doctors/patients/search?q=${encodeURIComponent(q)}`)
      .then((res) => {
        setResults(res.data.data || []);
        setOpen(true);
      })
      .catch(() => setResults([]))
      .finally(() => setLoading(false));
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
        placeholder="Search patient by name or phone..."
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
          {results.map((p) => (
            <button
              key={p.id}
              type="button"
              className="flex w-full items-start gap-3 px-4 py-3 text-left hover:bg-dreams-lightBg transition-colors"
              onMouseDown={() => {
                onSelect(p);
                setQuery("");
                setOpen(false);
              }}
            >
              <div className="flex-1">
                <p className="text-sm font-medium text-dreams-textPrimary">{p.full_name}</p>
                {p.phone && <p className="text-xs text-dreams-textSecondary">{p.phone}</p>}
              </div>
            </button>
          ))}
        </div>
      )}
      {open && results.length === 0 && !loading && query.length >= 2 && (
        <div className="absolute z-50 mt-1 w-full rounded-lg border border-dreams-border bg-white px-4 py-3 text-sm text-dreams-textSecondary shadow-lg">
          No patients found.
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// LinkAccountModal
// ---------------------------------------------------------------------------

function LinkAccountModal({
  provisionalPatientId,
  patientName,
  clinicId,
  onClose,
  onSuccess,
}: {
  provisionalPatientId: string;
  patientName: string;
  clinicId: string;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [code, setCode] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!code.trim()) { setError("Please enter the link code"); return; }
    setSubmitting(true);
    try {
      await linkProvisionalPatient(clinicId, {
        provisional_patient_id: provisionalPatientId,
        link_code: code.trim().toUpperCase(),
      });
      onSuccess();
      onClose();
    } catch (err: any) {
      const msg = err.response?.data?.detail?.error?.message || err.response?.data?.detail || "Failed to link account";
      setError(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Link patient account"
        className="w-[calc(100%-2rem)] sm:w-full sm:max-w-md rounded-xl bg-white shadow-xl"
      >
        <div className="flex items-center justify-between border-b border-dreams-border px-6 py-4">
          <h2 className="text-lg font-semibold text-dreams-textPrimary">Link patient account</h2>
          <button type="button" onClick={onClose} aria-label="Close" className="text-dreams-textSecondary hover:text-dreams-textPrimary">
            <X className="h-5 w-5" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="px-6 py-4 space-y-4">
          <p className="text-sm text-dreams-textSecondary">
            Linking walk-in record for{" "}
            <span className="font-medium text-dreams-textPrimary">{patientName}</span>. Ask the
            patient to open MedConnect, go to{" "}
            <span className="font-medium">My Clinics</span>, and share their link code.
          </p>
          {error && (
            <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-2 text-sm text-red-700">{error}</div>
          )}
          <div>
            <label
              htmlFor="link-code"
              className="mb-1 block text-sm font-medium text-dreams-textPrimary"
            >
              Patient&apos;s link code
            </label>
            <input
              id="link-code"
              type="text"
              value={code}
              onChange={(e) => setCode(e.target.value.toUpperCase())}
              placeholder="e.g., ABC1234567"
              maxLength={10}
              className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm font-mono tracking-widest focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
            />
          </div>
          <div className="flex gap-3 pt-1">
            <button
              type="submit"
              disabled={submitting}
              className="flex-1 rounded-lg bg-dreams-blue px-4 py-2.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50 transition-opacity"
            >
              {submitting ? "Linking..." : "Link Account"}
            </button>
            <button type="button" onClick={onClose}
              className="rounded-lg border border-dreams-border px-4 py-2.5 text-sm font-medium text-dreams-textPrimary hover:bg-dreams-lightBg transition-colors">
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// BookAppointmentModal
// ---------------------------------------------------------------------------

interface ClinicOption {
  id: string;
  name: string;
}

interface BookAppointmentModalProps {
  onClose: () => void;
  onSuccess: () => void;
  doctorId: string | null;
}

function BookAppointmentModal({ onClose, onSuccess, doctorId }: BookAppointmentModalProps) {
  const [tab, setTab] = useState<"existing" | "walkin">("existing");
  // Existing patient state
  const [selectedPatient, setSelectedPatient] = useState<PatientSuggestion | null>(null);
  // Walk-in state
  const [walkinName, setWalkinName] = useState("");
  const [walkinPhone, setWalkinPhone] = useState("");
  // Shared state
  const [date, setDate] = useState(formatDateInput(new Date()));
  const [time, setTime] = useState("09:00");
  const [duration, setDuration] = useState(30);
  const [type, setType] = useState<"in-person" | "teleconsult" | "follow-up">("in-person");
  const [chiefComplaint, setChiefComplaint] = useState("");
  const [clinicId, setClinicId] = useState("");
  const [branchId, setBranchId] = useState("");
  const [clinics, setClinics] = useState<ClinicOption[]>([]);
  // Receptionist path: caller has no Doctor profile, so pick the clinician.
  const [clinicDoctors, setClinicDoctors] = useState<{ id: string; full_name: string; specialization: string | null }[]>([]);
  const [pickedDoctorId, setPickedDoctorId] = useState("");
  const effectiveDoctorId = doctorId ?? (pickedDoctorId || undefined);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get("/api/v1/clinics/my")
      .then((res) => {
        const data = res.data?.data || res.data || [];
        setClinics(Array.isArray(data) ? data : []);
      })
      .catch(() => {});
  }, []);

  // Branches for the selected clinic; the branch selection resets in the
  // clinic select's onChange below.
  const { data: branches = [], isFetching: branchesLoading } = useQuery({
    queryKey: ["clinic-branches", clinicId],
    queryFn: () => getClinicBranches(clinicId),
    enabled: !!clinicId,
  });

  // Fetch clinic doctors (receptionist path) when a clinic is chosen.
  useEffect(() => {
    if (!clinicId || doctorId) return;
    api
      .get(`/api/v1/clinics/${clinicId}/doctors`)
      .then((res) => setClinicDoctors(res.data?.data ?? []))
      .catch(() => setClinicDoctors([]));
  }, [clinicId, doctorId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    const scheduledAt = new Date(`${date}T${time}:00`).toISOString();

    if (tab === "walkin") {
      if (!walkinName.trim()) { setError("Patient name is required"); return; }
      if (!walkinPhone.trim()) { setError("Phone number is required"); return; }
      if (!clinicId) { setError("A clinic must be selected for walk-in bookings"); return; }
      if (!doctorId && !pickedDoctorId) { setError("Please select a doctor"); return; }
      setSubmitting(true);
      try {
        await createGuestAppointment(clinicId, {
          patient_name: walkinName.trim(),
          patient_phone: walkinPhone.trim(),
          doctor_id: effectiveDoctorId,
          branch_id: branchId || undefined,
          scheduled_at: scheduledAt,
          duration_minutes: duration,
          type,
          chief_complaint: chiefComplaint || undefined,
        });
        onSuccess();
        onClose();
      } catch (err: any) {
        const msg = err.response?.data?.detail?.error?.message || err.response?.data?.detail || "Failed to create appointment";
        setError(typeof msg === "string" ? msg : JSON.stringify(msg));
      } finally {
        setSubmitting(false);
      }
      return;
    }

    if (!selectedPatient) { setError("Please select a patient"); return; }
    setSubmitting(true);
    try {
      await createAppointment({
        patient_id: selectedPatient.id,
        doctor_id: effectiveDoctorId,
        clinic_id: clinicId || undefined,
        branch_id: branchId || undefined,
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
        "Failed to create appointment";
      setError(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setSubmitting(false);
    }
  };

  const sharedFields = (
    <>
      {/* Date + Time */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label htmlFor="booking-date" className="mb-1 block text-sm font-medium text-dreams-textPrimary">Date *</label>
          <input
            id="booking-date"
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            min={formatDateInput(new Date())}
            required
            className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
          />
        </div>
        <div>
          <label htmlFor="booking-time" className="mb-1 block text-sm font-medium text-dreams-textPrimary">Time *</label>
          <input
            id="booking-time"
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
          <label htmlFor="booking-duration" className="mb-1 block text-sm font-medium text-dreams-textPrimary">Duration</label>
          <select
            id="booking-duration"
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
          <label htmlFor="booking-type" className="mb-1 block text-sm font-medium text-dreams-textPrimary">Type *</label>
          <select
            id="booking-type"
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
        <label htmlFor="booking-complaint" className="mb-1 block text-sm font-medium text-dreams-textPrimary">Chief Complaint</label>
        <input
          id="booking-complaint"
          type="text"
          value={chiefComplaint}
          onChange={(e) => setChiefComplaint(e.target.value)}
          placeholder="e.g., Fever, headache for 2 days"
          className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
        />
      </div>

      {/* Clinic */}
      {clinics.length > 0 && (
        <div>
          <label htmlFor="booking-clinic" className="mb-1 block text-sm font-medium text-dreams-textPrimary">
            Clinic{tab === "walkin" ? " *" : ""}
          </label>
          <select
            id="booking-clinic"
            value={clinicId}
            onChange={(e) => { setClinicId(e.target.value); setBranchId(""); }}
            className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
          >
            <option value="">{tab === "walkin" ? "Select clinic" : "No clinic (private)"}</option>
            {clinics.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </div>
      )}

      {/* Doctor — only for staff without a Doctor profile (e.g. receptionists) */}
      {!doctorId && clinicId && (
        <div>
          <label htmlFor="booking-doctor" className="mb-1 block text-sm font-medium text-dreams-textPrimary">Doctor *</label>
          <select
            id="booking-doctor"
            value={pickedDoctorId}
            onChange={(e) => setPickedDoctorId(e.target.value)}
            className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
          >
            <option value="">Select doctor</option>
            {clinicDoctors.map((d) => (
              <option key={d.id} value={d.id}>
                {d.full_name}{d.specialization ? ` — ${d.specialization}` : ""}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Branch */}
      {clinicId && (branchesLoading || branches.length > 0) && (
        <div>
          <label htmlFor="booking-branch" className="mb-1 block text-sm font-medium text-dreams-textPrimary">Branch</label>
          {branchesLoading ? (
            <div className="h-10 rounded-lg border border-dreams-border bg-gray-50 flex items-center px-3">
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-dreams-blue border-t-transparent" />
              <span className="ml-2 text-sm text-dreams-textSecondary">Loading branches...</span>
            </div>
          ) : (
            <select
              id="booking-branch"
              value={branchId}
              onChange={(e) => setBranchId(e.target.value)}
              className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
            >
              <option value="">Any branch</option>
              {branches.map((b) => (
                <option key={b.id} value={b.id}>{b.name}{b.city ? ` — ${b.city}` : ""}</option>
              ))}
            </select>
          )}
        </div>
      )}
    </>
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-label="New appointment"
        className="w-[calc(100%-2rem)] sm:w-full sm:max-w-lg rounded-xl bg-white shadow-xl"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-dreams-border px-6 py-4">
          <h2 className="text-lg font-semibold text-dreams-textPrimary">New Appointment</h2>
          <button type="button" onClick={onClose} aria-label="Close" className="text-dreams-textSecondary hover:text-dreams-textPrimary">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Tab toggle */}
        <div className="flex border-b border-dreams-border px-6">
          <button
            type="button"
            onClick={() => { setTab("existing"); setError(""); }}
            className={`py-3 px-4 text-sm font-medium border-b-2 transition-colors ${
              tab === "existing"
                ? "border-dreams-blue text-dreams-blue"
                : "border-transparent text-dreams-textSecondary hover:text-dreams-textPrimary"
            }`}
          >
            Existing Patient
          </button>
          <button
            type="button"
            onClick={() => { setTab("walkin"); setError(""); }}
            className={`py-3 px-4 text-sm font-medium border-b-2 transition-colors ${
              tab === "walkin"
                ? "border-dreams-blue text-dreams-blue"
                : "border-transparent text-dreams-textSecondary hover:text-dreams-textPrimary"
            }`}
          >
            Walk-in / Call-in
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-4 space-y-4 max-h-[70vh] overflow-y-auto">
          {error && (
            <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-2 text-sm text-red-700">{error}</div>
          )}

          {tab === "existing" ? (
            <div>
              <label htmlFor="booking-patient" className="mb-1 block text-sm font-medium text-dreams-textPrimary">Patient *</label>
              {selectedPatient ? (
                <div className="flex items-center gap-3 rounded-lg border border-dreams-blue bg-dreams-blue/5 px-4 py-2.5">
                  <div className="flex-1">
                    <p className="text-sm font-semibold text-dreams-textPrimary">{selectedPatient.full_name}</p>
                    {selectedPatient.phone && (
                      <p className="text-xs text-dreams-textSecondary">{selectedPatient.phone}</p>
                    )}
                  </div>
                  <button type="button" onClick={() => setSelectedPatient(null)}
                    aria-label="Clear selected patient"
                    className="text-dreams-textSecondary hover:text-red-500 transition-colors">
                    <X className="h-4 w-4" />
                  </button>
                </div>
              ) : (
                <PatientSearchInput id="booking-patient" onSelect={setSelectedPatient} />
              )}
            </div>
          ) : (
            <div className="space-y-3">
              <div>
                <label htmlFor="walkin-name" className="mb-1 block text-sm font-medium text-dreams-textPrimary">Patient Name *</label>
                <input
                  id="walkin-name"
                  type="text"
                  value={walkinName}
                  onChange={(e) => setWalkinName(e.target.value)}
                  placeholder="Full name"
                  className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
                />
              </div>
              <div>
                <label htmlFor="walkin-phone" className="mb-1 block text-sm font-medium text-dreams-textPrimary">Phone Number *</label>
                <input
                  id="walkin-phone"
                  type="tel"
                  value={walkinPhone}
                  onChange={(e) => setWalkinPhone(e.target.value)}
                  placeholder="+91 98765 43210"
                  className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
                />
              </div>
            </div>
          )}

          {sharedFields}

          {/* Actions */}
          <div className="flex gap-3 pt-2">
            <button
              type="submit"
              disabled={submitting || (tab === "existing" && !selectedPatient)}
              className="flex-1 rounded-lg bg-dreams-blue px-4 py-2.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50 transition-opacity"
            >
              {submitting ? "Booking..." : "Book Appointment"}
            </button>
            <button type="button" onClick={onClose}
              className="rounded-lg border border-dreams-border px-4 py-2.5 text-sm font-medium text-dreams-textPrimary hover:bg-dreams-lightBg transition-colors">
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Edit Appointment Modal (doctor: cannot change patient or reassign doctor)
// ---------------------------------------------------------------------------

function EditAppointmentModal({
  appointment,
  onClose,
  onSuccess,
}: {
  appointment: Appointment;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const initialDate = appointment.scheduled_at.slice(0, 10);
  const initialTime = new Date(appointment.scheduled_at).toTimeString().slice(0, 5);

  const [date, setDate] = useState(initialDate);
  const [time, setTime] = useState(initialTime);
  const [duration, setDuration] = useState(appointment.duration_minutes);
  const [type, setType] = useState<"in-person" | "teleconsult" | "follow-up">(appointment.type);
  const [chiefComplaint, setChiefComplaint] = useState(appointment.chief_complaint ?? "");
  const [clinicId, setClinicId] = useState(appointment.clinic_id ?? "");
  const [branchId, setBranchId] = useState(appointment.branch_id ?? "");
  const [clinics, setClinics] = useState<ClinicOption[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get("/api/v1/clinics/my")
      .then((res) => { const d = res.data?.data || res.data || []; setClinics(Array.isArray(d) ? d : []); })
      .catch(() => {});
  }, []);

  // Branches for the selected clinic; the branch selection resets in the
  // clinic select's onChange below. The appointment's existing branch is
  // preserved on open.
  const { data: branches = [], isFetching: branchesLoading } = useQuery({
    queryKey: ["clinic-branches", clinicId],
    queryFn: () => getClinicBranches(clinicId),
    enabled: !!clinicId,
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const payload: UpdateAppointmentData = {
        scheduled_at: new Date(`${date}T${time}:00`).toISOString(),
        duration_minutes: duration,
        type,
        chief_complaint: chiefComplaint || null,
        clinic_id: clinicId || null,
        branch_id: branchId || null,
      };
      await updateAppointment(appointment.id, payload);
      onSuccess();
      onClose();
    } catch (err: any) {
      const msg = err.response?.data?.detail?.error?.message || err.response?.data?.detail || "Failed to update appointment";
      setError(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Edit appointment"
        className="w-[calc(100%-2rem)] sm:w-full sm:max-w-lg rounded-xl bg-white shadow-xl"
      >
        <div className="flex items-center justify-between border-b border-dreams-border px-6 py-4">
          <h2 className="text-lg font-semibold text-dreams-textPrimary">Edit Appointment</h2>
          <button type="button" onClick={onClose} aria-label="Close" className="text-dreams-textSecondary hover:text-dreams-textPrimary">
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-4 space-y-4 max-h-[80vh] overflow-y-auto">
          {error && (
            <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-2 text-sm text-red-700">{error}</div>
          )}

          {/* Patient (read-only) */}
          <div>
            <span className="mb-1 block text-sm font-medium text-dreams-textPrimary">Patient</span>
            <div className="h-10 rounded-lg border border-dreams-border bg-dreams-lightBg px-3 flex items-center text-sm text-dreams-textSecondary">
              {appointment.patient_name ?? "—"}
            </div>
          </div>

          {/* Date + Time */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label htmlFor="edit-appt-date" className="mb-1 block text-sm font-medium text-dreams-textPrimary">Date *</label>
              <input id="edit-appt-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} required
                className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20" />
            </div>
            <div>
              <label htmlFor="edit-appt-time" className="mb-1 block text-sm font-medium text-dreams-textPrimary">Time *</label>
              <input id="edit-appt-time" type="time" value={time} onChange={(e) => setTime(e.target.value)} required
                className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20" />
            </div>
          </div>

          {/* Duration + Type */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label htmlFor="edit-appt-duration" className="mb-1 block text-sm font-medium text-dreams-textPrimary">Duration</label>
              <select id="edit-appt-duration" value={duration} onChange={(e) => setDuration(Number(e.target.value))}
                className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20">
                <option value={15}>15 min</option>
                <option value={30}>30 min</option>
                <option value={45}>45 min</option>
                <option value={60}>60 min</option>
              </select>
            </div>
            <div>
              <label htmlFor="edit-appt-type" className="mb-1 block text-sm font-medium text-dreams-textPrimary">Type *</label>
              <select id="edit-appt-type" value={type} onChange={(e) => setType(e.target.value as typeof type)}
                className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20">
                <option value="in-person">In Person</option>
                <option value="teleconsult">Teleconsult</option>
                <option value="follow-up">Follow-up</option>
              </select>
            </div>
          </div>

          {/* Chief Complaint */}
          <div>
            <label htmlFor="edit-appt-complaint" className="mb-1 block text-sm font-medium text-dreams-textPrimary">Chief Complaint</label>
            <input id="edit-appt-complaint" type="text" value={chiefComplaint} onChange={(e) => setChiefComplaint(e.target.value)}
              placeholder="e.g., Fever, headache for 2 days"
              className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20" />
          </div>

          {/* Clinic */}
          {clinics.length > 0 && (
            <div>
              <label htmlFor="edit-appt-clinic" className="mb-1 block text-sm font-medium text-dreams-textPrimary">Clinic</label>
              <select id="edit-appt-clinic" value={clinicId} onChange={(e) => { setClinicId(e.target.value); setBranchId(""); }}
                className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20">
                <option value="">No clinic (private)</option>
                {clinics.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
          )}

          {/* Branch */}
          {clinicId && (branchesLoading || branches.length > 0) && (
            <div>
              <label htmlFor="edit-appt-branch" className="mb-1 block text-sm font-medium text-dreams-textPrimary">Branch</label>
              {branchesLoading ? (
                <div className="h-10 rounded-lg border border-dreams-border bg-gray-50 flex items-center px-3">
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-dreams-blue border-t-transparent" />
                  <span className="ml-2 text-sm text-dreams-textSecondary">Loading branches...</span>
                </div>
              ) : (
                <select id="edit-appt-branch" value={branchId} onChange={(e) => setBranchId(e.target.value)}
                  className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20">
                  <option value="">Any branch</option>
                  {branches.map((b) => <option key={b.id} value={b.id}>{b.name}{b.city ? ` — ${b.city}` : ""}</option>)}
                </select>
              )}
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3 pt-2">
            <button type="submit" disabled={submitting}
              className="flex-1 rounded-lg bg-dreams-blue px-4 py-2.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50 transition-opacity">
              {submitting ? "Saving..." : "Save Changes"}
            </button>
            <button type="button" onClick={onClose}
              className="rounded-lg border border-dreams-border px-4 py-2.5 text-sm font-medium text-dreams-textPrimary hover:bg-dreams-lightBg transition-colors">
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Cancel Appointment Modal (doctor portal)
// ---------------------------------------------------------------------------

function CancelAppointmentModal({
  appointment,
  onClose,
  onSuccess,
}: {
  appointment: Appointment;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const handleCancel = async () => {
    setSubmitting(true);
    setError("");
    try {
      await cancelAppointment(appointment.id, reason || undefined);
      onSuccess();
      onClose();
    } catch (err: any) {
      const msg = err.response?.data?.detail?.error?.message || "Failed to cancel appointment";
      setError(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Cancel appointment"
        className="w-[calc(100%-2rem)] sm:w-full sm:max-w-md rounded-xl bg-white shadow-xl"
      >
        <div className="flex items-center justify-between border-b border-dreams-border px-6 py-4">
          <h2 className="text-lg font-semibold text-dreams-textPrimary">Cancel Appointment</h2>
          <button type="button" onClick={onClose} aria-label="Close" className="text-dreams-textSecondary hover:text-dreams-textPrimary">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="px-6 py-4 space-y-4">
          <p className="text-sm text-dreams-textSecondary">
            Cancel appointment for <span className="font-medium text-dreams-textPrimary">{appointment.patient_name}</span>?
          </p>
          {error && (
            <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-2 text-sm text-red-700">{error}</div>
          )}
          <div>
            <label htmlFor="cancel-reason" className="mb-1 block text-sm font-medium text-dreams-textPrimary">Reason (optional)</label>
            <input
              id="cancel-reason"
              type="text"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g., Doctor unavailable, patient requested..."
              className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
            />
          </div>
          <div className="flex gap-3 pt-1">
            <button
              onClick={handleCancel}
              disabled={submitting}
              className="flex-1 rounded-lg bg-red-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50 transition-colors"
            >
              {submitting ? "Cancelling..." : "Cancel Appointment"}
            </button>
            <button type="button" onClick={onClose}
              className="rounded-lg border border-dreams-border px-4 py-2.5 text-sm font-medium text-dreams-textPrimary hover:bg-dreams-lightBg transition-colors">
              Keep
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Status action buttons
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Week calendar view
// ---------------------------------------------------------------------------

interface WeekCalendarViewProps {
  weekStart: Date; // Monday, local time
  appointments: Appointment[];
  isLoading: boolean;
  onPrevWeek: () => void;
  onNextWeek: () => void;
  onToday: () => void;
  onSelectAppointment: (appt: Appointment) => void;
}

function WeekCalendarView({
  weekStart,
  appointments,
  isLoading,
  onPrevWeek,
  onNextWeek,
  onToday,
  onSelectAppointment,
}: WeekCalendarViewProps) {
  const t = useTranslations("doctorAppointments.calendar");
  const tAppt = useTranslations("appointments");
  const format = useFormatter();

  const days = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));
  const todayStr = formatLocalDate(new Date());
  const weekEnd = addDays(weekStart, 6);

  // Group by the appointment's local calendar day so cards land in the column
  // the doctor expects. The query fetches a ±1-day buffer around the week, so
  // anything outside these seven columns is simply not rendered.
  const byDay = new Map<string, Appointment[]>();
  for (const appt of appointments) {
    const key = formatLocalDate(new Date(appt.scheduled_at));
    const list = byDay.get(key) ?? [];
    list.push(appt);
    byDay.set(key, list);
  }
  byDay.forEach((list) =>
    list.sort((a: Appointment, b: Appointment) => a.scheduled_at.localeCompare(b.scheduled_at))
  );

  const rangeLabel = `${format.dateTime(weekStart, { day: "numeric", month: "short" })} – ${format.dateTime(weekEnd, { day: "numeric", month: "short", year: "numeric" })}`;

  const navButtonClass =
    "flex h-9 w-9 items-center justify-center rounded-lg border border-dreams-border bg-white text-dreams-textSecondary hover:bg-gray-50 hover:text-dreams-textPrimary transition-colors";

  const dayHeader = (day: Date) => {
    const key = formatLocalDate(day);
    const isTodayCol = key === todayStr;
    return (
      <div key={key} className="border-b border-dreams-border px-2 py-2 text-center">
        <p className="text-xs font-medium uppercase text-dreams-textSecondary">
          {format.dateTime(day, { weekday: "short" })}
        </p>
        <p
          className={`mx-auto mt-0.5 flex h-7 w-7 items-center justify-center rounded-full text-sm font-semibold ${
            isTodayCol ? "bg-dreams-blue text-white" : "text-dreams-textPrimary"
          }`}
        >
          {format.dateTime(day, { day: "numeric" })}
        </p>
      </div>
    );
  };

  return (
    <div className="space-y-4">
      {/* Week navigation */}
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" onClick={onPrevWeek} aria-label={t("prevWeek")} className={navButtonClass}>
          <ChevronLeft className="h-4 w-4" />
        </button>
        <button type="button" onClick={onNextWeek} aria-label={t("nextWeek")} className={navButtonClass}>
          <ChevronRight className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={onToday}
          className="rounded-lg border border-dreams-border bg-white px-3 py-2 text-sm text-dreams-textSecondary hover:bg-gray-50"
        >
          {t("today")}
        </button>
        <span className="text-sm font-medium text-dreams-textPrimary">{rangeLabel}</span>
      </div>

      {isLoading ? (
        /* Loading skeleton — preserves the 7-column shape while fetching */
        <div
          className="overflow-x-auto rounded-xl border border-dreams-border bg-white shadow-card"
          role="status"
          aria-label={t("loading")}
        >
          <div className="grid min-w-[840px] grid-cols-7 divide-x divide-dreams-border">
            {Array.from({ length: 7 }).map((_, i) => (
              <div key={i} className="animate-pulse">
                <div className="border-b border-dreams-border px-2 py-3">
                  <div className="mx-auto h-3 w-10 rounded bg-gray-200" />
                  <div className="mx-auto mt-2 h-6 w-6 rounded-full bg-gray-200" />
                </div>
                <div className="space-y-2 p-2">
                  <div className="h-12 rounded-md bg-gray-100" />
                  <div className="h-12 rounded-md bg-gray-100" />
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-dreams-border bg-white shadow-card">
          <div className="min-w-[840px]">
            {/* Day-of-week header */}
            <div className="grid grid-cols-7 divide-x divide-dreams-border">
              {days.map(dayHeader)}
            </div>
            {appointments.length === 0 ? (
              <div className="p-12 text-center">
                <Calendar className="mx-auto h-10 w-10 text-dreams-textSecondary opacity-50" />
                <p className="mt-3 font-medium text-dreams-textPrimary">{t("emptyTitle")}</p>
                <p className="mt-1 text-sm text-dreams-textSecondary">{t("emptyHint")}</p>
              </div>
            ) : (
              <div className="grid grid-cols-7 divide-x divide-dreams-border">
                {days.map((day) => {
                  const key = formatLocalDate(day);
                  const dayAppts = byDay.get(key) ?? [];
                  return (
                    <div key={key} className="min-h-[160px] space-y-1.5 p-1.5">
                      {dayAppts.map((appt) => {
                        const statusKey = STATUS_KEYS[appt.status];
                        return (
                          <button
                            key={appt.id}
                            type="button"
                            onClick={() => onSelectAppointment(appt)}
                            className={`w-full rounded-md border border-dreams-border border-l-4 bg-white p-2 text-left transition-colors hover:bg-dreams-lightBg ${
                              STATUS_ACCENT_CLASSES[appt.status] ?? "border-l-dreams-border"
                            }`}
                          >
                            <p className="text-xs font-semibold text-dreams-textPrimary">
                              {formatTime(appt.scheduled_at)}
                            </p>
                            <p className="mt-0.5 truncate text-xs text-dreams-textPrimary">
                              {appt.patient_name ?? t("unknownPatient")}
                            </p>
                            <div className="mt-1">
                              <Badge
                                variant={(STATUS_VARIANT_MAP[appt.status] as any) ?? "pending"}
                                className="px-1.5 py-0 text-[10px]"
                              >
                                {statusKey ? tAppt(`status.${statusKey}`) : appt.status}
                              </Badge>
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Appointment detail modal (calendar card click-through)
// ---------------------------------------------------------------------------

interface AppointmentDetailModalProps {
  appointment: Appointment;
  onClose: () => void;
  onStatusAction: (apptId: string, newStatus: string) => void;
  statusPending: boolean;
  onGenerateLink: (apptId: string) => void;
  linkPending: boolean;
  onEdit: () => void;
  onCancel: () => void;
  onLinkAccount?: () => void;
}

function AppointmentDetailModal({
  appointment: appt,
  onClose,
  onStatusAction,
  statusPending,
  onGenerateLink,
  linkPending,
  onEdit,
  onCancel,
  onLinkAccount,
}: AppointmentDetailModalProps) {
  const t = useTranslations("doctorAppointments.calendar.detail");
  const tAppt = useTranslations("appointments");
  const format = useFormatter();

  const typeKey = TYPE_KEYS[appt.type];
  const statusKey = STATUS_KEYS[appt.status];
  const isActive = ["scheduled", "arrived", "in-progress"].includes(appt.status);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-label={t("ariaLabel")}
        className="w-[calc(100%-2rem)] sm:w-full sm:max-w-md rounded-xl bg-white shadow-xl"
      >
        <div className="flex items-center justify-between border-b border-dreams-border px-6 py-4">
          <h2 className="text-lg font-semibold text-dreams-textPrimary">{t("title")}</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("close")}
            className="text-dreams-textSecondary hover:text-dreams-textPrimary"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="px-6 py-4 space-y-4">
          {/* Patient */}
          <div className="flex flex-wrap items-center gap-2">
            <User className="h-4 w-4 text-dreams-textSecondary flex-shrink-0" />
            <span className="font-semibold text-dreams-textPrimary">
              {appt.patient_name ?? t("unknownPatient")}
            </span>
            {appt.is_provisional && (
              <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">
                {t("walkIn")}
              </span>
            )}
            <Badge variant={(STATUS_VARIANT_MAP[appt.status] as any) ?? "pending"}>
              {statusKey ? tAppt(`status.${statusKey}`) : appt.status}
            </Badge>
          </div>
          {appt.is_provisional && appt.patient_phone && (
            <p className="-mt-2 text-xs text-dreams-textSecondary">{appt.patient_phone}</p>
          )}

          {/* Details grid */}
          <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
            <div>
              <dt className="text-xs font-medium uppercase text-dreams-textSecondary">{t("date")}</dt>
              <dd className="mt-0.5 text-dreams-textPrimary">
                {format.dateTime(new Date(appt.scheduled_at), {
                  weekday: "short",
                  day: "numeric",
                  month: "short",
                  year: "numeric",
                })}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase text-dreams-textSecondary">{t("time")}</dt>
              <dd className="mt-0.5 text-dreams-textPrimary">{formatTime(appt.scheduled_at)}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase text-dreams-textSecondary">{t("duration")}</dt>
              <dd className="mt-0.5 text-dreams-textPrimary">
                {t("durationMinutes", { count: appt.duration_minutes })}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase text-dreams-textSecondary">{t("type")}</dt>
              <dd className="mt-0.5 text-dreams-textPrimary">
                {typeKey ? tAppt(`types.${typeKey}`) : appt.type}
              </dd>
            </div>
            {appt.clinic_name && (
              <div className="col-span-2">
                <dt className="text-xs font-medium uppercase text-dreams-textSecondary">{t("clinic")}</dt>
                <dd className="mt-0.5 text-dreams-textPrimary">
                  {appt.clinic_name}
                  {appt.branch_name ? ` — ${appt.branch_name}` : ""}
                </dd>
              </div>
            )}
            {appt.chief_complaint && (
              <div className="col-span-2">
                <dt className="text-xs font-medium uppercase text-dreams-textSecondary">
                  {t("chiefComplaint")}
                </dt>
                <dd className="mt-0.5 text-dreams-textPrimary">{appt.chief_complaint}</dd>
              </div>
            )}
          </dl>

          {/* Status transitions — same rule set as the list cards */}
          <StatusActionButtons appt={appt} onAction={onStatusAction} isPending={statusPending} />

          {/* Footer actions */}
          <div className="flex flex-wrap items-center gap-1.5 border-t border-dreams-border pt-4">
            {appt.type === "teleconsult" && isActive &&
              (appt.meeting_url ? (
                <a
                  href={appt.meeting_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 rounded-md bg-dreams-blue px-2.5 py-1.5 text-xs font-medium text-white hover:opacity-90 transition-opacity"
                >
                  <Video className="h-3 w-3" />
                  {t("joinCall")}
                </a>
              ) : (
                <button
                  type="button"
                  onClick={() => onGenerateLink(appt.id)}
                  disabled={linkPending}
                  className="flex items-center gap-1 rounded-md border border-dreams-blue px-2.5 py-1.5 text-xs text-dreams-blue hover:bg-dreams-blue/10 transition-colors disabled:opacity-50"
                >
                  <Video className="h-3 w-3" />
                  {linkPending ? t("generatingLink") : t("getCallLink")}
                </button>
              ))}
            {appt.is_provisional && onLinkAccount && (
              <button
                type="button"
                onClick={onLinkAccount}
                className="flex items-center gap-1 rounded-md border border-dreams-blue px-2.5 py-1.5 text-xs text-dreams-blue hover:bg-dreams-blue/10 transition-colors"
              >
                <UserCheck className="h-3 w-3" />
                {t("linkAccount")}
              </button>
            )}
            {appt.status === "scheduled" && (
              <>
                <button
                  type="button"
                  onClick={onEdit}
                  className="flex items-center gap-1 rounded-md border border-dreams-border px-2.5 py-1.5 text-xs text-dreams-textSecondary hover:bg-dreams-lightBg transition-colors"
                >
                  <Pencil className="h-3 w-3" />
                  {t("edit")}
                </button>
                <button
                  type="button"
                  onClick={onCancel}
                  className="flex items-center gap-1 rounded-md border border-red-200 px-2.5 py-1.5 text-xs text-red-600 hover:bg-red-50 transition-colors"
                >
                  <XCircle className="h-3 w-3" />
                  {t("cancel")}
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

interface DoctorProfile {
  id: string;
}

interface LinkingAppt {
  provisionalPatientId: string;
  patientName: string;
}

export default function DoctorAppointmentsPage() {
  const today = formatDateInput(new Date());
  const [selectedDate, setSelectedDate] = useState(today);
  const [view, setView] = useState<"list" | "calendar">("list");
  const [weekAnchor, setWeekAnchor] = useState<Date>(() => new Date());
  const [detailAppt, setDetailAppt] = useState<Appointment | null>(null);
  const [showBookingModal, setShowBookingModal] = useState(false);
  const [editingAppointment, setEditingAppointment] = useState<Appointment | null>(null);
  const [cancellingAppointment, setCancellingAppointment] = useState<Appointment | null>(null);
  const [linkingAppt, setLinkingAppt] = useState<LinkingAppt | null>(null);
  const [doctorId, setDoctorId] = useState<string | null>(null);
  const [activeClinics, setActiveClinics] = useState<{ id: string; name: string }[]>([]);
  const queryClient = useQueryClient();
  const tCal = useTranslations("doctorAppointments");

  // Fetch doctor profile to get doctor ID for appointment creation
  useEffect(() => {
    api
      .get("/api/v1/doctors/profile")
      .then((res) => setDoctorId(res.data?.id || null))
      .catch(() => {});
    api
      .get("/api/v1/clinics/my")
      .then((res) => {
        const data = res.data?.data || res.data || [];
        setActiveClinics(Array.isArray(data) ? data : []);
      })
      .catch(() => {});
  }, []);

  const { data, isLoading } = useQuery({
    queryKey: ["doctor-appointments", selectedDate],
    queryFn: () => getAppointments({ date: selectedDate }),
  });

  // Week range (local Mon–Sun). Fetch a ±1-day buffer: the backend filters on
  // UTC day bounds, so an early-morning IST appointment would otherwise fall
  // just outside the requested window.
  const weekStart = startOfWeekMonday(weekAnchor);
  const weekFrom = formatLocalDate(addDays(weekStart, -1));
  const weekTo = formatLocalDate(addDays(weekStart, 7));

  const { data: weekData, isLoading: weekLoading } = useQuery({
    queryKey: ["doctor-appointments", "week", weekFrom],
    queryFn: () => getAppointments({ from: weekFrom, to: weekTo, limit: 100 }),
    enabled: view === "calendar",
  });
  const weekAppointments = weekData?.data ?? [];

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      updateAppointmentStatus(id, { status: status as any }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["doctor-appointments"] });
    },
  });

  const meetingLinkMutation = useMutation({
    mutationFn: (id: string) => generateMeetingLink(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["doctor-appointments"] });
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

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["doctor-appointments"] });

  // Use the first clinic as the active context for guest/link actions, if available
  const primaryClinicId = activeClinics[0]?.id ?? "";

  return (
    <div className="space-y-6">
      {showBookingModal && (
        <BookAppointmentModal
          doctorId={doctorId}
          onClose={() => setShowBookingModal(false)}
          onSuccess={invalidate}
        />
      )}
      {editingAppointment && (
        <EditAppointmentModal
          appointment={editingAppointment}
          onClose={() => setEditingAppointment(null)}
          onSuccess={() => { invalidate(); setEditingAppointment(null); }}
        />
      )}
      {cancellingAppointment && (
        <CancelAppointmentModal
          appointment={cancellingAppointment}
          onClose={() => setCancellingAppointment(null)}
          onSuccess={() => { invalidate(); setCancellingAppointment(null); }}
        />
      )}
      {linkingAppt && primaryClinicId && (
        <LinkAccountModal
          provisionalPatientId={linkingAppt.provisionalPatientId}
          patientName={linkingAppt.patientName}
          clinicId={primaryClinicId}
          onClose={() => setLinkingAppt(null)}
          onSuccess={() => { invalidate(); setLinkingAppt(null); }}
        />
      )}
      {detailAppt && (
        <AppointmentDetailModal
          appointment={detailAppt}
          onClose={() => setDetailAppt(null)}
          onStatusAction={(id, status) => {
            statusMutation.mutate({ id, status });
            setDetailAppt(null);
          }}
          statusPending={statusMutation.isPending}
          onGenerateLink={(id) => meetingLinkMutation.mutate(id)}
          linkPending={meetingLinkMutation.isPending}
          onEdit={() => { setEditingAppointment(detailAppt); setDetailAppt(null); }}
          onCancel={() => { setCancellingAppointment(detailAppt); setDetailAppt(null); }}
          onLinkAccount={
            primaryClinicId && detailAppt.is_provisional
              ? () => {
                  setLinkingAppt({
                    provisionalPatientId: detailAppt.patient_id,
                    patientName: detailAppt.patient_name ?? "Patient",
                  });
                  setDetailAppt(null);
                }
              : undefined
          }
        />
      )}

      <Breadcrumb
        items={[
          { label: "Dashboard", href: "/doctor/dashboard" },
          { label: "Appointments" },
        ]}
      />

      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-dreams-textPrimary">Appointments</h1>
          {view === "list" && (
            <p className="text-sm text-dreams-textSecondary mt-0.5">
              {isToday ? "Today's schedule" : displayDate}
            </p>
          )}
        </div>

        {/* View toggle + date picker + New Appointment button */}
        <div className="flex items-center gap-2 flex-wrap">
          <div
            role="group"
            aria-label={tCal("view.label")}
            className="flex rounded-lg border border-dreams-border bg-white p-0.5"
          >
            <button
              type="button"
              onClick={() => setView("list")}
              aria-pressed={view === "list"}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                view === "list"
                  ? "bg-dreams-blue text-white"
                  : "text-dreams-textSecondary hover:text-dreams-textPrimary"
              }`}
            >
              <List className="h-4 w-4" />
              {tCal("view.list")}
            </button>
            <button
              type="button"
              onClick={() => setView("calendar")}
              aria-pressed={view === "calendar"}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                view === "calendar"
                  ? "bg-dreams-blue text-white"
                  : "text-dreams-textSecondary hover:text-dreams-textPrimary"
              }`}
            >
              <CalendarDays className="h-4 w-4" />
              {tCal("view.calendar")}
            </button>
          </div>
          {view === "list" && (
            <>
              <Calendar className="h-4 w-4 text-dreams-textSecondary" aria-hidden="true" />
              <input
                type="date"
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
                aria-label="Appointments date"
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
            </>
          )}
          <button
            onClick={() => setShowBookingModal(true)}
            className="flex items-center gap-2 rounded-lg bg-dreams-blue px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
          >
            <Plus className="h-4 w-4" />
            New Appointment
          </button>
        </div>
      </div>

      {view === "calendar" && (
        <WeekCalendarView
          weekStart={weekStart}
          appointments={weekAppointments}
          isLoading={weekLoading}
          onPrevWeek={() => setWeekAnchor((d) => addDays(d, -7))}
          onNextWeek={() => setWeekAnchor((d) => addDays(d, 7))}
          onToday={() => setWeekAnchor(new Date())}
          onSelectAppointment={setDetailAppt}
        />
      )}

      {/* Summary */}
      {view === "list" && !isLoading && (
        <div className="flex items-center gap-2 text-sm text-dreams-textSecondary">
          <span className="font-medium text-dreams-textPrimary">{appointments.length}</span>
          {appointments.length === 1 ? " appointment" : " appointments"} scheduled
        </div>
      )}

      {/* Loading */}
      {view === "list" && isLoading && (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-200 border-t-dreams-blue" />
        </div>
      )}

      {/* Empty state */}
      {view === "list" && !isLoading && appointments.length === 0 && (
        <div className="rounded-xl border border-dreams-border bg-white p-12 text-center shadow-card">
          <Calendar className="mx-auto h-10 w-10 text-dreams-textSecondary opacity-50" />
          <p className="mt-3 font-medium text-dreams-textPrimary">No appointments</p>
          <p className="mt-1 text-sm text-dreams-textSecondary">
            {isToday ? "You have no appointments scheduled for today." : `No appointments on ${displayDate}.`}
          </p>
        </div>
      )}

      {/* Appointment cards */}
      {view === "list" && !isLoading && appointments.length > 0 && (
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
                    <div className="flex flex-wrap items-center gap-2">
                      <User className="h-4 w-4 text-dreams-textSecondary flex-shrink-0" />
                      <span className="font-semibold text-dreams-textPrimary">
                        {appt.patient_name ?? "Unknown Patient"}
                      </span>
                      {appt.is_provisional && (
                        <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">
                          Walk-in
                        </span>
                      )}
                      <Badge variant={TYPE_LABELS[appt.type] ? "upcoming" : "pending"} className="text-xs">
                        {TYPE_LABELS[appt.type] ?? appt.type}
                      </Badge>
                    </div>
                    {appt.is_provisional && appt.patient_phone && (
                      <p className="mt-0.5 text-xs text-dreams-textSecondary">{appt.patient_phone}</p>
                    )}

                    {appt.chief_complaint && (
                      <p className="mt-1 text-sm text-dreams-textSecondary">
                        Chief complaint: {appt.chief_complaint}
                      </p>
                    )}

                    {appt.clinic_name && (
                      <p className="mt-0.5 text-xs text-dreams-textSecondary">
                        {appt.clinic_name}
                        {appt.branch_name ? ` — ${appt.branch_name}` : ""}
                      </p>
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
                          href={`/doctor/prescriptions/new?appointment_id=${appt.id}&patient_id=${appt.patient_id}`}
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

                {/* Right: status badge + actions */}
                <div className="flex flex-col items-end gap-2 flex-shrink-0">
                  <Badge variant={STATUS_VARIANT_MAP[appt.status] as any}>
                    {STATUS_LABELS[appt.status] ?? appt.status}
                  </Badge>
                  <div className="flex flex-wrap items-center justify-end gap-1.5">
                    {appt.type === "teleconsult" &&
                      ["scheduled", "arrived", "in-progress"].includes(appt.status) &&
                      (appt.meeting_url ? (
                        <a
                          href={appt.meeting_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-1 rounded-md bg-dreams-blue px-2 py-1 text-xs font-medium text-white hover:opacity-90 transition-opacity"
                        >
                          <Video className="h-3 w-3" />
                          Join Call
                        </a>
                      ) : (
                        <button
                          onClick={() => meetingLinkMutation.mutate(appt.id)}
                          disabled={meetingLinkMutation.isPending}
                          className="flex items-center gap-1 rounded-md border border-dreams-blue px-2 py-1 text-xs text-dreams-blue hover:bg-dreams-blue/10 transition-colors disabled:opacity-50"
                        >
                          <Video className="h-3 w-3" />
                          {meetingLinkMutation.isPending ? "Generating…" : "Get Link"}
                        </button>
                      ))}
                    {appt.is_provisional && (
                      <button
                        onClick={() => setLinkingAppt({ provisionalPatientId: appt.patient_id, patientName: appt.patient_name ?? "Patient" })}
                        className="flex items-center gap-1 rounded-md border border-dreams-blue px-2 py-1 text-xs text-dreams-blue hover:bg-dreams-blue/10 transition-colors"
                      >
                        <UserCheck className="h-3 w-3" />
                        Link Account
                      </button>
                    )}
                    {appt.status === "scheduled" && (
                      <>
                        <button
                          onClick={() => setEditingAppointment(appt)}
                          className="flex items-center gap-1 rounded-md border border-dreams-border px-2 py-1 text-xs text-dreams-textSecondary hover:bg-dreams-lightBg transition-colors"
                        >
                          <Pencil className="h-3 w-3" />
                          Edit
                        </button>
                        <button
                          onClick={() => setCancellingAppointment(appt)}
                          className="flex items-center gap-1 rounded-md border border-red-200 px-2 py-1 text-xs text-red-600 hover:bg-red-50 transition-colors"
                        >
                          <XCircle className="h-3 w-3" />
                          Cancel
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
