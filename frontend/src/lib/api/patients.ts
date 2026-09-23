/**
 * Patient API Functions
 * Handles patient data operations
 */

import api from "../api";
import { downloadFile } from "../download";

export interface Patient {
  id: string;
  name: string;
  photo: string | null;
  status: "inProgress" | "completed" | "pending";
  statusLabel: string;
  lastVisit: string;
  gender: string;
  location: string;
  doctor: string;
  department: string;
  age: number;
  bloodType?: string;
  phone?: string;
  email?: string;
  address?: string;
  city?: string;
  state?: string;
  zipCode?: string;
  emergencyContact?: string;
  emergencyPhone?: string;
  consent_status?: string;
}

export interface PatientVital {
  id: string;
  name: string;
  value: string;
  unit: string;
  status: "normal" | "warning" | "critical";
  trend?: "up" | "down" | "stable";
  trendValue?: string;
  lastUpdated: string;
  normalRange?: { min: number; max: number };
}

export interface PatientVitalHistory {
  date: string;
  value: number;
}

export interface PatientAppointment {
  id: string;
  doctor: string;
  doctorPhoto: string | null;
  department: string;
  date: string;
  time: string;
  status: "upcoming" | "completed" | "cancelled";
  type: string;
  notes?: string;
}

export interface PatientsListParams {
  search?: string;
  status?: string;
  page?: number;
  limit?: number;
  clinic_id?: string;
  consent_status?: string;
}

export interface PatientsListResponse {
  patients: Patient[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}

/**
 * Get paginated list of patients
 */
export async function getPatients(
  params: PatientsListParams = {}
): Promise<PatientsListResponse> {
  const queryParams = new URLSearchParams();

  queryParams.append("role", "patient");

  if (params.search) queryParams.append("search", params.search);
  if (params.status) queryParams.append("status", params.status);
  if (params.page) queryParams.append("page", params.page.toString());
  if (params.limit) queryParams.append("limit", params.limit.toString());
  if (params.clinic_id) queryParams.append("clinic_id", params.clinic_id);
  if (params.consent_status) queryParams.append("consent_status", params.consent_status);

  const response = await api.get(`/api/v1/admin/users?${queryParams}`);
  const raw = response.data;

  const patients: Patient[] = (raw.data ?? []).map((u: {
    id: string;
    full_name: string;
    is_active: boolean;
    phone?: string;
    email?: string;
    consent_status?: string;
  }) => ({
    id: u.id,
    name: u.full_name,
    photo: null,
    status: u.is_active ? "completed" : "pending",
    statusLabel: u.is_active ? "Active" : "Inactive",
    lastVisit: "—",
    gender: "—",
    location: "—",
    doctor: "—",
    department: "—",
    age: 0,
    phone: u.phone,
    email: u.email,
    consent_status: u.consent_status,
  }));

  return {
    patients,
    total: raw.total,
    page: raw.page,
    limit: raw.limit,
    totalPages: raw.totalPages,
  };
}

export type PatientsExportParams = Pick<
  PatientsListParams,
  "search" | "status" | "clinic_id" | "consent_status"
> & { is_active?: boolean };

/**
 * Download the admin patients CSV export.
 *
 * Hits GET /api/v1/admin/patients/export with the same filters as the
 * patient list (the backend maps the page's `status` values onto
 * is_active). The filename (patients-export-<date>.csv) is resolved
 * from the response's Content-Disposition header by downloadFile().
 */
export async function exportPatientsCsv(
  params: PatientsExportParams = {}
): Promise<void> {
  const qs = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      qs.set(key, String(value));
    }
  }
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  await downloadFile(`/api/v1/admin/patients/export${suffix}`);
}

/**
 * Get patient details by ID (admin view — backed by the admin user detail
 * endpoint, mapped onto the Patient card shape).
 */
export async function getPatient(id: string): Promise<Patient> {
  const response = await api.get(`/api/v1/admin/users/${id}`);
  const u = response.data;
  return {
    id: u.id,
    name: u.full_name,
    photo: null,
    status: u.is_active ? "completed" : "pending",
    statusLabel: u.is_active ? "Active" : "Inactive",
    lastVisit: u.last_visit ?? "—",
    gender: "—",
    location: "—",
    doctor: "—",
    department: "—",
    age: 0,
    bloodType: u.blood_group ?? undefined,
    phone: u.phone ?? undefined,
    email: u.email ?? undefined,
    emergencyContact: u.emergency_contact_name ?? undefined,
    emergencyPhone: u.emergency_contact_phone ?? undefined,
  };
}

