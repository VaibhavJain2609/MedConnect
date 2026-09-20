"use client";

import { Suspense, useState, useRef, useCallback, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import api from "@/lib/api";
import { createEncounter } from "@/lib/api/encounters";
import { getAppointments, Appointment } from "@/lib/api/appointments";
import { useClinicStore } from "@/stores/clinic-store";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { X } from "lucide-react";

interface PatientSuggestion {
  id: string;
  full_name: string;
  phone: string | null;
  last_visit_at: string | null;
}

function PatientSearch({
  selected,
  onSelect,
}: {
  selected: PatientSuggestion | null;
  onSelect: (patient: PatientSuggestion | null) => void;
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

  if (selected) {
    return (
      <div className="flex items-center gap-3 rounded-lg border border-dreams-blue bg-dreams-blue/5 px-4 py-2.5">
        <div className="flex-1">
          <p className="text-sm font-semibold text-dreams-textPrimary">
            {selected.full_name}
          </p>
          {selected.phone && (
            <p className="text-xs text-dreams-textSecondary">{selected.phone}</p>
          )}
        </div>
        <button
          type="button"
          onClick={() => onSelect(null)}
          aria-label="Clear selected patient"
          className="text-dreams-textSecondary hover:text-red-500 transition-colors"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    );
  }

  return (
    <div className="relative">
      <input
        id="encounter-patient"
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
                setOpen(false);
                setQuery("");
                onSelect(p);
              }}
            >
              <div className="flex-1">
                <p className="text-sm font-medium text-dreams-textPrimary">
                  {p.full_name}
                </p>
                {p.phone && (
                  <p className="text-xs text-dreams-textSecondary">{p.phone}</p>
                )}
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

const VITAL_FIELDS: { key: string; label: string; unit: string }[] = [
  { key: "bp_systolic", label: "BP Systolic", unit: "mmHg" },
  { key: "bp_diastolic", label: "BP Diastolic", unit: "mmHg" },
  { key: "pulse", label: "Pulse", unit: "bpm" },
  { key: "spo2", label: "SpO2", unit: "%" },
  { key: "temperature_c", label: "Temperature", unit: "°C" },
  { key: "weight_kg", label: "Weight", unit: "kg" },
];

function NewEncounterForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const clinicId = useClinicStore((s) => s.activeClinicId) ?? null;

  const initialPatientId = searchParams.get("patient_id") || "";
  const initialAppointmentId = searchParams.get("appointment_id") || "";

  const [selectedPatient, setSelectedPatient] =
    useState<PatientSuggestion | null>(
      initialPatientId
        ? {
            id: initialPatientId,
            full_name: "Loading patient…",
            phone: null,
            last_visit_at: null,
          }
        : null
    );

  // Hydrate the patient's real name when arriving via ?patient_id=
  useEffect(() => {
    if (!initialPatientId) return;
    api
      .get(`/api/v1/doctors/patients/${initialPatientId}/profile`)
      .then((res) => {
        const p = res.data;
        if (p?.id) {
          setSelectedPatient({
            id: p.id,
            full_name: p.full_name || initialPatientId,
            phone: p.phone ?? null,
            last_visit_at: p.last_visit_at ?? null,
          });
        }
      })
      .catch(() => {
        setSelectedPatient((prev) =>
          prev?.id === initialPatientId
            ? { ...prev, full_name: initialPatientId }
            : prev
        );
      });
  }, [initialPatientId]);

  const [appointmentId, setAppointmentId] = useState(initialAppointmentId);
  const [appointments, setAppointments] = useState<Appointment[]>([]);

  // Load this patient's appointments for the optional link
  useEffect(() => {
    if (!selectedPatient) {
      setAppointments([]);
      return;
    }
    let cancelled = false;
    Promise.all([
      getAppointments({}),
      getAppointments({ upcoming: true }),
    ])
      .then(([today, upcoming]) => {
        if (cancelled) return;
        const seen = new Set<string>();
        const list: Appointment[] = [];
        for (const a of [...(today.data ?? []), ...(upcoming.data ?? [])]) {
          if (a.patient_id === selectedPatient.id && !seen.has(a.id)) {
            seen.add(a.id);
            list.push(a);
          }
        }
        list.sort(
          (a, b) =>
            new Date(b.scheduled_at).getTime() -
            new Date(a.scheduled_at).getTime()
        );
        setAppointments(list);
      })
      .catch(() => setAppointments([]));
    return () => {
      cancelled = true;
    };
  }, [selectedPatient]);

  const [subjective, setSubjective] = useState("");
  const [objective, setObjective] = useState("");
  const [assessment, setAssessment] = useState("");
  const [plan, setPlan] = useState("");
  const [vitals, setVitals] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!selectedPatient) {
      setError("Please select a patient");
      return;
    }
    if (!subjective && !objective && !assessment && !plan) {
      setError("Please fill in at least one SOAP section");
      return;
    }

    const vitalsSnapshot: Record<string, number> = {};
    for (const f of VITAL_FIELDS) {
      const raw = vitals[f.key]?.trim();
      if (raw) {
        const num = parseFloat(raw);
        if (!isNaN(num)) vitalsSnapshot[f.key] = num;
      }
    }

    setLoading(true);
    try {
      const enc = await createEncounter({
        patient_id: selectedPatient.id,
        appointment_id: appointmentId || undefined,
        clinic_id: clinicId || undefined,
        subjective: subjective || undefined,
        objective: objective || undefined,
        assessment: assessment || undefined,
        plan: plan || undefined,
        vitals_snapshot:
          Object.keys(vitalsSnapshot).length > 0 ? vitalsSnapshot : undefined,
      });
      router.push(`/doctor/visits/${enc.id}`);
    } catch (err: unknown) {
      const axiosError = err as {
        response?: { data?: { detail?: { error?: { message?: string } } | string } };
      };
      const detail = axiosError?.response?.data?.detail;
      setError(
        typeof detail === "object" && detail?.error?.message
          ? detail.error.message
          : "Failed to create encounter"
      );
    } finally {
      setLoading(false);
    }
  };

  const soapSections: {
    label: string;
    hint: string;
    value: string;
    setter: (v: string) => void;
  }[] = [
    {
      label: "Subjective",
      hint: "Chief complaint, history of present illness, patient-reported symptoms…",
      value: subjective,
      setter: setSubjective,
    },
    {
      label: "Objective",
      hint: "Examination findings, measurements, observations…",
      value: objective,
      setter: setObjective,
    },
    {
      label: "Assessment",
      hint: "Diagnosis or clinical impression…",
      value: assessment,
      setter: setAssessment,
    },
    {
      label: "Plan",
      hint: "Treatment plan, prescriptions advised, investigations, follow-up…",
      value: plan,
      setter: setPlan,
    },
  ];

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-white rounded-lg shadow-card p-6 max-w-4xl"
    >
      {error && (
        <div className="mb-4 rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="mb-4">
        <label htmlFor="encounter-patient" className="mb-1 block text-sm font-medium text-dreams-textPrimary">
          Patient *
        </label>
        <PatientSearch
          selected={selectedPatient}
          onSelect={(p) => {
            setSelectedPatient(p);
            setAppointmentId("");
          }}
        />
      </div>

      {selectedPatient && appointments.length > 0 && (
        <div className="mb-4">
          <label htmlFor="encounter-appointment" className="mb-1 block text-sm font-medium text-dreams-textPrimary">
            Linked Appointment (optional)
          </label>
          <select
            id="encounter-appointment"
            value={appointmentId}
            onChange={(e) => setAppointmentId(e.target.value)}
            className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
          >
            <option value="">Walk-in / not linked</option>
            {appointments.map((a) => (
              <option key={a.id} value={a.id}>
                {new Date(a.scheduled_at).toLocaleString("en-IN")} — {a.type} (
                {a.status})
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Vitals snapshot */}
      <div className="mb-6">
        <p className="mb-2 text-sm font-medium text-dreams-textPrimary">
          Vitals (optional)
        </p>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {VITAL_FIELDS.map((f) => (
            <div key={f.key}>
              <label className="mb-1 block text-xs text-dreams-textSecondary">
                {f.label} ({f.unit})
              </label>
              <input
                type="number"
                step="any"
                value={vitals[f.key] ?? ""}
                onChange={(e) =>
                  setVitals((v) => ({ ...v, [f.key]: e.target.value }))
                }
                className="w-full h-9 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
              />
            </div>
          ))}
        </div>
      </div>

      {/* SOAP four-pane editor */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        {soapSections.map((s) => (
          <div key={s.label} className="flex flex-col">
            <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">
              {s.label}
            </label>
            <textarea
              value={s.value}
              onChange={(e) => s.setter(e.target.value)}
              rows={6}
              placeholder={s.hint}
              className="w-full flex-1 rounded-lg border border-dreams-border px-3 py-2 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20 resize-y"
            />
          </div>
        ))}
      </div>

      <div className="flex gap-3">
        <button
          type="submit"
          disabled={loading || !selectedPatient}
          className="px-6 py-2.5 bg-dreams-blue text-white text-sm font-medium rounded-lg hover:opacity-90 disabled:opacity-50 transition-opacity"
        >
          {loading ? "Saving..." : "Save Encounter"}
        </button>
        <button
          type="button"
          onClick={() => router.back()}
          className="px-6 py-2.5 border border-dreams-border text-sm font-medium text-dreams-textPrimary rounded-lg hover:bg-dreams-lightBg transition-colors"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

export default function NewEncounterPage() {
  return (
    <div className="space-y-6">
      <Breadcrumb
        items={[
          { label: "Dashboard", href: "/doctor/dashboard" },
          { label: "Encounters", href: "/doctor/visits" },
          { label: "New Encounter" },
        ]}
      />

      <div>
        <h1 className="text-3xl font-bold text-dreams-textPrimary">
          New Encounter
        </h1>
        <p className="text-dreams-textSecondary mt-1">
          Record a SOAP note for a patient visit
        </p>
      </div>

      <Suspense
        fallback={<div className="h-96 animate-pulse rounded-lg bg-gray-100" />}
      >
        <NewEncounterForm />
      </Suspense>
    </div>
  );
}
