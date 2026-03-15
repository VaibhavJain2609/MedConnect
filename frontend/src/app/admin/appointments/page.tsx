"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ColumnDef } from "@tanstack/react-table";
import { Plus, Search, X, Pencil, XCircle } from "lucide-react";
import {
  getAppointments,
  createAppointment,
  updateAppointment,
  cancelAppointment,
  type Appointment,
  type UpdateAppointmentData,
} from "@/lib/api/appointments";
import { getClinicBranches, type ClinicBranch } from "@/lib/api/clinics";
import api from "@/lib/api";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { DataTable, DataTableColumnHeader } from "@/components/ui/data-table";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";

// ---------------------------------------------------------------------------
// Patient search typeahead (with inline quick-add)
// ---------------------------------------------------------------------------

interface PatientSuggestion {
  id: string;
  full_name: string;
  phone: string | null;
}

function PatientSearchInput({ onSelect }: { onSelect: (p: PatientSuggestion) => void }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<PatientSuggestion[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [showQuickAdd, setShowQuickAdd] = useState(false);
  const [newName, setNewName] = useState("");
  const [newPhone, setNewPhone] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const search = useCallback((q: string) => {
    if (q.length < 2) { setResults([]); setOpen(false); return; }
    setLoading(true);
    api.get(`/api/v1/admin/users?role=patient&search=${encodeURIComponent(q)}&limit=10`)
      .then((res) => { setResults(res.data.data || []); setOpen(true); })
      .catch(() => setResults([]))
      .finally(() => setLoading(false));
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setQuery(val);
    setShowQuickAdd(false);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => search(val), 400);
  };

  const handleQuickAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!newName.trim()) return;
    setCreating(true);
    setCreateError("");
    try {
      const res = await api.post("/api/v1/admin/users", {
        full_name: newName.trim(),
        phone: newPhone.trim() || undefined,
        email: newEmail.trim() || undefined,
      });
      onSelect({ id: res.data.id, full_name: res.data.full_name, phone: res.data.phone });
      setOpen(false);
      setShowQuickAdd(false);
      setQuery("");
      setNewName(""); setNewPhone(""); setNewEmail("");
    } catch (err: any) {
      const msg = err.response?.data?.detail?.error?.message || "Failed to create patient";
      setCreateError(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="relative">
      <input
        type="text"
        value={query}
        onChange={handleChange}
        placeholder="Search patient by name or phone..."
        className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => { if (!showQuickAdd) setOpen(false); }, 200)}
      />
      {loading && (
        <div className="absolute right-3 top-1/2 -translate-y-1/2">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-dreams-blue border-t-transparent" />
        </div>
      )}
      {open && (
        <div className="absolute z-50 mt-1 w-full rounded-lg border border-dreams-border bg-white shadow-lg">
          {results.map((p) => (
            <button key={p.id} type="button"
              className="flex w-full items-start gap-3 px-4 py-3 text-left hover:bg-dreams-lightBg transition-colors border-b border-dreams-border last:border-0"
              onMouseDown={() => { onSelect(p); setQuery(""); setOpen(false); }}>
              <div className="flex-1">
                <p className="text-sm font-medium text-dreams-textPrimary">{p.full_name}</p>
                {p.phone && <p className="text-xs text-dreams-textSecondary">{p.phone}</p>}
              </div>
            </button>
          ))}
          {!loading && query.length >= 2 && results.length === 0 && !showQuickAdd && (
            <div className="px-4 py-3 text-sm text-dreams-textSecondary">No patients found.</div>
          )}
          {!showQuickAdd ? (
            <button type="button"
              className="flex w-full items-center gap-2 px-4 py-3 text-sm font-medium text-dreams-blue hover:bg-dreams-blue/5 transition-colors border-t border-dreams-border"
              onMouseDown={(e) => { e.preventDefault(); setShowQuickAdd(true); setNewName(query); }}>
              <Plus className="h-4 w-4" />
              Add new patient{query ? ` "${query}"` : ""}
            </button>
          ) : (
            <div className="px-4 py-3 border-t border-dreams-border" onMouseDown={(e) => e.preventDefault()}>
              <p className="text-xs font-semibold text-dreams-textSecondary uppercase mb-2">Quick Add Patient</p>
              {createError && (
                <p className="mb-2 text-xs text-red-600">{createError}</p>
              )}
              <div className="space-y-2">
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="Full name *"
                  className="w-full h-9 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-1 focus:ring-dreams-blue/20"
                  autoFocus
                />
                <input
                  type="tel"
                  value={newPhone}
                  onChange={(e) => setNewPhone(e.target.value)}
                  placeholder="Phone"
                  className="w-full h-9 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-1 focus:ring-dreams-blue/20"
                />
                <input
                  type="email"
                  value={newEmail}
                  onChange={(e) => setNewEmail(e.target.value)}
                  placeholder="Email (optional)"
                  className="w-full h-9 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-1 focus:ring-dreams-blue/20"
                />
                <div className="flex gap-2 pt-1">
                  <button type="button" onClick={handleQuickAdd} disabled={creating || !newName.trim()}
                    className="flex-1 rounded-lg bg-dreams-blue px-3 py-1.5 text-xs font-medium text-white hover:opacity-90 disabled:opacity-50 transition-opacity">
                    {creating ? "Adding..." : "Add Patient"}
                  </button>
                  <button type="button" onClick={() => setShowQuickAdd(false)}
                    className="rounded-lg border border-dreams-border px-3 py-1.5 text-xs font-medium text-dreams-textPrimary hover:bg-dreams-lightBg transition-colors">
                    Cancel
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Doctor search typeahead
// ---------------------------------------------------------------------------

interface DoctorSuggestion {
  id: string;
  name: string;
  specialization: string | null;
}

function DoctorSearchInput({ onSelect }: { onSelect: (d: DoctorSuggestion) => void }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<DoctorSuggestion[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const search = useCallback((q: string) => {
    if (q.length < 2) { setResults([]); setOpen(false); return; }
    setLoading(true);
    api.get(`/api/v1/admin/doctors?search=${encodeURIComponent(q)}&limit=10`)
      .then((res) => { setResults(res.data.data || res.data.doctors || []); setOpen(true); })
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
        placeholder="Search doctor by name..."
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
            <button key={d.id} type="button"
              className="flex w-full items-start gap-3 px-4 py-3 text-left hover:bg-dreams-lightBg transition-colors"
              onMouseDown={() => { onSelect(d); setQuery(""); setOpen(false); }}>
              <div className="flex-1">
                <p className="text-sm font-medium text-dreams-textPrimary">{d.name}</p>
                {d.specialization && <p className="text-xs text-dreams-textSecondary">{d.specialization}</p>}
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
// Create Appointment Modal
// ---------------------------------------------------------------------------

interface ClinicOption { id: string; name: string; }

function formatDateInput(d: Date) { return d.toISOString().slice(0, 10); }

function CreateAppointmentModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const [selectedPatient, setSelectedPatient] = useState<PatientSuggestion | null>(null);
  const [selectedDoctor, setSelectedDoctor] = useState<DoctorSuggestion | null>(null);
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
    if (!selectedPatient) { setError("Please select a patient"); return; }
    if (!selectedDoctor) { setError("Please select a doctor"); return; }
    setSubmitting(true);
    try {
      await createAppointment({
        patient_id: selectedPatient.id,
        doctor_id: selectedDoctor.id,
        clinic_id: clinicId || undefined,
        branch_id: branchId || undefined,
        scheduled_at: new Date(`${date}T${time}:00`).toISOString(),
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
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-lg rounded-xl bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-dreams-border px-6 py-4">
          <h2 className="text-lg font-semibold text-dreams-textPrimary">New Appointment</h2>
          <button type="button" onClick={onClose} className="text-dreams-textSecondary hover:text-dreams-textPrimary">
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-4 space-y-4 max-h-[80vh] overflow-y-auto">
          {error && (
            <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-2 text-sm text-red-700">{error}</div>
          )}

          {/* Patient */}
          <div>
            <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">Patient *</label>
            {selectedPatient ? (
              <div className="flex items-center gap-3 rounded-lg border border-dreams-blue bg-dreams-blue/5 px-4 py-2.5">
                <div className="flex-1">
                  <p className="text-sm font-semibold text-dreams-textPrimary">{selectedPatient.full_name}</p>
                  {selectedPatient.phone && <p className="text-xs text-dreams-textSecondary">{selectedPatient.phone}</p>}
                </div>
                <button type="button" onClick={() => setSelectedPatient(null)} className="text-dreams-textSecondary hover:text-red-500">
                  <X className="h-4 w-4" />
                </button>
              </div>
            ) : (
              <PatientSearchInput onSelect={setSelectedPatient} />
            )}
          </div>

          {/* Doctor */}
          <div>
            <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">Doctor *</label>
            {selectedDoctor ? (
              <div className="flex items-center gap-3 rounded-lg border border-dreams-blue bg-dreams-blue/5 px-4 py-2.5">
                <div className="flex-1">
                  <p className="text-sm font-semibold text-dreams-textPrimary">{selectedDoctor.name}</p>
                  {selectedDoctor.specialization && <p className="text-xs text-dreams-textSecondary">{selectedDoctor.specialization}</p>}
                </div>
                <button type="button" onClick={() => setSelectedDoctor(null)} className="text-dreams-textSecondary hover:text-red-500">
                  <X className="h-4 w-4" />
                </button>
              </div>
            ) : (
              <DoctorSearchInput onSelect={setSelectedDoctor} />
            )}
          </div>

          {/* Date + Time */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">Date *</label>
              <input type="date" value={date} onChange={(e) => setDate(e.target.value)}
                min={formatDateInput(new Date())} required
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
            <button type="submit" disabled={submitting || !selectedPatient || !selectedDoctor}
              className="flex-1 rounded-lg bg-dreams-blue px-4 py-2.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50 transition-opacity">
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
// Edit Appointment Modal
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

  const [selectedDoctor, setSelectedDoctor] = useState<DoctorSuggestion | null>(
    appointment.doctor_name ? { id: appointment.doctor_id, name: appointment.doctor_name, specialization: null } : null
  );
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
    if (!selectedDoctor) { setError("Please select a doctor"); return; }
    setSubmitting(true);
    try {
      const payload: UpdateAppointmentData = {
        doctor_id: selectedDoctor.id,
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

          {/* Doctor */}
          <div>
            <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">Doctor *</label>
            {selectedDoctor ? (
              <div className="flex items-center gap-3 rounded-lg border border-dreams-blue bg-dreams-blue/5 px-4 py-2.5">
                <div className="flex-1">
                  <p className="text-sm font-semibold text-dreams-textPrimary">{selectedDoctor.name}</p>
                  {selectedDoctor.specialization && <p className="text-xs text-dreams-textSecondary">{selectedDoctor.specialization}</p>}
                </div>
                <button type="button" onClick={() => setSelectedDoctor(null)} className="text-dreams-textSecondary hover:text-red-500">
                  <X className="h-4 w-4" />
                </button>
              </div>
            ) : (
              <DoctorSearchInput onSelect={setSelectedDoctor} />
            )}
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
            <button type="submit" disabled={submitting || !selectedDoctor}
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
// Cancel Appointment Modal
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
            Cancel appointment for <span className="font-medium text-dreams-textPrimary">{appointment.patient_name}</span> with{" "}
            <span className="font-medium text-dreams-textPrimary">{appointment.doctor_name}</span>?
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
              placeholder="e.g., Patient requested, scheduling conflict..."
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
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-dreams-border px-4 py-2.5 text-sm font-medium text-dreams-textPrimary hover:bg-dreams-lightBg transition-colors"
            >
              Keep
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

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

const TYPE_LABELS: Record<string, string> = {
  "in-person": "In Person",
  "teleconsult": "Teleconsult",
  "follow-up": "Follow-up",
};

export default function AdminAppointmentsPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [showModal, setShowModal] = useState(false);
  const [editingAppointment, setEditingAppointment] = useState<Appointment | null>(null);
  const [cancellingAppointment, setCancellingAppointment] = useState<Appointment | null>(null);
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery({
    queryKey: ["admin-appointments", statusFilter],
    queryFn: () =>
      getAppointments({
        status: statusFilter !== "all" ? statusFilter : undefined,
        all: true,
      }),
  });

  const allAppointments: Appointment[] = data?.data ?? [];

  // Client-side search filter
  const appointments = searchQuery
    ? allAppointments.filter(
        (a) =>
          (a.patient_name ?? "").toLowerCase().includes(searchQuery.toLowerCase()) ||
          (a.doctor_name ?? "").toLowerCase().includes(searchQuery.toLowerCase()) ||
          a.id.includes(searchQuery)
      )
    : allAppointments;

  const columns: ColumnDef<Appointment>[] = [
    {
      accessorKey: "patient_name",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Patient" />
      ),
      cell: ({ row }) => (
        <div className="flex items-center gap-3">
          <Avatar
            fallback={row.getValue("patient_name") as string}
            size="sm"
          />
          <div>
            <span className="font-medium">{row.getValue("patient_name") ?? "—"}</span>
          </div>
        </div>
      ),
    },
    {
      accessorKey: "doctor_name",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Doctor" />
      ),
      cell: ({ row }) => (
        <div className="flex items-center gap-3">
          <Avatar
            fallback={row.getValue("doctor_name") as string}
            size="sm"
          />
          <span className="font-medium">{row.getValue("doctor_name") ?? "—"}</span>
        </div>
      ),
    },
    {
      accessorKey: "clinic_name",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Clinic" />
      ),
      cell: ({ row }) => (
        <span className="text-dreams-textSecondary">{row.getValue("clinic_name") ?? "—"}</span>
      ),
    },
    {
      accessorKey: "type",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Type" />
      ),
      cell: ({ row }) => (
        <span>{TYPE_LABELS[row.getValue("type") as string] ?? row.getValue("type")}</span>
      ),
    },
    {
      accessorKey: "scheduled_at",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Scheduled At" />
      ),
      cell: ({ row }) => {
        const d = new Date(row.getValue("scheduled_at") as string);
        return (
          <div>
            <p className="font-medium">
              {d.toLocaleDateString("en-IN", { month: "short", day: "numeric", year: "numeric" })}
            </p>
            <p className="text-xs text-dreams-textSecondary">
              {d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: true })}
            </p>
          </div>
        );
      },
    },
    {
      accessorKey: "status",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Status" />
      ),
      cell: ({ row }) => {
        const s = row.getValue("status") as string;
        return (
          <Badge variant={STATUS_VARIANT_MAP[s] as any}>
            {STATUS_LABELS[s] ?? s}
          </Badge>
        );
      },
    },
    {
      id: "actions",
      header: () => <span className="text-xs font-medium text-dreams-textSecondary">Actions</span>,
      cell: ({ row }) => {
        const appt = row.original;
        const isScheduled = appt.status === "scheduled";
        return (
          <div className="flex items-center gap-2">
            {isScheduled && (
              <button
                onClick={() => setEditingAppointment(appt)}
                className="flex items-center gap-1 rounded-md border border-dreams-border px-2 py-1 text-xs text-dreams-textSecondary hover:bg-dreams-lightBg transition-colors"
              >
                <Pencil className="h-3 w-3" />
                Edit
              </button>
            )}
            {isScheduled && (
              <button
                onClick={() => setCancellingAppointment(appt)}
                className="flex items-center gap-1 rounded-md border border-red-200 px-2 py-1 text-xs text-red-600 hover:bg-red-50 transition-colors"
              >
                <XCircle className="h-3 w-3" />
                Cancel
              </button>
            )}
          </div>
        );
      },
    },
  ];

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12 space-y-4">
        <p className="text-red-600 font-medium">Failed to load appointments</p>
        <p className="text-dreams-textSecondary text-sm">
          {error instanceof Error ? error.message : "An error occurred"}
        </p>
      </div>
    );
  }

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["admin-appointments", statusFilter] });

  return (
    <div className="space-y-6">
      {showModal && (
        <CreateAppointmentModal
          onClose={() => setShowModal(false)}
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

      <Breadcrumb items={[{ label: "Appointments" }]} />

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-dreams-textPrimary">Appointments</h1>
          <p className="text-dreams-textSecondary mt-1">
            Manage patient appointments and schedules
          </p>
        </div>

        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-dreams-blue text-white rounded-lg hover:opacity-90 transition-opacity"
        >
          <Plus className="h-5 w-5" />
          <span>New Appointment</span>
        </button>
      </div>

      {/* Search and Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search by patient, doctor, or ID..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full h-10 pl-10 pr-4 rounded-lg border border-dreams-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
          />
        </div>

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="h-10 px-4 rounded-lg border border-dreams-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
        >
          <option value="all">All Status</option>
          <option value="scheduled">Scheduled</option>
          <option value="arrived">Arrived</option>
          <option value="in-progress">In Progress</option>
          <option value="completed">Completed</option>
          <option value="cancelled">Cancelled</option>
          <option value="no-show">No Show</option>
        </select>
      </div>

      {/* Data Table */}
      <DataTable
        columns={columns}
        data={appointments}
        pageSize={10}
        searchColumn="patient_name"
        searchPlaceholder="Search appointments..."
      />
    </div>
  );
}
