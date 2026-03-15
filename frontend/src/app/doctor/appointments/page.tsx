"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Calendar, Clock, User, FileText, FilePlus, CheckCircle, XCircle, UserCheck, Plus, X, Pencil } from "lucide-react";
import Link from "next/link";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { Badge } from "@/components/ui/badge";
import {
  getAppointments,
  updateAppointmentStatus,
  updateAppointment,
  cancelAppointment,
  createAppointment,
  type Appointment,
  type UpdateAppointmentData,
} from "@/lib/api/appointments";
import { getClinicBranches, type ClinicBranch } from "@/lib/api/clinics";
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
}: {
  onSelect: (p: PatientSuggestion) => void;
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
  const [selectedPatient, setSelectedPatient] = useState<PatientSuggestion | null>(null);
  const [date, setDate] = useState(formatDateInput(new Date()));
  const [time, setTime] = useState("09:00");
  const [duration, setDuration] = useState(30);
  const [type, setType] = useState<"in-person" | "teleconsult" | "follow-up">("in-person");
  const [chiefComplaint, setChiefComplaint] = useState("");
  const [clinicId, setClinicId] = useState("");
  const [branchId, setBranchId] = useState("");
  const [clinics, setClinics] = useState<ClinicOption[]>([]);
  const [branches, setBranches] = useState<ClinicBranch[]>([]);
  const [branchesLoading, setBranchesLoading] = useState(false);
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

  // Fetch branches when a clinic is selected
  useEffect(() => {
    setBranchId("");
    setBranches([]);
    if (!clinicId) return;
    setBranchesLoading(true);
    getClinicBranches(clinicId)
      .then((data) => setBranches(data))
      .catch(() => setBranches([]))
      .finally(() => setBranchesLoading(false));
  }, [clinicId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!selectedPatient) {
      setError("Please select a patient");
      return;
    }
    setSubmitting(true);
    try {
      const scheduledAt = new Date(`${date}T${time}:00`).toISOString();
      await createAppointment({
        patient_id: selectedPatient.id,
        doctor_id: doctorId ?? undefined,
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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-lg rounded-xl bg-white shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-dreams-border px-6 py-4">
          <h2 className="text-lg font-semibold text-dreams-textPrimary">New Appointment</h2>
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

          {/* Patient */}
          <div>
            <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">
              Patient *
            </label>
            {selectedPatient ? (
              <div className="flex items-center gap-3 rounded-lg border border-dreams-blue bg-dreams-blue/5 px-4 py-2.5">
                <div className="flex-1">
                  <p className="text-sm font-semibold text-dreams-textPrimary">{selectedPatient.full_name}</p>
                  {selectedPatient.phone && (
                    <p className="text-xs text-dreams-textSecondary">{selectedPatient.phone}</p>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedPatient(null)}
                  className="text-dreams-textSecondary hover:text-red-500 transition-colors"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ) : (
              <PatientSearchInput onSelect={setSelectedPatient} />
            )}
          </div>

          {/* Date + Time */}
          <div className="grid grid-cols-2 gap-3">
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
          <div className="grid grid-cols-2 gap-3">
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

          {/* Clinic (if any) */}
          {clinics.length > 0 && (
            <div>
              <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">Clinic</label>
              <select
                value={clinicId}
                onChange={(e) => setClinicId(e.target.value)}
                className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
              >
                <option value="">No clinic (private)</option>
                {clinics.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Branch selector (shown when a clinic with branches is selected) */}
          {clinicId && (branchesLoading || branches.length > 0) && (
            <div>
              <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">Branch</label>
              {branchesLoading ? (
                <div className="h-10 rounded-lg border border-dreams-border bg-gray-50 flex items-center px-3">
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-dreams-blue border-t-transparent" />
                  <span className="ml-2 text-sm text-dreams-textSecondary">Loading branches...</span>
                </div>
              ) : (
                <select
                  value={branchId}
                  onChange={(e) => setBranchId(e.target.value)}
                  className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
                >
                  <option value="">Any branch</option>
                  {branches.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name}{b.city ? ` — ${b.city}` : ""}
                    </option>
                  ))}
                </select>
              )}
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3 pt-2">
            <button
              type="submit"
              disabled={submitting || !selectedPatient}
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
  const [branches, setBranches] = useState<ClinicBranch[]>([]);
  const [branchesLoading, setBranchesLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get("/api/v1/clinics/my")
      .then((res) => { const d = res.data?.data || res.data || []; setClinics(Array.isArray(d) ? d : []); })
      .catch(() => {});
  }, []);

  useEffect(() => {
    setBranchId(""); setBranches([]);
    if (!clinicId) return;
    setBranchesLoading(true);
    getClinicBranches(clinicId)
      .then((d) => setBranches(d))
      .catch(() => setBranches([]))
      .finally(() => setBranchesLoading(false));
  }, [clinicId]);

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
      <div className="w-full max-w-lg rounded-xl bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-dreams-border px-6 py-4">
          <h2 className="text-lg font-semibold text-dreams-textPrimary">Edit Appointment</h2>
          <button type="button" onClick={onClose} className="text-dreams-textSecondary hover:text-dreams-textPrimary">
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-4 space-y-4 max-h-[80vh] overflow-y-auto">
          {error && (
            <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-2 text-sm text-red-700">{error}</div>
          )}

          {/* Patient (read-only) */}
          <div>
            <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">Patient</label>
            <div className="h-10 rounded-lg border border-dreams-border bg-dreams-lightBg px-3 flex items-center text-sm text-dreams-textSecondary">
              {appointment.patient_name ?? "—"}
            </div>
          </div>

          {/* Date + Time */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">Date *</label>
              <input type="date" value={date} onChange={(e) => setDate(e.target.value)} required
                className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20" />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">Time *</label>
              <input type="time" value={time} onChange={(e) => setTime(e.target.value)} required
                className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20" />
            </div>
          </div>

          {/* Duration + Type */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">Duration</label>
              <select value={duration} onChange={(e) => setDuration(Number(e.target.value))}
                className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20">
                <option value={15}>15 min</option>
                <option value={30}>30 min</option>
                <option value={45}>45 min</option>
                <option value={60}>60 min</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">Type *</label>
              <select value={type} onChange={(e) => setType(e.target.value as typeof type)}
                className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20">
                <option value="in-person">In Person</option>
                <option value="teleconsult">Teleconsult</option>
                <option value="follow-up">Follow-up</option>
              </select>
            </div>
          </div>

          {/* Chief Complaint */}
          <div>
            <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">Chief Complaint</label>
            <input type="text" value={chiefComplaint} onChange={(e) => setChiefComplaint(e.target.value)}
              placeholder="e.g., Fever, headache for 2 days"
              className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20" />
          </div>

          {/* Clinic */}
          {clinics.length > 0 && (
            <div>
              <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">Clinic</label>
              <select value={clinicId} onChange={(e) => setClinicId(e.target.value)}
                className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20">
                <option value="">No clinic (private)</option>
                {clinics.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
          )}

          {/* Branch */}
          {clinicId && (branchesLoading || branches.length > 0) && (
            <div>
              <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">Branch</label>
              {branchesLoading ? (
                <div className="h-10 rounded-lg border border-dreams-border bg-gray-50 flex items-center px-3">
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-dreams-blue border-t-transparent" />
                  <span className="ml-2 text-sm text-dreams-textSecondary">Loading branches...</span>
                </div>
              ) : (
                <select value={branchId} onChange={(e) => setBranchId(e.target.value)}
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
      <div className="w-full max-w-md rounded-xl bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-dreams-border px-6 py-4">
          <h2 className="text-lg font-semibold text-dreams-textPrimary">Cancel Appointment</h2>
          <button type="button" onClick={onClose} className="text-dreams-textSecondary hover:text-dreams-textPrimary">
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
            <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">Reason (optional)</label>
            <input
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
// Main page
// ---------------------------------------------------------------------------

interface DoctorProfile {
  id: string;
}

export default function DoctorAppointmentsPage() {
  const today = formatDateInput(new Date());
  const [selectedDate, setSelectedDate] = useState(today);
  const [showBookingModal, setShowBookingModal] = useState(false);
  const [editingAppointment, setEditingAppointment] = useState<Appointment | null>(null);
  const [cancellingAppointment, setCancellingAppointment] = useState<Appointment | null>(null);
  const [doctorId, setDoctorId] = useState<string | null>(null);
  const queryClient = useQueryClient();

  // Fetch doctor profile to get doctor ID for appointment creation
  useEffect(() => {
    api
      .get("/api/v1/doctors/profile")
      .then((res) => setDoctorId(res.data?.id || null))
      .catch(() => {});
  }, []);

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

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["doctor-appointments", selectedDate] });

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

        {/* Date picker + New Appointment button */}
        <div className="flex items-center gap-2 flex-wrap">
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
          <button
            onClick={() => setShowBookingModal(true)}
            className="flex items-center gap-2 rounded-lg bg-dreams-blue px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
          >
            <Plus className="h-4 w-4" />
            New Appointment
          </button>
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
                  {appt.status === "scheduled" && (
                    <div className="flex items-center gap-1.5">
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
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