/**
 * Get patient current vitals (admin read endpoint).
 * Backend returns {data: [{id, vital_type, value, unit, recorded_at, ...}]}.
 */
export async function getPatientVitals(id: string): Promise<PatientVital[]> {
  const response = await api.get(`/api/v1/admin/patients/${id}/vitals`);
  const rows = response.data?.data ?? [];
  return rows.map(
    (v: {
      id: string;
      vital_type: string;
      value: number;
      unit: string;
      recorded_at: string;
      abnormal_flag?: boolean;
      normalRange?: { min: number; max: number };
    }) => ({
      id: v.id,
      name: v.vital_type,
      value: String(v.value),
      unit: v.unit,
      status: v.abnormal_flag ? "critical" : "normal",
      lastUpdated: v.recorded_at,
    })
  );
}

/**
 * Get patient vitals history (admin read endpoint).
 * Backend returns [{date, value}] directly.
 */
export async function getPatientVitalsHistory(
  id: string,
  vitalType: string
): Promise<PatientVitalHistory[]> {
  const response = await api.get(
    `/api/v1/admin/patients/${id}/vitals/history?type=${vitalType}`
  );
  return response.data;
}

/**
 * Get patient appointments (admin read endpoint).
 * Backend returns PatientAppointment-shaped items directly.
 */
export async function getPatientAppointments(
  id: string
): Promise<PatientAppointment[]> {
  const response = await api.get(`/api/v1/admin/patients/${id}/appointments`);
  return response.data;
}

/**
 * Create new patient
 */
export async function createPatient(data: {
  full_name: string;
  phone?: string;
  email?: string;
}): Promise<{ id: string; [key: string]: unknown }> {
  const response = await api.post("/api/v1/admin/users", data);
  return response.data;
}

/**
 * Update patient
 */
export async function updatePatient(
  id: string,
  data: Partial<Patient>
): Promise<Patient> {
  const response = await api.put(`/api/v1/admin/users/${id}`, data);
  return response.data;
}

/**
 * Delete patient (soft delete)
 */
export async function deletePatient(id: string): Promise<void> {
  await api.delete(`/api/v1/admin/users/${id}`);
}

/**
 * Current patient's medical history profile fields.
 * Used by the patient medical-history form and the onboarding checklist.
 */
export interface MedicalHistory {
  blood_group: string | null;
  allergies: string[];
  chronic_conditions: string[];
  height_cm: number | null;
  weight_kg: number | null;
}

export async function getMedicalHistory(): Promise<MedicalHistory> {
  const response = await api.get("/api/v1/patients/medical-history");
  return response.data;
}

/**
 * A patient ↔ clinic link row (GET /api/v1/patients/clinic-links).
 */
export interface ClinicLink {
  id: string;
  clinic_id: string;
  clinic_name: string;
  clinic_city: string | null;
  consent_status: "pending" | "approved" | "revoked";
  consented_at: string | null;
  created_at: string;
}

export async function getMyClinicLinks(): Promise<{ data: ClinicLink[] }> {
  const response = await api.get("/api/v1/patients/clinic-links");
  return response.data;
}

/**
 * DPDP privacy status for the current patient (consent + erasure state).
 */
export interface PrivacyStatus {
  consent_at: string | null;
  consent_version: string | null;
  erasure_requested_at: string | null;
  erased_at: string | null;
}

export async function getPrivacyStatus(): Promise<PrivacyStatus> {
  const response = await api.get("/api/v1/patients/privacy");
  return response.data;
}

/**
 * Request DPDP data erasure for the current patient.
 * Idempotent — the backend returns "already_processed" on repeat calls.
 */
export async function requestErasure(): Promise<{
  status: "erased" | "already_processed";
  erasure_requested_at: string | null;
  erased_at: string | null;
}> {
  const response = await api.post("/api/v1/patients/erasure");
  return response.data;
}
