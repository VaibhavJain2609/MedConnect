"use client";

import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import api from "@/lib/api";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import MedicineAutocomplete from "@/components/medicine/MedicineAutocomplete";
import DrugInteractionWarning from "@/components/medicine/DrugInteractionWarning";
import PatientAllergyBanner from "@/components/prescriptions/PatientAllergyBanner";
import { AlertTriangle, X, BookOpen, Save, History } from "lucide-react";
import { getMyClinics, getClinicBranches, type ClinicBranch } from "@/lib/api/clinics";
import {
  checkDrugInteractions,
  type DrugInteraction,
} from "@/lib/api/medicines-emr";
import { getDoctorPatientProfile } from "@/lib/api/prescriptions";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Medicine {
  _uid: string;
  brand_name: string;
  brand_id: string | null;
  salt_id: string | null;
  /** Salt composition string from autocomplete — used for allergy cross-check. */
  composition: string;
  dose: string;
  frequency: string;
  duration: string;
  route: string;
  instructions: string;
}

interface ClinicOption {
  id: string;
  name: string;
}

interface PatientSuggestion {
  id: string;
  full_name: string;
  phone: string | null;
  last_visit_at: string | null;
}

interface PrescriptionTemplate {
  id: string;
  name: string;
  medicines: Medicine[];
  diagnosis: string | null;
  notes: string | null;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

function newEmptyMedicine(): Medicine {
  return {
    _uid: Math.random().toString(36).slice(2),
    brand_name: "",
    brand_id: null,
    salt_id: null,
    composition: "",
    dose: "",
    frequency: "OD",
    duration: "7 days",
    route: "oral",
    instructions: "",
  };
}

const FREQUENCY_OPTIONS = ["OD", "BD", "TDS", "QID", "1-0-1", "SOS", "HS"];
const DURATION_OPTIONS = [
  "3 days",
  "5 days",
  "7 days",
  "10 days",
  "14 days",
  "1 month",
  "2 months",
  "3 months",
  "Ongoing",
];
const ROUTE_OPTIONS = [
  { value: "oral", label: "Oral" },
  { value: "topical", label: "Topical" },
  { value: "IV", label: "IV" },
  { value: "IM", label: "IM" },
  { value: "SC", label: "SC" },
  { value: "inhaled", label: "Inhaled" },
  { value: "sublingual", label: "Sublingual" },
];

// ---------------------------------------------------------------------------
// Draft auto-save (localStorage)
// ---------------------------------------------------------------------------

const DRAFT_STORAGE_KEY = "rx-draft";

interface RxDraft {
  version: 1;
  saved_at: string;
  patient: PatientSuggestion | null;
  medicines: Medicine[];
  diagnosis: string;
  notes: string;
  valid_until: string;
  clinic_id: string;
  branch_id: string;
}

/** User.allergies / chronic_conditions are JSONB — strings or small objects. */
function extractTerms(list: unknown): string[] {
  if (!Array.isArray(list)) return [];
  const out: string[] = [];
  for (const item of list) {
    if (typeof item === "string" && item.trim()) {
      out.push(item.trim());
    } else if (item && typeof item === "object") {
      const rec = item as Record<string, unknown>;
      for (const key of ["name", "substance", "allergen", "drug", "condition", "value"]) {
        const v = rec[key];
        if (typeof v === "string" && v.trim()) {
          out.push(v.trim());
          break;
        }
      }
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// Patient Search Typeahead
// ---------------------------------------------------------------------------

function PatientSearch({
  onSelect,
}: {
  onSelect: (patient: PatientSuggestion) => void;
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
      .catch(() => {
        setResults([]);
      })
      .finally(() => setLoading(false));
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setQuery(val);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => search(val), 400);
  };

  const handleSelect = (patient: PatientSuggestion) => {
    setOpen(false);
    setQuery("");
    onSelect(patient);
  };

  return (
    <div className="relative">
      <input
        id="rx-patient"
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
              onMouseDown={() => handleSelect(p)}
            >
              <div className="flex-1">
                <p className="text-sm font-medium text-dreams-textPrimary">
                  {p.full_name}
                </p>
                {p.phone && (
                  <p className="text-xs text-dreams-textSecondary">{p.phone}</p>
                )}
              </div>
              {p.last_visit_at && (
                <p className="text-xs text-dreams-textSecondary whitespace-nowrap">
                  Last visit:{" "}
                  {new Date(p.last_visit_at).toLocaleDateString("en-IN")}
                </p>
              )}
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
// Safety helpers — interaction severity ordering + allergy cross-check
// ---------------------------------------------------------------------------

const SEVERITY_ORDER: Record<string, number> = {
  contraindicated: 4,
  major: 3,
  moderate: 2,
  minor: 1,
};

function sortBySeverity(interactions: DrugInteraction[]): DrugInteraction[] {
  return [...interactions].sort(
    (a, b) => (SEVERITY_ORDER[b.severity] ?? 0) - (SEVERITY_ORDER[a.severity] ?? 0)
  );
}

const BLOCKING_SEVERITIES = new Set(["major", "contraindicated"]);

interface AllergyConflict {
  allergy: string;
  medicine: string;
}

/**
 * Cross-check the patient's recorded allergies (free-text strings) against the
 * selected medicines' brand names and salt compositions. Matching is a
 * case-insensitive substring check in both directions — free-text allergy
 * entries can't be resolved to salt IDs without backend support.
 */
function findAllergyConflicts(
  meds: Medicine[],
  allergyList: string[]
): AllergyConflict[] {
  const conflicts: AllergyConflict[] = [];
  const seen = new Set<string>();

  for (const allergy of allergyList) {
    const a = String(allergy).toLowerCase().trim();
    if (a.length < 3) continue;
    for (const m of meds) {
      const brand = m.brand_name.trim().toLowerCase();
      if (!brand) continue;
      const haystack = `${m.brand_name} ${m.composition}`.toLowerCase();
      if (haystack.includes(a) || (brand.length >= 3 && a.includes(brand))) {
        const key = `${a}::${brand}`;
        if (!seen.has(key)) {
          seen.add(key);
          conflicts.push({ allergy: String(allergy), medicine: m.brand_name });
        }
      }
    }
  }
  return conflicts;
}

// ---------------------------------------------------------------------------
// Template Modal
// ---------------------------------------------------------------------------

function LoadTemplateModal({
  templates,
  onLoad,
  onClose,
}: {
  templates: PrescriptionTemplate[];
  onLoad: (t: PrescriptionTemplate) => void;
  onClose: () => void;
}) {
  // Close on Escape
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Load template"
        className="w-full max-w-md rounded-xl bg-white shadow-xl p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-dreams-textPrimary">
            Load Template
          </h3>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="text-dreams-textSecondary hover:text-dreams-textPrimary"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        {templates.length === 0 ? (
          <p className="text-sm text-dreams-textSecondary text-center py-4">
            No templates saved yet.
          </p>
        ) : (
          <ul className="space-y-2 max-h-72 overflow-y-auto">
            {templates.map((t) => (
              <li key={t.id}>
                <button
                  type="button"
                  className="w-full text-left rounded-lg border border-dreams-border px-4 py-3 hover:border-dreams-blue hover:bg-dreams-lightBg transition-colors"
                  onClick={() => onLoad(t)}
                >
                  <p className="text-sm font-medium text-dreams-textPrimary">
                    {t.name}
                  </p>
                  {t.diagnosis && (
                    <p className="text-xs text-dreams-textSecondary mt-0.5">
                      {t.diagnosis}
                    </p>
                  )}
                  <p className="text-xs text-dreams-textSecondary mt-0.5">
                    {t.medicines.length} medicine
                    {t.medicines.length !== 1 ? "s" : ""}
                  </p>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function SaveTemplateModal({
  onSave,
  onClose,
}: {
  onSave: (name: string) => void;
  onClose: () => void;
}) {
  const [name, setName] = useState("");

  // Close on Escape
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Save as template"
        className="w-full max-w-sm rounded-xl bg-white shadow-xl p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-dreams-textPrimary">
            Save as Template
          </h3>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="text-dreams-textSecondary hover:text-dreams-textPrimary"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Template name (e.g., Fever protocol)"
          aria-label="Template name"
          className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20 mb-4"
          autoFocus
        />
        <div className="flex gap-3">
          <button
            type="button"
            disabled={!name.trim()}
            onClick={() => name.trim() && onSave(name.trim())}
            className="flex-1 px-4 py-2 bg-dreams-blue text-white text-sm font-medium rounded-lg hover:opacity-90 disabled:opacity-50 transition-opacity"
          >
            Save Template
          </button>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 border border-dreams-border text-sm font-medium text-dreams-textPrimary rounded-lg hover:bg-dreams-lightBg transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function NewPrescriptionPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // Read appointment context from query params (set when navigating from appointments page)
  const appointmentId = searchParams.get("appointment_id");
  const prefillPatientId = searchParams.get("patient_id");

  // Patient state
  const [selectedPatient, setSelectedPatient] =
    useState<PatientSuggestion | null>(null);

  // Clinic + branch state
  const [clinics, setClinics] = useState<ClinicOption[]>([]);
  const [selectedClinicId, setSelectedClinicId] = useState("");
  const [branches, setBranches] = useState<ClinicBranch[]>([]);
  const [selectedBranchId, setSelectedBranchId] = useState("");
  const [branchesLoading, setBranchesLoading] = useState(false);

  // Form fields
  const [diagnosis, setDiagnosis] = useState("");
  const [notes, setNotes] = useState("");
  const [validUntil, setValidUntil] = useState("");
  const [medicines, setMedicines] = useState<Medicine[]>([newEmptyMedicine()]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  // Double-submit protection: one key per form-mount; regenerated after a
  // successful submit so a deliberate second Rx is a fresh operation.
  const [idempotencyKey, setIdempotencyKey] = useState(() => crypto.randomUUID());

  // Safety-override flow: 409 SAFETY_OVERRIDE_REQUIRED → reason + resubmit
  const [overrideAlerts, setOverrideAlerts] = useState<any[] | null>(null);
  const [overrideReason, setOverrideReason] = useState("");

  // Patient safety info (allergies / chronic conditions from profile).
  // Raw fetch results — the surfaced lists are derived below so clearing the
  // patient doesn't require a synchronous reset inside an effect.
  const [fetchedAllergies, setPatientAllergies] = useState<string[]>([]);
  const [fetchedChronic, setPatientChronic] = useState<string[]>([]);

  // Drug interactions — raw fetch results; the surfaced list is derived
  // below (only meaningful with 2+ salt-tagged medicines).
  const [fetchedInteractions, setInteractions] =
    useState<DrugInteraction[]>([]);

  // Draft auto-save
  const [draftRestored, setDraftRestored] = useState(false);
  const draftReadyRef = useRef(false);
  const pendingBranchRef = useRef<string | null>(null);

  // Safety gate — set when a submit attempt hits blocking alerts
  // (major/contraindicated interactions or allergy conflicts)
  const [safetyAckRequired, setSafetyAckRequired] = useState(false);
  const [safetyAcknowledged, setSafetyAcknowledged] = useState(false);

  // Templates
  const [templates, setTemplates] = useState<PrescriptionTemplate[]>([]);
  const [showLoadModal, setShowLoadModal] = useState(false);
  const [showSaveModal, setShowSaveModal] = useState(false);

  // Derived inputs shared by the safety effects below. `patientId` is the
  // stable primitive the effects actually depend on; `saltIds` is memoized
  // so effect deps track `medicines` without re-firing on every render.
  const patientId = selectedPatient?.id ?? null;
  const saltIds = useMemo(
    () =>
      medicines
        .map((m) => m.salt_id)
        .filter((id): id is string => !!id),
    [medicines]
  );

  // Derived views — gated on the same conditions the effects used to reset
  // for, so no synchronous setState-in-effect is needed.
  const patientAllergies = selectedPatient ? fetchedAllergies : [];
  const patientChronic = selectedPatient ? fetchedChronic : [];
  const interactions = saltIds.length >= 2 ? fetchedInteractions : [];

  // Restore a saved draft from localStorage (runs once, before prefill).
  // Skipped when the draft names a different patient than the one the URL
  // pre-fills — restoring another patient's draft would be unsafe.
  // The synchronous setState calls below are intentional: this multi-field
  // restore must happen post-mount (a lazy useState initializer would run on
  // the server too and produce a hydration mismatch when a draft exists).
  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect -- mount-once localStorage restore; see comment above */
    try {
      const raw = localStorage.getItem(DRAFT_STORAGE_KEY);
      if (raw) {
        const draft = JSON.parse(raw) as RxDraft;
        const wrongPatient = !!(
          prefillPatientId &&
          draft?.patient?.id &&
          draft.patient.id !== prefillPatientId
        );
        if (draft?.version === 1 && !wrongPatient) {
          if (draft.patient) setSelectedPatient(draft.patient);
          if (Array.isArray(draft.medicines) && draft.medicines.length > 0) {
            setMedicines(
              draft.medicines.map((m) => ({
                ...newEmptyMedicine(),
                ...m,
                _uid: m._uid || Math.random().toString(36).slice(2),
              }))
            );
          }
          setDiagnosis(draft.diagnosis || "");
          setNotes(draft.notes || "");
          setValidUntil(draft.valid_until || "");
          setSelectedClinicId(draft.clinic_id || "");
          if (draft.clinic_id) setBranchesLoading(true);
          pendingBranchRef.current = draft.branch_id || null;
          setDraftRestored(true);
        }
      }
    } catch {
      // Corrupt or unreadable draft — ignore and start fresh.
    }
    draftReadyRef.current = true;
    /* eslint-enable react-hooks/set-state-in-effect */
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Load templates and clinics on mount; pre-fill patient if appointment_id provided
  useEffect(() => {
    api
      .get("/api/v1/doctors/prescription-templates")
      .then((res) => setTemplates(res.data.data || []))
      .catch(() => {});
    getMyClinics()
      .then((res) => setClinics(res.data || []))
      .catch(() => {});

    // Pre-fill patient when navigating from appointments page — unless a
    // restored draft already set a patient.
    if (prefillPatientId) {
      getDoctorPatientProfile(prefillPatientId)
        .then((p) => {
          if (p?.id) {
            setSelectedPatient((prev) =>
              prev ?? {
                id: p.id,
                full_name: p.full_name || "Unknown",
                phone: p.phone || null,
                last_visit_at: null,
              }
            );
            setPatientAllergies(extractTerms(p.allergies));
          }
        })
        .catch(() => {});
    }
  }, [prefillPatientId]);

  // Auto-save the form as a draft (debounced ~500ms). An "empty" form removes
  // the key instead of persisting a blank draft.
  useEffect(() => {
    if (!draftReadyRef.current) return;

    const timer = setTimeout(() => {
      const meaningful =
        !!selectedPatient ||
        medicines.some((m) => m.brand_name) ||
        diagnosis.trim() !== "" ||
        notes.trim() !== "" ||
        validUntil !== "";

      try {
        if (!meaningful) {
          localStorage.removeItem(DRAFT_STORAGE_KEY);
          return;
        }
        const draft: RxDraft = {
          version: 1,
          saved_at: new Date().toISOString(),
          patient: selectedPatient,
          medicines,
          diagnosis,
          notes,
          valid_until: validUntil,
          clinic_id: selectedClinicId,
          branch_id: selectedBranchId,
        };
        localStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(draft));
      } catch {
        // localStorage unavailable or full — drafts are best-effort.
      }
    }, 500);

    return () => clearTimeout(timer);
  }, [
    selectedPatient,
    medicines,
    diagnosis,
    notes,
    validUntil,
    selectedClinicId,
    selectedBranchId,
  ]);

  // Fetch branches when a clinic is selected. Re-applies a branch restored
  // from a draft once the branch list arrives. The selection/loading resets
  // live in the clinic select's onChange (and the draft-restore effect), so
  // this effect only performs the fetch.
  useEffect(() => {
    if (!selectedClinicId) return;
    // Consume the pending draft branch only when a fetch actually runs —
    // reading it before the clinic guard would drop it on mount.
    const pendingBranch = pendingBranchRef.current;
    pendingBranchRef.current = null;
    getClinicBranches(selectedClinicId)
      .then((data) => {
        setBranches(data);
        if (pendingBranch && data.some((b) => b.id === pendingBranch)) {
          setSelectedBranchId(pendingBranch);
        }
      })
      .catch(() => setBranches([]))
      .finally(() => setBranchesLoading(false));
  }, [selectedClinicId]);

  // Fetch the selected patient's allergies / chronic conditions for the
  // safety banner. Fails silently when the doctor has no profile access.
  useEffect(() => {
    if (!patientId) return;
    let cancelled = false;
    getDoctorPatientProfile(patientId)
      .then((profile) => {
        if (cancelled) return;
        setPatientAllergies(extractTerms(profile?.allergies));
        setPatientChronic(extractTerms(profile?.chronic_conditions));
      })
      .catch(() => {
        if (cancelled) return;
        setPatientAllergies([]);
        setPatientChronic([]);
      });
    return () => {
      cancelled = true;
    };
  }, [patientId]);

  // Any medicine edit invalidates a prior safety acknowledgment — adjusted
  // during render via the prev-value pattern.
  const [prevMedicines, setPrevMedicines] = useState(medicines);
  if (prevMedicines !== medicines) {
    setPrevMedicines(medicines);
    setSafetyAckRequired(false);
    setSafetyAcknowledged(false);
  }

  // Drug interaction check whenever medicines change (2+ with salt_id).
  // The debounce and cancellation are unchanged; stale results are hidden
  // by the derived `interactions` view once salt count drops below 2.
  useEffect(() => {
    if (saltIds.length < 2) return;

    const timer = setTimeout(() => {
      checkDrugInteractions(saltIds)
        .then((res) => setInteractions(sortBySeverity(res || [])))
        .catch(() => setInteractions([]));
    }, 600);

    return () => clearTimeout(timer);
  }, [saltIds]);

  // ---------------------------------------------------------------------------
  // Derived safety data — allergies vs selected medicines. Server-side check
  // against salt names is authoritative; the local substring matcher covers
  // medicines with no salt_id and acts as the fail-open fallback.
  // ---------------------------------------------------------------------------

  const [fetchedServerConflicts, setServerAllergyConflicts] = useState<
    AllergyConflict[]
  >([]);
  // Gated view — hidden (rather than reset inside the effect) when there is
  // no patient or no salt-tagged medicine.
  const serverAllergyConflicts =
    patientId && saltIds.length > 0 ? fetchedServerConflicts : [];

  useEffect(() => {
    if (!patientId || saltIds.length === 0) return;
    let cancelled = false;
    const timer = setTimeout(() => {
      api
        .post("/api/v1/interactions/check-allergies", {
          patient_id: patientId,
          salt_ids: saltIds,
        })
        .then((res) => {
          if (cancelled) return;
          const conflicts: AllergyConflict[] = (
            res.data?.conflicts || []
          ).map((c: any) => ({
            allergy: c.allergy,
            medicine: c.salt_name,
          }));
          setServerAllergyConflicts(conflicts);
        })
        .catch(() => {
          if (!cancelled) setServerAllergyConflicts([]);
        });
    }, 600);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [patientId, saltIds]);

  const localConflicts = findAllergyConflicts(medicines, patientAllergies);
  const seenConflicts = new Set<string>();
  const allergyConflicts = [...serverAllergyConflicts, ...localConflicts].filter(
    (c) => {
      const key = `${c.allergy.toLowerCase()}::${c.medicine.toLowerCase()}`;
      if (seenConflicts.has(key)) return false;
      seenConflicts.add(key);
      return true;
    }
  );

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  const fetchPatientAllergies = (patientId: string) => {
    api
      .get(`/api/v1/doctors/patients/${patientId}/profile`)
      .then((res) => {
        const list = res.data?.allergies;
        setPatientAllergies(Array.isArray(list) ? list : []);
      })
      .catch(() => setPatientAllergies([]));
  };

  const handlePatientSelect = (patient: PatientSuggestion) => {
    setSelectedPatient(patient);
    setSafetyAckRequired(false);
    setSafetyAcknowledged(false);
    fetchPatientAllergies(patient.id);
  };

  const handlePatientClear = () => {
    setSelectedPatient(null);
    setPatientAllergies([]);
    setSafetyAckRequired(false);
    setSafetyAcknowledged(false);
  };

  const updateMedicine = (index: number, field: keyof Medicine, value: string | null) => {
    const updated = [...medicines];
    updated[index] = { ...updated[index], [field]: value };
    setMedicines(updated);
  };

  const addMedicine = () => {
    setMedicines([...medicines, newEmptyMedicine()]);
  };

  const removeMedicine = (index: number) => {
    if (medicines.length > 1) {
      setMedicines(medicines.filter((_, i) => i !== index));
    }
  };

  const handleMedicineSelect = (
    index: number,
    medicine: {
      brandId: string;
      brandName: string;
      composition: string;
      manufacturerId: string;
      manufacturerName: string;
      dosageForm: string;
      strength: string;
      saltId?: string;
    }
  ) => {
    const updated = [...medicines];
    updated[index] = {
      ...updated[index],
      brand_name: medicine.brandName,
      brand_id: medicine.brandId || null,
      salt_id: medicine.saltId || null,
      composition: medicine.composition || "",
      dose: `${medicine.dosageForm} ${medicine.strength}`.trim(),
    };
    setMedicines(updated);
  };

  const handleLoadTemplate = (t: PrescriptionTemplate) => {
    setMedicines(
      t.medicines.map((m) => ({
        _uid: Math.random().toString(36).slice(2),
        brand_name: m.brand_name || "",
        brand_id: m.brand_id || null,
        salt_id: m.salt_id || null,
        composition: m.composition || "",
        dose: m.dose || "",
        frequency: m.frequency || "OD",
        duration: m.duration || "7 days",
        route: m.route || "oral",
        instructions: m.instructions || "",
      }))
    );
    if (t.diagnosis) setDiagnosis(t.diagnosis);
    if (t.notes) setNotes(t.notes);
    setShowLoadModal(false);
  };

  const handleSaveTemplate = async (name: string) => {
    const validMeds = medicines.filter((m) => m.brand_name);
    if (validMeds.length === 0) return;
    try {
      const res = await api.post("/api/v1/doctors/prescription-templates", {
        name,
        medicines: validMeds,
        diagnosis: diagnosis || undefined,
        notes: notes || undefined,
      });
      setTemplates((prev) => [res.data, ...prev]);
      setShowSaveModal(false);
    } catch (err) {
      console.error("Template save failed:", err);
      // non-critical — prescription can still be created without saving template
    }
  };

  const handleDiscardDraft = () => {
    try {
      localStorage.removeItem(DRAFT_STORAGE_KEY);
    } catch {
      // best-effort
    }
    setSelectedPatient(null);
    setMedicines([newEmptyMedicine()]);
    setDiagnosis("");
    setNotes("");
    setValidUntil("");
    setSelectedClinicId("");
    setSelectedBranchId("");
    setBranches([]);
    pendingBranchRef.current = null;
    setInteractions([]);
    setDraftRestored(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    if (!selectedPatient) {
      setError("Please select a patient");
      setLoading(false);
      return;
    }

    const medicinesFormatted = medicines
      .filter((m) => m.brand_name)
      .map((m) => ({
        brand_name: m.brand_name,
        brand_id: m.brand_id || undefined,
        salt_id: m.salt_id || undefined,
        dose: m.dose,
        frequency: m.frequency,
        duration: m.duration,
        route: m.route,
        instructions: m.instructions || undefined,
      }));

    if (medicinesFormatted.length === 0) {
      setError("Please add at least one medicine");
      setLoading(false);
      return;
    }

    // ------------------------------------------------------------------
    // Safety gate — re-run the interaction check at submit time so the
    // decision is based on fresh data, not the debounced preview.
    // ------------------------------------------------------------------
    const saltIds = medicinesFormatted
      .map((m) => m.salt_id)
      .filter((id): id is string => !!id);

    let latestInteractions = interactions;
    if (saltIds.length >= 2) {
      try {
        latestInteractions = await checkDrugInteractions(saltIds);
        setInteractions(latestInteractions || []);
      } catch {
        // Check failed — fall back to whatever the live check last returned
        // rather than blocking the prescription on a network hiccup.
      }
    } else {
      latestInteractions = [];
      setInteractions([]);
    }

    const blockingInteractions = (latestInteractions || []).filter((ix) =>
      BLOCKING_SEVERITIES.has(ix.severity)
    );

    if (
      (blockingInteractions.length > 0 || allergyConflicts.length > 0) &&
      !safetyAcknowledged
    ) {
      setSafetyAckRequired(true);
      setError(
        "Safety review required: this prescription has major drug interactions or allergy conflicts. Review the warnings below and check the acknowledgment box to proceed."
      );
      setLoading(false);
      return;
    }

    try {
      await api.post(
        "/api/v1/doctors/prescriptions",
        {
          patient_id: selectedPatient.id,
          medicines: medicinesFormatted,
          diagnosis: diagnosis || undefined,
          notes: notes || undefined,
          valid_until: validUntil || undefined,
          clinic_id: selectedClinicId || undefined,
          branch_id: selectedBranchId || undefined,
          appointment_id: appointmentId || undefined,
        },
        {
          headers: {
            "Idempotency-Key": idempotencyKey,
            ...(selectedClinicId ? { "X-Clinic-Id": selectedClinicId } : {}),
          },
        }
      );
      try {
        localStorage.removeItem(DRAFT_STORAGE_KEY);
      } catch {
        // best-effort
      }
      setIdempotencyKey(crypto.randomUUID());
      setSuccess(true);
      setTimeout(() => router.push("/doctor/prescriptions"), 1500);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      if (
        err.response?.status === 409 &&
        detail?.error?.code === "SAFETY_OVERRIDE_REQUIRED"
      ) {
        setOverrideAlerts(detail.error.alerts || []);
        setError(
          "Major safety alert: enter a clinical justification to proceed"
        );
      } else {
        const errorMsg =
          detail?.error?.message || detail || "Failed to create prescription";
        setError(typeof errorMsg === "string" ? errorMsg : JSON.stringify(errorMsg));
      }
    } finally {
      setLoading(false);
    }
  };

  const handleOverrideSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!overrideReason.trim()) return;
    setError("");
    setLoading(true);
    const medicinesFormatted = medicines
      .filter((m) => m.brand_name)
      .map((m) => ({
        brand_name: m.brand_name,
        brand_id: m.brand_id || undefined,
        salt_id: m.salt_id || undefined,
        dose: m.dose,
        frequency: m.frequency,
        duration: m.duration,
        route: m.route,
        instructions: m.instructions || undefined,
      }));
    try {
      await api.post(
        "/api/v1/doctors/prescriptions",
        {
          patient_id: selectedPatient?.id,
          medicines: medicinesFormatted,
          diagnosis: diagnosis || undefined,
          notes: notes || undefined,
          valid_until: validUntil || undefined,
          clinic_id: selectedClinicId || undefined,
          branch_id: selectedBranchId || undefined,
          appointment_id: appointmentId || undefined,
          safety_override_reason: overrideReason.trim(),
        },
        {
          headers: {
            "Idempotency-Key": idempotencyKey,
            ...(selectedClinicId ? { "X-Clinic-Id": selectedClinicId } : {}),
          },
        }
      );
      try {
        localStorage.removeItem(DRAFT_STORAGE_KEY);
      } catch {
        // best-effort
      }
      setIdempotencyKey(crypto.randomUUID());
      setSuccess(true);
      setTimeout(() => router.push("/doctor/prescriptions"), 1500);
    } catch (err: any) {
      const errorMsg =
        err.response?.data?.detail?.error?.message ||
        err.response?.data?.detail ||
        "Failed to create prescription";
      setError(typeof errorMsg === "string" ? errorMsg : JSON.stringify(errorMsg));
    } finally {
      setLoading(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  if (success) {
    return (
      <div className="space-y-6">
        <Breadcrumb
          items={[
            { label: "Prescriptions", href: "/doctor/prescriptions" },
            { label: "New Prescription" },
          ]}
        />
        <div className="bg-green-50 rounded-lg border border-green-200 p-6 text-center">
          <p className="text-lg font-medium text-green-800">
            Prescription created!
          </p>
          <p className="mt-1 text-sm text-green-600">
            The patient can now see this in their timeline.
          </p>
        </div>
      </div>
    );
  }

  const hasMedicines = medicines.some((m) => m.brand_name);

  return (
    <div className="space-y-6">
      {showLoadModal && (
        <LoadTemplateModal
          templates={templates}
          onLoad={handleLoadTemplate}
          onClose={() => setShowLoadModal(false)}
        />
      )}
      {showSaveModal && (
        <SaveTemplateModal
          onSave={handleSaveTemplate}
          onClose={() => setShowSaveModal(false)}
        />
      )}

      <Breadcrumb
        items={[
          { label: "Prescriptions", href: "/doctor/prescriptions" },
          { label: "New Prescription" },
        ]}
      />

      {appointmentId && (
        <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800">
          Linked to appointment — prescription will be associated with this appointment on save.
        </div>
      )}

      {draftRestored && (
        <div className="flex items-center gap-3 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800">
          <History className="h-4 w-4 flex-shrink-0" />
          <span className="flex-1">
            Draft restored — your unsaved prescription was recovered from this
            browser.
          </span>
          <button
            type="button"
            onClick={handleDiscardDraft}
            className="text-xs font-medium text-blue-700 hover:underline whitespace-nowrap"
          >
            Discard draft
          </button>
          <button
            type="button"
            onClick={() => setDraftRestored(false)}
            aria-label="Dismiss draft notice"
            className="text-blue-500 hover:text-blue-700 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-dreams-textPrimary">
            Create Prescription
          </h1>
          <p className="text-dreams-textSecondary mt-1">
            Write a new prescription for a patient
          </p>
        </div>
        <div className="flex gap-2">
          {templates.length > 0 && (
            <button
              type="button"
              onClick={() => setShowLoadModal(true)}
              className="flex items-center gap-2 px-4 py-2 border border-dreams-border text-sm font-medium text-dreams-textPrimary rounded-lg hover:bg-dreams-lightBg transition-colors"
            >
              <BookOpen className="h-4 w-4" />
              Load Template
            </button>
          )}
          {hasMedicines && (
            <button
              type="button"
              onClick={() => setShowSaveModal(true)}
              className="flex items-center gap-2 px-4 py-2 border border-dreams-border text-sm font-medium text-dreams-textPrimary rounded-lg hover:bg-dreams-lightBg transition-colors"
            >
              <Save className="h-4 w-4" />
              Save as Template
            </button>
          )}
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6 max-w-4xl">
        {/* Patient & Diagnosis */}
        <div className="bg-white rounded-lg shadow-card p-6">
          <h2 className="text-lg font-semibold text-dreams-textPrimary mb-4">
            Patient Details
          </h2>

          {error && (
            <div className="mb-4 rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {overrideAlerts && (
            <div className="mb-4 rounded-lg border border-amber-300 bg-amber-50 p-4">
              <p className="text-sm font-semibold text-amber-900 mb-2">
                Major safety alerts detected
              </p>
              <ul className="mb-3 space-y-1 text-sm text-amber-800 list-disc pl-5">
                {overrideAlerts.map((a: any, i: number) => (
                  <li key={i}>
                    {typeof a === "string" ? a : a.description || a.message || a.drug_pair || JSON.stringify(a)}
                    {(a?.severity || a?.level) && (
                      <span className="ml-1 text-xs uppercase font-medium">
                        [{a.severity || a.level}]
                      </span>
                    )}
                  </li>
                ))}
              </ul>
              <label htmlFor="override-reason" className="mb-1 block text-sm font-medium text-amber-900">
                Clinical justification *
              </label>
              <textarea
                id="override-reason"
                value={overrideReason}
                onChange={(e) => setOverrideReason(e.target.value)}
                rows={2}
                className="mb-2 w-full rounded-lg border border-amber-300 bg-white px-3 py-2 text-sm focus:border-amber-500 focus:outline-none"
                placeholder="Reason for prescribing despite the alert"
              />
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={handleOverrideSubmit}
                  disabled={loading || !overrideReason.trim()}
                  className="rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-700 disabled:opacity-50"
                >
                  {loading ? "Saving…" : "Save with override"}
                </button>
                <button
                  type="button"
                  onClick={() => { setOverrideAlerts(null); setOverrideReason(""); setError(""); }}
                  className="rounded-lg border border-amber-300 px-4 py-2 text-sm font-medium text-amber-800 hover:bg-amber-100"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          <div className="mb-4">
            <label htmlFor="rx-patient" className="mb-1 block text-sm font-medium text-dreams-textPrimary">
              Patient *
            </label>
            {selectedPatient ? (
              <div className="flex items-center gap-3 rounded-lg border border-dreams-blue bg-dreams-blue/5 px-4 py-2.5">
                <div className="flex-1">
                  <p className="text-sm font-semibold text-dreams-textPrimary">
                    {selectedPatient.full_name}
                  </p>
                  {selectedPatient.phone && (
                    <p className="text-xs text-dreams-textSecondary">
                      {selectedPatient.phone}
                    </p>
                  )}
                </div>
                <button
                  type="button"
                  onClick={handlePatientClear}
                  aria-label="Clear selected patient"
                  className="text-dreams-textSecondary hover:text-red-500 transition-colors"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ) : (
              <PatientSearch onSelect={handlePatientSelect} />
            )}
          </div>

          {/* Patient allergy / chronic-condition safety banner */}
          {selectedPatient && (
            <PatientAllergyBanner
              allergies={patientAllergies}
              chronicConditions={patientChronic}
              className="mb-4"
            />
          )}

          {/* Allergy × selected-medicine conflicts — blocks submit until acked */}
          {selectedPatient && allergyConflicts.length > 0 && (
            <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 flex items-start gap-3">
              <AlertTriangle className="h-5 w-5 mt-0.5 flex-shrink-0 text-red-500" />
              <div className="flex-1">
                <p className="text-sm font-semibold text-red-800">
                  Possible allergy conflicts
                </p>
                <ul className="mt-1.5 space-y-0.5">
                  {allergyConflicts.map((c, i) => (
                    <li
                      key={`${c.allergy}-${c.medicine}-${i}`}
                      className="text-xs font-medium text-red-800"
                    >
                      "{c.allergy}" may match selected medicine "{c.medicine}".
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {/* Clinic selector */}
          {clinics.length > 0 && (
            <div className="mb-4">
              <label htmlFor="rx-clinic" className="mb-1 block text-sm font-medium text-dreams-textPrimary">
                Clinic
              </label>
              <select
                id="rx-clinic"
                value={selectedClinicId}
                onChange={(e) => {
                  setSelectedClinicId(e.target.value);
                  setSelectedBranchId("");
                  setBranches([]);
                  setBranchesLoading(Boolean(e.target.value));
                }}
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

          {/* Branch selector (shown when clinic has branches) */}
          {selectedClinicId && (branchesLoading || branches.length > 0) && (
            <div className="mb-4">
              <label htmlFor="rx-branch" className="mb-1 block text-sm font-medium text-dreams-textPrimary">
                Branch
              </label>
              {branchesLoading ? (
                <div className="h-10 rounded-lg border border-dreams-border bg-gray-50 flex items-center px-3">
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-dreams-blue border-t-transparent" />
                  <span className="ml-2 text-sm text-dreams-textSecondary">Loading branches...</span>
                </div>
              ) : (
                <select
                  id="rx-branch"
                  value={selectedBranchId}
                  onChange={(e) => setSelectedBranchId(e.target.value)}
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

          <div className="mb-4">
            <label htmlFor="rx-diagnosis" className="mb-1 block text-sm font-medium text-dreams-textPrimary">
              Diagnosis
            </label>
            <input
              id="rx-diagnosis"
              type="text"
              value={diagnosis}
              onChange={(e) => setDiagnosis(e.target.value)}
              placeholder="e.g., Upper respiratory infection"
              className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
            />
          </div>

          <div className="mb-4">
            <label htmlFor="rx-valid-until" className="mb-1 block text-sm font-medium text-dreams-textPrimary">
              Valid until (optional)
            </label>
            <input
              id="rx-valid-until"
              type="date"
              value={validUntil}
              min={new Date().toISOString().slice(0, 10)}
              onChange={(e) => setValidUntil(e.target.value)}
              className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
            />
          </div>

          <div>
            <label htmlFor="rx-notes" className="mb-1 block text-sm font-medium text-dreams-textPrimary">
              Notes
            </label>
            <textarea
              id="rx-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              placeholder="Additional instructions..."
              className="w-full rounded-lg border border-dreams-border px-3 py-2 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
            />
          </div>
        </div>

        {/* Medicines */}
        <div>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-dreams-textPrimary">
              Medicines
            </h2>
            <button
              type="button"
              onClick={addMedicine}
              className="text-sm text-dreams-blue hover:underline font-medium"
            >
              + Add Medicine
            </button>
          </div>

          {/* Drug interaction warnings */}
          <DrugInteractionWarning
            interactions={sortBySeverity(interactions)}
            className="mb-4"
          />

          {medicines.map((med, idx) => (
            <div key={med._uid} className="mb-4 bg-white rounded-lg shadow-card p-6">
              <div className="mb-4 flex items-center justify-between">
                <span className="text-sm font-medium text-dreams-textSecondary">
                  Medicine {idx + 1}
                </span>
                {medicines.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeMedicine(idx)}
                    className="text-xs text-red-500 hover:underline"
                  >
                    Remove
                  </button>
                )}
              </div>

              {/* Medicine Search — wrapping <label> gives implicit association
                  with the input rendered inside MedicineAutocomplete */}
              <div className="mb-4">
                <label className="block">
                  <span className="mb-2 block text-sm font-medium text-dreams-textPrimary">
                    Medicine Name *
                  </span>
                  <MedicineAutocomplete
                    onSelect={(medicine) => handleMedicineSelect(idx, medicine)}
                    placeholder="Search for medicine (e.g., Dolo, Paracetamol)..."
                    className="w-full"
                  />
                </label>
                {med.brand_name ? (
                  <div className="mt-2 rounded-md bg-green-50 border-2 border-green-200 px-3 py-2">
                    <div className="flex items-center gap-2">
                      <div>
                        <p className="text-sm font-medium text-green-900">
                          {med.brand_name}
                        </p>
                        {med.dose && (
                          <p className="text-xs text-green-700 mt-1">
                            {med.dose}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                ) : (
                  <p className="mt-2 text-xs text-dreams-textSecondary">
                    Start typing to search medicines...
                  </p>
                )}
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                {/* Dose */}
                <div>
                  <label htmlFor={`rx-dose-${idx}`} className="mb-1 block text-sm font-medium text-dreams-textPrimary">
                    Dose
                  </label>
                  <input
                    id={`rx-dose-${idx}`}
                    type="text"
                    value={med.dose}
                    onChange={(e) => updateMedicine(idx, "dose", e.target.value)}
                    placeholder="e.g., 500mg tablet"
                    className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
                  />
                </div>

                {/* Frequency */}
                <div>
                  <span id={`rx-frequency-label-${idx}`} className="mb-1 block text-sm font-medium text-dreams-textPrimary">
                    Frequency *
                  </span>
                  <div
                    role="group"
                    aria-labelledby={`rx-frequency-label-${idx}`}
                    className="flex flex-wrap gap-1.5"
                  >
                    {FREQUENCY_OPTIONS.map((f) => (
                      <button
                        key={f}
                        type="button"
                        onClick={() => updateMedicine(idx, "frequency", f)}
                        className={`rounded-md border px-3 py-1.5 text-xs font-medium transition-colors
                          ${
                            med.frequency === f
                              ? "border-dreams-blue bg-dreams-blue text-white"
                              : "border-dreams-border bg-white text-dreams-textPrimary hover:border-dreams-blue/50"
                          }`}
                      >
                        {f}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Duration */}
                <div>
                  <label htmlFor={`rx-duration-${idx}`} className="mb-1 block text-sm font-medium text-dreams-textPrimary">
                    Duration *
                  </label>
                  <select
                    id={`rx-duration-${idx}`}
                    value={med.duration}
                    onChange={(e) =>
                      updateMedicine(idx, "duration", e.target.value)
                    }
                    className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
                  >
                    {DURATION_OPTIONS.map((d) => (
                      <option key={d} value={d}>
                        {d}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Route */}
                <div>
                  <label htmlFor={`rx-route-${idx}`} className="mb-1 block text-sm font-medium text-dreams-textPrimary">
                    Route
                  </label>
                  <select
                    id={`rx-route-${idx}`}
                    value={med.route}
                    onChange={(e) =>
                      updateMedicine(idx, "route", e.target.value)
                    }
                    className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
                  >
                    {ROUTE_OPTIONS.map((r) => (
                      <option key={r.value} value={r.value}>
                        {r.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Instructions */}
              <div className="mt-4">
                <label htmlFor={`rx-instructions-${idx}`} className="mb-1 block text-sm font-medium text-dreams-textPrimary">
                  Instructions
                </label>
                <input
                  id={`rx-instructions-${idx}`}
                  type="text"
                  value={med.instructions}
                  onChange={(e) =>
                    updateMedicine(idx, "instructions", e.target.value)
                  }
                  placeholder="e.g., Take with plenty of water, after meals"
                  className="w-full h-10 rounded-lg border border-dreams-border px-3 text-sm focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
                />
              </div>
            </div>
          ))}
        </div>

        {/* Submit */}
        <div>
          {!hasMedicines && (
            <div className="mb-3 rounded-lg bg-amber-50 border border-amber-200 px-4 py-2 text-sm text-amber-800">
              Please select at least one medicine
            </div>
          )}

          {/* Safety gate — explicit acknowledgment required for blocking alerts */}
          {safetyAckRequired && (
            <div className="mb-4 rounded-lg border-2 border-red-300 bg-red-50 p-4">
              <div className="flex items-start gap-3">
                <AlertTriangle className="h-5 w-5 mt-0.5 flex-shrink-0 text-red-600" />
                <div className="flex-1">
                  <p className="text-sm font-semibold text-red-800">
                    Safety review required before this prescription can be
                    created
                  </p>
                  <ul className="mt-2 space-y-1">
                    {interactions
                      .filter((ix) => BLOCKING_SEVERITIES.has(ix.severity))
                      .map((ix) => (
                        <li
                          key={ix.interaction_id}
                          className="text-xs text-red-700"
                        >
                          <span className="font-semibold capitalize">
                            [{ix.severity}]
                          </span>{" "}
                          {ix.salt_1.name} + {ix.salt_2.name} — {ix.effect}
                        </li>
                      ))}
                    {allergyConflicts.map((c, i) => (
                      <li
                        key={`ack-allergy-${i}`}
                        className="text-xs text-red-700"
                      >
                        <span className="font-semibold">[allergy]</span>{" "}
                        {c.medicine} may conflict with recorded allergy "
                        {c.allergy}"
                      </li>
                    ))}
                  </ul>
                  <label className="mt-3 flex items-start gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={safetyAcknowledged}
                      onChange={(e) => setSafetyAcknowledged(e.target.checked)}
                      className="mt-0.5 h-4 w-4 rounded border-red-300 accent-red-600"
                    />
                    <span className="text-sm font-medium text-red-800">
                      I acknowledge the interaction warnings
                      {allergyConflicts.length > 0 &&
                        " and allergy conflicts"}{" "}
                      and take clinical responsibility for this prescription.
                    </span>
                  </label>
                  {!safetyAcknowledged && (
                    <p className="mt-1.5 text-xs text-red-600">
                      Check the box above, then click Create Prescription again
                      to proceed.
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}

          <div className="flex gap-3">
            <button
              type="submit"
              disabled={
                loading ||
                !selectedPatient ||
                !hasMedicines ||
                (safetyAckRequired && !safetyAcknowledged)
              }
              className="px-6 py-2.5 bg-dreams-blue text-white text-sm font-medium rounded-lg hover:opacity-90 disabled:opacity-50 transition-opacity"
            >
              {loading ? "Creating..." : "Create Prescription"}
            </button>
            <button
              type="button"
              onClick={() => router.back()}
              className="px-6 py-2.5 border border-dreams-border text-sm font-medium text-dreams-textPrimary rounded-lg hover:bg-dreams-lightBg transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
