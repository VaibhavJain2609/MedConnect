/**
 * Vitals API Functions
 * Handles patient vitals time-series data
 */

import api from "../api";

export const VITAL_TYPES = [
  "bp_systolic",
  "bp_diastolic",
  "glucose_fasting",
  "glucose_pp",
  "weight_kg",
  "spo2",
  "pulse",
  "temperature_c",
] as const;

export type VitalType = (typeof VITAL_TYPES)[number];

export const VITAL_META: Record<
  VitalType,
  { label: string; unit: string; normalRange: string; color: string }
> = {
  bp_systolic: {
    label: "BP Systolic",
    unit: "mmHg",
    normalRange: "90–120 mmHg",
    color: "#EF4444",
  },
  bp_diastolic: {
    label: "BP Diastolic",
    unit: "mmHg",
    normalRange: "60–80 mmHg",
    color: "#F97316",
  },
  glucose_fasting: {
    label: "Glucose (Fasting)",
    unit: "mg/dL",
    normalRange: "70–100 mg/dL",
    color: "#EAB308",
  },
  glucose_pp: {
    label: "Glucose (PP)",
    unit: "mg/dL",
    normalRange: "< 140 mg/dL",
    color: "#84CC16",
  },
  weight_kg: {
    label: "Weight",
    unit: "kg",
    normalRange: "Varies by individual",
    color: "#06B6D4",
  },
  spo2: {
    label: "SpO2",
    unit: "%",
    normalRange: "95–100%",
    color: "#3B82F6",
  },
  pulse: {
    label: "Pulse",
    unit: "bpm",
    normalRange: "60–100 bpm",
    color: "#8B5CF6",
  },
  temperature_c: {
    label: "Temperature",
    unit: "°C",
    normalRange: "36.1–37.2 °C",
    color: "#EC4899",
  },
};

export interface Vital {
  id: string;
  patient_id: string;
  vital_type: VitalType;
  value: number;
  unit: string;
  recorded_at: string;
  notes?: string;
  recorded_by?: string;
  created_at: string;
  abnormal_flag?: boolean;
}

/**
 * Client-side threshold check matching the backend VITAL_THRESHOLDS.
 * Returns true if the value is outside the critical range.
 */
export const VITAL_THRESHOLDS: Partial<
  Record<VitalType, { min?: number; max?: number }>
> = {
  bp_systolic:     { max: 180 },
  bp_diastolic:    { max: 120 },
  glucose_fasting: { min: 70, max: 300 },
  glucose_pp:      { min: 70, max: 300 },
  spo2:            { min: 92 },
  pulse:           { min: 40, max: 150 },
};

export function isVitalAbnormal(vitalType: VitalType, value: number): boolean {
  const t = VITAL_THRESHOLDS[vitalType];
  if (!t) return false;
  if (t.min !== undefined && value < t.min) return true;
  if (t.max !== undefined && value > t.max) return true;
  return false;
}

export interface VitalsListResponse {
  data: Vital[];
  total: number;
}

export interface VitalCreatePayload {
  vital_type: VitalType;
  value: number;
  unit: string;
  recorded_at?: string;
  notes?: string;
}

/**
 * Record a new vital reading (patient)
 */
export async function createVital(payload: VitalCreatePayload): Promise<Vital> {
  const response = await api.post("/api/v1/patients/vitals", payload);
  return response.data;
}

/**
 * Get patient's own vitals
 */
export async function getMyVitals(params: {
  type?: string;
  days?: number;
  limit?: number;
}): Promise<VitalsListResponse> {
  const queryParams = new URLSearchParams();
  if (params.type) queryParams.append("type", params.type);
  if (params.days) queryParams.append("days", String(params.days));
  if (params.limit) queryParams.append("limit", String(params.limit));
  const response = await api.get(`/api/v1/patients/vitals?${queryParams}`);
  return response.data;
}

/**
 * Get patient vitals for a doctor
 */
export async function getPatientVitals(
  patientId: string,
  params: { type?: string; days?: number }
): Promise<VitalsListResponse> {
  const queryParams = new URLSearchParams();
  if (params.type) queryParams.append("type", params.type);
  if (params.days) queryParams.append("days", String(params.days));
  const response = await api.get(
    `/api/v1/doctors/patients/${patientId}/vitals?${queryParams}`
  );
  return response.data;
}
