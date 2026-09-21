/**
 * Prescription API utilities
 */

import api from '@/lib/api';

export interface Medicine {
  name: string;
  dosage: string;
  frequency: string;
  duration: string;
  timing?: string;
  notes?: string;
}

export interface PrescriptionData {
  id: string;
  medicines: Medicine[];
  diagnosis?: string;
  notes?: string;
  created_at: string;
  doctor_name?: string;
  valid_until?: string;
  doctor_id?: string;
  patient_id?: string;
}

/**
 * Extract prescription data from medical record
 */
export function extractPrescriptionFromRecord(record: any): PrescriptionData | null {
  if (record.record_type !== 'prescription') {
    return null;
  }

  // First, check if prescription data is included in the record (from joined query)
  if (record.prescription) {
    return {
      id: record.id,
      medicines: record.prescription.medicines || [],
      diagnosis: record.prescription.diagnosis,
      notes: record.prescription.notes,
      created_at: record.created_at,
      doctor_name: record.doctor_name,
      valid_until: record.prescription.valid_until,
    };
  }

  // Second, try to extract from FHIR bundle
  const fhirBundle = record.fhir_bundle;
  let medicines: Medicine[] = [];

  if (fhirBundle?.entry) {
    // Extract from FHIR bundle (MedicationRequest resources)
    const medicationRequests = fhirBundle.entry.filter(
      (e: any) => e.resource?.resourceType === 'MedicationRequest'
    );

    medicines = medicationRequests.map((entry: any) => {
      const resource = entry.resource;
      const dosageInstruction = resource.dosageInstruction?.[0] || {};

      return {
        name: resource.medicationCodeableConcept?.text || 'Unknown',
        dosage: dosageInstruction.doseAndRate?.[0]?.doseQuantity?.value || '',
        frequency: dosageInstruction.timing?.code?.text || '',
        duration: '', // Not in FHIR structure
        timing: dosageInstruction.additionalInstruction?.[0]?.text,
        notes: resource.note?.[0]?.text,
      };
    });
  }

  // Fallback: Show message if no data available
  if (medicines.length === 0) {
    medicines = [{
      name: 'Prescription details not available',
      dosage: 'Please contact your doctor',
      frequency: 'N/A',
      duration: 'N/A',
      timing: undefined,
      notes: undefined,
    }];
  }

  return {
    id: record.id,
    medicines,
    diagnosis: record.title?.replace('Prescription — ', '') || undefined,
    notes: record.description,
    created_at: record.created_at,
    doctor_name: record.doctor_name,
    valid_until: undefined,
  };
}

/**
 * Fetch full prescription details by record ID
 */
export async function fetchPrescriptionDetails(recordId: string): Promise<PrescriptionData> {
  // First get the medical record
  const recordRes = await api.get(`/api/v1/patients/records/${recordId}`);
  const record = recordRes.data;

  // Try to find associated prescription entity
  try {
    const prescriptionsRes = await api.get('/api/v1/patients/prescriptions');
    const prescriptions = prescriptionsRes.data.items || [];

    // Find prescription with matching record_id
    const prescription = prescriptions.find((p: any) => p.record_id === recordId);

    if (prescription) {
      return {
        id: prescription.id,
        medicines: prescription.medicines,
        diagnosis: prescription.diagnosis,
        notes: prescription.notes,
        created_at: prescription.created_at,
        valid_until: prescription.valid_until,
        doctor_id: prescription.doctor_id,
        patient_id: prescription.patient_id,
      };
    }
  } catch (err) {
    console.warn('Could not fetch prescription details:', err);
  }

  // Fallback to extracted data from record
  return extractPrescriptionFromRecord(record) || {
    id: recordId,
    medicines: [],
    created_at: record.created_at,
  };
}

// ─── Adherence helpers (patient medications view) ────────────────────────────

const DAY_MS = 24 * 60 * 60 * 1000;

/**
 * Days ahead of `valid_until` at which a prescription is considered "expiring".
 * Mirrors EXPIRING_SOON_DAYS in
 * backend/app/workers/tasks/prescription_expiry.py — the daily worker notifies
 * patients and prescribers at the same threshold, so the badge matches what
 * the notification says.
 */
export const PRESCRIPTION_EXPIRY_WARNING_DAYS = 3;

function startOfDay(d: Date): Date {
  const copy = new Date(d);
  copy.setHours(0, 0, 0, 0);
  return copy;
}

const INDEFINITE_DURATION =
  /ongoing|continu|indefinit|long[\s-]?term|life[\s-]?long|sos|prn|chronic/i;

/**
 * Parse a free-text `duration` from a medicines JSONB item into days.
 *
 * Handles the shapes doctors actually enter: "7 days", "1 month", "2 weeks",
 * "5d", "10-14 days" (lower bound wins). Indefinite courses ("Ongoing",
 * "Continuous", "SOS") and unparseable text return null.
 */
