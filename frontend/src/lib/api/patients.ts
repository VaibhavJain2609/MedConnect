/**
 * Patient API Functions
 * Handles patient data operations
 */

import api from "../api";

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

/**
 * Get patient details by ID
 */
export async function getPatient(id: string): Promise<Patient> {
  const response = await api.get(`/api/v1/patients/${id}`);
  return response.data;
}

/**
 * Get patient current vitals
 */
export async function getPatientVitals(id: string): Promise<PatientVital[]> {
  const response = await api.get(`/api/v1/patients/${id}/vitals`);
  return response.data;
}

/**
 * Get patient vitals history
 */
export async function getPatientVitalsHistory(
  id: string,
  vitalType: string
): Promise<PatientVitalHistory[]> {
  const response = await api.get(
    `/api/v1/patients/${id}/vitals/history?type=${vitalType}`
  );
  return response.data;
}

/**
 * Get patient appointments
 */
export async function getPatientAppointments(
  id: string
): Promise<PatientAppointment[]> {
  const response = await api.get(`/api/v1/patients/${id}/appointments`);
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
  const response = await api.put(`/api/v1/admin/patients/${id}`, data);
  return response.data;
}

/**
 * Delete patient (soft delete)
 */
export async function deletePatient(id: string): Promise<void> {
  await api.delete(`/api/v1/admin/patients/${id}`);
}
