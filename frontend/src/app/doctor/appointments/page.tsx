"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { Calendar, Clock, User, FileText, FilePlus, CheckCircle, XCircle, UserCheck, Plus, X, Pencil, Video } from "lucide-react";
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

// Type and status labels come from the shared "appointments.types" /
// "appointments.status" message namespaces (see docs/i18n.md).
const KNOWN_TYPES = new Set<string>(["in-person", "teleconsult", "follow-up"]);

const STATUS_VARIANT_MAP: Record<string, string> = {
  scheduled: "upcoming",
  arrived: "inProgress",
  "in-progress": "inProgress",
  completed: "completed",
  cancelled: "overdue",
  "no-show": "pending",
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
  id,
}: {
  onSelect: (p: PatientSuggestion) => void;
  id?: string;
}) {
  const t = useTranslations("doctorAppointments.search");
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
        placeholder={t("placeholder")}
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
          {t("empty")}
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
  const t = useTranslations("doctorAppointments.linkModal");
  const tCommon = useTranslations("common");
  const [code, setCode] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!code.trim()) { setError(t("errorCode")); return; }
    setSubmitting(true);
    try {
      await linkProvisionalPatient(clinicId, {
        provisional_patient_id: provisionalPatientId,
        link_code: code.trim().toUpperCase(),
      });
      onSuccess();
      onClose();
    } catch (err: any) {
      const msg = err.response?.data?.detail?.error?.message || err.response?.data?.detail || t("errorFailed");
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
        aria-label={t("ariaLabel")}
        className="w-[calc(100%-2rem)] sm:w-full sm:max-w-md rounded-xl bg-white shadow-xl"
      >
        <div className="flex items-center justify-between border-b border-dreams-border px-6 py-4">
          <h2 className="text-lg font-semibold text-dreams-textPrimary">{t("title")}</h2>
          <button type="button" onClick={onClose} aria-label={tCommon("close")} className="text-dreams-textSecondary hover:text-dreams-textPrimary">
            <X className="h-5 w-5" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="px-6 py-4 space-y-4">
          <p className="text-sm text-dreams-textSecondary">
            {t.rich("body", {
              name: patientName,
              strong: (chunks) => (
                <span className="font-medium text-dreams-textPrimary">{chunks}</span>
              ),
              b: (chunks) => <span className="font-medium">{chunks}</span>,
            })}
          </p>
          {error && (
            <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-2 text-sm text-red-700">{error}</div>
          )}
          <div>
            <label
              htmlFor="link-code"
              className="mb-1 block text-sm font-medium text-dreams-textPrimary"
            >
              {t("codeLabel")}
            </label>
            <input
              id="link-code"
              type="text"
              value={code}
              onChange={(e) => setCode(e.target.value.toUpperCase())}
              placeholder={t("codePlaceholder")}
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
              {submitting ? t("submitting") : t("submit")}
            </button>
            <button type="button" onClick={onClose}
              className="rounded-lg border border-dreams-border px-4 py-2.5 text-sm font-medium text-dreams-textPrimary hover:bg-dreams-lightBg transition-colors">
              {tCommon("cancel")}
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
  const t = useTranslations("doctorAppointments.booking");
  const tTypes = useTranslations("appointments.types");
  const tCommon = useTranslations("common");
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
      if (!walkinName.trim()) { setError(t("errorName")); return; }
      if (!walkinPhone.trim()) { setError(t("errorPhone")); return; }
      if (!clinicId) { setError(t("errorClinic")); return; }
      if (!doctorId && !pickedDoctorId) { setError(t("errorDoctor")); return; }
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
        const msg = err.response?.data?.detail?.error?.message || err.response?.data?.detail || t("errorFailed");
        setError(typeof msg === "string" ? msg : JSON.stringify(msg));
      } finally {
        setSubmitting(false);
      }
      return;
    }

    if (!selectedPatient) { setError(t("errorPatient")); return; }
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
        t("errorFailed");
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
          <label htmlFor="booking-date" className="mb-1 block text-sm font-medium text-dreams-textPrimary">{t("date")}</label>
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
          <label htmlFor="booking-time" className="mb-1 block text-sm font-medium text-dreams-textPrimary">{t("time")}</label>
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
          <label htmlFor="booking-duration" className="mb-1 block text-sm font-medium text-dreams-textPrimary">{t("duration")}</label>
          <select
            id="booking-duration"
            value={duration}
            onChange={(e) => setDuration(Number(e.target.value))}
            className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
          >
            {[15, 30, 45, 60].map((m) => (
              <option key={m} value={m}>{t("durationOption", { count: m })}</option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="booking-type" className="mb-1 block text-sm font-medium text-dreams-textPrimary">{t("type")}</label>
          <select
            id="booking-type"
            value={type}
            onChange={(e) => setType(e.target.value as typeof type)}
            className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
          >
            <option value="in-person">{tTypes("in-person")}</option>
            <option value="teleconsult">{tTypes("teleconsult")}</option>
            <option value="follow-up">{tTypes("follow-up")}</option>
          </select>
        </div>
      </div>

      {/* Chief Complaint */}
      <div>
        <label htmlFor="booking-complaint" className="mb-1 block text-sm font-medium text-dreams-textPrimary">{t("chiefComplaint")}</label>
        <input
          id="booking-complaint"
          type="text"
          value={chiefComplaint}
          onChange={(e) => setChiefComplaint(e.target.value)}
          placeholder={t("chiefComplaintPlaceholder")}
          className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
        />
      </div>

      {/* Clinic */}
      {clinics.length > 0 && (
        <div>
          <label htmlFor="booking-clinic" className="mb-1 block text-sm font-medium text-dreams-textPrimary">
            {tab === "walkin" ? t("clinicRequired") : t("clinic")}
          </label>
          <select
            id="booking-clinic"
            value={clinicId}
            onChange={(e) => { setClinicId(e.target.value); setBranchId(""); }}
            className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
          >
            <option value="">{tab === "walkin" ? t("selectClinic") : t("noClinic")}</option>
            {clinics.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </div>
      )}

      {/* Doctor — only for staff without a Doctor profile (e.g. receptionists) */}
      {!doctorId && clinicId && (
        <div>
          <label htmlFor="booking-doctor" className="mb-1 block text-sm font-medium text-dreams-textPrimary">{t("doctor")}</label>
          <select
            id="booking-doctor"
            value={pickedDoctorId}
            onChange={(e) => setPickedDoctorId(e.target.value)}
            className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
          >
            <option value="">{t("selectDoctor")}</option>
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
          <label htmlFor="booking-branch" className="mb-1 block text-sm font-medium text-dreams-textPrimary">{t("branch")}</label>
          {branchesLoading ? (
            <div className="h-10 rounded-lg border border-dreams-border bg-gray-50 flex items-center px-3">
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-dreams-blue border-t-transparent" />
              <span className="ml-2 text-sm text-dreams-textSecondary">{t("loadingBranches")}</span>
            </div>
          ) : (
            <select
              id="booking-branch"
              value={branchId}
              onChange={(e) => setBranchId(e.target.value)}
              className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
            >
              <option value="">{t("anyBranch")}</option>
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
        aria-label={t("ariaLabel")}
        className="w-[calc(100%-2rem)] sm:w-full sm:max-w-lg rounded-xl bg-white shadow-xl"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-dreams-border px-6 py-4">
          <h2 className="text-lg font-semibold text-dreams-textPrimary">{t("title")}</h2>
          <button type="button" onClick={onClose} aria-label={tCommon("close")} className="text-dreams-textSecondary hover:text-dreams-textPrimary">
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
            {t("tabExisting")}
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
            {t("tabWalkin")}
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-4 space-y-4 max-h-[70vh] overflow-y-auto">
          {error && (
            <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-2 text-sm text-red-700">{error}</div>
          )}

          {tab === "existing" ? (
            <div>
              <label htmlFor="booking-patient" className="mb-1 block text-sm font-medium text-dreams-textPrimary">{t("patient")}</label>
              {selectedPatient ? (
                <div className="flex items-center gap-3 rounded-lg border border-dreams-blue bg-dreams-blue/5 px-4 py-2.5">
                  <div className="flex-1">
                    <p className="text-sm font-semibold text-dreams-textPrimary">{selectedPatient.full_name}</p>
                    {selectedPatient.phone && (
                      <p className="text-xs text-dreams-textSecondary">{selectedPatient.phone}</p>
                    )}
                  </div>
                  <button type="button" onClick={() => setSelectedPatient(null)}
                    aria-label={t("clearPatient")}
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
                <label htmlFor="walkin-name" className="mb-1 block text-sm font-medium text-dreams-textPrimary">{t("patientName")}</label>
                <input
                  id="walkin-name"
                  type="text"
                  value={walkinName}
                  onChange={(e) => setWalkinName(e.target.value)}
                  placeholder={t("patientNamePlaceholder")}
                  className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
                />
              </div>
              <div>
                <label htmlFor="walkin-phone" className="mb-1 block text-sm font-medium text-dreams-textPrimary">{t("phone")}</label>
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
              {submitting ? t("submitting") : t("submit")}
            </button>
            <button type="button" onClick={onClose}
              className="rounded-lg border border-dreams-border px-4 py-2.5 text-sm font-medium text-dreams-textPrimary hover:bg-dreams-lightBg transition-colors">
              {tCommon("cancel")}
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
  const t = useTranslations("doctorAppointments.editModal");
  const tBooking = useTranslations("doctorAppointments.booking");
  const tTypes = useTranslations("appointments.types");
  const tCommon = useTranslations("common");
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
      const msg = err.response?.data?.detail?.error?.message || err.response?.data?.detail || t("errorFailed");
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
        aria-label={t("ariaLabel")}
        className="w-[calc(100%-2rem)] sm:w-full sm:max-w-lg rounded-xl bg-white shadow-xl"
      >
        <div className="flex items-center justify-between border-b border-dreams-border px-6 py-4">
          <h2 className="text-lg font-semibold text-dreams-textPrimary">{t("title")}</h2>
          <button type="button" onClick={onClose} aria-label={tCommon("close")} className="text-dreams-textSecondary hover:text-dreams-textPrimary">
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-4 space-y-4 max-h-[80vh] overflow-y-auto">
          {error && (
            <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-2 text-sm text-red-700">{error}</div>
          )}

          {/* Patient (read-only) */}
          <div>
            <span className="mb-1 block text-sm font-medium text-dreams-textPrimary">{t("patient")}</span>
            <div className="h-10 rounded-lg border border-dreams-border bg-dreams-lightBg px-3 flex items-center text-sm text-dreams-textSecondary">
              {appointment.patient_name ?? "—"}
            </div>
          </div>

          {/* Date + Time */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label htmlFor="edit-appt-date" className="mb-1 block text-sm font-medium text-dreams-textPrimary">{tBooking("date")}</label>
              <input id="edit-appt-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} required
                className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20" />
            </div>
            <div>
              <label htmlFor="edit-appt-time" className="mb-1 block text-sm font-medium text-dreams-textPrimary">{tBooking("time")}</label>
              <input id="edit-appt-time" type="time" value={time} onChange={(e) => setTime(e.target.value)} required
                className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20" />
            </div>
          </div>

          {/* Duration + Type */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label htmlFor="edit-appt-duration" className="mb-1 block text-sm font-medium text-dreams-textPrimary">{tBooking("duration")}</label>
              <select id="edit-appt-duration" value={duration} onChange={(e) => setDuration(Number(e.target.value))}
                className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20">
                {[15, 30, 45, 60].map((m) => (
                  <option key={m} value={m}>{tBooking("durationOption", { count: m })}</option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="edit-appt-type" className="mb-1 block text-sm font-medium text-dreams-textPrimary">{tBooking("type")}</label>
              <select id="edit-appt-type" value={type} onChange={(e) => setType(e.target.value as typeof type)}
                className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20">
                <option value="in-person">{tTypes("in-person")}</option>
                <option value="teleconsult">{tTypes("teleconsult")}</option>
                <option value="follow-up">{tTypes("follow-up")}</option>
              </select>
            </div>
          </div>

          {/* Chief Complaint */}
          <div>
            <label htmlFor="edit-appt-complaint" className="mb-1 block text-sm font-medium text-dreams-textPrimary">{tBooking("chiefComplaint")}</label>
            <input id="edit-appt-complaint" type="text" value={chiefComplaint} onChange={(e) => setChiefComplaint(e.target.value)}
              placeholder={tBooking("chiefComplaintPlaceholder")}
              className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20" />
          </div>

          {/* Clinic */}
          {clinics.length > 0 && (
            <div>
              <label htmlFor="edit-appt-clinic" className="mb-1 block text-sm font-medium text-dreams-textPrimary">{tBooking("clinic")}</label>
              <select id="edit-appt-clinic" value={clinicId} onChange={(e) => { setClinicId(e.target.value); setBranchId(""); }}
                className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20">
                <option value="">{tBooking("noClinic")}</option>
                {clinics.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
          )}

          {/* Branch */}
          {clinicId && (branchesLoading || branches.length > 0) && (
            <div>
              <label htmlFor="edit-appt-branch" className="mb-1 block text-sm font-medium text-dreams-textPrimary">{tBooking("branch")}</label>
              {branchesLoading ? (
                <div className="h-10 rounded-lg border border-dreams-border bg-gray-50 flex items-center px-3">
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-dreams-blue border-t-transparent" />
                  <span className="ml-2 text-sm text-dreams-textSecondary">{tBooking("loadingBranches")}</span>
                </div>
              ) : (
                <select id="edit-appt-branch" value={branchId} onChange={(e) => setBranchId(e.target.value)}
                  className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20">
                  <option value="">{tBooking("anyBranch")}</option>
                  {branches.map((b) => <option key={b.id} value={b.id}>{b.name}{b.city ? ` — ${b.city}` : ""}</option>)}
                </select>
              )}
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3 pt-2">
            <button type="submit" disabled={submitting}
              className="flex-1 rounded-lg bg-dreams-blue px-4 py-2.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50 transition-opacity">
              {submitting ? t("saving") : t("submit")}
            </button>
            <button type="button" onClick={onClose}
              className="rounded-lg border border-dreams-border px-4 py-2.5 text-sm font-medium text-dreams-textPrimary hover:bg-dreams-lightBg transition-colors">
              {tCommon("cancel")}
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
  const t = useTranslations("doctorAppointments.cancelModal");
  const tCommon = useTranslations("common");
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
      const msg = err.response?.data?.detail?.error?.message || t("errorFailed");
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
        aria-label={t("ariaLabel")}
        className="w-[calc(100%-2rem)] sm:w-full sm:max-w-md rounded-xl bg-white shadow-xl"
      >
        <div className="flex items-center justify-between border-b border-dreams-border px-6 py-4">
          <h2 className="text-lg font-semibold text-dreams-textPrimary">{t("title")}</h2>
          <button type="button" onClick={onClose} aria-label={tCommon("close")} className="text-dreams-textSecondary hover:text-dreams-textPrimary">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="px-6 py-4 space-y-4">
          <p className="text-sm text-dreams-textSecondary">
            {t.rich("body", {
              name: appointment.patient_name ?? "",
              strong: (chunks) => (
                <span className="font-medium text-dreams-textPrimary">{chunks}</span>
              ),
            })}
          </p>
          {error && (
            <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-2 text-sm text-red-700">{error}</div>
          )}
          <div>
            <label htmlFor="cancel-reason" className="mb-1 block text-sm font-medium text-dreams-textPrimary">{t("reason")}</label>
            <input
              id="cancel-reason"
              type="text"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder={t("reasonPlaceholder")}
              className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
            />
          </div>
          <div className="flex gap-3 pt-1">
            <button
              onClick={handleCancel}
              disabled={submitting}
              className="flex-1 rounded-lg bg-red-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50 transition-colors"
            >
              {submitting ? t("cancelling") : t("confirm")}
            </button>
            <button type="button" onClick={onClose}
              className="rounded-lg border border-dreams-border px-4 py-2.5 text-sm font-medium text-dreams-textPrimary hover:bg-dreams-lightBg transition-colors">
              {t("keep")}
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
  const t = useTranslations("doctorAppointments.actions");
  const actions: { labelKey: "markArrived" | "noShow" | "start" | "complete"; nextStatus: string; icon: React.ReactNode; className: string }[] = [];

  if (appt.status === "scheduled") {
    actions.push({
      labelKey: "markArrived",
      nextStatus: "arrived",
      icon: <UserCheck className="h-3.5 w-3.5" />,
      className: "bg-blue-50 text-blue-700 hover:bg-blue-100",
    });
    actions.push({
      labelKey: "noShow",
      nextStatus: "no-show",
      icon: <XCircle className="h-3.5 w-3.5" />,
      className: "bg-gray-50 text-gray-600 hover:bg-gray-100",
    });
  }
  if (appt.status === "arrived") {
    actions.push({
      labelKey: "start",
      nextStatus: "in-progress",
      icon: <Clock className="h-3.5 w-3.5" />,
      className: "bg-yellow-50 text-yellow-700 hover:bg-yellow-100",
    });
  }
  if (appt.status === "in-progress") {
    actions.push({
      labelKey: "complete",
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
          {t(a.labelKey)}
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

interface LinkingAppt {
  provisionalPatientId: string;
  patientName: string;
}

export default function DoctorAppointmentsPage() {
  const t = useTranslations("doctorAppointments");
  const tNav = useTranslations("nav");
  const tTypes = useTranslations("appointments.types");
  const tStatus = useTranslations("appointments.status");
  const tCommon = useTranslations("common");
  const today = formatDateInput(new Date());
  const [selectedDate, setSelectedDate] = useState(today);
  const [showBookingModal, setShowBookingModal] = useState(false);
  const [editingAppointment, setEditingAppointment] = useState<Appointment | null>(null);
  const [cancellingAppointment, setCancellingAppointment] = useState<Appointment | null>(null);
  const [linkingAppt, setLinkingAppt] = useState<LinkingAppt | null>(null);
  const [doctorId, setDoctorId] = useState<string | null>(null);
  const [activeClinics, setActiveClinics] = useState<{ id: string; name: string }[]>([]);
  const queryClient = useQueryClient();

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

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      updateAppointmentStatus(id, { status: status as any }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["doctor-appointments", selectedDate] });
    },
  });

  const meetingLinkMutation = useMutation({
    mutationFn: (id: string) => generateMeetingLink(id),
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

      <Breadcrumb
        items={[
          { label: tNav("doctorDashboard"), href: "/doctor/dashboard" },
          { label: t("breadcrumb") },
        ]}
      />

      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-dreams-textPrimary">{t("title")}</h1>
          <p className="text-sm text-dreams-textSecondary mt-0.5">
            {isToday ? t("todaysSchedule") : displayDate}
          </p>
        </div>

        {/* Date picker + New Appointment button */}
        <div className="flex items-center gap-2 flex-wrap">
          <Calendar className="h-4 w-4 text-dreams-textSecondary" aria-hidden="true" />
          <input
            type="date"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
            aria-label={t("dateAriaLabel")}
            className="rounded-lg border border-dreams-border bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-dreams-blue"
          />
          {!isToday && (
            <button
              onClick={() => setSelectedDate(today)}
              className="rounded-lg border border-dreams-border bg-white px-3 py-2 text-sm text-dreams-textSecondary hover:bg-gray-50"
            >
              {t("today")}
            </button>
          )}
          <button
            onClick={() => setShowBookingModal(true)}
            className="flex items-center gap-2 rounded-lg bg-dreams-blue px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
          >
            <Plus className="h-4 w-4" />
            {t("newAppointment")}
          </button>
        </div>
      </div>

      {/* Summary */}
      {!isLoading && (
        <div className="flex items-center gap-2 text-sm text-dreams-textSecondary">
          {t("summary", { count: appointments.length })}
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
          <p className="mt-3 font-medium text-dreams-textPrimary">{t("emptyTitle")}</p>
          <p className="mt-1 text-sm text-dreams-textSecondary">
            {isToday ? t("emptyToday") : t("emptyDate", { date: displayDate })}
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
                    <div className="flex flex-wrap items-center gap-2">
                      <User className="h-4 w-4 text-dreams-textSecondary flex-shrink-0" />
                      <span className="font-semibold text-dreams-textPrimary">
                        {appt.patient_name ?? tCommon("unknownPatient")}
                      </span>
                      {appt.is_provisional && (
                        <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">
                          {t("walkIn")}
                        </span>
                      )}
                      <Badge variant={KNOWN_TYPES.has(appt.type) ? "upcoming" : "pending"} className="text-xs">
                        {KNOWN_TYPES.has(appt.type) ? tTypes(appt.type) : appt.type}
                      </Badge>
                    </div>
                    {appt.is_provisional && appt.patient_phone && (
                      <p className="mt-0.5 text-xs text-dreams-textSecondary">{appt.patient_phone}</p>
                    )}

                    {appt.chief_complaint && (
                      <p className="mt-1 text-sm text-dreams-textSecondary">
                        {t("chiefComplaint", { complaint: appt.chief_complaint })}
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
                          {t("newPrescription")}
                        </Link>
                        <Link
                          href="/doctor/records/new"
                          className="flex items-center gap-1 text-xs text-dreams-blue hover:underline"
                        >
                          <FileText className="h-3.5 w-3.5" />
                          {t("newRecord")}
                        </Link>
                      </div>
                    )}
                  </div>
                </div>

                {/* Right: status badge + actions */}
                <div className="flex flex-col items-end gap-2 flex-shrink-0">
                  <Badge variant={STATUS_VARIANT_MAP[appt.status] as any}>
                    {tStatus(appt.status)}
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
                          {t("joinCall")}
                        </a>
                      ) : (
                        <button
                          onClick={() => meetingLinkMutation.mutate(appt.id)}
                          disabled={meetingLinkMutation.isPending}
                          className="flex items-center gap-1 rounded-md border border-dreams-blue px-2 py-1 text-xs text-dreams-blue hover:bg-dreams-blue/10 transition-colors disabled:opacity-50"
                        >
                          <Video className="h-3 w-3" />
                          {meetingLinkMutation.isPending ? t("generating") : t("getLink")}
                        </button>
                      ))}
                    {appt.is_provisional && (
                      <button
                        onClick={() => setLinkingAppt({ provisionalPatientId: appt.patient_id, patientName: appt.patient_name ?? tCommon("unknownPatient") })}
                        className="flex items-center gap-1 rounded-md border border-dreams-blue px-2 py-1 text-xs text-dreams-blue hover:bg-dreams-blue/10 transition-colors"
                      >
                        <UserCheck className="h-3 w-3" />
                        {t("linkAccount")}
                      </button>
                    )}
                    {appt.status === "scheduled" && (
                      <>
                        <button
                          onClick={() => setEditingAppointment(appt)}
                          className="flex items-center gap-1 rounded-md border border-dreams-border px-2 py-1 text-xs text-dreams-textSecondary hover:bg-dreams-lightBg transition-colors"
                        >
                          <Pencil className="h-3 w-3" />
                          {t("edit")}
                        </button>
                        <button
                          onClick={() => setCancellingAppointment(appt)}
                          className="flex items-center gap-1 rounded-md border border-red-200 px-2 py-1 text-xs text-red-600 hover:bg-red-50 transition-colors"
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
          ))}
        </div>
      )}
    </div>
  );
}