export function parseDurationDays(
  duration: string | null | undefined
): number | null {
  if (!duration) return null;
  const text = duration.trim();
  if (!text || INDEFINITE_DURATION.test(text)) return null;

  const match = text.match(/(\d+)\s*(day|days|week|weeks|month|months|year|years|d|w|m|y)\b/i);
  if (!match) return null;

  const n = parseInt(match[1], 10);
  if (!Number.isFinite(n) || n <= 0) return null;

  const unit = match[2].toLowerCase();
  if (unit.startsWith("d")) return n;
  if (unit.startsWith("w")) return n * 7;
  if (unit.startsWith("m")) return n * 30;
  if (unit.startsWith("y")) return n * 365;
  return null;
}

export type AdherenceStatus = "active" | "expiring" | "expired";

export interface PrescriptionAdherence {
  /** Calendar day the course started (prescription created_at, day-truncated). */
  startDate: Date;
  /**
   * Effective course end: `valid_until` when set, else
   * `created_at + duration`. Null when the course is indefinite.
   */
  endDate: Date | null;
  /** Which field produced endDate — drives badge wording ("expires" vs "course ends"). */
  endSource: "valid_until" | "duration" | null;
  /** True when no finite end could be derived (no valid_until + indefinite duration). */
  ongoing: boolean;
  status: AdherenceStatus;
  /** Days until endDate, clamped at 0; null when ongoing. */
  daysRemaining: number | null;
  /** Total course length in days (>= 1); null when ongoing. */
  totalDays: number | null;
  /** Days since startDate clamped to [0, totalDays]; null when ongoing. */
  elapsedDays: number | null;
  /** 0–100 course completion; null when ongoing. */
  percentComplete: number | null;
}

/**
 * Derive adherence context for one medicine item on a prescription.
 *
 * - `valid_until` (a Date column) is the authoritative expiry when present;
 *   the backend expiry worker only looks at it.
 * - Otherwise the item's free-text `duration` is added to `created_at` to
 *   estimate the course end.
 * - Items with neither are treated as ongoing (never "expired").
 */
export function computePrescriptionAdherence(args: {
  createdAt: string;
  validUntil: string | null | undefined;
  duration?: string | null;
  today?: Date;
}): PrescriptionAdherence {
  const today = startOfDay(args.today ?? new Date());
  const startDate = startOfDay(new Date(args.createdAt));

  let endDate: Date | null = null;
  let endSource: PrescriptionAdherence["endSource"] = null;
  if (args.validUntil) {
    endDate = startOfDay(new Date(args.validUntil));
    endSource = "valid_until";
  } else {
    const durationDays = parseDurationDays(args.duration);
    if (durationDays != null) {
      endDate = new Date(startDate.getTime() + durationDays * DAY_MS);
      endSource = "duration";
    }
  }

  if (!endDate) {
    return {
      startDate,
      endDate: null,
      endSource: null,
      ongoing: true,
      status: "active",
      daysRemaining: null,
      totalDays: null,
      elapsedDays: null,
      percentComplete: null,
    };
  }

  const totalDays = Math.max(
    1,
    Math.round((endDate.getTime() - startDate.getTime()) / DAY_MS)
  );
  const elapsedDays = Math.min(
    totalDays,
    Math.max(0, Math.round((today.getTime() - startDate.getTime()) / DAY_MS))
  );
  const daysRemaining = Math.max(
    0,
    Math.round((endDate.getTime() - today.getTime()) / DAY_MS)
  );
  const expired = endDate.getTime() < today.getTime();
  const expiring = !expired && daysRemaining <= PRESCRIPTION_EXPIRY_WARNING_DAYS;

  return {
    startDate,
    endDate,
    endSource,
    ongoing: false,
    status: expired ? "expired" : expiring ? "expiring" : "active",
    daysRemaining,
    totalDays,
    elapsedDays,
    percentComplete: Math.round((elapsedDays / totalDays) * 100),
  };
}

// ─── Patient prescriptions (cursor-exhausting fetch) ─────────────────────────

/** Re-exported so adherence UI can type items without importing the portal module. */
export type { PatientPrescription, PrescriptionMedicine } from "./patient-portal";

/**
 * Fetch every prescription for the current patient by following the
 * cursor-based pagination of GET /api/v1/patients/prescriptions.
 *
 * Capped at `maxPages` requests as a runaway-pagination guard.
 */
export async function getAllMyPrescriptions(
  pageSize = 100,
  maxPages = 25
): Promise<import("./patient-portal").PatientPrescription[]> {
  const out: import("./patient-portal").PatientPrescription[] = [];
  let cursor: string | null = null;

  for (let page = 0; page < maxPages; page++) {
    const qs = new URLSearchParams({ limit: String(pageSize) });
    if (cursor) qs.set("cursor", cursor);
    const res = await api.get(`/api/v1/patients/prescriptions?${qs}`);
    const body = res.data;
    out.push(...(body.data ?? []));
    const next = body.pagination?.next_cursor ?? null;
    if (!body.pagination?.has_more || !next) break;
    cursor = next;
  }

  return out;
}
