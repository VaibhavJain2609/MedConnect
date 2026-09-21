/**
 * Patient Portal API Functions
 * Patient-scoped endpoints for lab results, billing, and medications.
 */

import api from "../api";

export interface Paginated<T> {
  data: T[];
  pagination: {
    next_cursor: string | null;
    has_more: boolean;
    limit: number;
  };
}

// ─── Lab results ─────────────────────────────────────────────────────────────

export interface PatientLabResult {
  id: string;
  test_id: string;
  test_name: string;
  test_category: string | null;
  appointment_date: string;
  status: string;
  result_value: string | null;
  result_unit: string | null;
  normal_range: string | null;
  abnormal_flag: boolean;
  notes: string | null;
  doctor_id: string | null;
  doctor_name: string | null;
  created_at: string;
}

export async function getMyLabResults(params: {
  category?: string;
  cursor?: string;
  limit?: number;
} = {}): Promise<Paginated<PatientLabResult>> {
  const queryParams = new URLSearchParams();
  if (params.category) queryParams.append("category", params.category);
  if (params.cursor) queryParams.append("cursor", params.cursor);
  if (params.limit) queryParams.append("limit", params.limit.toString());
  const response = await api.get(`/api/v1/patients/lab-results?${queryParams}`);
  return response.data;
}

export async function getMyLabResult(id: string): Promise<PatientLabResult> {
  const response = await api.get(`/api/v1/patients/lab-results/${id}`);
  return response.data;
}

// ─── Billing ─────────────────────────────────────────────────────────────────

export interface BillItem {
  id: string;
  description: string;
  quantity: string;
  unit_amount: string;
  amount: string;
}

export interface PatientBill {
  id: string;
  patient_id: string;
  patient_name: string | null;
  clinic_id: string | null;
  clinic_name: string | null;
  appointment_id: string | null;
  amount: string;
  status: string; // pending | paid | cancelled | refunded
  payment_method: string | null;
  notes: string | null;
  items: BillItem[];
  created_at: string;
  updated_at: string;
}

export async function getMyBills(params: {
  status?: string;
  limit?: number;
} = {}): Promise<{ data: PatientBill[]; total: number }> {
  const queryParams = new URLSearchParams();
  if (params.status) queryParams.append("status", params.status);
  if (params.limit) queryParams.append("limit", params.limit.toString());
  const qs = queryParams.toString();
  const response = await api.get(`/api/v1/billing${qs ? `?${qs}` : ""}`);
  return response.data;
}

export async function getMyBill(id: string): Promise<PatientBill> {
  const response = await api.get(`/api/v1/billing/${id}`);
  return response.data;
}

// ─── Prescriptions / medications ─────────────────────────────────────────────

/** Medicine item as stored in the prescription JSONB column. */
export interface PrescriptionMedicine {
  brand_name?: string;
  name?: string; // legacy shape
  dose?: string;
  dosage?: string; // legacy shape
  frequency?: string;
  duration?: string;
  route?: string;
  instructions?: string;
  timing?: string;
  notes?: string;
}

export interface PatientPrescription {
  id: string;
  record_id: string;
  medicines: PrescriptionMedicine[];
  diagnosis: string | null;
  notes: string | null;
  doctor_id?: string;
  doctor_name?: string | null;
  valid_until: string | null;
  created_at: string;
}

export async function getMyPrescriptions(params: {
  cursor?: string;
  limit?: number;
} = {}): Promise<Paginated<PatientPrescription>> {
  const queryParams = new URLSearchParams();
  if (params.cursor) queryParams.append("cursor", params.cursor);
  if (params.limit) queryParams.append("limit", params.limit.toString());
  const response = await api.get(`/api/v1/patients/prescriptions?${queryParams}`);
  return response.data;
}
